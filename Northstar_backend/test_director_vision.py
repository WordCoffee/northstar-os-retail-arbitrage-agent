"""The director's eyes: one probe, one state file, one consumer — and a refusal that holds.

Ty's Vision has no queue and no merge right. What it has is route truth, and the canonical loop is
the only consumer. These tests pin the three things that make that safe:

* a paused or locked desktop is a **named refusal**, never a silent skip and never an action;
* the probe's output is parsed into `rendered / total / shell_routes`, not trusted as prose;
* the consumer (`replan`) only sees a bundle when the measurement is fresh and real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools"), str(ROOT / "scripts")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import director_vision  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Every test gets its own PAUSE and state file; the real ones are never touched."""
    monkeypatch.setattr(director_vision, "PAUSE", tmp_path / "PAUSE", raising=False)
    monkeypatch.setattr(director_vision, "STATE", tmp_path / "vision.json", raising=False)
    monkeypatch.setattr(director_vision, "AUDIT", tmp_path / "ux_audit.json", raising=False)
    # A deterministic foreground: unlocked, and not the lock screen.
    monkeypatch.setattr(director_vision, "foreground",
                        lambda: {"title": "NorthstarOS — Retail Arbitrage Suite", "process": "chrome.exe"})
    return tmp_path


def test_a_pause_file_is_a_named_refusal_and_writes_no_result(_isolate):
    director_vision.PAUSE.write_text("owner paused browser work", encoding="utf-8")
    payload = director_vision.probe()
    assert payload["state"] == "refused"
    assert "PAUSE" in payload["reason"]
    # the refusal is recorded, and it contains no measurement it did not take
    saved = json.loads(director_vision.STATE.read_text(encoding="utf-8"))
    assert saved["state"] == "refused"
    assert "rendered" not in saved


def test_a_locked_desktop_is_a_refusal_too(monkeypatch):
    monkeypatch.setattr(director_vision, "foreground",
                        lambda: {"title": "Windows Default Lock Screen", "process": "LockApp.exe"})
    assert "locked" in (director_vision.blocked_reason() or "")
    assert director_vision.probe()["state"] == "refused"


def test_status_reports_the_eyes_without_acting(_isolate):
    status = director_vision.status()
    assert status["pause"] is False
    assert status["allowed"] is True
    assert status["fresh"] is False
    assert status["rendered"] is None


def test_the_probe_parses_route_truth(_isolate, monkeypatch):
    def fake_run(args, **kwargs):
        class Done:
            returncode = 0
            stdout = "audit complete"
            stderr = ""

        director_vision.AUDIT.write_text(json.dumps({
            "total": 29, "rendered": 12,
            "shell_routes": ["listings", "socialpulse", "competitor-monitor"],
        }), encoding="utf-8")
        return Done()

    monkeypatch.setattr(director_vision.subprocess, "run", fake_run)
    payload = director_vision.probe()
    assert payload["state"] == "ok"
    assert payload["rendered"] == 12 and payload["total"] == 29
    assert payload["shell_routes"] == ["competitor-monitor", "listings", "socialpulse"]
    assert json.loads(director_vision.STATE.read_text(encoding="utf-8"))["rendered"] == 12


def test_the_consumer_builds_a_bundle_only_from_a_real_measurement(_isolate):
    assert director_vision.queue_hint() is None  # nothing measured yet
    director_vision.STATE.write_text(json.dumps({"state": "refused", "reason": "paused"}),
                                      encoding="utf-8")
    assert director_vision.queue_hint() is None  # a refusal is not a measurement
    director_vision.STATE.write_text(json.dumps({
        "state": "ok", "rendered": 12, "total": 29,
        "shell_routes": ["listings", "socialpulse"],
    }), encoding="utf-8")
    hint = director_vision.queue_hint()
    assert hint["services"] == ["listings", "socialpulse"]
    assert hint["points"] == 20.0
    assert "shell" in hint["title"].lower()


def test_the_consumer_builds_no_bundle_when_every_route_renders(_isolate):
    director_vision.STATE.write_text(json.dumps({
        "state": "ok", "rendered": 29, "total": 29, "shell_routes": []}), encoding="utf-8")
    assert director_vision.queue_hint() is None


def test_the_launcher_reports_the_eyes_in_the_heartbeat():
    import ty_director

    status = ty_director.vision_status()
    assert "allowed" in status
    # and a vision fault is contained: the launcher keeps its own shape
    assert set(status) & {"pause", "error"}
