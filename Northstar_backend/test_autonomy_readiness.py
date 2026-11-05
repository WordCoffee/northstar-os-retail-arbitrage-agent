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
    prebuilt = [t for t in runnable if str(t.get("execution") or "prebuilt") == "prebuilt"]
    model_tasks = [t for t in runnable if str(t.get("execution")) == "ty"]
    # The 2026-10-31 campaign proved eight prebuilt apply tasks; they remain.
    assert len(prebuilt) >= 8
    for task in prebuilt:
        assert task["schema_version"] == 2
        assert task["authorization_note"]
        assert task["apply_commands"]
        assert task["precheck_commands"]
        assert task["checks"]
        assert task["commit_paths"]
        assert not cl.validate_task(task)
    # Model-authored work is a separate contract: no prebuilt apply, but an
    # objective, a writable scope, an independent acceptance probe and a model.
    for task in model_tasks:
        assert task["schema_version"] == 2
        assert task["authorization_note"]
        assert task["objective"].strip()
        assert task["write_paths"] and task["commit_paths"]
        assert task["acceptance_commands"] and task["checks"]
        assert task.get("model") and task.get("provider") == "ollama"
        assert not task.get("apply_commands"), "a ty task must not ship a prebuilt patch"
        assert not cl.validate_task(task)
    blocked = [t for t in queue["tasks"] if t.get("authorized") is False]
    assert any("auth" in str(t.get("blocked") or "").lower() for t in blocked)


# ── measured residency, not a pre-load guess ───────────────────────────────

def _evidence(tmp_path, monkeypatch, *, model="bojo:gpu-orig", verdict="FLOOR-MET",
              min_free=4.09, age_min=1.0, resident_system=0.0):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(cl, "MODEL_RESIDENT_EVIDENCE", evidence_dir)
    record = {"model": model, "verdict": verdict, "min_available_gb": min_free,
              "resident_total_gb": 2.24, "resident_system_gb": resident_system,
              "resident_vram_gb": 2.24, "tokens": 456, "elapsed_s": 37.8}
    path = evidence_dir / f"model_resident_{cl.model_slug(model)}_20261101T000000Z.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    stamp = time.time() - age_min * 60.0
    import os
    os.utime(path, (stamp, stamp))
    return path


def test_resident_evidence_must_be_fresh_and_meet_the_floor(tmp_path, monkeypatch):
    _evidence(tmp_path, monkeypatch, min_free=4.09)
    fresh = cl.resident_evidence("bojo:gpu-orig")
    assert fresh["ok"] is True and "FLOOR-MET" in fresh["reason"]

    stale = cl.resident_evidence("bojo:gpu-orig", max_age_min=0.001)
    assert stale["ok"] is False
    assert "min old" in stale["reason"]

    _evidence(tmp_path, monkeypatch, verdict="FLOOR-MISSED", min_free=1.19)
    missed = cl.resident_evidence("bojo:gpu-orig")
    assert missed["ok"] is False
    assert "FLOOR-MISSED" in missed["reason"]


def test_resident_evidence_is_scoped_to_the_model(tmp_path, monkeypatch):
    _evidence(tmp_path, monkeypatch, model="bojo:gpu-orig")
    other = cl.resident_evidence("qwen3.5:2b")
    assert other["ok"] is False
    assert "no measured residency" in other["reason"]


def test_resident_evidence_without_any_record_is_not_ok(tmp_path, monkeypatch):
    empty = tmp_path / "evidence"
    empty.mkdir()
    monkeypatch.setattr(cl, "MODEL_RESIDENT_EVIDENCE", empty)
    out = cl.resident_evidence("bojo:gpu-orig")
    assert out["ok"] is False and out["age_min"] is None


