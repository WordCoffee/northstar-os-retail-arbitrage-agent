"""A/B evidence: compositor realism passes on the REAL dev plate.

Renders the same mockup twice on `data/studio_generated/44318b...png`:
  A) shading=0.0  — flat paste (the pre-realism read)
  B) shading=0.5  — surface-realism passes at the research-recommended dial

and writes side-by-side + crop artifacts plus a JSON sidecar of the realism
parameters and per-face metrics, for the operator to judge at 100%.

Outputs (renders/):
  ab_realism_flat.png / ab_realism_real.png
  ab_realism_side_by_side.png
  ab_realism_crop.png
  ab_realism.json

Usage: python scripts/compositor_realism_ab.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
sys.path.insert(0, str(BACKEND))

import mockup_compositor as mc  # noqa: E402
import compositor_realism as cr  # noqa: E402

PLATE = BACKEND / "data" / "studio_generated" / "44318b36606f4c859487c250d5a0a671.png"
LOGO = BACKEND / "assets" / "brand" / "mogra_logo.png"
OUT = ROOT / "renders"


def main() -> int:
    if not PLATE.is_file():
        print(json.dumps({"ok": False, "error": f"plate missing: {PLATE}"}))
        return 1
    if not LOGO.is_file():
        print(json.dumps({"ok": False, "error": f"logo missing: {LOGO}"}))
        return 1

    preset = mc.get_preset("mogra-forest-dusk") or {}
    base_kw = dict(
        template_id="mogra-forest-dusk", plate_path=PLATE, logo_path=LOGO,
        skus=preset.get("skus"), quads=preset.get("quads"),
        erases=preset.get("erases"), glyph_box=preset.get("glyph_box"),
    )

    OUT.mkdir(exist_ok=True)
    t0 = time.time()

    flat_path = OUT / "ab_realism_flat.png"
    real_path = OUT / "ab_realism_real.png"

    res_flat = mc.compose_mockup(out_path=flat_path, shading=0.0, **base_kw)
    res_real = mc.compose_mockup(out_path=real_path, shading=0.5, **base_kw)

    a = Image.open(flat_path).convert("RGB")
    b = Image.open(real_path).convert("RGB")

    # side-by-side (downscaled 50% for a quick read)
    w, h = a.size
    sbs = Image.new("RGB", (w, h * 2 + 8), (18, 18, 18))
    sbs.paste(a, (0, 0))
    sbs.paste(b, (0, h + 8))
    sbs = sbs.resize((w // 2, (h * 2 + 8) // 2), Image.LANCZOS)
    sbs.save(OUT / "ab_realism_side_by_side.png")

    # 100% crop of the left pouch face (quad 1 interior), flat over real
    q = (preset.get("quads") or [[[124, 455], [558, 452], [568, 1002], [112, 1006]]])[0]
    x0 = int(min(p[0] for p in q)) + 7
    x1 = int(max(p[0] for p in q)) - 7
    y0 = int(min(p[1] for p in q)) + 7
    y1 = int(min(max(p[1] for p in q) - 7, y0 + 420))
    ca = a.crop((x0, y0, x1, y1))
    cb = b.crop((x0, y0, x1, y1))
    strip = Image.new("RGB", (ca.width * 2 + 6, ca.height), (18, 18, 18))
    strip.paste(ca, (0, 0))
    strip.paste(cb, (ca.width + 6, 0))
    d = ImageDraw.Draw(strip)
    d.text((6, 6), "FLAT (shading=0.0)", fill=(255, 220, 120))
    d.text((ca.width + 12, 6), "REALISM (shading=0.5)", fill=(120, 255, 180))
    strip.save(OUT / "ab_realism_crop.png")

    diff = np.abs(np.asarray(a, dtype=int) - np.asarray(b, dtype=int))
    sidecar = {
        "ok": True,
        "plate": PLATE.name,
        "logo": str(LOGO.relative_to(ROOT)).replace("\\", "/"),
        "flat": {"file": flat_path.name, "shading": 0.0,
                 "face_metrics": res_flat.get("face_metrics")},
        "realism": {"file": real_path.name, "shading": 0.5,
                    "params": res_real.get("realism"),
                    "face_metrics": res_real.get("face_metrics")},
        "delta": {"mean_abs": round(float(diff.mean()), 3),
                  "p99_abs": int(np.percentile(diff, 99)),
                  "changed_gt8_pct": round(float((diff.max(axis=2) > 8).mean() * 100), 2)},
        "seconds": round(time.time() - t0, 1),
        "how_to_judge": "Open ab_realism_crop.png at 100%: the right half must show "
                        "the print following the pouch folds and taking its shading; "
                        "no text wobble; cream ink keeps its read.",
    }
    (OUT / "ab_realism.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "sidecar": str(OUT / "ab_realism.json"),
                      "delta": sidecar["delta"], "seconds": sidecar["seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
