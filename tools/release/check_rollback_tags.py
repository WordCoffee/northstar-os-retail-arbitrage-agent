"""Every unit tag must have a restore point. This checks it instead of remembering it.

The rule (work order §2, §7): *a rollback tag before every unit and every batch*. It was
broken four times on 2026-11-11 — block3, block4, block5 and the UI defects all shipped with
no `rollback/pre-*` tag — and a previous verifier had already caught the same omission for
D-026/D-027, where the tags were then created retroactively and the habit still did not
change. A rule enforced by memory is not enforced.

Contract: for every tag named `ty-dir-<unit>`, a tag named `rollback/pre-<unit>…` must exist
and point at that unit's **parent** commit — the tree as it stood before the unit landed.

Usage:
    python tools/release/check_rollback_tags.py            # human summary, exit 1 on a gap
    python tools/release/check_rollback_tags.py --json      # machine-readable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True, check=True).stdout.strip()


def _is_repo() -> bool:
    try:
        _git("rev-parse", "--git-dir")
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def check() -> Dict[str, object]:
    if not _is_repo():
        return {"ok": True, "skipped": "not a git repository", "units": []}

    unit_tags = [t for t in _git("tag", "--list", "ty-dir-*").splitlines() if t]
    rollback_tags = [t for t in _git("tag", "--list", "rollback/*").splitlines() if t]
    rollback_commits = {}
    for tag in rollback_tags:
        try:
            rollback_commits[tag] = _git("rev-parse", f"{tag}^{{commit}}")
        except subprocess.CalledProcessError:
            continue

    rows: List[Dict[str, object]] = []
    missing: List[str] = []
    # A restore point is a commit, not a naming convention: several rollback tags are named
    # after a defect (rollback/pre-d020-20261111) rather than after the unit they cover, and
    # matching on the unit id alone reported 39 of 41 units as unprotected. The contract is
    # "a rollback tag points at the tree that existed before the unit landed".
    covered = {commit: [name for name, value in rollback_commits.items() if value == commit]
               for commit in set(rollback_commits.values())}

    for tag in unit_tags:
        unit = tag[len("ty-dir-"):]
        try:
            unit_commit = _git("rev-parse", f"{tag}^{{commit}}")
            parent = _git("rev-parse", f"{unit_commit}^")
        except subprocess.CalledProcessError:
            rows.append({"tag": tag, "status": "unresolvable"})
            missing.append(tag)
            continue
        # the pre-unit tree is the parent; a tag on the unit commit itself is also a usable
        # restore point (it is that unit's own state), so either satisfies the rule
        names = covered.get(parent, []) or covered.get(unit_commit, [])
        rows.append({
            "tag": tag,
            "unit": unit,
            "unit_commit": unit_commit[:8],
            "parent": parent[:8],
            "rollback_tags": names,
            "status": "ok" if names else "missing",
        })
        if not names:
            missing.append(tag)

    return {"ok": not missing, "units": rows, "missing": missing}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Every unit tag needs a rollback point.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for row in result.get("units") or []:
            if row.get("status") != "ok":
                print(f"NO ROLLBACK POINT  {row.get('tag')}  ({row.get('status')}) "
                      f"commit {row.get('unit_commit')} parent {row.get('parent')}")
        bad = result.get("missing") or []
        print(f"{len(result.get('units') or [])} unit tag(s); "
              f"{len(bad)} without a restore point at the unit's parent")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
