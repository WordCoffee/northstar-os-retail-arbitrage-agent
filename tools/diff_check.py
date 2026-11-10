"""Check a unified diff's shape and per-hunk line arithmetic.

    python tools/diff_check.py <file.diff>

Exit 0 only when the diff is usable as written. The authority is
`agent_kernel.content.validate_patch` — the same check the benchmark validator
applies — so the work order's acceptance and the scored bar cannot drift apart.

It deliberately does NOT test applicability against a workspace: the patch
records the fix, so once the file has been corrected the patch no longer matches
it, and `git apply` is the tool for applying a patch to a tree, not this.

Prints the first problem, because that is what a repair loop needs to read.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel.content import validate_patch  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: diff_check.py <file.diff>")
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"bad: missing {path}")
        return 1
    result = validate_patch(path)
    if result["valid"]:
        sem = (result.get("checks") or {}).get("semantics") or {}
        print(f"ok: {sem.get('hunks', 0)} hunk(s), arithmetic holds")
        return 0
    checks = result.get("checks") or {}
    sem = checks.get("semantics") or {}
    missing = [k for k in ("has_minus_file", "has_plus_file", "has_hunk")
               if not checks.get(k)]
    if missing:
        print("bad: missing " + ", ".join(missing))
        return 1
    for bad in sem.get("bad_hunks") or []:
        old_seen, old_want = bad["old"]
        new_seen, new_want = bad["new"]
        print(f"bad: hunk at line {bad['line']} declares -{old_want}/+{new_want} "
              f"lines but its body has {old_seen} old and {new_seen} new lines; "
              "the @@ header must match the body exactly")
        return 1
    print("bad: " + str(result.get("detail") or "patch rejected"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
