"""Regression by test name, not by count.

The old canary compared pass counts to a frozen number. That works only while
nobody adds a test - and this programme adds tests every cycle, so the canary
went RED on its own progress and the loop would have "fixed" its new tests.

This checker compares the *set of test ids*:

  * a test that disappears is a REGRESSION (someone deleted or shadowed it);
  * a failing test is a REGRESSION (by name, with its message);
  * new tests are reported and allowed.

    python tools/check_regression.py --write --collect     # freeze the id set
    python tools/check_regression.py --junit run.xml        # check a run

Exit codes: 0 clean (additions ok), 1 regression, 2 the check could not run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "BASELINE_TESTS.json"
COLLECT = re.compile(r"^(\S+::\S+?)(?:\[.*\])?\s*$")


def _ids_from_collect(text: str) -> Set[str]:
    ids: Set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("=", "-", "no tests", "collected")):
            continue
        match = COLLECT.match(line)
        if match:
            ids.add(match.group(1))
    return ids


def _from_junit(path: Path) -> Dict[str, str]:
    """id -> 'passed' | 'failed' | 'skipped' | 'error'."""
    tree = ET.parse(path)
    out: Dict[str, str] = {}
    for case in tree.iter("testcase"):
        cls = case.get("classname") or ""
        name = case.get("name") or ""
        base = name.split("[", 1)[0]
        test_id = f"{cls}::{base}" if cls else base
        status = "passed"
        for child in case:
            tag = child.tag
            if tag == "failure":
                status = "failed"
            elif tag == "error":
                status = "error"
            elif tag == "skipped" and status == "passed":
                status = "skipped"
        out[test_id] = status
    return out


def write_baseline(ids: Set[str], path: Optional[Path] = None) -> dict:
    target = Path(path) if path else BASELINE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": 1, "count": len(ids), "tests": sorted(ids)}
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"written": str(target), "count": len(ids)}


def compare(current: Dict[str, str], baseline: Set[str]) -> dict:
    present = set(current)
    removed = sorted(baseline - present)
    added = sorted(present - baseline)
    failed = sorted(k for k, v in current.items() if v in ("failed", "error"))
    skipped = sorted(k for k, v in current.items() if v == "skipped")
    return {
        "baseline": len(baseline),
        "current": len(present),
        "added": added,
        "removed": removed,
        "failed": failed,
        "skipped": skipped,
        "ok": not removed and not failed,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Name-based regression guard.")
    parser.add_argument("--write", action="store_true", help="freeze the current id set")
    parser.add_argument("--collect", action="store_true",
                        help="read ids from stdin (pytest --collect-only -q output)")
    parser.add_argument("--junit", default="", help="junit xml from a run to check")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if ns.write:
        if not ns.collect:
            print("refusing: --write needs --collect (pipe pytest --collect-only -q)",
                  file=sys.stderr)
            return 2
        ids = _ids_from_collect(sys.stdin.read())
        if not ids:
            print("refusing: no test ids parsed from the collect output", file=sys.stderr)
            return 2
        result = write_baseline(ids)
        print(json.dumps(result, indent=2))
        return 0

    if not ns.junit:
        print("usage: --junit <xml> or --write --collect", file=sys.stderr)
        return 2
    junit = Path(ns.junit)
    if not junit.is_file():
        print(f"junit not found: {junit}", file=sys.stderr)
        return 2
    if not BASELINE.is_file():
        print(f"baseline not found: {BASELINE} (run --write --collect first)",
              file=sys.stderr)
        return 2

    baseline = set(json.loads(BASELINE.read_text(encoding="utf-8"))["tests"])
    current = _from_junit(junit)
    # A partial run is not a regression. Refusing avoids the worst false alarm
    # available to this tool: "6039 tests removed" because someone ran one file.
    if baseline and len(current) < max(20, int(len(baseline) * 0.5)):
        print(f"refusing: this junit covers {len(current)} of {len(baseline)} baseline "
              f"tests - that is a subset run, not a regression check", file=sys.stderr)
        return 2
    result = compare(current, baseline)
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['current']} tests, baseline {result['baseline']}: "
              f"+{len(result['added'])} new, -{len(result['removed'])} removed, "
              f"{len(result['failed'])} failing")
        for name in result["removed"][:10]:
            print(f"  REMOVED  {name}")
        for name in result["failed"][:10]:
            print(f"  FAILED   {name}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
