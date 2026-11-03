"""Outcome memory for the autonomous loop.

The supervisor already refuses to run when it is not safe (readiness), halts on
consecutive failures, restores a failed task's files and journals everything. What
it could not do was REMEMBER: `state/continuous_loop_state.json` is reset as tasks
are retried, so on 2026-11-02 it spent two campaigns re-dispatching
`ty-diff-select-headers` and `ty-artifact-jpeg` - tasks this lane has never once
passed - and halted on the same wall both times (1 completed of 10 attempted).

These tests pin the fix: a durable per-task record keyed by a hash of the task
spec, a door that closes after N attempts with zero passes, a door that REOPENS
when the brief/acceptance/lane changes, and a campaign that walks past a task it
cannot solve instead of dying on it.

Offline: the model lane is stubbed. Nothing here loads a model or touches the GPU.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "continuous_loop_under_test", ROOT / "scripts" / "continuous_loop.py")
cl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cl)


def _task(tid: str, **over) -> dict:
    task = {
        "id": tid,
        "name": tid,
        "schema_version": 2,
        "authorized": True,
        "authorization_note": "offline unit test",
        "risk": "low",
        "risk_class": "low",
        "execution": "prebuilt",
        "objective": f"do {tid}",
        "dependencies": [],
        "write_paths": [f"docs/{tid}.md"],
        "read_paths": [],
        "apply_commands": [],
        "precheck_commands": [],
        "checks": [],
        "acceptance_commands": [["python", "-c", "raise SystemExit(0)"]],
        "commit_paths": [f"docs/{tid}.md"],
        "commit_message": f"docs: {tid}",
        "timeout_seconds": 60,
        "max_repairs": 0,
        "max_steps": 1,
    }
    task.update(over)
    return task


@pytest.fixture()
def loop(tmp_path, monkeypatch):
    """Point every durable path this module owns at a temp dir."""
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "HISTORY_PATH", tmp_path / "task_history.json")
    monkeypatch.setattr(cl, "LOCK_PATH", tmp_path / "lock.json")
    monkeypatch.setattr(cl, "HEARTBEAT_PATH", tmp_path / "heartbeat.json")
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    monkeypatch.setattr(cl, "CAMPAIGN_MANIFEST_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(cl, "AUTONOMY_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cl, "log_event", lambda *a, **k: None)
    monkeypatch.setattr(cl, "resolve_lane", lambda task=None, **k: {"model": None})
    return tmp_path


def test_spec_hash_tracks_the_brief_not_the_run(loop):
    a = _task("t1")
    b = _task("t1")
    assert cl.task_spec_hash(a) == cl.task_spec_hash(b)
    b["objective"] = "something else entirely"
    assert cl.task_spec_hash(a) != cl.task_spec_hash(b)
    # bookkeeping fields do not change the question being asked
    b2 = _task("t1")
    b2["blocked"] = "manual hold"
    assert cl.task_spec_hash(a) == cl.task_spec_hash(b2)


def test_three_attempts_without_a_pass_becomes_needs_author(loop):
    task = _task("hard")
    for i in range(cl.MAX_ATTEMPTS_BEFORE_AUTHOR):
        assert cl.history_block(task) is None
        cl.record_attempt(task, run_id=f"r{i}", status="failed", error="max_steps")
    block = cl.history_block(task)
    assert block is not None
    assert "never_solved" in block and "needs_author" in block
    row = cl.load_history()["tasks"]["hard"]
    assert row["attempts"] == cl.MAX_ATTEMPTS_BEFORE_AUTHOR
    assert row["completed"] == 0
    assert row["last_error"] == "max_steps"


def test_one_pass_clears_the_door(loop):
    task = _task("flaky")
    for i in range(5):
        cl.record_attempt(task, run_id=f"r{i}", status="failed", error="acceptance")
    assert cl.history_block(task) is not None
    cl.record_attempt(task, run_id="r-ok", status="completed")
    assert cl.history_block(task) is None


def test_a_changed_spec_opens_the_door_again(loop):
    task = _task("stuck")
    for i in range(6):
        cl.record_attempt(task, run_id=f"r{i}", status="failed", error="max_steps")
    assert cl.history_block(task) is not None
    # A new brief/acceptance/lane is a new question: the old 0/6 does not answer it.
    changed = _task("stuck", objective="a different approach entirely")
    assert cl.history_block(changed) is None
    cl.record_attempt(changed, run_id="r-new", status="failed", error="max_steps")
    assert cl.load_history()["tasks"]["stuck"]["attempts"] == 1


def test_select_task_skips_a_never_solved_task_and_picks_the_next(loop):
    tasks = {"tasks": [_task("dead"), _task("alive")]}
    state = {"completed": {}, "tasks": {}}
    dead = tasks["tasks"][0]
    for i in range(cl.MAX_ATTEMPTS_BEFORE_AUTHOR):
        cl.record_attempt(dead, run_id=f"r{i}", status="failed", error="max_steps")
    picked = cl.select_task(tasks, state)
    assert picked is not None and picked["id"] == "alive"


def test_a_campaign_does_not_halt_on_a_task_it_has_never_solved(loop):
    tasks = {"tasks": [_task("dead1"), _task("dead2"), _task("good")]}
    for t in tasks["tasks"][:2]:
        for i in range(cl.MAX_ATTEMPTS_BEFORE_AUTHOR):
            cl.record_attempt(t, run_id=f"old{i}", status="failed", error="max_steps")

    seen = []

    def fake_execute(task, state, **kwargs):
        # execute_task's contract: it records the final status in the shared state.
        seen.append(task["id"])
        state.setdefault("tasks", {})[task["id"]] = {"status": "completed"}
        return {"status": "completed", "checks": [], "commit": {"ok": True, "sha": "abc"}}

    state = {"completed": {}, "tasks": {}}
    out = cl.run_campaign(tasks, state, max_tasks=2, dry_run=False,
                          readiness={"ok": True, "verdict": "GO", "checks": []},
                          execute=fake_execute)

    assert seen == ["good"], "a never-solved task must not be dispatched again"
    assert out["stop_reason"] in ("queue_blocked", "queue_exhausted", "max_tasks")
    assert out["results"][0]["status"] == "completed"
