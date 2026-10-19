"""Smoke: BiRefNet cutout -> Amazon MAIN framing -> compliance check.

The listing-image lane end to end, on a real render:
  1. cut the product out (BiRefNet, local ComfyUI)
  2. trim + centre on white so it fills the frame
  3. measure the result against the mechanical MAIN rules

Usage: python scripts/smoke_cutout_main.py [--input <png>] [--size 2000]
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
os.environ["MEDIA_GEN_LIVE"] = "1"  # local GPU, no spend, operator-requested

import image_prep as ip  # noqa: E402
import studio_generation as sg  # noqa: E402

DEFAULT_INPUT = ROOT / "renders" / "ab_realism_real.png"
OUT_CUTOUT = ROOT / "renders" / "smoke_cutout_alpha.png"
OUT_FRAMED = ROOT / "renders" / "smoke_main_2000.png"
OUT_JSON = ROOT / "renders" / "smoke_cutout_main.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--size", type=int, default=2000)
    ap.add_argument("--fill", type=float, default=0.88)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(json.dumps({"ok": False, "error": f"input missing: {src}"}))
        return 1

    t0 = time.time()
    try:
        cut = sg.generate_cutout(src.read_bytes())
    except Exception as exc:  # noqa: BLE001
        sidecar = {"ok": False, "stage": "cutout", "error": str(exc)[:600],
                   "input": str(src), "seconds": round(time.time() - t0, 1)}
        OUT_JSON.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        print(json.dumps({"ok": False, "error": str(exc)[:300]}))
        return 2

    OUT_CUTOUT.write_bytes(cut["bytes"])

    framed = ip.frame_on_white_bytes(cut["bytes"], fill=args.fill, size=args.size)
    OUT_FRAMED.write_bytes(framed["bytes"])
    check = ip.check_main_compliance(framed["bytes"], min_fill=0.85, min_side=2000)

    sidecar = {
        "ok": True, "input": str(src.relative_to(ROOT)).replace("\\", "/"),
        "cutout": {"file": OUT_CUTOUT.name, "model": cut["model"],
                   "bytes": len(cut["bytes"])},
        "framed": {k: v for k, v in framed.items() if k != "bytes"},
        "framed_file": OUT_FRAMED.name,
        "compliance": check,
        "seconds": round(time.time() - t0, 1),
        "how_to_judge": ("Open smoke_cutout_alpha.png on a dark background: edges must "
                         "be clean, no halo. smoke_main_2000.png is what a listing slot "
                         "gets; compliance.blockers says whether it would pass."),
    }
    OUT_JSON.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "cutout_bytes": len(cut["bytes"]),
                      "framed": framed["size"], "verdict": check["verdict"],
                      "blockers": check["blockers"],
                      "seconds": sidecar["seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
