"""Smoke: Qwen-Image-Edit-2511 edit lane (local ComfyUI).

Feeds a REAL composed mockup through the edit lane and asks for a scene change
that must NOT touch the product or its typography, then writes the result plus
a JSON sidecar (timings, model, seed, steps) for the operator.

Usage:
  python scripts/smoke_qwen_edit2511.py [--steps 8] [--tier fast] [--input <png>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("COMFYUI_URL", "http://127.0.0.1:8199")
os.environ["MEDIA_GEN_LIVE"] = "1"  # local GPU render: no spend, operator-requested

import studio_generation as sg  # noqa: E402

DEFAULT_INPUT = ROOT / "renders" / "ab_realism_real.png"
OUT_PNG = ROOT / "renders" / "smoke_qwen_edit_2511.png"
OUT_JSON = ROOT / "renders" / "smoke_qwen_edit_2511.json"

PROMPT = (
    "Replace the background with a warm terracotta studio backdrop and add soft "
    "natural contact shadows beneath the two stand-up pouches. Keep the pouches, "
    "their matte texture, and every printed word and icon exactly unchanged."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=0)
    ap.add_argument("--tier", default="fast", choices=["fast", "draft", "final"])
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--prompt", default=PROMPT)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(json.dumps({"ok": False, "error": f"input missing: {src}"}))
        return 1

    status = sg.engine_status()
    print(json.dumps({"engine_status": {k: v for k, v in status.items() if k != "models"},
                      "edit_model": status["models"].get("edit")}))

    t0 = time.time()
    try:
        res = sg.generate_edit(src.read_bytes(), args.prompt, tier=args.tier,
                               steps=args.steps or None)
    except Exception as exc:  # noqa: BLE001
        sidecar = {"ok": False, "error": str(exc)[:600], "input": str(src),
                   "seconds": round(time.time() - t0, 1),
                   "engine": status}
        OUT_JSON.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        print(json.dumps({"ok": False, "error": str(exc)[:400]}))
        return 2

    OUT_PNG.write_bytes(res["bytes"])
    sidecar = {
        "ok": True, "input": str(src.relative_to(ROOT)).replace("\\", "/"),
        "out": str(OUT_PNG.relative_to(ROOT)).replace("\\", "/"),
        "model": res["model"], "seed": res["seed"], "steps": res["steps"],
        "cfg": res["cfg"], "bytes": len(res["bytes"]),
        "seconds": round(time.time() - t0, 1), "prompt": args.prompt,
        "accept": "the pouches and every printed word must be unchanged; only the "
                  "background and grounding shadows should differ from the input.",
    }
    OUT_JSON.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT_PNG), "seconds": sidecar["seconds"],
                      "steps": res["steps"], "seed": res["seed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