def test_campaign_refuses_a_ty_task_without_measured_residency(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    empty = tmp_path / "evidence"
    empty.mkdir()
    monkeypatch.setattr(cl, "MODEL_RESIDENT_EVIDENCE", empty)
    # Any real measurement would fail to reach Ollama here; make it explicit.
    monkeypatch.setattr(cl, "measure_model_resident",
                        lambda model, *a, **k: {"ok": False, "record": {"verdict": "UNMEASURED"},
                                                "raw_output": "offline", "evidence": ""})
    ty_task = _task("ty-needs-model", execution="ty",
                    write_paths=["Northstar_backend/x.py"],
                    wiring={"imported_by": ["Northstar_backend/tys_api.py"]},
                    acceptance_commands=[["python", "-c", "print(1)"]])
    result = cl.run_campaign({"tasks": [ty_task]}, {"tasks": {}, "completed": {}},
                             max_tasks=1, deadline_minutes=1,
                             readiness={"ok": True, "verdict": "GO", "checks": []},
                             execute=lambda *a, **k: pytest.fail("must not execute"))
    assert result["stop_reason"] == "model_resident_no_go"
    assert result["results"] == []


def test_campaign_dispatches_a_ty_task_only_with_fresh_residency(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    _evidence(tmp_path, monkeypatch, min_free=4.09)
    # The lane choice itself is exercised elsewhere; this case is about the
    # residency evidence, so pin the lane instead of depending on today's free RAM.
    monkeypatch.setattr(cl, "resolve_lane", lambda *a, **k: {
        "ok": True, "provider": "ollama", "model": "bojo:gpu-orig",
        "reason": "pinned for the residency test"})
    seen = {}

    def fake_execute(task, state, **kw):
        seen["id"] = task["id"]
        return {"status": "completed", "task": task["id"],
                "commit": {"sha": "abc123"}, "duration_s": 0.01,
                "lane": {"provider": "ollama", "model": "bojo:gpu-orig"},
                "checks": [], "changed": []}

    ty_task = _task("ty-ok", execution="ty", write_paths=["Northstar_backend/x.py"],
                    wiring={"imported_by": ["Northstar_backend/tys_api.py"]},
                    acceptance_commands=[["python", "-c", "print(1)"]])
    result = cl.run_campaign({"tasks": [ty_task]}, {"tasks": {}, "completed": {}},
                             max_tasks=1, deadline_minutes=1,
                             readiness={"ok": True, "verdict": "GO", "checks": []},
                             execute=fake_execute)
    assert seen["id"] == "ty-ok"
    assert result["ok"] is True


# ── profile-aware readiness and runtime floor ──────────────────────────────

def test_preload_shortfall_refuses_before_loading(monkeypatch):
    called = {"n": 0}

    def must_not_measure(*a, **k):
        called["n"] += 1
        raise AssertionError("a low-memory host must not be loaded")

    out = cl.evaluate_profiles([{"model": "qwen2.5-coder:3b", "num_ctx": 8192}],
                               free_gb=4.5, measure=must_not_measure)
    assert out["ok"] is False
    assert out["preload_ok"] is False
    assert called["n"] == 0
    assert "pre-load 4.50 GB < 6.0 GB required" in out["reason"]


def test_preload_met_measures_with_the_profile_context(monkeypatch):
    seen = {}

    def fake_measure(model, *, num_ctx=None, **kw):
        seen.update({"model": model, "num_ctx": num_ctx})
        return {"ok": True, "evidence": "x", "record": {
            "model": model, "num_ctx": num_ctx, "verdict": "FLOOR-MET",
            "min_available_gb": 3.4, "resident_system_gb": 2.0}}

    out = cl.evaluate_profiles([{"model": "qwen2.5-coder:3b", "num_ctx": 8192}],
                               free_gb=6.5, measure=fake_measure)
    assert out["ok"] is True
    assert seen == {"model": "qwen2.5-coder:3b", "num_ctx": 8192}


def test_resident_shortfall_refuses_go(monkeypatch):
    def fake_measure(model, *, num_ctx=None, **kw):
        return {"ok": False, "evidence": "x", "record": {
            "model": model, "num_ctx": num_ctx, "verdict": "FLOOR-MISSED",
            "min_available_gb": 2.1, "resident_system_gb": 2.0}}

    out = cl.evaluate_profiles([{"model": "qwen2.5-coder:3b", "num_ctx": 8192}],
                               free_gb=6.5, measure=fake_measure)
    assert out["ok"] is False
    assert out["preload_ok"] is True
    assert "FLOOR-MISSED" in out["reason"]


def test_resident_evidence_is_context_scoped(tmp_path, monkeypatch):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    monkeypatch.setattr(cl, "MODEL_RESIDENT_EVIDENCE", evidence_dir)
    record = {"model": "qwen2.5-coder:3b", "num_ctx": 8192, "verdict": "FLOOR-MET",
              "min_available_gb": 3.4, "resident_total_gb": 2.0,
              "resident_system_gb": 2.0}
    (evidence_dir / "model_resident_qwen_ctx8192.json").write_text(
        json.dumps(record), encoding="utf-8")
    assert cl.resident_evidence("qwen2.5-coder:3b", num_ctx=8192)["ok"] is True
    # A 32768-context dispatch must not ride an 8192-context measurement.
    assert cl.resident_evidence("qwen2.5-coder:3b", num_ctx=32768)["ok"] is False


def test_campaign_refuses_a_lane_that_does_not_match_the_task(monkeypatch, tmp_path):
    _campaign_paths(tmp_path, monkeypatch)
    _evidence(tmp_path, monkeypatch, min_free=4.0)
    monkeypatch.setattr(cl, "measure_model_resident",
                        lambda *a, **k: {"ok": False, "record": {"verdict": "UNMEASURED"}})
    ty = _task("ty-mismatch", execution="ty", model="qwen2.5-coder:3b",
               write_paths=["Northstar_backend/x.py"],
               wiring={"imported_by": ["Northstar_backend/tys_api.py"]},
               acceptance_commands=[["python", "-c", "print(1)"]])
    monkeypatch.setattr(cl, "resolve_lane", lambda *a, **k: {
        "ok": True, "provider": "ollama", "model": "bojo:gpu-orig", "reason": "pinned"})
    result = cl.run_campaign({"tasks": [ty]}, {"tasks": {}, "completed": {}},
                             max_tasks=1, deadline_minutes=1,
                             readiness={"ok": True, "verdict": "GO", "checks": []},
                             execute=lambda *a, **k: pytest.fail("must not execute"))
    assert result["stop_reason"] == "profile_mismatch"
    assert result["results"] == []


def test_ram_floor_breach_needs_two_samples():
    assert cl.ram_floor_breached(2.9, 0) is False      # first reading: warn only
    assert cl.ram_floor_breached(2.9, 1) is True       # second: stop
    assert cl.ram_floor_breached(3.0, 1) is False      # exactly at the floor is fine
    assert cl.ram_floor_breached(None, 5) is False


def test_deadline_is_enforced_even_with_task_budget_left(tmp_path, monkeypatch):
    _campaign_paths(tmp_path, monkeypatch)
    tasks = {"tasks": [_task("t0")]}
    result = cl.run_campaign(tasks, {"tasks": {}, "completed": {}},
                             max_tasks=5, deadline_minutes=0.0,
                             readiness={"ok": True},
                             execute=lambda *a, **k: pytest.fail("deadline must stop first"))
    assert result["stop_reason"] == "deadline_minutes"
    assert result["attempted"] == 0
