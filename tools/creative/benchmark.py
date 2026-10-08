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


def _precision(filename: str) -> str:
    f = (filename or "").lower()
    if "nvfp4" in f:
        return "nvfp4"
    if "fp8" in f:
        return "fp8"
    if "fp16" in f:
        return "fp16"
    if "bf16" in f:
        return "bf16"
    if "q4_k_m" in f:
        return "gguf-q4_k_m"
    if f.endswith(".gguf"):
        return "gguf"
    return "unspecified"


def _decode_check(path):
    if not path:
        return {"ok": False, "reason": "no output"}
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return {"ok": True, "size": list(im.size), "mode": im.mode}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="generate")
    ap.add_argument("--mode", default="standard")
    ap.add_argument("--lane", default=None)
    ap.add_argument("--prompt", default="studio product photograph of a glass jar on a neutral "
                                        "background, soft light, photorealistic")
    ap.add_argument("--source", default=None)
    ap.add_argument("--mask", default=None)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--label", default="run")
    ap.add_argument("--cold", action="store_true")
    ap.add_argument("--payload-json", default=None,
                    help="extra JSON payload merged in (for full jobs: product_ad, packaging_concept, ad_layout, inpaint)")
    args = ap.parse_args()

    payload = {"prompt": args.prompt, "mode": args.mode, "width": args.width,
               "height": args.height, "seed": args.seed}
    if args.lane:
        payload["lane"] = args.lane
    if args.source:
        payload["source"] = args.source
    if args.mask:
        payload["mask"] = args.mask
    if args.payload_json:
        raw = args.payload_json
        if raw.startswith("@"):
            raw = Path(raw[1:]).read_text(encoding="utf-8-sig")
        payload.update(json.loads(raw))

    pre = gpu_stats() if args.cold else None
    t0 = time.time()
    r = _post("/api/creative/pipeline", {"task": args.task, "payload": payload})
    jid = r["job_id"]
    peak = 0.0
    retries = 0
    while True:
        time.sleep(1.5)
        try:
            j = _get(f"/api/creative/jobs/{jid}")
        except Exception:
            retries += 1
            continue
        peak = max(peak, vram_mb())
        if j["status"] in ("done", "error", "cancelled"):
            break
    total = round(time.time() - t0, 2)

    plan = j.get("plan") or {}
    primary = plan.get("primary") or {}
    result = j.get("result") or {}
    lane = result.get("lane") or primary.get("lane")
    model_file = result.get("model_file") or primary.get("model_file") or (result.get("component") or "")
    decode = _decode_check(j.get("output") or result.get("mask") or result.get("composited"))

    # provenance stages (finishing/helpers actually executed)
    stages = []
    prov = j.get("provenance")
    if prov and Path(prov).exists():
        try:
            rec = json.loads(Path(prov).read_text(encoding="utf-8"))
            stages = [s.get("stage") for s in rec.get("stages", []) if isinstance(s, dict)]
        except Exception:
            pass

    source = args.source or payload.get("source")
    if args.task in ("generate", "packaging_concept"):
        input_source = "reused" if source else "freshly-generated"
    else:
        input_source = "reused" if source else "none"
    cached_nodes = result.get("cached_nodes") or j.get("cached_nodes") or []
    rec = {
        "label": args.label, "task": args.task, "mode": args.mode, "requested_lane": args.lane,
        "lane": lane, "component": result.get("component") or primary.get("component"),
        "family": primary.get("family"),
        "model_file": model_file, "precision": _precision(str(model_file)),
        "workflow": primary.get("workflow") or result.get("workflow"),
        "sampling": primary.get("preset") or result.get("preset"),
        "dimensions": [args.width, args.height],
        "input_source": input_source,
        "full_job_stages": stages or ([result.get("lane")] if result.get("lane") else []),
        "comfy_prompt_id": result.get("prompt_id"),
        "comfy_execution_s": result.get("execution_s"),
        "comfy_cached_nodes": cached_nodes,
        "cache_hits": len(cached_nodes),
        "model_load_included": result.get("model_load_included"),
        "stage_times": j.get("stage_times"),
        "interval_s": j.get("interval_s"),
        "status": j["status"], "total_s": total,
        "max_observed_device_vram_mb": peak, "cold": bool(args.cold), "pre_gpu": pre,
        "retries": retries,
        "output": j.get("output"), "output_check": decode,
        "rejected": not decode.get("ok"),
        "provenance": j.get("provenance"), "error": j.get("error"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metric_note": ("max_observed_device_vram_mb is the maximum nvidia-smi "
                        "memory.used seen across samples at a ~1.5 s interval — "
                        "device-wide (all processes), NOT continuous peak, NOT "
                        "per-process allocated/reserved."),
    }
    p = OUT / f"{args.label}_{int(time.time())}.json"
    p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec, indent=2))
    return 0 if j["status"] == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
