"""Autonomy readiness: policy fingerprint, lane choice, campaign controls, logs."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl


def _task(task_id: str, **extra):
    base = {
        "id": task_id,
        "name": task_id,
        "schema_version": 2,
        "authorized": True,
        "authorization_note": "local test task",
        "risk": "low",
        "risk_class": "low",
        "execution": "prebuilt",
        "objective": "test",
        "write_paths": [],
        "precheck_commands": [],
        "apply_commands": [],
        "checks": [{"name": "ok", "cmd": ["python", "-c", "print('ok')"]}],
        "commit_paths": ["docs/autonomy-test.md"],
    }
    base.update(extra)
    return base


def test_policy_fingerprint_compares_committed_content_and_normalizes_crlf(tmp_path, monkeypatch):
    git = shutil.which("git")
    if not git:
        pytest.skip("git required")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([git, "config", "user.email", "loop@northstar.invalid"], cwd=repo, check=True)
    subprocess.run([git, "config", "user.name", "loop test"], cwd=repo, check=True)
    (repo / "policy.txt").write_text("approved\n", encoding="utf-8")
    subprocess.run([git, "add", "policy.txt"], cwd=repo, check=True)
    subprocess.run([git, "commit", "-m", "base"], cwd=repo, check=True)
    monkeypatch.setattr(cl, "ROOT", repo)
    # Working copy with CRLF is still the approved content.
    (repo / "policy.txt").write_bytes(b"approved\r\n")
    assert cl.policy_fingerprint(["policy.txt"])["ok"] is True
    (repo / "policy.txt").write_text("changed\n", encoding="utf-8")
    out = cl.policy_fingerprint(["policy.txt"])
    assert out["ok"] is False
    assert out["files"][0]["match"] is False


def test_lane_resolution_uses_installed_smallest_proven_lane_and_rechecks_ram():
    tags = {"ok": True, "models": [
        {"name": "bojo", "size_gb": 2.7},
        {"name": "qwen2.5vl:7b", "size_gb": 6.0},
    ]}
    out = cl.resolve_lane({"execution": "ty"}, tags=tags, free_ram_gb=4.85)
    assert out["ok"] is True
    assert out["model"] == "bojo"
    no = cl.resolve_lane({"execution": "ty"}, tags=tags, free_ram_gb=0.5)
    assert no["ok"] is False
    prebuilt = cl.resolve_lane({"execution": "prebuilt"}, tags=tags, free_ram_gb=0.5)
    assert prebuilt["ok"] is True and prebuilt["provider"] == "prebuilt"


def _campaign_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "LOCK_PATH", tmp_path / "loop.lock")
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    monkeypatch.setattr(cl, "CAMPAIGN_HEARTBEAT_PATH", tmp_path / "campaign.json")
    monkeypatch.setattr(cl, "AUTONOMY_LOG_DIR", tmp_path / "reports")
    monkeypatch.setattr(cl, "CAMPAIGN_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(cl, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(cl, "RUN_DIR", tmp_path / "runs")


def test_campaign_enforces_max_tasks_and_writes_manifest(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    tasks = {"tasks": [_task(f"t{i}") for i in range(4)]}
    state = {"tasks": {}, "completed": {}}

    def execute(task, state, **kwargs):
        state["tasks"][task["id"]] = {"status": "completed"}
        return {"status": "completed", "commit": {"sha": "abc123"},
                "duration_s": 0.01, "lane": {"provider": "prebuilt", "model": ""},
                "checks": [], "changed": []}

    result = cl.run_campaign(tasks, state, max_tasks=2, deadline_minutes=5,
                             max_consecutive_failures=2, readiness={"ok": True},
                             execute=execute)
    assert result["attempted"] == 2
    assert result["completed"] == 2
    assert result["stop_reason"] == "max_tasks"
    assert not (tmp_path / "loop.lock").exists()
    manifest = json.loads((tmp_path / "manifests" / f"{result['run_id']}.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["completed"] == 2
    assert (tmp_path / "campaign.json").is_file()
    assert list((tmp_path / "reports").glob("autonomy_log_*.log"))


def test_campaign_halts_on_consecutive_failures_not_forever(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    tasks = {"tasks": [_task(f"f{i}") for i in range(5)]}
    state = {"tasks": {}, "completed": {}}
    calls = []

    def execute(task, state, **kwargs):
        calls.append(task["id"])
        state["tasks"][task["id"]] = {"status": "failed", "reason": "test failure"}
        return {"status": "failed", "error": "test failure",
                "duration_s": 0.01, "lane": {"provider": "prebuilt", "model": ""},
                "checks": [], "changed": []}

    result = cl.run_campaign(tasks, state, max_tasks=5, deadline_minutes=5,
                             max_consecutive_failures=2, readiness={"ok": True},
                             execute=execute)
    assert calls == ["f0", "f1"]
    assert result["attempted"] == 2
    assert result["stop_reason"] == "max_consecutive_failures"
    assert not (tmp_path / "loop.lock").exists()
    heartbeat = json.loads((tmp_path / "campaign.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "finished"
    assert heartbeat["stop_reason"] == "max_consecutive_failures"


def test_campaign_refuses_readiness_no_go(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    tasks = {"tasks": [_task("never")]}
    result = cl.run_campaign(tasks, {"tasks": {}, "completed": {}},
                             max_tasks=1, deadline_minutes=1,
                             readiness={"ok": False, "verdict": "NO-GO",
                                        "failures": [{"name": "ram-floor"}]},
                             execute=lambda *a, **k: pytest.fail("must not execute"))
    assert result["ok"] is False
    assert result["stop_reason"] == "readiness_no_go"
    assert not (tmp_path / "loop.lock").exists()


def test_authorized_queue_has_eight_apply_tasks_and_a_blocked_auth_proposal():
    queue = json.loads((ROOT / "config" / "continuous_loop_tasks.json").read_text(encoding="utf-8"))
    runnable = [t for t in queue["tasks"] if t.get("authorized") is True]
    assert len(runnable) >= 8
    for task in runnable:
        assert task["schema_version"] == 2
        assert task["authorization_note"]
        assert task["apply_commands"]
        assert task["precheck_commands"]
        assert task["checks"]
        assert task["commit_paths"]
        assert not cl.validate_task(task)
    blocked = [t for t in queue["tasks"] if t.get("authorized") is False]
    assert any("auth" in str(t.get("blocked") or "").lower() for t in blocked)


def test_deadline_is_enforced_even_with_task_budget_left(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    tasks = {"tasks": [_task("t0")]}
    result = cl.run_campaign(tasks, {"tasks": {}, "completed": {}},
                             max_tasks=5, deadline_minutes=0.0,
                             readiness={"ok": True},
                             execute=lambda *a, **k: pytest.fail("deadline must stop first"))
    assert result["stop_reason"] == "deadline_minutes"
    assert result["attempted"] == 0
