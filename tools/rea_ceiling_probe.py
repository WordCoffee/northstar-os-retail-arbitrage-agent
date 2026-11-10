"""
ITEM 0.2 — time one render at each long-edge ceiling (1216 vs 2048).

Runs a SINGLE draft render through the real studio_generation path against the
local ComfyUI, while sampling host RAM and GPU memory every 0.5 s.

Sampling is coarse: the numbers are reported as a SNAPSHOT OF PEAKS at 0.5 s
resolution, not a true instantaneous peak.

One ceiling per process, so a crash at 2048 cannot destroy the 1216 measurement.

Run:
  python tools/rea_ceiling_probe.py --ceiling 1216
  python tools/rea_ceiling_probe.py --ceiling 2048
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "rea_probe"
OUT.mkdir(parents=True, exist_ok=True)


def gpu_used_mb() -> int | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip().splitlines()[0]) if r.returncode == 0 else None
    except Exception:
        return None


def comfy_alive() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ceiling", type=int, required=True)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1536)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    os.environ["MEDIA_GEN_LIVE"] = "1"
    os.environ["STUDIO_MAX_EDGE_PX"] = str(args.ceiling)
    sys.path.insert(0, str(ROOT / "Northstar_backend"))

    import psutil  # type: ignore
    import studio_generation as sg  # noqa: E402

    samples: list[dict] = []
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            vm = psutil.virtual_memory()
            samples.append({
                "t": round(time.perf_counter(), 3),
                "ram_used_mb": round((vm.total - vm.available) / 1e6, 1),
                "ram_avail_mb": round(vm.available / 1e6, 1),
                "vram_used_mb": gpu_used_mb(),
            })
            stop.wait(0.5)

    comfy_before = comfy_alive()
    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    t0 = time.perf_counter()
    result: dict = {}
    error = None
    try:
        out = sg.generate_image(
            "a plain kraft stand-up pouch on a neutral studio sweep, no text",
            width=args.width, height=args.height, tier="draft", seed=4242)
        result = {k: out.get(k) for k in
                  ("width", "height", "fitted", "requested", "engine_max_edge_px",
                   "exact_size_pass", "duration_seconds", "filename")}
        result["asset_bytes"] = len(out.get("data") or b"") if isinstance(out.get("data"), (bytes, bytearray)) else None
    except Exception as exc:  # noqa: BLE001 - the failure mode is the finding
        error = f"{type(exc).__name__}: {exc}"
        result["traceback_tail"] = traceback.format_exc().strip().splitlines()[-3:]
    finally:
        elapsed = round(time.perf_counter() - t0, 1)
        stop.set()
        th.join(timeout=2)

    vrams = [s["vram_used_mb"] for s in samples if s["vram_used_mb"] is not None]
    rams = [s["ram_used_mb"] for s in samples]
    payload = {
        "probe": "rea_ceiling_probe",
        "date": "2026-10-28",
        "ceiling_requested": args.ceiling,
        "max_edge_px_seen_by_code": getattr(sg, "MAX_EDGE_PX", None),
        "request": {"width": args.width, "height": args.height, "tier": "draft", "seed": 4242},
        "elapsed_s": elapsed,
        "result": result,
        "error": error,
        "comfyui_alive_before": comfy_before,
        "comfyui_alive_after": comfy_alive(),
        "samples": len(samples),
        "sampling_interval_s": 0.5,
        "peak_ram_used_mb": max(rams) if rams else None,
        "peak_vram_used_mb": max(vrams) if vrams else None,
        "baseline_vram_mb": vrams[0] if vrams else None,
        "peak_is": "sampled peak at 0.5 s resolution (coarse), not an instantaneous peak",
    }
    path = OUT / f"ceiling_{args.ceiling}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
