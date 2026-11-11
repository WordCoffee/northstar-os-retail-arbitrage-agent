"""Run one real-plate seller pass inside a ComfyUI lane (start, work, stop).

The lane owns the GPU for its lifetime: ComfyUI is started fresh with
`--cache-none`, the pass runs through the shipped CLI, and the process is stopped
in `finally`. Nothing is trusted to `/free` (this build answers 200 and releases
nothing), so the evidence that the GPU was released is that the process exited.

    python tools/comfy_plate_pass.py --limit 3 --out renders/comfy_plate1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import comfy_lane  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(ROOT / "ty" / "seller_briefs.json"))
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--mode", default="prompt_only")
    parser.add_argument("--out", default="renders/comfy_plate1")
    parser.add_argument("--summary", default="reports/ty/comfy_plate_pass.json")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if summary_path.exists():
        summary_path.unlink()

    def work() -> dict:
        command = [sys.executable, "-m", "tools.seller_tester", "product",
                   "--catalog", str(args.catalog), "--renderer", "comfy",
                   "--skip-unavailable", "--limit", str(int(args.limit)),
                   "--out-dir", args.out, "--summary-out", str(summary_path),
                   "--gaps", str(ROOT / "state" / "seller" / "comfy_gaps.json")]
        if args.mode:
            command += ["--mode", args.mode]
        if args.seed is not None:
            command += ["--seed", str(int(args.seed))]
        environment = dict(os.environ, COMFY_LANE_OWNED="1")
        done = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                              timeout=3600, env=environment)
        payload: dict = {"returncode": done.returncode}
        if summary_path.exists():
            payload["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            payload["stderr_tail"] = (done.stderr or "")[-2000:]
        payload["stdout_tail"] = (done.stdout or "")[-2000:]
        return payload

    result = comfy_lane.lane(work, role="seller-real-plate")
    print(json.dumps({k: result.get(k) for k in ("ok", "reason", "refused", "seconds")},
                     indent=1))
    payload = result.get("result") or {}
    summary = payload.get("summary") or {}
    if summary:
        head = {k: summary.get(k) for k in ("generator", "selected", "scored", "passed",
                                            "failed", "mean_score", "plate_source")}
        print(json.dumps(head, indent=1))
        for row in summary.get("results") or []:
            print(json.dumps({"brief": row.get("brief_id"),
                              "plate": ((row.get("generation") or {}).get("plate") or {}).get("source"),
                              "score": row.get("score"), "passed": row.get("passed"),
                              "failed": row.get("failed_checks")}))
    else:
        print(json.dumps(payload, indent=1)[:2000])
    return 0 if result.get("ok") and summary else 1


if __name__ == "__main__":
    raise SystemExit(main())
