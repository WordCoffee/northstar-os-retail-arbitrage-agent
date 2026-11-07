"""S1 gate: 20 consecutive runs of the cancel test under CPU load.

Run from the worktree root:
    python .spike_acceptance/s1_accept.py

A race cannot be proven absent by one run. The plan's target check is "that test,
20 consecutive runs under load"; this is exactly that, with the load fixed at 20
spin processes so the check is reproducible rather than dependent on whatever else
the box is doing.

Exit 0 only if all 20 runs pass.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TEST = ("Northstar_backend/foundation/tests/"
        "test_jobs_durable_lifecycle.py")
KEYWORD = "test_cancel_leased_job_cooperative"
RUNS = 20
LOAD = 20
SPIN = "import itertools\nc = 0\nfor x in itertools.count():\n    c = (c + x) % 1000003\n"


def main() -> int:
    root = Path.cwd()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    args = [sys.executable, "-m", "pytest", TEST, "-x", "-q",
            "-p", "no:cacheprovider", "-k", KEYWORD]

    spin_path = Path(os.environ.get("TEMP", ".")) / "s1_spin.py"
    spin_path.write_text(SPIN, encoding="utf-8")
    spinners = [subprocess.Popen([sys.executable, str(spin_path)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL) for _ in range(LOAD)]
    runs = []
    started = time.time()
    try:
        for i in range(1, RUNS + 1):
            proc = subprocess.run(args, cwd=str(root), capture_output=True,
                                  text=True, timeout=300, env=env)
            text = (proc.stdout or "") + (proc.stderr or "")
            runs.append({
                "run": i, "exit": proc.returncode,
                "illegal": re.findall(r"illegal transition[^\n]{0,100}", text)[:2],
                "tail": [ln.strip() for ln in text.splitlines()
                         if "Error" in ln or "FAILED" in ln or "passed" in ln][-2:],
            })
    finally:
        for p in spinners:
            try:
                p.kill()
            except Exception:  # noqa: BLE001 - teardown never fails the gate
                pass

    failed = [r for r in runs if r["exit"] != 0]
    payload = {"gate": "S1", "runs": RUNS, "load": LOAD,
               "total_seconds": round(time.time() - started, 1),
               "passed": RUNS - len(failed), "failed": len(failed),
               "ok": not failed, "failures": failed[:3]}
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
