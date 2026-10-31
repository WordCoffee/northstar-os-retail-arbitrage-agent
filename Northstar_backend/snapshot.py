"""Diff-scoped snapshots and auto-rollback (T1 autonomy).

The operating model: an agent may change code freely, and if the test gate goes
red the change is reverted WITHOUT asking. That is only safe if the revert is
narrow. This module therefore never restores the whole tree - it restores only
the paths the loop actually wrote, computed as a diff against the snapshot.

`git stash create` is the primitive: it produces a commit object capturing the
working tree WITHOUT touching it and without a branch or index change. Snapshot
is therefore cheap enough to run before and after every loop.

Untracked files are not in a stash commit. `manifest()` records them by hash so
`restore()` can report (and optionally delete) files the loop created, and
`copy_aside()` keeps a byte copy for anything gitignored but precious.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

GIT = shutil.which("git") or "git"
SNAPSHOT_DIR = Path("state") / "snapshots"


class SnapshotError(RuntimeError):
    pass


def _run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([GIT, *args], cwd=str(root), capture_output=True, text=True,
                          timeout=180, check=False)
    if check and proc.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:300]}")
    return proc


def is_repo(root: Path | str) -> bool:
    try:
        return _run(Path(root), "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except SnapshotError:
        return False


def snapshot(root: Path | str, label: str = "loop") -> Dict[str, object]:
    """Capture the working tree in a dangling commit. Never mutates the tree."""
    root = Path(root).resolve()
    if not is_repo(root):
        raise SnapshotError(f"not a git work tree: {root}")

    proc = _run(root, "stash", "create", check=False)
    sha = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raise SnapshotError(f"git stash create failed: {proc.stderr.strip()[:300]}")
    if not sha:
        # Clean tree: HEAD is already the snapshot.
        sha = _run(root, "rev-parse", "HEAD").stdout.strip()
        clean = True
    else:
        clean = False

    record = {
        "label": label,
        "sha": sha,
        "head": _run(root, "rev-parse", "HEAD").stdout.strip(),
        "clean_tree": clean,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root": str(root),
    }
    record["untracked"] = manifest(_untracked(root))
    out_dir = root / SNAPSHOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{label}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def _untracked(root: Path) -> List[str]:
    out = _run(root, "ls-files", "--others", "--exclude-standard").stdout
    return [line for line in out.splitlines() if line.strip()]


def manifest(paths: Iterable[str], root: Path | str = ".") -> Dict[str, str]:
    """sha256 per file, so a rollback can tell 'changed' from 'created'."""
    root = Path(root)
    out: Dict[str, str] = {}
    for rel in paths:
        p = root / rel
        try:
            if p.is_file():
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
    return out


def changed_paths(root: Path | str, sha: str) -> List[str]:
    """Tracked paths that differ between the snapshot commit and the working tree."""
    root = Path(root)
    proc = _run(root, "diff", "--name-only", sha, check=False)
    if proc.returncode != 0:
        raise SnapshotError(f"git diff against {sha[:8]} failed: {proc.stderr.strip()[:200]}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def restore(root: Path | str, sha: str, paths: Optional[Sequence[str]] = None,
            *, remove_created: Optional[Iterable[str]] = None,
            dry_run: bool = False) -> Dict[str, object]:
    """Restore ONLY `paths` (default: everything that changed since `sha`).

    Never a whole-tree reset. `remove_created` deletes files the snapshot proves
    did not exist - it is opt-in and never inferred, because deleting is the one
    operation that cannot be undone by another restore.
    """
    root = Path(root).resolve()
    targets = list(paths) if paths else changed_paths(root, sha)
    removed: List[str] = []
    if not dry_run:
        for rel in list(remove_created or []):
            p = root / rel
            try:
                if p.is_file():
                    p.unlink()
                    removed.append(rel)
            except OSError:
                continue
        if targets:
            _run(root, "restore", f"--source={sha}", "--", *targets)
    return {
        "sha": sha,
        "restored": targets,
        "removed": removed,
        "dry_run": dry_run,
        "count": len(targets),
    }


def copy_aside(root: Path | str, label: str, paths: Iterable[str]) -> Dict[str, str]:
    """Byte copy for gitignored but precious outputs (renders, exports)."""
    root = Path(root).resolve()
    dest_root = root / "backups" / "snapshots" / label
    saved: Dict[str, str] = {}
    for rel in paths:
        src = root / rel
        if not src.is_file():
            continue
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        saved[rel] = str(dest.relative_to(root))
    return saved


def rollback_if_red(root: Path | str, sha: str, gate_ok: bool,
                    paths: Optional[Sequence[str]] = None) -> Dict[str, object]:
    """The T1 policy in one call: restore only when the gate failed."""
    if gate_ok:
        return {"rolled_back": False, "reason": "gate green"}
    result = restore(root, sha, paths)
    result["rolled_back"] = True
    result["reason"] = "gate red"
    return result


__all__ = ["snapshot", "restore", "changed_paths", "manifest", "copy_aside",
           "rollback_if_red", "is_repo", "SnapshotError", "SNAPSHOT_DIR"]
