"""The launcher obeys the director lease: one writer per tree.

Measured 2026-11-11: a stale lease (a pid that had died) let the scheduled
`NorthstarTysWatchdog` start a `tys` agent on the director's worktree at 05:32 while three
builder lanes were writing in it; files from one lane and a verifier report were gone by the
next check. A live lease must refuse the start, and a stale one must not.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tys_launcher as L  # noqa: E402


def _write_lease(root: Path, pid: int) -> Path:
    path = root / "state" / "director" / "director.pid"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": pid, "cmd": ["test"]}), encoding="utf-8")
    return path


def test_no_lease_file_means_no_holder(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "ROOT", tmp_path)
    assert L._director_lease_holder() is None


def test_a_live_lease_names_its_holder(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "ROOT", tmp_path)
    # this very process is alive and is not the launcher's own pid for the purpose of
    # the check only if it differs; use the parent pid to be sure it is a real process
    other = os.getppid()
    _write_lease(tmp_path, other)
    assert L._director_lease_holder() == other


def test_a_dead_pid_is_not_a_holder(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "ROOT", tmp_path)
    _write_lease(tmp_path, 999_999)
    assert L._director_lease_holder() is None


def test_a_corrupt_lease_does_not_block_the_lane(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "ROOT", tmp_path)
    path = tmp_path / "state" / "director" / "director.pid"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert L._director_lease_holder() is None


def test_a_live_lease_stops_main_before_any_work(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "ROOT", tmp_path)
    _write_lease(tmp_path, os.getppid())
    ran = {"heartbeat": 0}

    def fake_heartbeat(**kwargs):
        ran["heartbeat"] += 1
        return {}

    monkeypatch.setattr(L, "heartbeat", fake_heartbeat)
    monkeypatch.setattr(L, "_append", lambda *a, **k: None)
    code = L.main(["--max-cycles", "1"])
    assert code == 0
    # two beats and no more: the "starting" one, then the "refused" one. A worker cycle
    # would add another beat per cycle, which is what must not happen on a live lease.
    assert ran["heartbeat"] == 2, ran
