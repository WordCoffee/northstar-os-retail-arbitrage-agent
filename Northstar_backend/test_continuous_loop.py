"""Continuous-loop supervisor: task selection, contract validation, safety, state."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl


def _task(task_id: str, **extra):
    base = {
        "id": task_id,
        "name": task_id,
        "authorized": True,
        "risk": "low",
        "execution": "prebuilt",
        "commit_paths": [f"docs/{task_id}.md"],
        "checks": [],
    }
    base.update(extra)
    return base


def _tasks():
    return {"tasks": [
        _task("a"),
        _task("b", blocked="not authorized yet"),
        _task("c", dependencies=["a"]),
    ]}


def test_select_task_picks_first_eligible_and_skips_blocked_or_dependent():
    tasks = _tasks()
    state = {"tasks": {}, "completed": {}}
    assert cl.select_task(tasks, state)["id"] == "a"
    state["tasks"]["a"] = {"status": "completed"}
    assert cl.select_task(tasks, state)["id"] == "c"
    assert cl.select_task(tasks, state, "b") is None
    assert cl.select_task(tasks, state, "a") is None


def test_dependency_must_be_completed_not_merely_present():
    tasks = _tasks()
    state = {"tasks": {"a": {"status": "failed"}}, "completed": {}}
    assert cl.blocked_reason(tasks["tasks"][2], state) == "dependency 'a' is failed"


def test_contract_requires_explicit_authorization_and_low_risk():
    bad = _task("x", authorized=False)
    assert any("authorized" in e for e in cl.validate_task(bad))
    high = _task("y", risk="high")
    assert any("risk" in e for e in cl.validate_task(high))
    ty = _task("z", execution="ty", write_paths=[], acceptance_commands=[])
    assert any("objective" in e or "write_paths" in e for e in cl.validate_task(ty))


def test_contract_rejects_forbidden_commands_and_escape_paths():
    bad = _task("x", checks=[{"name": "bad", "cmd": ["python", "amazon_search.py"]}])
    assert any("forbidden" in e for e in cl.validate_task(bad))
    escape = _task("y", commit_paths=["../outside.md"])
    assert any("refused" in e for e in cl.validate_task(escape))


def test_commit_paths_allowlist_and_denylist():
    allowed, refused = cl.validate_commit_paths([
        "config/continuous_loop_tasks.json",
        "docs/CONTINUOUS_LOOP.md",
        "scripts/continuous_loop.py",
        "Northstar_backend/main.py",
        "../outside.py",
        "exports/run.png",
        "Northstar_backend/.env",
        "data/northstar.db",
        "/absolute/path.py",
        "random/file.py",
    ])
    assert "config/continuous_loop_tasks.json" in allowed
    assert "scripts/continuous_loop.py" in allowed
    assert "Northstar_backend/main.py" in allowed
    assert len(refused) == 6
    assert any("escape" in r for r in refused)
    assert any("protected" in r for r in refused)
    assert any("allowlist" in r for r in refused)


def test_forbidden_command_tokens_and_executables():
    assert cl.check_command(["python", "-m", "pytest"]) is None
    assert cl.check_command(["npm", "run", "test:ui"]) is None
    assert "amazon" in (cl.check_command(["python", "amazon_search.py"]) or "")
    assert "chrome" in (cl.check_command(["node", "chromeconnect.js"]) or "")
    assert "not allowed" in (cl.check_command(["powershell", "Get-Item", "."]) or "")


def test_recover_interrupted_marks_stale_running_task(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    state = {"completed": {}, "tasks": {"x": {"status": "running", "pid": 999999}}}
    recovered = cl.recover_interrupted(state)
    assert recovered and state["tasks"]["x"]["status"] == "interrupted"
    assert "stale" in state["tasks"]["x"]["reason"]


def test_scrub_redacts_secret_shaped_text():
    text = "token=abc123 password: hunter2 sk-live-123456789 Bearer abc.def"
    out = cl._scrub(text)
    assert "abc123" not in out
    assert "hunter2" not in out
    assert "sk-live-123456789" not in out
    assert out.count("<redacted>") >= 3


def test_append_ledger_is_jsonl(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    cl.append_ledger({"cycle": "one", "status": "ok"}, ledger)
    cl.append_ledger({"cycle": "two", "status": "failed"}, ledger)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [r["cycle"] for r in rows] == ["one", "two"]


def test_status_separates_eligible_blocked_completed_and_failed(tmp_path):
    tasks = {"tasks": [_task("a"), _task("b", blocked="needs operator"),
                       _task("c"), _task("d")]}
    state = {"completed": {}, "tasks": {
        "a": {"status": "completed"},
        "c": {"status": "failed", "reason": "acceptance"},
        "d": {"status": "interrupted", "reason": "stale"},
    }}
    out = cl.status_report(tasks, state, tmp_path / "no-ledger.jsonl")
    assert out["buckets"]["completed"] == ["a"]
    assert out["buckets"]["failed"][0]["id"] == "c"
    assert out["buckets"]["interrupted"][0]["id"] == "d"
    assert out["buckets"]["blocked"][0]["id"] == "b"
    assert "a" not in out["buckets"]["eligible"]


def test_execute_prebuilt_failure_is_recorded_not_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    task = _task("fail", checks=[{"name": "fail", "cmd": ["python", "-c", "raise SystemExit(1)"]}])
    state = {"completed": {}, "tasks": {}}
    result = cl.execute_task(task, state)
    assert result["status"] == "failed"
    assert state["tasks"]["fail"]["status"] == "failed"
    assert "acceptance failed" in state["tasks"]["fail"]["reason"]


def test_execute_prebuilt_success_marks_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    task = _task("pass", checks=[{"name": "pass", "cmd": ["python", "-c", "print('ok')"]}])
    state = {"completed": {}, "tasks": {}}
    result = cl.execute_task(task, state, no_commit=True)
    assert result["status"] == "completed"
    assert state["tasks"]["pass"]["status"] == "completed"


def test_commit_task_preserves_pre_existing_staged_work(tmp_path, monkeypatch):
    git = shutil.which("git")
    if not git:
        pytest.skip("git required")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([git, "config", "user.email", "loop@northstar.invalid"], cwd=repo, check=True)
    subprocess.run([git, "config", "user.name", "loop test"], cwd=repo, check=True)
    (repo / "user.txt").write_text("base\n", encoding="utf-8")
    subprocess.run([git, "add", "user.txt"], cwd=repo, check=True)
    subprocess.run([git, "commit", "-m", "base"], cwd=repo, check=True)
    # The operator has staged an unrelated edit before the task runs.
    (repo / "user.txt").write_text("operator staged work\n", encoding="utf-8")
    subprocess.run([git, "add", "user.txt"], cwd=repo, check=True)
    (repo / "docs").mkdir()
    (repo / "docs" / "task.md").write_text("task output\n", encoding="utf-8")
    monkeypatch.setattr(cl, "ROOT", repo)
    result = cl.commit_task({"commit_paths": ["docs/task.md"],
                             "commit_message": "task commit"},
                            {"docs/task.md"}, {})
    assert result["ok"] and result["committed"], result
    head = subprocess.run([git, "show", "--name-only", "--format=", "HEAD"],
                          cwd=repo, capture_output=True, text=True, check=True).stdout
    assert "docs/task.md" in head
    assert "user.txt" not in head
    staged = subprocess.run([git, "diff", "--cached", "--name-only"],
                            cwd=repo, capture_output=True, text=True, check=True).stdout
    assert "user.txt" in staged


def test_lock_refuses_a_live_owner_and_reclaims_a_dead_one(tmp_path, monkeypatch):
    lock = tmp_path / "loop.lock"
    monkeypatch.setattr(cl, "LOCK_PATH", lock)
    lock.write_text(json.dumps({"pid": __import__("os").getpid(), "created_ts": __import__("time").time()}),
                    encoding="utf-8")
    with pytest.raises(cl.LoopError):
        cl.acquire_lock("run-1")
    lock.write_text(json.dumps({"pid": 999999, "created_ts": 0}), encoding="utf-8")
    record = cl.acquire_lock("run-2")
    assert record["run_id"] == "run-2"
    cl.release_lock()


def test_stop_blocks_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    (tmp_path / "STOP").write_text("stop", encoding="utf-8")
    with pytest.raises(cl.LoopError):
        cl.execute_task(_task("stop"), {"completed": {}, "tasks": {}})


def test_command_timeout_is_reported():
    result = cl.run_command(["python", "-c", "import time; time.sleep(2)"], timeout=0.2)
    assert result["ok"] is False
    assert "timeout" in result["error"]


def test_commit_task_refuses_out_of_scope_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "ROOT", tmp_path)
    result = cl.commit_task(_task("scope"), {"Northstar_backend/evil.py"}, {})
    assert result["ok"] is False
    assert "outside commit_paths" in result["error"]


def test_dry_run_command_does_not_execute(tmp_path):
    out = cl.run_command(["python", "-c", "raise SystemExit(1)"],
                         cwd=tmp_path, dry_run=True)
    assert out["ok"] is True
    assert out["output"] == "[dry-run]"

# ---------------------------------------------------------------------------
# wiring: a new module nobody calls is not a completed task
# ---------------------------------------------------------------------------

def test_new_module_without_a_consumer_is_refused(monkeypatch):
    monkeypatch.setattr(cl, "_git_show",
                        lambda rel, rev="HEAD": b"x" if rel == "Northstar_backend/tys_assistant.py" else None)
    task = _task("w", execution="ty", objective="build the thing",
                 write_paths=["Northstar_backend/brand_new.py"],
                 commit_paths=["Northstar_backend/brand_new.py"])
    errors = cl.validate_task(task)
    assert any("wiring" in e for e in errors), errors


def test_new_module_with_a_named_consumer_validates(monkeypatch):
    monkeypatch.setattr(cl, "_git_show",
                        lambda rel, rev="HEAD": b"x" if rel == "Northstar_backend/tys_assistant.py" else None)
    task = _task("w", execution="ty", objective="build the thing",
                 write_paths=["Northstar_backend/brand_new.py"],
                 commit_paths=["Northstar_backend/brand_new.py"],
                 wiring={"imported_by": ["Northstar_backend/tys_assistant.py"]})
    assert cl.validate_task(task) == []


def test_wiring_consumer_must_already_exist(monkeypatch):
    monkeypatch.setattr(cl, "_git_show",
                        lambda rel, rev="HEAD": b"x" if rel == "Northstar_backend/tys_assistant.py" else None)
    task = _task("w", execution="ty", objective="build the thing",
                 write_paths=["Northstar_backend/brand_new.py"],
                 commit_paths=["Northstar_backend/brand_new.py"],
                 wiring={"imported_by": ["Northstar_backend/imaginary.py"]})
    assert any("does not exist" in e for e in cl.validate_task(task))


def test_wiring_verification_fails_when_the_consumer_never_calls_it(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "_git_show", lambda rel, rev="HEAD": None)
    consumer = tmp_path / "consumer.py"
    consumer.write_text("print('unrelated')\n", encoding="utf-8")
    task = {"write_paths": ["Northstar_backend/brand_new.py"],
            "wiring": {"imported_by": ["consumer.py"]}}
    report = cl.verify_wiring(task, root=tmp_path)
    assert report["ok"] is False
    assert "never imports or calls" in report["checks"][0]["detail"]

    consumer.write_text("import brand_new\n", encoding="utf-8")
    assert cl.verify_wiring(task, root=tmp_path)["ok"] is True
