"""D6 - privacy and control: V5 and V7.

V5: a window matching the blocklist produces no frame, no OCR text and no interaction,
and a password field is masked.
V7: the pause file and the kill switch both stop input immediately.

These are the two acceptance tests D6 exists for, so they are tested against the real
capture path (mss/PIL) and, where the machine allows it, against a real window.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from vision import capture, control, privacy  # noqa: E402


@pytest.fixture()
def vision_state(tmp_path, monkeypatch):
    for module, names in (
        (capture, {"STATE": tmp_path / "state" / "vision",
                   "FRAMES": tmp_path / "state" / "vision" / "frames",
                   "EVENTS": tmp_path / "state" / "vision" / "events.jsonl"}),
        (control, {"STATE": tmp_path / "state" / "vision",
                   "PAUSE": tmp_path / "state" / "vision" / "PAUSE",
                   "INDICATOR": tmp_path / "state" / "vision" / "indicator.json"}),
    ):
        for name, value in names.items():
            monkeypatch.setattr(module, name, value)
    return tmp_path / "state" / "vision"


# ----------------------------------------------------------------------- V5
def test_amazon_is_blocked_by_title_process_and_url():
    for kwargs in ({"title": "Amazon Seller Central"},
                   {"title": "Chrome", "process": "amazon.exe"},
                   {"title": "Chrome", "url": "https://www.amazon.com/dp/X"}):
        verdict = privacy.classify(**kwargs)
        assert verdict["allow"] is False, kwargs
        assert verdict["matched"]


def test_an_ordinary_editor_is_allowed():
    verdict = privacy.classify(title="main.py - Visual Studio Code",
                               process="Code.exe", url="file:///repo/main.py")
    assert verdict["allow"] is True
    assert verdict["reason"] == "no blocked pattern"


def test_a_blocked_window_produces_no_pixels_and_no_write(vision_state, monkeypatch):
    called = {"n": 0}

    def grab(*_a, **_k):
        called["n"] += 1
        return {"ok": True, "png": b"pixels", "backend": "mss", "size": [1, 1]}

    monkeypatch.setattr(capture, "_grab", grab)
    out = capture.frame({"hwnd": 1, "title": "1Password - vault",
                         "process": "1Password.exe", "rect": [0, 0, 10, 10]})

    assert out["ok"] is False and out["blocked"] is True
    assert out["png"] is None
    assert called["n"] == 0, "a refused window must never be grabbed"
    events = (vision_state / "events.jsonl").read_text(encoding="utf-8")
    assert "blocked-window" in events
    assert "pixels" not in events            # no frame content in the record
    assert "1Password" in events             # the title is recorded, the pixels are not


def test_an_allowed_window_gives_pixels_but_writes_nothing(vision_state, monkeypatch):
    monkeypatch.setattr(capture, "_grab", lambda rect=None: {
        "ok": True, "png": b"pixels", "backend": "mss", "size": [10, 10]})
    out = capture.frame({"hwnd": 2, "title": "main.py - Visual Studio Code",
                         "process": "Code.exe", "rect": [0, 0, 10, 10]})

    assert out["ok"] is True and out["png"] == b"pixels"
    assert out["written"] is None
    assert not (vision_state / "frames").exists()


def test_credentials_are_redacted_before_text_leaves_the_machine():
    text = ("Authorization: Bearer abcdef1234567890\n"
            "key sk-live-abcdefgh1234\n"
            "password=hunter2\n"
            "AKIAIOSFODNN7EXAMPLE\n"
            "ghp_abcdefghijklmnopqrstuvwx\n")
    cleaned = privacy.redact(text)

    for secret in ("abcdef1234567890", "sk-live-abcdefgh1234", "hunter2",
                   "AKIAIOSFODNN7EXAMPLE", "ghp_abcdefghijklmnopqrstuvwx"):
        assert secret not in cleaned
    assert cleaned.count("[redacted]") >= 5


def test_password_and_payment_fields_are_masked_not_read():
    masked = privacy.mask_regions([
        {"role": "Edit", "name": "Password", "value": "hunter2"},
        {"role": "Edit", "name": "Card number", "value": "4111111111111111"},
        {"role": "Edit", "name": "Search", "value": "widgets"},
    ])

    assert masked[0]["mask"] is True and masked[0]["value"] == ""
    assert masked[1]["mask"] is True and masked[1]["value"] == ""
    assert masked[2].get("mask") is not True
    assert masked[2]["value"] == "widgets"


def test_a_real_blocked_window_is_refused(vision_state):
    """The end-to-end version: a real top-level window whose title matches."""
    tkinter = pytest.importorskip("tkinter")
    try:
        root = tkinter.Tk()
    except Exception as exc:  # noqa: BLE001 - a headless session is a skip, not a pass
        pytest.skip(f"no window station available: {exc}")
    try:
        root.title("1Password - test vault")
        root.geometry("200x100+40+40")
        root.update()
        found = [w for w in capture.windows() if "1Password" in w["title"]]
        assert found, "the test window should be enumerable"
        out = capture.frame(found[0])
        assert out["blocked"] is True and out["png"] is None
    finally:
        root.destroy()


# ----------------------------------------------------------------------- V7
def test_the_pause_file_stops_every_action(vision_state):
    vision_state.mkdir(parents=True, exist_ok=True)
    (vision_state / "PAUSE").write_text("paused\n", encoding="utf-8")
    guard = control.Control()

    assert guard.can_act() == {"allow": False, "reason": "pause_file"}
    ran = {"n": 0}
    out = guard.act(lambda: ran.__setitem__("n", ran["n"] + 1))
    assert out["blocked"] is True and ran["n"] == 0


def test_the_kill_switch_stops_input_within_a_second(vision_state):
    guard = control.Control()
    assert guard.can_act()["allow"] is True

    started = time.time()
    guard.trigger_kill()
    verdict = guard.can_act()
    elapsed = time.time() - started

    assert verdict == {"allow": False, "reason": "kill_switch"}
    assert elapsed < 1.0
    ran = {"n": 0}
    assert guard.act(lambda: ran.__setitem__("n", 1))["blocked"] is True
    assert ran["n"] == 0


def test_the_indicator_turns_on_only_while_input_is_held(vision_state):
    guard = control.Control()
    guard.indicator(True)
    assert '"on": true' in (vision_state / "indicator.json").read_text(encoding="utf-8")
    guard.trigger_kill()
    assert '"on": false' in (vision_state / "indicator.json").read_text(encoding="utf-8")


def test_audit_frames_are_pruned_after_the_retention_window(vision_state):
    frames = vision_state / "frames"
    frames.mkdir(parents=True)
    old = frames / "old.png"
    old.write_bytes(b"x")
    fresh = frames / "fresh.png"
    fresh.write_bytes(b"x")
    import os

    os.utime(old, (time.time() - 8 * 86400, time.time() - 8 * 86400))

    removed = capture.prune(days=7, frames=frames)

    assert removed == ["old.png"]
    assert fresh.exists()
