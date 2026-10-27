"""Render session manager tests (offline, no real process killing).

Covers the lifecycle contract:
- normal acquire -> render -> restore -> release
- duplicate submission is rejected while a render is active
- a timed-out render keeps the lock (never restores/replays an ambiguous job)
- a crashed supervisor leaves a state file that the next start recovers
- the lock is honoured across processes and stale owners are reclaimed
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import studio_generation as sg  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch, tmp_path):
    """Point the state file and lock file at a temp dir for every test."""
    state = str(tmp_path / "state.json")
    lock = str(tmp_path / "render.lock")
    monkeypatch.setattr(sg, "_RENDER_STATE_PATH", state)
    monkeypatch.setattr(sg._RENDER_LOCK, "path", lock)
    monkeypatch.setattr(sg._RENDER_LOCK, "_owned", False, raising=False)
    # Ensure a fresh thread lock (a failed earlier test could leave it held).
    import threading
    monkeypatch.setattr(sg._RENDER_LOCK, "_thread_lock", threading.Lock())
    return {"state": state, "lock": lock}


def _patch_engine(monkeypatch, stopped=None):
    monkeypatch.setattr(sg, "unload_brain", lambda wait_s=45.0: True)
    monkeypatch.setattr(sg, "ensure_system_ram", lambda **kw: {
        "ok": True, "stopped": list(stopped or []), "free_mb_before": 8192.0,
        "free_mb_after": 8192.0, "needed_mb": 4096, "refusal": None})
    monkeypatch.setattr(sg, "restore_after_render", lambda stopped: stopped)
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)


def _short_lock_timeout(monkeypatch):
    orig = sg._RENDER_LOCK.acquire

    def _acquire(timeout=10.0):
        return orig(timeout=min(float(timeout), 0.5))

    monkeypatch.setattr(sg._RENDER_LOCK, "acquire", _acquire)


def test_render_session_normal_cycle(monkeypatch, tmp_path, _isolate_paths):
    _patch_engine(monkeypatch)
    with sg.RenderSession(lane="image") as rs:
        assert rs.stopped == []
        rs.mark_render_started()
        rs.mark_render_finished()
        rs.result = {"ok": True}
    assert not os.path.exists(_isolate_paths["state"])
    assert not os.path.exists(_isolate_paths["lock"])


def test_duplicate_submission_rejected_while_active(monkeypatch, _isolate_paths):
    _patch_engine(monkeypatch)
    _short_lock_timeout(monkeypatch)
    rs1 = sg.RenderSession(lane="image")
    with rs1:
        rs1.mark_render_started()
        rs2 = sg.RenderSession(lane="image")
        with pytest.raises(RuntimeError) as exc:
            rs2.__enter__()
        assert "render_session_busy" in str(exc.value)
        rs1.mark_render_finished()
    # After the first finishes, a new session can acquire.
    with sg.RenderSession(lane="image") as rs3:
        assert rs3.lane == "image"


def test_timeout_keeps_lock_and_state(monkeypatch, _isolate_paths):
    _patch_engine(monkeypatch)
    rs = sg.RenderSession(lane="image", max_seconds=0)
    try:
        with rs:
            rs.mark_render_started()
            rs._start = time.time() - 10
            rs.check_timeout()
    except RuntimeError as exc:
        assert "render_timeout" in str(exc)
    # Lock and state survive: an ambiguous job must not be replayed.
    assert os.path.exists(_isolate_paths["state"])
    with open(_isolate_paths["state"], encoding="utf-8") as fh:
        assert json.load(fh)["status"] == "orphaned"
    assert sg._RENDER_LOCK._owned is True
    # Clean up the held lock so later tests in the same process are not blocked.
    sg._RENDER_LOCK.release()


def test_crash_mid_render_restores(monkeypatch, _isolate_paths):
    _patch_engine(monkeypatch, stopped=[{"pid": 1, "name": "ollama", "ram_mb": 100.0}])
    restored = {"called": False}

    def fake_restore(stopped):
        restored["called"] = True
        return stopped

    monkeypatch.setattr(sg, "restore_after_render", fake_restore)
    try:
        with sg.RenderSession(lane="image") as rs:
            rs.mark_render_started()
            raise RuntimeError("simulated crash")
    except RuntimeError:
        pass
    assert restored["called"] is True
    assert not os.path.exists(_isolate_paths["state"])


def test_refusal_aborts_and_restores(monkeypatch, _isolate_paths):
    monkeypatch.setattr(sg, "unload_brain", lambda wait_s=45.0: True)
    monkeypatch.setattr(sg, "ensure_system_ram", lambda **kw: (_ for _ in ()).throw(
        RuntimeError("system_ram_insufficient: free 1024 MB, need 4096 MB")))
    restored = {"called": False}
    monkeypatch.setattr(sg, "restore_after_render",
                        lambda stopped: restored.__setitem__("called", True) or stopped)
    monkeypatch.setattr(sg.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError) as exc:
        with sg.RenderSession(lane="image"):
            pass
    assert "system_ram_insufficient" in str(exc.value)
    assert restored["called"] is True


def test_restore_pending_session_on_crash(monkeypatch, _isolate_paths):
    with open(_isolate_paths["state"], "w", encoding="utf-8") as fh:
        json.dump({"lane": "image", "started_at": 1000,
                   "stopped": [{"pid": 2, "name": "ollama", "ram_mb": 500.0}],
                   "status": "running"}, fh)
    restored = {"stopped": None}
    monkeypatch.setattr(sg, "restore_after_render",
                        lambda stopped: restored.__setitem__("stopped", stopped) or stopped)
    out = sg.restore_pending_session()
    assert out.get("restored") is True
    assert restored["stopped"] == [{"pid": 2, "name": "ollama", "ram_mb": 500.0}]
    assert not os.path.exists(_isolate_paths["state"])


def test_restore_pending_session_noop_when_no_state(monkeypatch, _isolate_paths):
    out = sg.restore_pending_session()
    assert out == {} or out.get("restored") is not True


def test_orphaned_state_is_recovered_on_next_start(monkeypatch, _isolate_paths):
    """A timed-out session leaves an orphaned state file; next start restores."""
    _patch_engine(monkeypatch)
    rs = sg.RenderSession(lane="image", max_seconds=0)
    try:
        with rs:
            rs.mark_render_started()
            rs._start = time.time() - 10
            rs.check_timeout()
    except RuntimeError:
        pass
    sg._RENDER_LOCK.release()
    restored = {"stopped": None}
    monkeypatch.setattr(sg, "restore_after_render",
                        lambda stopped: restored.__setitem__("stopped", stopped) or stopped)
    out = sg.restore_pending_session()
    assert out.get("restored") is True
    assert out.get("status") == "orphaned"
    assert not os.path.exists(_isolate_paths["state"])


def test_stale_lock_from_dead_pid_is_reclaimed(_isolate_paths):
    with open(_isolate_paths["lock"], "w", encoding="ascii") as fh:
        fh.write("999999:1000.0")  # PID that is almost certainly not alive
    lock = sg._CrossProcessRenderLock(_isolate_paths["lock"], max_seconds=60)
    assert lock.acquire(timeout=2.0) is True
    lock.release()
    assert not os.path.exists(_isolate_paths["lock"])


def test_lock_is_honoured_across_processes(_isolate_paths):
    """A live process holding the lock file blocks this process."""
    lock_path = _isolate_paths["lock"]
    child = subprocess.Popen([
        sys.executable, "-c",
        "import os,sys,time; p=sys.argv[1]; "
        "fd=os.open(p, os.O_CREAT|os.O_EXCL|os.O_WRONLY); "
        "os.write(fd, ('%d:%.3f'%(os.getpid(), time.time())).encode()); "
        "os.close(fd); time.sleep(30)",
        lock_path,
    ])
    try:
        deadline = time.time() + 5
        while not os.path.exists(lock_path) and time.time() < deadline:
            time.sleep(0.05)
        assert os.path.exists(lock_path), "child did not create the lock file"
        lock = sg._CrossProcessRenderLock(lock_path, max_seconds=60)
        assert lock.acquire(timeout=1.0) is False
    finally:
        child.terminate()
        child.wait(timeout=5)
    # The child is dead but its file remains: stale, so reclaimable.
    lock = sg._CrossProcessRenderLock(lock_path, max_seconds=60)
    assert lock.acquire(timeout=3.0) is True
    lock.release()


def test_stop_list_excludes_docker_and_infra():
    names = [n.lower() for n in sg._STOP_LIST_NAMES]
    for forbidden in ("docker", "dockerd", "com.docker", "postgres", "mysql",
                      "redis", "uvicorn", "northstar", "chrome", "opencode"):
        assert forbidden not in names, forbidden
    for allowed in ("ollama", "llama-server", "llama-cli"):
        assert allowed in names, allowed
