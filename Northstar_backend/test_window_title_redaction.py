"""A window title must never reach a file the loop keeps.

The heartbeat, `vision.json`, the run logs, the handoff and the digests outlive the moment they
describe. A title is a tab name, a mailbox, a customer's document — so the writer records the
process name and the blocked/unblocked verdict, and this module pins both halves: the code that
writes, and the artifacts already on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import director_vision  # noqa: E402
import redact_window_titles  # noqa: E402

CANARY = "PRIVATE-TAB-7f3a - Google Chrome"


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(director_vision, "PAUSE", tmp_path / "PAUSE", raising=False)
    monkeypatch.setattr(director_vision, "STATE", tmp_path / "vision.json", raising=False)
    monkeypatch.setattr(director_vision, "AUDIT", tmp_path / "ux_audit.json", raising=False)
    monkeypatch.setattr(director_vision, "foreground",
                        lambda: {"title": CANARY, "process": "chrome.exe"})
    return tmp_path


def test_status_records_the_process_and_the_verdict_never_the_title(isolated):
    payload = director_vision.status()
    blob = json.dumps(payload)
    assert CANARY not in blob
    assert "PRIVATE-TAB" not in blob
    assert payload["foreground_process"] == "chrome.exe"
    assert payload["blocked"] is False
    assert payload["allowed"] is True
    assert "foreground" not in payload  # the title-bearing key is gone, not just emptied


def test_a_locked_desktop_reason_names_the_process_not_the_window(isolated, monkeypatch):
    monkeypatch.setattr(director_vision, "foreground",
                        lambda: {"title": CANARY, "process": "LockApp.exe"})
    reason = director_vision.blocked_reason()
    assert reason and "locked" in reason
    assert "LockApp.exe" in reason
    assert CANARY not in reason
    assert "PRIVATE-TAB" not in reason


def test_a_probe_refusal_carries_no_title(isolated):
    director_vision.PAUSE.write_text("paused", encoding="utf-8")
    payload = director_vision.probe()
    blob = json.dumps(payload)
    assert payload["state"] == "refused"
    assert CANARY not in blob and "PRIVATE-TAB" not in blob


def test_the_scrubber_is_idempotent(tmp_path):
    path = tmp_path / "log.txt"
    path.write_text("desktop unlocked (foreground 'Some Private Tab - Google Chrome'); running\n"
                    '{"foreground": "Mail - someone@example.com - Google Chrome"}\n',
                    encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    cleaned, first = redact_window_titles.scrub(text)
    assert first == 2
    assert "Some Private Tab" not in cleaned
    assert "someone@example.com" not in cleaned
    again, second = redact_window_titles.scrub(cleaned)
    assert second == 0, "a scrubber that rewrites its own marker never reaches zero"
    assert again == cleaned


def test_the_loop_artifacts_carry_no_window_title_today():
    """The guard on what is already written. It fails the day a writer starts leaking again."""
    offenders = []
    for path in redact_window_titles.targets():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = redact_window_titles.count(text)
        if hits:
            offenders.append(f"{path.relative_to(ROOT)}: {hits}")
    assert offenders == [], offenders
