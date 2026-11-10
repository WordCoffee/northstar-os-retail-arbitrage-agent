"""How much of the staging candidate's suite exists on main, by test name.

Main cannot be collected at all right now (files it needs live in slices the gitleaks hook refuses),
so the honest comparison is: which candidate test ids have their module on main, and which do not —
named, not just counted.

    python tools/main_vs_candidate.py [--candidate-idlist PATH] [--ref main]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IDLIST = ROOT / "reports" / "ty" / "_idlist_candidate10_20261109.txt"
OUT = ROOT / "reports" / "ty" / "main_vs_candidate_by_name.json"


def load_ids(path: Path) -> list:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return [str(name).strip('"') for name in payload.get("ids") or []]
    return [str(name).strip('"') for name in payload]


def tree(ref: str) -> set:
    listing = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref],
                                      cwd=str(ROOT), text=True)
    return {line.strip().replace("\\", "/") for line in listing.splitlines() if line.strip()}


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Candidate test ids vs what is on main")
    parser.add_argument("--candidate-idlist", type=Path, default=DEFAULT_IDLIST)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    ids = load_ids(ns.candidate_idlist)
    present = tree(ns.ref)
    per_module = defaultdict(lambda: {"present": 0, "missing": 0})
    for test_id in ids:
        module = test_id.split("::")[0]
        path = f"Northstar_backend/{module}"
        row = per_module[module]
        if path in present:
            row["present"] += 1
        else:
            row["missing"] += 1
    missing_modules = sorted(name for name, row in per_module.items() if row["missing"])
    on_main = sum(row["present"] for row in per_module.values())
    result = {
        "ref": ns.ref,
        "candidate_ids": len(ids),
        "ids_with_module_on_main": on_main,
        "ids_with_module_missing_from_main": len(ids) - on_main,
        "modules_present": sum(1 for row in per_module.values() if row["present"]),
        "modules_missing": len(missing_modules),
        "missing_modules": missing_modules,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if ns.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"candidate ids           {len(ids)}")
    print(f"module present on {ns.ref:5s}  {on_main} ids  "
          f"({result['modules_present']} modules)")
    print(f"module missing on {ns.ref:5s}  {len(ids) - on_main} ids  "
          f"({len(missing_modules)} modules)")
    for name in missing_modules[:15]:
        print("   -", name)
    if len(missing_modules) > 15:
        print(f"   ... and {len(missing_modules) - 15} more (full list in {OUT.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
