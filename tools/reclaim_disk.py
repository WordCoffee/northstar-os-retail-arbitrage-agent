"""Reclaim disk from things the loop itself produced - never from the operator.

Disk is the current binding constraint (9.7 GB free; downloads need 10 GB+, and
the image lane's weights are missing). This tool says exactly what it would
delete and refuses anything outside a declared, narrow list.

    python tools/reclaim_disk.py            # dry run, prints the plan
    python tools/reclaim_disk.py --apply    # delete

Rules (all relative to the repo root, all produced by the loop):

  state/runs/**            campaign run scratch, older than --run-days (7)
  state/checkpoints/**     keep the newest --keep-checkpoints (5) by mtime
  state/evidence/*.tmp     abandoned temp writes
  renders/autonomy_probe/bench/*_a[2-9].png   retry artifacts (attempt 1 kept)
  tmp/**                   scratch files the probe scripts create
  **/__pycache__, .pytest_cache, .hypothesis, test-results, playwright-report

Never touched: data/, backups/, renders/references/, renders/mogra_lions_mane/,
any model directory, .git, node_modules, .env*, and anything not matched above.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]

SAFE_DIR_NAMES = ("__pycache__", ".pytest_cache", ".hypothesis", "test-results",
                  "playwright-report")
#: Anything containing these path fragments is never deleted, even if matched.
PROTECTED = ("data/", "backups/", "renders/references/", "renders/mogra_lions_mane/",
             ".git/", "node_modules/", "shared/", "config/", "docs/", "Northstar_backend/data/")


def _size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(base) / name).stat().st_size
            except OSError:
                pass
    return total


def _newest_mtime(path: Path) -> float:
    """Newest mtime in a tree. A directory's own mtime is when it was written to,
    which for scratch directories is "now" even when everything inside is old."""
    if path.is_file():
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0
    newest = 0.0
    for base, dirs, files in os.walk(path):
        for name in files:
            try:
                newest = max(newest, (Path(base) / name).stat().st_mtime)
            except OSError:
                pass
        if not files and not dirs:
            try:
                newest = max(newest, Path(base).stat().st_mtime)
            except OSError:
                pass
    return newest or (path.stat().st_mtime if path.exists() else 0.0)


def _older_than(path: Path, days: float) -> bool:
    newest = _newest_mtime(path)
    return newest > 0 and (time.time() - newest) > days * 86400


def _protected(path: Path) -> bool:
    rel = str(path.relative_to(ROOT)).replace("\\", "/") + "/"
    return any(frag in rel for frag in PROTECTED)


def plan(*, run_days: float = 7.0, keep_checkpoints: int = 5) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def add(path: Path, reason: str) -> None:
        if not path.exists() or _protected(path):
            return
        items.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                      "bytes": _size(path), "reason": reason})

    runs = ROOT / "state" / "runs"
    if runs.is_dir():
        for child in sorted(runs.iterdir()):
            if child.is_dir() and _older_than(child, run_days):
                add(child, f"run scratch older than {run_days:g} days")

    checkpoints = ROOT / "state" / "checkpoints"
    if checkpoints.is_dir():
        # Sort by the NEWEST file inside each checkpoint, not the directory's own
        # mtime: a directory's mtime is when it was last written to, which is
        # "now" for a checkpoint that was just touched. Sorting on it kept an
        # arbitrary set (caught by the full-suite run, not the isolated test).
        kids = sorted((p for p in checkpoints.iterdir() if p.is_dir()),
                      key=lambda p: _newest_mtime(p), reverse=True)
        for child in kids[max(1, keep_checkpoints):]:
            add(child, f"checkpoint beyond the newest {keep_checkpoints}")

    for tmp in (ROOT / "state" / "evidence").glob("*.tmp") if (ROOT / "state" / "evidence").is_dir() else []:
        add(tmp, "abandoned temp write")

    bench = ROOT / "renders" / "autonomy_probe" / "bench"
    if bench.is_dir():
        for png in bench.glob("*_a[2-9].png"):
            add(png, "retry artifact (attempt 1 is kept)")

    scratch = ROOT / "tmp"
    if scratch.is_dir():
        for child in scratch.iterdir():
            add(child, "scratch directory")

    for base, dirs, _files in os.walk(ROOT):
        base_path = Path(base)
        if any(frag in str(base_path).replace("\\", "/") + "/" for frag in PROTECTED):
            dirs[:] = []
            continue
        for name in list(dirs):
            if name in SAFE_DIR_NAMES:
                add(base_path / name, f"{name} cache")
                dirs.remove(name)

    return items


def apply(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    freed = 0
    removed: List[str] = []
    failed: List[str] = []
    for item in items:
        path = ROOT / item["path"]
        if not path.exists() or _protected(path):
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            freed += int(item["bytes"])
            removed.append(item["path"])
        except OSError:
            failed.append(item["path"])
    return {"removed": len(removed), "failed": failed, "freed_bytes": freed,
            "freed_gb": round(freed / 1e9, 2), "paths": removed[:40]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Reclaim loop-generated disk.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--run-days", type=float, default=7.0)
    parser.add_argument("--keep-checkpoints", type=int, default=5)
    ns = parser.parse_args(argv)

    items = plan(run_days=ns.run_days, keep_checkpoints=ns.keep_checkpoints)
    total = sum(i["bytes"] for i in items)
    if not ns.apply:
        print(json.dumps({"dry_run": True, "targets": len(items),
                          "reclaimable_gb": round(total / 1e9, 2),
                          "items": items[:40]}, indent=2))
        return 0
    result = apply(items)
    result["dry_run"] = False
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
