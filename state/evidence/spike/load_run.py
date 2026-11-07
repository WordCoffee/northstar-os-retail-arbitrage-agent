"""Acceptance harness for S1: N consecutive runs of one test under CPU load.

The plan's target check for S1 is "that test, 20 consecutive runs under load".
A single green run proves nothing about a race, so this harness:

  * starts `--load` spin processes (busy Python loops) on the same box,
  * runs the named test `--runs` times, each in its own pytest process,
  * records every exit code, the failing runs' short error lines, and the
    observed illegal transitions,
  * always kills the spinners, even when a run raises.

Exit code 0 only when every run passed. Print JSON so the evidence file is the
literal output of this command.

Usage:
  python state/evidence/spike/load_run.py --root <workspace> --runs 20 --load 20 \
      --test Northstar_backend/foundation/tests/test_jobs_durable_lifecycle.py \
      -k test_cancel_leased_job_cooperative
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SPIN = "import itertools\nc = 0\nfor x in itertools.count():\n    c = (c + x) % 1000003\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--load", type=int, default=20)
    ap.add_argument("-k", dest="keyword", default="")
    ap.add_argument("--marker", default="")
    ap.add_argument("--env", action="append", default=[],
                    help="NAME=VALUE passed to each pytest process")
    ns = ap.parse_args()

    root = Path(ns.root).resolve()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    for pair in ns.env:
        k, _, v = pair.partition("=")
        env[k] = v

    args = [sys.executable, "-m", "pytest", ns.test, "-x", "-q", "-p", "no:cacheprovider"]
    if ns.keyword:
        args += ["-k", ns.keyword]
    if ns.marker:
        args += ["-m", ns.marker]

    spin_file = Path(os.environ.get("TEMP", ".")) / "spike_spin.py"
    spin_file.write_text(SPIN, encoding="utf-8")
    spinners = []
    for _ in range(max(0, ns.load)):
        spinners.append(subprocess.Popen(
            [sys.executable, str(spin_file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    runs = []
    started = time.time()
    try:
        for i in range(1, ns.runs + 1):
            t0 = time.time()
            proc = subprocess.run(args, cwd=str(root), capture_output=True, text=True,
                                  timeout=300, env=env)
            text = (proc.stdout or "") + (proc.stderr or "")
            illegal = re.findall(r"illegal transition[^\n]{0,120}", text)
            tail = [ln for ln in text.splitlines()
                    if ln.strip() and ("FAILED" in ln or "assert" in ln
                                       or "Error" in ln or "passed" in ln
                                       or "failed" in ln)][-3:]
            runs.append({"run": i, "exit": proc.returncode,
                         "seconds": round(time.time() - t0, 2),
                         "illegal_transitions": illegal[:3], "tail": tail})
    finally:
        for p in spinners:
            try:
                p.kill()
            except Exception:  # noqa: BLE001 - teardown never fails the check
                pass

    failed = [r for r in runs if r["exit"] != 0]
    payload = {
        "check": "S1-race-under-load",
        "root": str(root),
        "test": ns.test, "keyword": ns.keyword, "runs": ns.runs, "load": ns.load,
        "total_seconds": round(time.time() - started, 1),
        "passed": len(runs) - len(failed),
        "failed": len(failed),
        "ok": not failed,
        "failures": failed[:5],
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
