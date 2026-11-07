"""Baseline: prove every gate FAILS on the committed tree before any candidate.

    python state/evidence/spike/baseline.py

If a gate passes at baseline it measures nothing and the case is void, so this is
run once, first, and written to state/evidence/spike/baseline.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
HARNESS = SPIKE / "harness"
WORKTREE = Path(os.environ.get("TEMP", ".")) / "ns-spike-wt"
GATES = {"S1": (["python", ".spike_acceptance/s1_accept.py"], 600),
         "S2": (["python", ".spike_acceptance/s2_accept.py"], 300),
         "S3": (["node", ".spike_acceptance/s3_accept.mjs"], 120),
         "S4": (["python", ".spike_acceptance/s4_accept.py"], 300),
         "S5": (["python", ".spike_acceptance/s5_accept.py"], 300)}
TESTS = {
    "S1": ["python", "-m", "pytest", "Northstar_backend/foundation/tests/"
           "test_jobs_durable_lifecycle.py", "-x", "-q"],
    "S2": ["python", "-m", "pytest", "Northstar_backend/test_picture_scorecard.py",
           "-x", "-q"],
    "S3": ["node", "northstar-os-ui/scripts/check-contrast.mjs"],
    "S4": ["python", "-m", "pytest", "Northstar_backend/test_aplus_render.py", "-x", "-q"],
    "S5": ["python", "-m", "pytest", "Northstar_backend/test_render_text_guard.py",
           "-x", "-q"],
}


def main() -> int:
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=str(WORKTREE),
                   capture_output=True)
    subprocess.run(["git", "clean", "-fd"], cwd=str(WORKTREE), capture_output=True)
    dest = WORKTREE / ".spike_acceptance"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in ("s1_accept.py", "s2_accept.py", "s3_accept.mjs",
                 "s4_accept.py", "s5_accept.py"):
        shutil.copy2(HARNESS / name, dest / name)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORKTREE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    out = {"root": str(WORKTREE), "gates": {}}
    for case, (argv, timeout) in GATES.items():
        gate = subprocess.run(argv, cwd=str(WORKTREE), capture_output=True,
                              text=True, timeout=timeout, env=env)
        test = subprocess.run(TESTS[case], cwd=str(WORKTREE), capture_output=True,
                              text=True, timeout=900, env=env)
        out["gates"][case] = {
            "gate_exit": gate.returncode,
            "gate_fails_at_baseline": gate.returncode != 0,
            "gate_stdout": gate.stdout[-2500:],
            "targeted_test_exit": test.returncode,
            "targeted_test_tail": (test.stdout or "")[-300:],
        }
        print(f"{case}: gate exit {gate.returncode}, test exit {test.returncode}",
              flush=True)
    (SPIKE / "baseline.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v["gate_fails_at_baseline"] for k, v in out["gates"].items()},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
