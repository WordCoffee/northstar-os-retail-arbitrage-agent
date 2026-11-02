"""External-author handoff: the supervisor keeps scope, verification and commit.

The author writes; these tests prove the supervisor's controls still decide.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import author_lane as al
import continuous_loop as cl

GIT = shutil.which("git")
TARGET = "Northstar_backend/src/mod.py"


def _repo(tmp_path, monkeypatch):
    if not GIT:
        pytest.skip("git required")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.email", "loop@northstar.invalid"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.name", "loop test"], cwd=repo, check=True)
    (repo / "Northstar_backend" / "src").mkdir(parents=True)
    (repo / TARGET).write_text("def f():\n    return 1\n", encoding="utf-8")
    (repo / "probe.py").write_text(
        "import sys\nsys.path.insert(0,'Northstar_backend/src')\nfrom mod import f\n"
        "raise SystemExit(0 if f()==2 else 1)\n", encoding="utf-8")
    subprocess.run([GIT, "add", "-A"], cwd=repo, check=True)
    subprocess.run([GIT, "commit", "-m", "base"], cwd=repo, check=True)
    monkeypatch.setattr(cl, "ROOT", repo)
    monkeypatch.setattr(cl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cl, "STOP_PATH", tmp_path / "STOP")
    monkeypatch.setattr(cl, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(cl, "RUN_DIR", tmp_path / "runs")
    monkeypatch.setattr(cl, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(al, "HANDOFF_DIR", tmp_path / "handoffs")
    return repo


def _task(**over):
    task = {"id": "t", "name": "t", "schema_version": 2, "authorized": True,
            "authorization_note": "x", "risk": "low", "execution": "ty",
            "objective": "make f return 2", "write_paths": [TARGET],
            "read_paths": [TARGET], "acceptance_commands": [["python", "probe.py"]],
            "checks": [{"name": "probe", "cmd": ["python", "probe.py"], "cwd": "."}],
            "commit_paths": [TARGET], "commit_message": "fix: f returns 2",
            "required_artifact": TARGET, "timeout_seconds": 60,
            "max_repairs": 0, "max_steps": 8}
    task.update(over)
    return task


def test_open_hands_only_the_permitted_context(tmp_path, monkeypatch):
    _repo(tmp_path, monkeypatch)
    tasks = {"tasks": [_task()]}
    state = {"tasks": {}, "completed": {}}
    handoff = al.open_task("t", tasks, state)
    assert handoff["write_paths"] == [TARGET]
    assert handoff["read_paths"] == [TARGET]
    assert "supervisor" not in json.dumps(handoff).lower()
    assert state["tasks"]["t"]["status"] == "authoring"


def test_close_refuses_and_restores_an_out_of_scope_edit(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    tasks = {"tasks": [_task()]}
    state = {"tasks": {}, "completed": {}}
    al.open_task("t", tasks, state)
    (repo / TARGET).write_text("def f():\n    return 2\n", encoding="utf-8")
    (repo / "extra.py").write_text("x = 1\n", encoding="utf-8")     # out of scope
    out = al.close_task("t", tasks, state)
    assert out["status"] == "failed" and "out-of-scope" in out["error"]
    assert not (repo / "extra.py").exists()
    assert (repo / TARGET).read_text(encoding="utf-8") == "def f():\n    return 1\n"


def test_close_restores_when_the_probe_fails(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    tasks = {"tasks": [_task()]}
    state = {"tasks": {}, "completed": {}}
    al.open_task("t", tasks, state)
    (repo / TARGET).write_text("def f():\n    return 3\n", encoding="utf-8")
    out = al.close_task("t", tasks, state)
    assert out["status"] == "failed" and "acceptance failed" in out["error"]
    assert (repo / TARGET).read_text(encoding="utf-8") == "def f():\n    return 1\n"


def test_close_commits_only_the_task_file(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    tasks = {"tasks": [_task()]}
    state = {"tasks": {}, "completed": {}}
    al.open_task("t", tasks, state)
    (repo / TARGET).write_text("def f():\n    return 2\n", encoding="utf-8")
    out = al.close_task("t", tasks, state)
    assert out["status"] == "completed", out
    sha = out["commit"]["sha"]
    files = subprocess.run([GIT, "show", "--name-only", "--format=", sha],
                           cwd=repo, capture_output=True, text=True).stdout.split()
    assert files == [TARGET]
    assert state["tasks"]["t"]["status"] == "completed"
