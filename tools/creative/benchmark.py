"""Benchmark shared creative lanes through the live backend API.

Runs a 1-variant job on a named lane/mode, measures wall-clock time and peak
dedicated VRAM (nvidia-smi), and writes a JSON artifact. Cold vs warm runs are
recorded by the caller running twice.

Usage:
    python tools/creative/benchmark.py --task generate --mode standard --lane sdxl-standard \
        --prompt "studio product photograph..." --label sdxl_standard --cold
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports" / "creative_benchmarks"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read())


def vram_mb() -> float:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, check=True)
        return float(out.stdout.strip().splitlines()[0])
    except Exception:
        return -1.0


def gpu_stats() -> dict:
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,temperature.gpu,clocks.sm,power.draw,clocks_throttle_reasons.active",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True)
        p = [x.strip() for x in out.stdout.strip().split(",")]
        return {"util_pct": float(p[0]), "vram_used_mb": float(p[1]), "temp_c": float(p[2]),
                "sm_clock_mhz": float(p[3]), "power_w": float(p[4]), "throttle": p[5]}
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="generate")
    ap.add_argument("--mode", default="standard")
    ap.add_argument("--lane", default=None)
    ap.add_argument("--prompt", default="studio product photograph of a glass jar on a neutral "
                                        "background, soft light, photorealistic")
    ap.add_argument("--source", default=None)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--label", default="run")
    ap.add_argument("--cold", action="store_true")
    args = ap.parse_args()

    payload = {"prompt": args.prompt, "mode": args.mode, "width": args.width,
               "height": args.height, "seed": args.seed}
    if args.lane:
        payload["lane"] = args.lane
    if args.source:
        payload["source"] = args.source

    pre = gpu_stats() if args.cold else None
    t0 = time.time()
    r = _post("/api/creative/pipeline", {"task": args.task, "payload": payload})
    jid = r["job_id"]
    peak = 0.0
    while True:
        time.sleep(1.5)
        j = _get(f"/api/creative/jobs/{jid}")
        peak = max(peak, vram_mb())
        if j["status"] in ("done", "error", "cancelled"):
            break
    total = round(time.time() - t0, 2)
    lane = (j.get("result") or {}).get("lane") or (j.get("plan") or {}).get("primary", {}).get("lane")
    rec = {
        "label": args.label, "task": args.task, "mode": args.mode, "requested_lane": args.lane,
        "lane": lane, "status": j["status"], "total_s": total,
        "peak_vram_mb": peak, "cold": bool(args.cold), "pre_gpu": pre,
        "dimensions": [args.width, args.height],
        "output": j.get("output"), "provenance": j.get("provenance"),
        "error": j.get("error"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    p = OUT / f"{args.label}_{int(time.time())}.json"
    p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec, indent=2))
    return 0 if j["status"] == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
