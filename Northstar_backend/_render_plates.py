"""Temp: render remaining base plates (skips ones already on disk)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import studio_generation as sg  # noqa: E402

OUT = ROOT / "data" / "studio_generated"

PLATES = [
    ("plate_pouch_front", (
        "Photorealistic product photography of ONE plain unprinted matte kraft stand-up pouch "
        "(doypack) with resealable zipper and bottom gusset, standing upright, empty completely "
        "blank smooth front face with no print, no marks, no label, no text, centered front view, "
        "soft studio lighting with gentle edge highlights, subtle contact shadow, standing on a "
        "light oak shelf with a softly blurred warm beige background, premium natural-foods styling")),
    ("plate_pouch_back", (
        "Photorealistic product photography, BACK view of ONE plain unprinted matte kraft stand-up "
        "pouch (doypack) with zipper, standing upright, completely blank back face with no print, "
        "no marks, no label, no text, centered rear view, soft studio lighting, subtle contact "
        "shadow, on a light oak shelf, softly blurred warm beige background")),
    ("plate_tube_front", (
        "Photorealistic product photography of ONE plain unprinted matte kraft paper tube canister "
        "with a flat kraft lid, standing upright, completely blank smooth wrapper with no print, no "
        "marks, no label, no text, centered front view, soft studio lighting with gentle cylindrical "
        "shading highlight, subtle contact shadow, on a light oak shelf with a softly blurred warm "
        "beige background, premium tea-brand styling")),
    ("plate_tube_back", (
        "Photorealistic product photography, BACK view of ONE plain unprinted matte kraft paper tube "
        "canister with flat kraft lid, standing upright, completely blank wrapper, no print, no "
        "marks, no label, no text, centered rear view, soft studio lighting, cylindrical shading, "
        "subtle contact shadow, on a light oak shelf, softly blurred warm beige background")),
]

for name, prompt in PLATES:
    target = OUT / f"{name}.png"
    if target.is_file() and target.stat().st_size > 50_000:
        print(f"{name}: exists, skipping")
        continue
    try:
        out = sg.generate_image(prompt=prompt, width=1024, height=1024, tier="final")
        target.write_bytes(out["bytes"])
        print(f"{name}: OK {out['model']} {len(out['bytes'])} bytes", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{name}: FAILED {str(exc)[:300]}", flush=True)
