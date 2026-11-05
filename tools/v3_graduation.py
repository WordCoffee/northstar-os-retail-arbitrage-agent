"""V3 graduation gate — the three stages before a module is deployable.

Stage 1  AST symbol audit (no duplicate top-level symbols, no placeholder
         markers) and a passing test command. 100% means 100%.
Stage 2  Visual verification by Ty's Vision: a screenshot/render must satisfy a
         stated design constraint. No screenshot means NOT VERIFIED, never pass.
Stage 3  An end-to-end benchmark command must exit 0. No E2E means NOT RUN.

    python tools/v3_graduation.py \
      --module Northstar_backend/tys_ops/memory.py \
      --tests "python -m pytest Northstar_backend/test_semantic_memory.py -q" \
      --screenshot renders/mogra_lions_mane/reference_pp/product_front.png \
      --constraint "a kraft pouch with a readable MOGRA wordmark and net weight" \
      --e2e "python -c \"raise SystemExit(0)\""

Exit 0 only when all three stages pass. The report is written as JSON.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import vision_verify  # noqa: E402

PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b")
DEFAULT_TESTS = ["python", "-m", "pytest", "-q"]


def audit_symbols(path: Path) -> Dict[str, Any]:
    """Top-level symbols and placeholder markers in one module."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    names = [node.name for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    placeholders = [{"line": i, "marker": m.group(0)}
                    for i, line in enumerate(text.splitlines(), 1)
                    for m in [PLACEHOLDER.search(line)] if m]
    return {"ok": not duplicates and not placeholders, "path": str(path),
            "symbols": len(names), "duplicates": duplicates,
            "placeholders": placeholders[:20]}


def run_command(cmd: Sequence[str], *, timeout: float = 1800.0) -> Dict[str, Any]:
    started = time.time()
    proc = subprocess.run(list(cmd), cwd=str(ROOT), capture_output=True,
                          text=True, timeout=timeout)
    output = ((proc.stdout or "") + (proc.stderr or ""))[-1200:]
    return {"ok": proc.returncode == 0, "exit": proc.returncode,
            "seconds": round(time.time() - started, 1),
            "cmd": list(cmd), "output": output}


def grade(*, module: Path, tests_cmd: Sequence[str], screenshot: Optional[Path] = None,
          constraint: str = "", e2e_cmd: Optional[Sequence[str]] = None,
          vision_caller=None) -> Dict[str, Any]:
    stage1_symbols = audit_symbols(module)
    stage1_tests = run_command(tests_cmd)
    stage1 = {"ok": bool(stage1_symbols["ok"] and stage1_tests["ok"]),
              "symbols": stage1_symbols, "tests": stage1_tests}

    if screenshot is None:
        stage2 = {"ok": False, "status": "not_verified",
                  "reason": "no screenshot supplied; visual verification cannot pass"}
    else:
        verdict = vision_verify.verify(screenshot.read_bytes(), constraint,
                                       caller=vision_caller)
        stage2 = {"ok": bool(verdict.get("ok")), "status": "passed" if verdict.get("ok")
                  else "failed", "verdict": verdict}

    if e2e_cmd is None:
        stage3 = {"ok": False, "status": "not_run",
                  "reason": "no end-to-end command supplied"}
    else:
        stage3 = run_command(e2e_cmd)
        stage3["status"] = "passed" if stage3["ok"] else "failed"

    overall = bool(stage1["ok"] and stage2["ok"] and stage3["ok"])
    return {"overall": "passed" if overall else "failed",
            "ok": overall, "module": str(module),
            "stage1": stage1, "stage2": stage2, "stage3": stage3,
            "graduated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--module", required=True)
    ap.add_argument("--tests", default=" ".join(DEFAULT_TESTS))
    ap.add_argument("--screenshot")
    ap.add_argument("--constraint", default="")
    ap.add_argument("--e2e")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    module = (ROOT / args.module).resolve()
    if not module.is_file():
        raise SystemExit(f"module not found: {module}")
    screenshot = (ROOT / args.screenshot).resolve() if args.screenshot else None
    report = grade(module=module,
                   tests_cmd=shlex.split(args.tests),
                   screenshot=screenshot, constraint=args.constraint,
                   e2e_cmd=shlex.split(args.e2e) if args.e2e else None)
    out = Path(args.out) if args.out else (
        ROOT / "reports" / f"v3_graduation_{module.stem}_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "stage1": report["stage1"]["ok"],
                      "stage2": report["stage2"]["status"],
                      "stage3": report["stage3"]["status"],
                      "report": str(out)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
