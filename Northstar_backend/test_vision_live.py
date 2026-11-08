"""D13 live mode: narrate the screen, answer about it, and never leak a refused window."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import live  # noqa: E402


def fake_windows():
    return [
        {"title": "OC | Ty director finish order", "process": "WindowsTerminal.exe"},
        {"title": "Amazon.com - Cart", "process": "chrome.exe"},
        {"title": "Settings", "process": "SystemSettings.exe"},
    ]


def fake_tree(title_hint=""):
    return {"ok": True, "elements": [
        {"role": "ButtonControl", "name": "Run"},
        {"role": "TextControl", "name": "Output"},
    ]}


def make_session(**overrides):
    defaults = dict(
        capture_frame=lambda: {"ok": True, "png": b"png", "size": [1280, 800]},
        speak=lambda **kwargs: {"ok": True, "apps": [{"name": "Windows Terminal",
                                                      "purpose": "terminal"}],
                                "foreground": "Windows Terminal", "seconds": 0.1,
                                "model": "test"},
        windows=fake_windows,
        describe_tree=fake_tree,
    )
    defaults.update(overrides)
    return live.LiveSession(**defaults)


def test_a_blocked_window_is_dropped_before_it_is_described():
    seen = {}

    def speak(**kwargs):
        seen["called"] = True
        return {"ok": True, "apps": [], "foreground": ""}

    session = make_session(speak=speak)
    session.start()
    observation = session.observe()
    assert observation["ok"] is True
    titles = [row["title"] for row in observation["windows"]]
    # the Amazon window is present as a refusal with no title and no content
    assert "Amazon.com - Cart" not in titles
    blocked = [row for row in observation["windows"] if not row["allowed"]]
    assert blocked and blocked[0]["title"] == ""
    assert "reason" in blocked[0]


def test_narration_names_the_windows_and_counts_elements():
    session = make_session()
    session.start()
    observation = session.observe()
    assert "WindowsTerminal.exe" in observation["narration"]
    assert "2 actionable elements" in observation["narration"]
    assert observation["narrated"] is True


def test_questions_are_answered_from_the_observation():
    session = make_session()
    session.start()
    screen = session.ask("What is on screen?")
    focus = session.ask("Which app has focus?")
    count = session.ask("How many elements?")
    assert "WindowsTerminal" in screen["answer"]
    assert focus["answer"] == "Windows Terminal"
    assert "2" in count["answer"]
    # every ask() takes its own observation, so the transcript records both kinds of turn
    assert len(session.transcript) == 6


def test_a_session_that_was_not_started_answers_nothing():
    session = make_session()
    assert session.observe()["ok"] is False
    assert session.ask("what is on screen?")["ok"] is False


def test_a_blocked_frame_answers_with_the_privacy_reason():
    session = make_session(capture_frame=lambda: {"ok": False, "blocked": True,
                                                  "reason": "title matches 'amazon'"})
    session.start()
    answer = session.ask("what is on screen?")
    assert "cannot look" in answer["answer"]
    assert "blocked-window" in answer["answer"]


def test_live_demo_passes_against_injected_inputs(monkeypatch, tmp_path):
    built = make_session()
    monkeypatch.setattr(live, "LiveSession", lambda: built)
    monkeypatch.setattr(live, "TRANSCRIPTS", tmp_path)
    result = live.demo()
    assert result["d13"]["pass"] is True
    assert Path(result["d13"]["transcript"]).exists()
    saved = json.loads(Path(result["d13"]["transcript"]).read_text(encoding="utf-8"))
    assert saved["turns"]
