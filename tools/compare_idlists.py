"""Compare main's test ids with the staging candidate's, by test name.

The owner asked for the main-tree suite to be reported **by test name** against the staging
candidate, not by count. Counts hide the interesting cases: a test that exists on main and not on
staging is a regression in the promotion, and one that exists on staging and not on main is work
still waiting for a slice.

    python tools/compare_idlists.py reports/ty/_idlist_main_X.txt reports/ty/_idlist_candidate10_20261109.txt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def load(path: Path) -> List[str]:
    ids: List[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            ids.append(name)
    return ids


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two pytest id lists by name")
    parser.add_argument("main_idlist", type=Path)
    parser.add_argument("candidate_idlist", type=Path)
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    main_ids = load(ns.main_idlist)
    cand_ids = load(ns.candidate_idlist)
    main_set, cand_set = set(main_ids), set(cand_ids)
    only_main = sorted(main_set - cand_set)
    only_candidate = sorted(cand_set - main_set)
    result: Dict[str, object] = {
        "main": {"file": ns.main_idlist.name, "ids": len(main_ids)},
        "candidate": {"file": ns.candidate_idlist.name, "ids": len(cand_ids)},
        "shared": len(main_set & cand_set),
        "only_on_main": only_main,
        "only_on_candidate": only_candidate,
    }
    if ns.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"main      {result['main']['ids']:5d} ids  ({ns.main_idlist.name})")
    print(f"candidate {result['candidate']['ids']:5d} ids  ({ns.candidate_idlist.name})")
    print(f"shared    {result['shared']:5d}")
    print(f"only on main      {len(only_main)}")
    for name in only_main[:40]:
        print("   +", name)
    print(f"only on candidate {len(only_candidate)}")
    for name in only_candidate[:40]:
        print("   -", name)
    if len(only_candidate) > 40:
        print(f"   ... and {len(only_candidate) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
