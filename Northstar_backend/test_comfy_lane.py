"""The render lane owns ComfyUI and can prove it stopped it (WORK ORDER 3, folded fix 3).

`free_comfy()` is not used anywhere here on purpose: this build acknowledges `/free` and
releases nothing, so the only release that counts is a process that has exited.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import comfy_lane  # noqa: E402


def test_a_lane_starts_works_and_stops_in_order(monkeypatch):
    order = []
    lease = {"pid": 4242}

    monkeypatch.setattr(comfy_lane, "reachable", lambda *a, **k: False)

    def start():
        order.append("start")
        return {"ok": True, "pid": lease["pid"]}

    def ready():
        order.append("ready")
        return {"ok": True}

    def stop(pid):
        order.append(("stop", pid))
        return {"ok": True, "pid": pid, "stopped": True}

    def work():
        order.append("work")
        return {"rendered": 3}

    result = comfy_lane.lane(work, start=start, ready=ready, stop=stop,
                             vram=lambda: 12.0)
    assert result["ok"] is True
    assert order == ["start", "ready", "work", ("stop", 4242)]


def test_a_lane_refuses_to_borrow_a_running_instance(monkeypatch):
    monkeypatch.setattr(comfy_lane, "reachable", lambda *a, **k: True)
    called = {"start": False}

    def start():
        called["start"] = True
        return {"ok": True, "pid": 1}

    result = comfy_lane.lane(lambda: None, start=start, ready=lambda: {"ok": True},
                             stop=lambda pid: {"ok": True})
    assert result["ok"] is False and result["refused"] is True
    assert called["start"] is False


def test_the_lane_stops_even_when_the_work_raises(monkeypatch):
    monkeypatch.setattr(comfy_lane, "reachable", lambda *a, **k: False)
    stopped = {"pid": None}

    def stop(pid):
        stopped["pid"] = pid
        return {"ok": True, "pid": pid}

    with pytest.raises(RuntimeError):
        comfy_lane.lane(lambda: (_ for _ in ()).throw(RuntimeError("render died")),
                        start=lambda: {"ok": True, "pid": 99},
                        ready=lambda: {"ok": True}, stop=stop)
    assert stopped["pid"] == 99


def test_a_lane_that_never_becomes_ready_is_still_stopped(monkeypatch):
    monkeypatch.setattr(comfy_lane, "reachable", lambda *a, **k: False)
    stopped = {"called": False}

    def stop(pid):
        stopped["called"] = True
        return {"ok": True, "pid": pid}

    result = comfy_lane.lane(lambda: None, start=lambda: {"ok": True, "pid": 7},
                             ready=lambda: {"ok": False, "reason": "never answered"},
                             stop=stop)
    assert result["ok"] is False
    assert stopped["called"] is True


def test_a_failed_start_does_not_call_stop(monkeypatch):
    monkeypatch.setattr(comfy_lane, "reachable", lambda *a, **k: False)
    called = {"stop": False}

    def stop(pid):
        called["stop"] = True
        return {"ok": True}

    result = comfy_lane.lane(lambda: None,
                             start=lambda: {"ok": False, "reason": "no comfy"},
                             ready=lambda: {"ok": True}, stop=stop)
    assert result["ok"] is False
    assert called["stop"] is False


def test_stop_is_verified_by_the_port_closing(monkeypatch):
    monkeypatch.setattr(comfy_lane.subprocess, "run",
                        lambda *a, **k: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(comfy_lane, "port_open", lambda *a, **k: False)
    result = comfy_lane._stop(123)
    assert result["ok"] is True and result["stopped"] is True


def test_a_stop_that_leaves_the_port_open_is_a_failure(monkeypatch):
    monkeypatch.setattr(comfy_lane.subprocess, "run",
                        lambda *a, **k: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(comfy_lane, "port_open", lambda *a, **k: True)
    monkeypatch.setattr(comfy_lane.time, "sleep", lambda *_: None)
    monkeypatch.setattr(comfy_lane.time, "time",
                        iter([0, 1, 2, 40, 41, 42]).__next__)
    result = comfy_lane._stop(123, timeout=1.0)
    assert result["ok"] is False
    assert "still open" in result["reason"]
