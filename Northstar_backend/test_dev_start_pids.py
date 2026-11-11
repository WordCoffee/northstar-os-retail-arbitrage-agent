"""D-009: the dev-start pid record must describe processes that exist.

Measured 2026-11-11: `dev-start.pids` listed 11664,16960,23512,17252,25384 while three of those
no longer existed, and the live vite process was not in it — the script recorded the wrappers it
spawned, not the children that serve the ports. The record is now resolved from the listening
sockets and the process tree, and anything dead is pruned before it is written.

The test drives the script's `-DryRun` path, which exercises the real recording code and starts
nothing.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dev-start.ps1"


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    target = tmp_path_factory.mktemp("devstart") / "dev-start.pids"
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
         "-DryRun", "-PidFile", str(target)],
        capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr or out.stdout
    return target, out


def test_a_dead_pid_is_pruned_before_the_record_is_written(recorded):
    target, _ = recorded
    assert target.is_file(), "the record was not written"
    ids = [part for part in target.read_text(encoding="utf-8-sig").strip().split(",") if part]
    assert "999999" not in ids, "the probe's dead pid must be pruned, not recorded"


def test_the_live_probe_pid_survives(recorded):
    target, out = recorded
    ids = [part for part in target.read_text(encoding="utf-8-sig").strip().split(",") if part]
    assert ids, "a live process was recorded as nothing"
    sidecar = json.loads((target.parent / (target.name + ".json")).read_text(encoding="utf-8-sig"))
    assert sidecar["probe-alive"] in [int(i) for i in ids]


def test_a_role_map_sits_beside_the_list(recorded):
    target, _ = recorded
    sidecar = json.loads((target.parent / (target.name + ".json")).read_text(encoding="utf-8-sig"))
    assert "probe-alive" in sidecar
    # The listener is the authority, so when a dev stack is up its port owner is named by role.
    for role in ("ui", "backend"):
        if role in sidecar:
            assert isinstance(sidecar[role], int)


def test_the_dry_run_starts_nothing(recorded):
    _, out = recorded
    assert "dry run: nothing was started" in (out.stdout or "")
