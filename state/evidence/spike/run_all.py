"""Run every spike candidate in order and write the matrix.

    python state/evidence/spike/run_all.py [S1 S2 ...]

Sequential on purpose: this box is RAM-bound (one local model at a time), and the
plan's whole point is comparable, not parallel, measurements.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
ROOT = SPIKE.parents[2]
CASES = ("S1", "S2", "S3", "S4", "S5")
CANDIDATES = (1, 2, 3)


def main() -> int:
    wanted = [a.upper() for a in sys.argv[1:]] or list(CASES)
    rows = []
    started = time.time()
    for case in wanted:
        for cand in CANDIDATES:
            print(f"== {case} cand{cand} {time.strftime('%H:%M:%S')}", flush=True)
            subprocess.run([sys.executable, str(SPIKE / "run_case.py"),
                            "--case", case, "--candidate", str(cand)],
                           cwd=str(ROOT), timeout=1800)
            verdict_path = next((SPIKE).glob(
                f"*/cand{cand}/verdict.json"))
            rows.append({"case": case, "candidate": cand,
                         "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    (SPIKE / "run_all_last.json").write_text(
        json.dumps({"cases": wanted, "rows": rows,
                    "elapsed_s": round(time.time() - started, 1)}, indent=2),
        encoding="utf-8")
    print(f"done in {round(time.time() - started, 1)}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
