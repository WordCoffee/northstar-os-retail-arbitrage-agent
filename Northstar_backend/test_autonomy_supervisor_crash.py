"""Real supervisor-crash simulation: kill mid-task, relaunch, detect, resume."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git required")


def test_kill_supervisor_mid_task_then_recover_and_resume(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "state").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    (repo / "Northstar_backend").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "continuous_loop.py", repo / "scripts" / "continuous_loop.py")
    shutil.copy2(ROOT / "Northstar_backend" / "snapshot.py", repo / "Northstar_backend" / "snapshot.py")
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.email", "loop@northstar.invalid"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.name", "loop test"], cwd=repo, check=True)
    (repo / "work.txt").write_text("base\n", encoding="utf-8")
    subprocess.run([GIT, "add", "work.txt"], cwd=repo, check=True)
    subprocess.run([GIT, "commit", "-m", "base"], cwd=repo, check=True)
    task = {
        "id": "crash-mid-task", "name": "slow apply", "schema_version": 2,
        "authorized": True, "authorization_note": "test", "risk": "low",
        "risk_class": "low", "execution": "prebuilt", "objective": "sleep",
        "write_paths": ["work.txt"],
        "precheck_commands": [["python", "-c", "raise SystemExit(1)"]],
        "apply_commands": [["python", "-c", "import time; time.sleep(30)"]],
        "checks": [["python", "-c", "print('never')"]],
        "commit_paths": ["work.txt"],
    }
    (repo / "config" / "continuous_loop_tasks.json").write_text(
        json.dumps({"schema": "test", "tasks": [task]}), encoding="utf-8")
    (repo / "state" / "continuous_loop_state.json").write_text(
        json.dumps({"tasks": {}, "completed": {}}), encoding="utf-8")
    child_code = (
        "import sys; sys.path.insert(0, r'%s'); import continuous_loop as cl; "
        "tasks=cl.load_tasks(); state=cl.load_state(); "
        "cl.execute_task(tasks['tasks'][0], state, no_commit=True)"
        % (ROOT / "scripts")
    )
    env = dict(os.environ, NORTHSTAR_LOOP_ROOT=str(repo))
    child_log = open(repo / "child.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", child_code], cwd=repo, env=env,
                            stdout=child_log, stderr=subprocess.STDOUT)
    state_path = repo / "state" / "continuous_loop_state.json"
    deadline = time.time() + 15
    state = {}
    while time.time() < deadline:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        if (state.get("tasks") or {}).get("crash-mid-task", {}).get("status") in ("running", "verifying"):
            break
        time.sleep(0.1)
    if state.get("tasks", {}).get("crash-mid-task", {}).get("status") not in ("running", "verifying"):
        child_log.flush()
        print((repo / "child.log").read_text(encoding="utf-8", errors="replace")[-4000:])
    assert state.get("tasks", {}).get("crash-mid-task", {}).get("status") in ("running", "verifying")
    # Kill the supervisor and its child tree, as an OS crash would.
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       capture_output=True, text=True, timeout=30)
    else:
        os.killpg(os.getpgid(proc.pid), 9)
    proc.wait(timeout=10)
    # A relaunch detects the dead owner and resumes explicitly; no auto-replay.
    sys.path.insert(0, str(ROOT / "scripts"))
    import continuous_loop as cl
    monkeypatch.setattr(cl, "ROOT", repo)
    monkeypatch.setattr(cl, "STATE_PATH", state_path)
    monkeypatch.setattr(cl, "RUN_DIR", repo / "state" / "runs")
    monkeypatch.setattr(cl, "HEARTBEAT_PATH", repo / "state" / "continuous_loop_heartbeat.json")
    monkeypatch.setattr(cl, "STOP_PATH", repo / "STOP")
    state = cl.load_state(state_path)
    recovered = cl.recover_interrupted(state)
    assert recovered and state["tasks"]["crash-mid-task"]["status"] == "interrupted"
    cl.resume_task("crash-mid-task", {"tasks": []}, state)
    assert state["tasks"]["crash-mid-task"]["status"] == "pending"
    log = subprocess.run([GIT, "log", "--oneline"], cwd=repo, capture_output=True,
                         text=True, check=True).stdout
    assert log.count("\n") == 1  # only the base commit; no duplicate side effect
    assert (repo / "work.txt").read_text(encoding="utf-8") == "base\n"
