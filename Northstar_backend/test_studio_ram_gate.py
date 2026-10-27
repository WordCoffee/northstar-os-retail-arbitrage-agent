"""System-RAM pre-render gate tests (offline, no real process killing)."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import studio_generation as sg  # noqa: E402


def test_system_ram_free_mb_returns_float():
    v = sg.system_ram_free_mb()
    assert isinstance(v, float)
    assert v >= 0


def test_ensure_system_ram_ok_when_above_floor(monkeypatch):
    monkeypatch.setattr(sg, "system_ram_free_mb", lambda: 8192.0)
    monkeypatch.setattr(sg, "SYSTEM_RAM_FLOOR_MB", 4096)
    out = sg.ensure_system_ram()
    assert out["ok"] is True
    assert out["free_mb_after"] == 8192.0
    assert out["stopped"] == []
    assert out["refusal"] is None


def test_ensure_system_ram_refusal_when_below_floor_after_stoplist(monkeypatch):
    # Free RAM below floor even after stop-list (stop_for_render returns []).
    monkeypatch.setattr(sg, "system_ram_free_mb", lambda: 1024.0)
    monkeypatch.setattr(sg, "SYSTEM_RAM_FLOOR_MB", 4096)
    monkeypatch.setattr(sg, "stop_for_render", lambda **kw: [])
    try:
        sg.ensure_system_ram()
        assert False, "should have raised"
    except RuntimeError as exc:
        assert "system_ram_insufficient" in str(exc)
        assert "free 1024 MB, need 4096 MB" in str(exc)


def test_ensure_system_ram_stops_when_below_floor(monkeypatch):
    calls = {"stopped": False}
    freed = [{"pid": 1, "name": "docker", "ram_mb": 512.0}]

    def fake_stop(**kw):
        calls["stopped"] = True
        return freed

    # First call below floor, second call (after stop) above floor.
    values = iter([2048.0, 5000.0])
    monkeypatch.setattr(sg, "system_ram_free_mb", lambda: next(values))
    monkeypatch.setattr(sg, "SYSTEM_RAM_FLOOR_MB", 4096)
    monkeypatch.setattr(sg, "stop_for_render", fake_stop)
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)

    out = sg.ensure_system_ram()
    assert calls["stopped"] is True
    assert out["ok"] is True
    assert out["stopped"] == freed
    assert out["free_mb_before"] == 2048.0
    assert out["free_mb_after"] == 5000.0


def test_stop_for_render_skips_self_and_opencode(monkeypatch):
    # Mock psutil.process_iter to return fake processes.
    self_proc = MagicMock()
    self_proc.info = {"pid": os.getpid(), "name": "python.exe", "memory_info": MagicMock(rss=100*1024*1024)}
    opencode_proc = MagicMock()
    opencode_proc.info = {"pid": 9999, "name": "opencode.exe", "memory_info": MagicMock(rss=200*1024*1024)}
    docker_proc = MagicMock()
    docker_proc.info = {"pid": 1234, "name": "dockerd.exe", "memory_info": MagicMock(rss=50*1024*1024)}
    docker_proc.terminate = MagicMock()
    docker_proc.wait = MagicMock()

    monkeypatch.setattr(sg._psutil, "process_iter", lambda attrs=None: [self_proc, opencode_proc, docker_proc])
    monkeypatch.setattr(sg._psutil, "NoSuchProcess", Exception)
    monkeypatch.setattr(sg._psutil, "AccessDenied", Exception)
    monkeypatch.setattr(sg._psutil, "TimeoutExpired", Exception)

    stopped = sg.stop_for_render()
    names = [s["name"] for s in stopped]
    assert "dockerd.exe" in names
    assert "python.exe" not in names
    assert "opencode.exe" not in names


def test_stop_for_render_chrome_excluded_by_default(monkeypatch):
    chrome_proc = MagicMock()
    chrome_proc.info = {"pid": 5555, "name": "chrome.exe", "memory_info": MagicMock(rss=300*1024*1024)}
    chrome_proc.terminate = MagicMock()
    chrome_proc.wait = MagicMock()

    monkeypatch.setattr(sg._psutil, "process_iter", lambda attrs=None: [chrome_proc])
    monkeypatch.setattr(sg._psutil, "NoSuchProcess", Exception)
    monkeypatch.setattr(sg._psutil, "AccessDenied", Exception)
    monkeypatch.setattr(sg._psutil, "TimeoutExpired", Exception)

    stopped = sg.stop_for_render(shutdown_chrome=False)
    assert "chrome.exe" not in [s["name"] for s in stopped]

    stopped2 = sg.stop_for_render(shutdown_chrome=True)
    # chrome_proc.terminate should have been called
    assert chrome_proc.terminate.called


def test_restore_after_render_returns_list():
    stopped = [{"pid": 1, "name": "docker", "ram_mb": 512.0}]
    out = sg.restore_after_render(stopped)
    assert out == stopped


def test_system_ram_floor_constant_documented():
    assert sg.SYSTEM_RAM_FLOOR_MB >= 1024
    assert isinstance(sg.SYSTEM_RAM_FLOOR_MB, int)