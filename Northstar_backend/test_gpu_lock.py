"""The GPU lock: one heavy job at a time, and a dead holder must not wedge the lane.

On 2026-11-09 a killed composite left `state/gpu/lock.json` naming a pid that no longer existed, and
the next run refused with `gpu_locked` for a process that was gone. Refusing a *live* holder is the
whole point of the lock; refusing a *dead* one is a wedged machine.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import gpu_budget as G  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "STATE", tmp_path)
    monkeypatch.setattr(G, "LOCK", tmp_path / "lock.json")
    return tmp_path / "lock.json"


def _write(lock_path, pid, *, age_s=0.0, role="seller_composite"):
    lock_path.write_text(json.dumps({"role": role, "pid": pid, "ts": time.time() - age_s,
                                     "at": "2026-11-09T19:45:12+00:00"}), encoding="utf-8")


def test_a_live_foreign_holder_is_refused(isolated_lock, monkeypatch):
    _write(isolated_lock, pid=4242)
    monkeypatch.setattr(G, "_pid_alive", lambda pid: True)
    verdict = G.lock("another_role")
    assert verdict["ok"] is False
    assert verdict["reason"] == "gpu_locked"
    assert verdict["held_by"]["pid"] == 4242


def test_a_dead_holder_is_reclaimed_and_the_reclaim_is_recorded(isolated_lock, monkeypatch):
    _write(isolated_lock, pid=11448)
    monkeypatch.setattr(G, "_pid_alive", lambda pid: False)
    verdict = G.lock("seller_composite")
    assert verdict["ok"] is True
    assert verdict["reclaimed"]["pid"] == 11448
    stored = json.loads(isolated_lock.read_text(encoding="utf-8"))
    assert stored["pid"] != 11448
    assert stored["reclaimed"]["why"].startswith("the recorded pid was not running")


def test_an_expired_lock_is_taken_without_a_reclaim_note(isolated_lock, monkeypatch):
    _write(isolated_lock, pid=4242, age_s=7200)
    monkeypatch.setattr(G, "_pid_alive", lambda pid: True)
    verdict = G.lock("seller_composite")
    assert verdict["ok"] is True
    assert "reclaimed" not in verdict


def test_an_unreadable_lock_does_not_block(isolated_lock):
    isolated_lock.write_text("{not json", encoding="utf-8")
    assert G.lock("seller_composite")["ok"] is True


def test_unlock_removes_the_file(isolated_lock):
    _write(isolated_lock, pid=1)
    G.unlock("seller_composite")
    assert not isolated_lock.exists()


def test_a_probe_that_raises_counts_as_alive(monkeypatch):
    # stealing a lock because psutil is missing would be worse than refusing
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(G.os, "kill", lambda pid, sig: (_ for _ in ()).throw(OSError("gone")))
    assert G._pid_alive(123456) is False
    monkeypatch.setattr(G.os, "kill", lambda pid, sig: None)
    assert G._pid_alive(123456) is True
