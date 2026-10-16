"""Smoke: FLUX.2 klein 9B through the studio's own generation path.

Uses studio_generation.generate_image (the exact studio lane) with
STUDIO_IMAGE_MODEL pointed at the newly-pulled 9B Q8 GGUF, draft tier.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

os.environ.setdefault("MEDIA_GEN_LIVE", "1")
os.environ.setdefault("COMFYUI_URL", "http://127.0.0.1:8199")
if len(sys.argv) > 1:
    os.environ["STUDIO_IMAGE_MODEL"] = sys.argv[1]
else:
    os.environ.setdefault("STUDIO_IMAGE_MODEL", "Flux-2-Klein-9B-KV-Q8_0.gguf")
_SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20261016
if "9b" in os.environ["STUDIO_IMAGE_MODEL"].lower():
    os.environ.setdefault("STUDIO_TEXT_ENCODER", "qwen_3_8b_fp8mixed.safetensors")
elif "4b" in os.environ["STUDIO_IMAGE_MODEL"].lower():
    os.environ.setdefault("STUDIO_TEXT_ENCODER", "qwen_3_4b_fp8_mixed.safetensors")


def main() -> int:
    import studio_generation as sg

    st = sg.engine_status()
    if not st.get("armed"):
        print(json.dumps({"ok": False, "error": "engine_not_armed", "engine": st}))
        return 2

    t0 = time.time()
    out = sg.generate_image(
        prompt=("premium stand-up pouch product mockup standing on a warm oak table, "
                "soft blurred greenhouse background, late afternoon light, matte finish"),
        width=1024, height=1024, tier="draft", seed=_SEED)
    png = ROOT / "renders" / "smoke_klein9b.png"
    png.write_bytes(out["bytes"])
    print(json.dumps({
        "ok": True, "file": str(png), "model_requested": os.environ["STUDIO_IMAGE_MODEL"],
        "encoder_requested": os.environ.get("STUDIO_TEXT_ENCODER"),
        "model_reported": out.get("model"), "bytes": len(out["bytes"]),
        "seconds": round(time.time() - t0, 1),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
