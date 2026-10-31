"""T1 gate wiring: green leaves the tree alone, red restores only the diff."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))

import t1_gate

GIT = __import__("shutil").which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git required")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    def g(*a):
        subprocess.run([GIT, "-c", "core.autocrlf=false", *a], cwd=str(root),
                       capture_output=True, text=True, check=True)
    g("init", "-q"); g("config", "user.email", "a@b.invalid"); g("config", "user.name", "t")
    (root / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "other.py").write_text("KEEP = 'mine'\n", encoding="utf-8")
    (root / ".gitignore").write_text("state/\n", encoding="utf-8")
    g("add", "."); g("commit", "-qm", "init")
    return root


def test_green_gate_changes_nothing(tmp_path):
    root = _repo(tmp_path)
    (root / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    out = t1_gate.guarded_run(["python -c \"print('ok')\""], root=root, label="green")
    assert out["ok"] is True
    assert out["rolled_back"] is False
    assert (root / "mod.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_red_gate_restores_the_change(tmp_path):
    root = _repo(tmp_path)
    sha = t1_gate.snapshot.snapshot(root, "pre-edit")["sha"]   # snapshot BEFORE the edit
    (root / "mod.py").write_text("BROKEN = (\n", encoding="utf-8")
    out = t1_gate.guarded_run(["python -c \"import sys; sys.exit(1)\""], root=root,
                              label="red", restore_point=sha)
    assert out["ok"] is False
    assert out["rolled_back"] is True
    assert (root / "mod.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_red_gate_leaves_untouched_files_alone(tmp_path):
    root = _repo(tmp_path)
    sha = t1_gate.snapshot.snapshot(root, "pre-edit-2")["sha"]
    (root / "mod.py").write_text("BROKEN = (\n", encoding="utf-8")
    (root / "other.py").write_text("KEEP = 'edited by operator'\n", encoding="utf-8")
    out = t1_gate.guarded_run(["python -c \"import sys; sys.exit(2)\""], root=root,
                              label="red2", paths=["mod.py"], restore_point=sha)
    assert out["rolled_back"] is True
    assert (root / "mod.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert "operator" in (root / "other.py").read_text(encoding="utf-8")


def test_the_gate_stops_at_the_first_failure(tmp_path):
    root = _repo(tmp_path)
    out = t1_gate.guarded_run([
        "python -c \"import sys; sys.exit(3)\"",
        "python -c \"open('should_not_exist.txt','w').write('x')\"",
    ], root=root, label="stop")
    assert len(out["results"]) == 1
    assert not (root / "should_not_exist.txt").exists()


def test_gate_writes_its_record(tmp_path):
    root = _repo(tmp_path)
    t1_gate.guarded_run(["python -c \"print(1)\""], root=root, label="record")
    assert (root / "state" / "snapshots" / "record.gate.json").exists()
