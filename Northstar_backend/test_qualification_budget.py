"""Bounded requalification contract: 20 steps for exactly two tasks, nothing else.

The step budget is a task-contract setting. This module records the superseding
records explicitly (the previous contract and its two failed dispatches stay in the
evidence) and proves the budget cannot bypass the campaign's real limits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import continuous_loop as cl
from agent_kernel.coding_agent import CodingAgent
from agent_kernel.coding_tools import Workspace

REG = ROOT / "config" / "continuous_loop_tasks.json"
BUDGETED = {"ty-artifact-jpeg", "ty-diff-select-headers"}


def _tasks():
    return json.loads(REG.read_text(encoding="utf-8-sig"))["tasks"]


def test_only_the_two_remaining_tasks_get_twenty_steps():
    for task in _tasks():
        if task.get("execution") != "ty":
            continue
        if task.get("id") in BUDGETED:
            assert task["max_steps"] == 20, task["id"]
        else:
            assert task["max_steps"] < 20, f"{task['id']} must keep its own limit"


def test_the_superseding_records_are_explicit_and_link_to_history():
    for task in _tasks():
        if task.get("id") in BUDGETED:
            assert task.get("contract_version") == 2
            assert "max_steps=8" in str(task.get("supersedes") or "")
            assert task.get("authorization_note")


def test_the_completed_fix_is_untouched():
    state = json.loads((ROOT / "state" / "continuous_loop_state.json")
                       .read_text(encoding="utf-8-sig"))
    done = state["tasks"]["ty-hitl-skip-report"]
    assert done["status"] == "completed"
    assert str(done["commit"]).startswith("883a7fed")


def test_the_budgeted_tasks_still_validate():
    for task in _tasks():
        if task.get("id") in BUDGETED:
            assert cl.validate_task(task) == []


def test_a_twenty_step_task_still_stops_on_the_campaign_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "LOCK_PATH", tmp_path / "loop.lock")
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    monkeypatch.setattr(cl, "CAMPAIGN_HEARTBEAT_PATH", tmp_path / "campaign.json")
    monkeypatch.setattr(cl, "AUTONOMY_LOG_DIR", tmp_path / "reports")
    monkeypatch.setattr(cl, "CAMPAIGN_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(cl, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(cl, "RUN_DIR", tmp_path / "runs")
    task = {"id": "t1", "name": "t1", "schema_version": 2, "authorized": True,
            "authorization_note": "x", "risk": "low", "execution": "prebuilt",
            "objective": "x", "write_paths": [], "prechecks": [],
            "apply_commands": [], "checks": [], "commit_paths": [],
            "max_steps": 20}
    result = cl.run_campaign({"tasks": [task]}, {"tasks": {}, "completed": {}},
                             max_tasks=5, deadline_minutes=0.0, readiness={"ok": True},
                             execute=lambda *a, **k: pytest.fail("deadline must stop first"))
    assert result["stop_reason"] == "deadline_minutes"


def test_a_twenty_step_task_still_stops_on_the_failure_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "LOCK_PATH", tmp_path / "loop.lock")
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    monkeypatch.setattr(cl, "CAMPAIGN_HEARTBEAT_PATH", tmp_path / "campaign.json")
    monkeypatch.setattr(cl, "AUTONOMY_LOG_DIR", tmp_path / "reports")
    monkeypatch.setattr(cl, "CAMPAIGN_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(cl, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(cl, "RUN_DIR", tmp_path / "runs")
    tasks = [{"id": f"t{i}", "name": f"t{i}", "schema_version": 2, "authorized": True,
              "authorization_note": "x", "risk": "low", "execution": "prebuilt",
              "objective": "x", "write_paths": [], "precheck_commands": [],
              "apply_commands": [], "commit_paths": ["docs/budget-test.md"],
              "checks": [{"name": "ok", "cmd": ["python", "-c", "print('ok')"]}],
              "max_steps": 20} for i in range(4)]
    result = cl.run_campaign({"tasks": tasks}, {"tasks": {}, "completed": {}},
                             max_tasks=4, deadline_minutes=5,
                             max_consecutive_failures=2, readiness={"ok": True},
                             execute=lambda *a, **k: {"status": "failed", "error": "x",
                                                      "commit": None, "checks": [],
                                                      "changed": []})
    assert result["stop_reason"] == "max_consecutive_failures"


def test_the_read_budget_is_unchanged_by_a_larger_step_budget(tmp_path):
    ws = Workspace(tmp_path / "ws", allow_paths=["src.py"], read_paths=["src.py"])
    (tmp_path / "ws" / "src.py").write_text("x = 1\n", encoding="utf-8")
    agent = CodingAgent(ws, lambda p: '{"tool":"finish","args":{}}', max_steps=20)
    assert agent.read_budget_per_path == 4
