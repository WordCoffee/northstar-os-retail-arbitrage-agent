"""Diff-scoped snapshots and auto-rollback (T1 autonomy)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import snapshot as snap

GIT = __import__("shutil").which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git required")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    def g(*a):
        subprocess.run([GIT, "-c", "core.autocrlf=false", *a], cwd=str(root),
                       capture_output=True, text=True, check=True)
    g("init", "-q")
    g("config", "user.email", "a@b.invalid")
    g("config", "user.name", "test")
    (root / "a.txt").write_text("one", encoding="utf-8")
    (root / "b.txt").write_text("two", encoding="utf-8")
    g("add", ".")
    g("commit", "-qm", "init")
    return root


def test_snapshot_does_not_disturb_the_tree(tmp_path):
    root = _repo(tmp_path)
    (root / "a.txt").write_text("changed", encoding="utf-8")
    rec = snap.snapshot(root, "t1")
    assert rec["sha"]
    assert rec["clean_tree"] is False
    assert (root / "a.txt").read_text(encoding="utf-8") == "changed"


def test_snapshot_on_a_clean_tree_uses_head(tmp_path):
    root = _repo(tmp_path)
    rec = snap.snapshot(root, "t2")
    assert rec["clean_tree"] is True
    assert rec["sha"] == rec["head"]


def test_restore_brings_back_only_the_named_path(tmp_path):
    root = _repo(tmp_path)
    sha = snap.snapshot(root, "t3")["sha"]
    (root / "a.txt").write_text("broken", encoding="utf-8")
    (root / "b.txt").write_text("also broken", encoding="utf-8")
    out = snap.restore(root, sha, ["a.txt"])
    assert out["restored"] == ["a.txt"]
    assert (root / "a.txt").read_text(encoding="utf-8") == "one"
    # the untouched sibling keeps its edit - a whole-tree reset would lose it
    assert (root / "b.txt").read_text(encoding="utf-8") == "also broken"


def test_restore_defaults_to_the_changed_set(tmp_path):
    root = _repo(tmp_path)
    sha = snap.snapshot(root, "t4")["sha"]
    (root / "a.txt").write_text("x", encoding="utf-8")
    (root / "b.txt").write_text("y", encoding="utf-8")
    out = snap.restore(root, sha)
    assert sorted(out["restored"]) == ["a.txt", "b.txt"]
    assert (root / "a.txt").read_text(encoding="utf-8") == "one"


def test_dry_run_reports_without_writing(tmp_path):
    root = _repo(tmp_path)
    sha = snap.snapshot(root, "t5")["sha"]
    (root / "a.txt").write_text("x", encoding="utf-8")
    out = snap.restore(root, sha, ["a.txt"], dry_run=True)
    assert out["dry_run"] is True
    assert (root / "a.txt").read_text(encoding="utf-8") == "x"


def test_manifest_hashes_files_and_skips_missing(tmp_path):
    root = _repo(tmp_path)
    m = snap.manifest(["a.txt", "nope.txt"], root)
    assert list(m) == ["a.txt"]
    assert len(m["a.txt"]) == 64


def test_managed_files_are_removed_only_when_named(tmp_path):
    root = _repo(tmp_path)
    sha = snap.snapshot(root, "t6")["sha"]
    (root / "new.txt").write_text("created by an agent", encoding="utf-8")
    out = snap.restore(root, sha, [], remove_created=["new.txt"])
    assert out["removed"] == ["new.txt"]
    assert not (root / "new.txt").exists()


def test_rollback_if_red_does_nothing_on_green(tmp_path):
    root = _repo(tmp_path)
    sha = snap.snapshot(root, "t7")["sha"]
    (root / "a.txt").write_text("x", encoding="utf-8")
    out = snap.rollback_if_red(root, sha, gate_ok=True)
    assert out["rolled_back"] is False
    assert (root / "a.txt").read_text(encoding="utf-8") == "x"


def test_rollback_if_red_restores_on_failure(tmp_path):
    root = _repo(tmp_path)
    sha = snap.snapshot(root, "t8")["sha"]
    (root / "a.txt").write_text("x", encoding="utf-8")
    out = snap.rollback_if_red(root, sha, gate_ok=False)
    assert out["rolled_back"] is True
    assert (root / "a.txt").read_text(encoding="utf-8") == "one"


def test_copy_aside_keeps_a_byte_copy(tmp_path):
    root = _repo(tmp_path)
    (root / "render.png").write_bytes(b"\x89PNG-fake")
    saved = snap.copy_aside(root, "t9", ["render.png"])
    assert saved["render.png"].endswith("render.png")
    assert (root / saved["render.png"]).read_bytes() == b"\x89PNG-fake"


def test_non_repo_raises(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(snap.SnapshotError):
        snap.snapshot(plain, "nope")
