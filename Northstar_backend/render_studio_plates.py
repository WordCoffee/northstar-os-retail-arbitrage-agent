"""Render compositing-ready studio plates: white package on a flat light-grey sweep.

v2 plates fix the root cause of the 'sticker' look: the old plates were kraft
packages on warm beige backgrounds, so any print patch had hard edges with an
abrupt colour break. These plates are matte-white packages on a flat, uniform
light-grey backdrop -> clean silhouette segmentation, and the print can bake the
photo's own lighting (a white base multiplies to true print colours).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("MEDIA_GEN_LIVE", "1")
os.environ.setdefault("COMFYUI_URL", "http://127.0.0.1:8199")
os.environ.setdefault("STUDIO_IMAGE_MODEL", "flux-2-klein-4b-Q8_0.gguf")
os.environ.setdefault("STUDIO_TEXT_ENCODER", "qwen_3_4b_fp8_mixed.safetensors")

import studio_generation as sg  # noqa: E402

OUT = ROOT / "data" / "studio_generated"

STUDIO = ("perfectly centered straight-on view, even soft studio lighting from the "
          "upper left, soft subtle contact shadow, seamless flat light grey studio "
          "backdrop, plain uniform background, nothing else in frame")

PLATES = [
    ("plate2_pouch_front",
     "Photorealistic e-commerce product mockup photograph of ONE plain unprinted matte white "
     "stand-up pouch (doypack) with a resealable zipper and bottom gusset, standing upright, "
     "completely blank smooth front face, no print, no text, no logo, no label, no marks, "
     + STUDIO),
    ("plate2_pouch_back",
     "Photorealistic e-commerce product mockup photograph of ONE plain unprinted matte white "
     "stand-up pouch (doypack) with a resealable zipper, standing upright, back view, "
     "completely blank smooth back face, no print, no text, no logo, no label, no marks, "
     + STUDIO),
    ("plate2_tube_front",
     "Photorealistic e-commerce product mockup photograph of ONE plain unprinted matte white "
     "paper tube canister with a flat kraft lid, standing upright, completely blank smooth "
     "wrapper, no print, no text, no logo, no label, no marks, gentle cylindrical shading, "
     + STUDIO),
    ("plate2_tube_back",
     "Photorealistic e-commerce product mockup photograph of ONE plain unprinted matte white "
     "paper tube canister with a flat kraft lid, standing upright, back view, completely blank "
     "smooth wrapper, no print, no text, no logo, no label, no marks, gentle cylindrical shading, "
     + STUDIO),
]

for name, prompt in PLATES:
    target = OUT / f"{name}.png"
    if target.is_file() and target.stat().st_size > 50_000:
        print(f"{name}: exists, skipping", flush=True)
        continue
    try:
        out = sg.generate_image(prompt=prompt, width=1024, height=1024, tier="final")
        target.write_bytes(out["bytes"])
        print(f"{name}: OK {out['model']} {len(out['bytes'])} bytes", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{name}: FAILED {str(exc)[:300]}", flush=True)

print("done", flush=True)
