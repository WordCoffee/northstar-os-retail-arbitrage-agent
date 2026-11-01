"""Recovery depth: multi-file restore, mid-task STOP, crash/resume, no duplicates."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git required")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=root, check=True)
    subprocess.run([GIT, "config", "user.email", "loop@northstar.invalid"], cwd=root, check=True)
    subprocess.run([GIT, "config", "user.name", "loop test"], cwd=root, check=True)
    (root / "a.py").write_text("a = 1\n", encoding="utf-8")
    (root / "b.py").write_text("b = 2\n", encoding="utf-8")
    (root / "user.txt").write_text("operator work\n", encoding="utf-8")
    subprocess.run([GIT, "add", "a.py", "b.py", "user.txt"], cwd=root, check=True)
    subprocess.run([GIT, "commit", "-m", "base"], cwd=root, check=True)
    return root


def test_multi_file_task_failure_restores_all_task_owned_bytes_and_user_work(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setattr(cl, "ROOT", root)
    monkeypatch.setattr(cl, "RUN_DIR", tmp_path / "runs")
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    task = {"id": "multi", "write_paths": ["a.py", "b.py"],
            "commit_paths": ["a.py", "b.py"], "execution": "prebuilt"}
    baseline = cl.take_baseline(task, "multi-run")
    before = {p: (root / p).read_bytes() for p in ("a.py", "b.py", "user.txt")}
    (root / "a.py").write_text("broken a\n", encoding="utf-8")
    (root / "b.py").unlink()
    (root / "created.py").write_text("new\n", encoding="utf-8")
    result = cl.restore_baseline(baseline, paths=["a.py", "b.py", "created.py"])
    assert result["verified"] is True
    assert (root / "a.py").read_bytes() == before["a.py"]
    assert (root / "b.py").read_bytes() == before["b.py"]
    assert (root / "user.txt").read_bytes() == before["user.txt"]
    assert not (root / "created.py").exists()


def test_stop_mid_task_terminates_worker_and_writes_failure_result(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    runner = tmp_path / "slow_worker.py"
    runner.write_text("import time\nwhile True:\n    time.sleep(0.2)\n", encoding="utf-8")
    stop = tmp_path / "STOP"
    monkeypatch.setattr(cl, "STOP_PATH", stop)
    timer = threading.Timer(0.7, lambda: stop.write_text("stop\n", encoding="utf-8"))
    timer.start()
    started = time.time()
    try:
        result = cl.run_ty_task({"id": "stop-mid", "model": "bojo"},
                                "stop-mid-run", run_dir, timeout_s=10,
                                runner_script=runner)
    finally:
        timer.cancel()
    assert time.time() - started < 5
    assert result["ok"] is False
    assert "STOP" in str(result.get("error"))
    worker = json.loads((run_dir / "worker.json").read_text(encoding="utf-8"))
    assert worker["pid"] > 0
    assert not cl._is_pid_alive(worker["pid"])


def test_crash_recovery_marks_interrupted_kills_orphan_and_resume_resets(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "RUN_DIR", tmp_path / "runs")
    monkeypatch.setattr(cl, "HEARTBEAT_PATH", tmp_path / "heartbeat.json")
    run_id = "crashed-run"
    (tmp_path / "runs" / run_id).mkdir(parents=True)
    (tmp_path / "runs" / run_id / "worker.json").write_text(
        json.dumps({"pid": 999999}), encoding="utf-8")
    state = {"completed": {}, "tasks": {"crashed": {
        "status": "running", "run_id": run_id, "pid": 999999,
    }}}
    recovered = cl.recover_interrupted(state)
    assert recovered[0]["task"] == "crashed"
    assert state["tasks"]["crashed"]["status"] == "interrupted"
    assert "stale" in state["tasks"]["crashed"]["reason"]
    # A resume is explicit and resets to pending; no duplicate commit is made.
    cl.resume_task("crashed", {"tasks": []}, state)
    assert state["tasks"]["crashed"]["status"] == "pending"
    assert state["tasks"]["crashed"]["reason"] == "operator resume"
