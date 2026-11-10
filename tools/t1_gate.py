#!/usr/bin/env python3
"""T1 test gate: snapshot -> run commands -> rollback the diff if red.

The policy in one command:

    python tools/t1_gate.py --label loop-42 \\
        --command "python -m pytest Northstar_backend/test_snapshot.py -q" \\
        --command "npm --prefix northstar-os-ui run build"

Green: nothing is touched, the snapshot stays as a restore point.
Red:   `git restore --source=<sha>` on ONLY the paths this loop changed, then a
       non-zero exit so a caller can stop. Unrelated working-tree edits survive,
       which is the whole point of a diff-scoped rollback.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import snapshot  # noqa: E402


def run_commands(commands: List[str], *, root: Path, timeout: int = 1800) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for cmd in commands:
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(root), shell=True, capture_output=True,
                              text=True, timeout=timeout, check=False)
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-6:]
        results.append({"command": cmd, "exit": proc.returncode,
                        "seconds": round(time.time() - t0, 1), "tail": tail})
        if proc.returncode != 0:
            break          # a red gate stops the loop; no point running the rest
    return results


def guarded_run(commands: List[str], *, root: Path | str = ROOT, label: str = "t1",
                paths: Optional[List[str]] = None,
                timeout: int = 1800,
                restore_point: Optional[str] = None) -> Dict[str, Any]:
    """Run the gate. `restore_point` is the sha taken BEFORE the agent edited.

    If it is omitted the snapshot is taken here, which only helps a caller that
    has not edited anything yet - the normal flow is snapshot -> edit -> gate, so
    the caller passes the sha it took.
    """
    root = Path(root).resolve()
    snap_sha = restore_point or snapshot.snapshot(root, label)["sha"]
    results = run_commands(commands, root=root, timeout=timeout)
    ok = bool(results) and all(r["exit"] == 0 for r in results)
    out: Dict[str, Any] = {"label": label, "snapshot": snap_sha, "ok": ok,
                           "results": results, "rolled_back": False}
    if not ok:
        rb = snapshot.rollback_if_red(root, snap_sha, gate_ok=False, paths=paths)
        out["rolled_back"] = bool(rb.get("rolled_back"))
        out["restored"] = rb.get("restored", [])
        out["removed"] = rb.get("removed", [])
    (root / "state" / "snapshots").mkdir(parents=True, exist_ok=True)
    (root / "state" / "snapshots" / f"{label}.gate.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default=f"t1-{int(time.time())}")
    ap.add_argument("--command", action="append", default=[])
    ap.add_argument("--path", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args(argv)
    if not args.command:
        ap.error("at least one --command is required")
    result = guarded_run(args.command, label=args.label,
                         paths=(args.path or None), timeout=args.timeout)
    print(json.dumps(result, indent=2)[:2000])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
