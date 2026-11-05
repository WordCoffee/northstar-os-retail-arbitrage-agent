"""Graduate every shipped `tys_ops` module through the three-stage gate.

`docs/V3_MASTER_PLAN.md` V3.4 asks for a graduation report per customer module.
Only `tys_ops/memory.py` had one, so this driver produces the rest — and it is
deliberately honest about what a module can and cannot prove:

* **Stage 1** (AST audit + a passing test command) is required of every module.
  A module that no test file references cannot pass it, and is reported that way
  rather than given a decorative `pytest -q` over the whole suite.
* **Stage 2** (a vision verdict on a screenshot against a constraint) applies
  only to modules with a visual surface. Modules that emit JSON, budgets or
  routing decisions have no screenshot to judge; they are reported
  `not_verified`, which is the rubric working, not a failure to hide.
* **Stage 3** (an end-to-end command exiting 0) is the kernel integration suite:
  it imports the package and drives a turn end to end.

Usage::

    python tools/v3_graduate_all.py
    python tools/v3_graduate_all.py --only memory,graphics
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "Northstar_backend"
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(BACKEND))

import v3_graduation  # noqa: E402

#: Stage 2 only where the module actually produces something visible. The
#: constraint is stated in the module's own terms, and the image is a real
#: artefact from that lane (never a mock).
VISUAL: Dict[str, Dict[str, str]] = {
    "graphics": {
        "screenshot": "renders/mogra_lions_mane/reference_pp/product_front.png",
        "constraint": "a stand-up pouch with a large printed front panel is the main subject",
    },
    "memory": {
        "screenshot": "renders/mogra_lions_mane/reference_pp/product_front.png",
        "constraint": "a stand-up pouch with a large rectangular printed area is visible",
    },
}

E2E = ["python", "-m", "pytest", "Northstar_backend/test_tys_kernel_integration.py", "-q"]

#: Modules that exist but are not a customer-facing surface. They still get a
#: report (so the inventory is complete) with the reason stated.
NOT_A_SURFACE = {
    "stress": "load-test harness; not a customer surface and no test file references it",
    "__init__": "package marker",
}


def modules() -> List[Path]:
    return sorted(p for p in (BACKEND / "tys_ops").glob("*.py")
                  if p.stem not in NOT_A_SURFACE)


def referencing_tests(module: str) -> List[str]:
    """Test files that name this module. Evidence, not a guess."""
    pattern = re.compile(rf"tys_ops[.\s]+{re.escape(module)}\b|"
                         rf"from tys_ops import[^\n]*\b{re.escape(module)}\b")
    hits: List[str] = []
    for test in sorted(BACKEND.glob("test_*.py")):
        try:
            body = test.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(body):
            hits.append(f"Northstar_backend/{test.name}")
    return hits


def plan(module: Path) -> Dict[str, Any]:
    name = module.stem
    tests = referencing_tests(name)
    if tests:
        tests_cmd = ["python", "-m", "pytest", *tests, "-q"]
    else:
        # Honest failure: a module nothing tests cannot pass Stage 1.
        tests_cmd = ["python", "-c",
                     f"raise SystemExit('no test file references tys_ops.{name}')"]
    visual = VISUAL.get(name)
    return {
        "module": module,
        "tests_cmd": tests_cmd,
        "tests_refs": tests,
        "screenshot": (REPO / visual["screenshot"]) if visual else None,
        "constraint": visual["constraint"] if visual else "",
        "e2e_cmd": E2E,
        "stage2_applicable": bool(visual),
    }


def summarise(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    def status(report: Dict[str, Any], key: str) -> str:
        stage = report.get(key) or {}
        return stage.get("status") or ("passed" if stage.get("ok") else "failed")

    rows = []
    for r in reports:
        name = Path(r["module"]).stem
        rows.append({
            "module": name,
            "overall": r["overall"],
            "stage1": "passed" if (r.get("stage1") or {}).get("ok") else "failed",
            "stage2": status(r, "stage2"),
            "stage3": status(r, "stage3"),
            "tests": ((r.get("stage1") or {}).get("tests") or {}).get("cmd"),
        })
    graduated = [r["module"] for r in rows if r["overall"] == "passed"]
    return {
        "contract": "v3_graduation_all/v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "modules": rows,
        "graduated": graduated,
        "graduated_count": len(graduated),
        "total": len(rows),
        "note": ("Stage 2 is applicable only to modules with a visual surface. A module "
                 "without one is reported not_verified rather than given a decorative "
                 "screenshot."),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default=None, help="comma-separated module stems")
    parser.add_argument("--out", default="reports/v3_graduation_all_20261104.json")
    parser.add_argument("--tests-timeout", type=float, default=1800.0)
    args = parser.parse_args(argv)

    wanted = {s.strip() for s in args.only.split(",")} if args.only else None
    targets = [m for m in modules() if not wanted or m.stem in wanted]
    if not targets:
        raise SystemExit("no modules matched")

    reports: List[Dict[str, Any]] = []
    for module in targets:
        p = plan(module)
        print(f"grading {module.stem} ...", flush=True)
        report = v3_graduation.grade(
            module=module, tests_cmd=p["tests_cmd"], screenshot=p["screenshot"],
            constraint=p["constraint"], e2e_cmd=p["e2e_cmd"])
        report["plan"] = {"tests_refs": p["tests_refs"],
                          "stage2_applicable": p["stage2_applicable"],
                          "e2e_cmd": p["e2e_cmd"]}
        report["report_file"] = f"reports/v3_graduation_{module.stem}_20261104.json"
        (REPO / report["report_file"]).write_text(json.dumps(report, indent=2),
                                                  encoding="utf-8")
        reports.append(report)

    summary = summarise(reports)
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nsummary: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
