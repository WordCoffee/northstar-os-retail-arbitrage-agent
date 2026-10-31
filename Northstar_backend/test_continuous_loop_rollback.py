"""Rollback proof in a disposable repo: create, modify, delete, bad edit, bytes."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from snapshot import restore, snapshot

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git required")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run([GIT, "-c", "core.autocrlf=false", *args], cwd=str(root),
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "sandbox"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "loop@northstar.invalid")
    _git(root, "config", "user.name", "loop test")
    (root / "keep.txt").write_text("keep-original\n", encoding="utf-8")
    (root / "gone.txt").write_text("gone-original\n", encoding="utf-8")
    _git(root, "add", "keep.txt", "gone.txt")
    _git(root, "commit", "-m", "baseline")
    return root


def test_restore_creation_modification_deletion_and_bad_edit(tmp_path):
    root = _repo(tmp_path)
    sha = snapshot(root, "rollback-test")["sha"]
    before_keep = (root / "keep.txt").read_bytes()
    before_gone = (root / "gone.txt").read_bytes()

    # A real edit sequence: modify, delete, create, and a syntactically bad edit.
    (root / "keep.txt").write_text("def broken(:\n", encoding="utf-8")
    (root / "gone.txt").unlink()
    (root / "created.txt").write_text("new file\n", encoding="utf-8")

    result = restore(root, sha, ["keep.txt", "gone.txt"],
                     remove_created=["created.txt"])
    assert result["count"] == 2
    assert (root / "keep.txt").read_bytes() == before_keep
    assert (root / "gone.txt").read_bytes() == before_gone
    assert not (root / "created.txt").exists()
    assert result["removed"] == ["created.txt"]

    # A second failed edit follows the same bytes-level proof.
    (root / "keep.txt").write_text("still broken\n", encoding="utf-8")
    restore(root, sha, ["keep.txt"])
    assert (root / "keep.txt").read_bytes() == before_keep


def test_restore_is_scoped_and_leaves_unrelated_work_alone(tmp_path):
    root = _repo(tmp_path)
    sha = snapshot(root, "scoped-test")["sha"]
    (root / "keep.txt").write_text("task change\n", encoding="utf-8")
    (root / "unrelated.txt").write_text("user work\n", encoding="utf-8")
    restore(root, sha, ["keep.txt"])
    assert (root / "keep.txt").read_text(encoding="utf-8") == "keep-original\n"
    assert (root / "unrelated.txt").read_text(encoding="utf-8") == "user work\n"
