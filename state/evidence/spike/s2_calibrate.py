"""Calibrate S2's acceptance bar BEFORE any candidate runs.

S2's target check is fixed by the plan: with an explicit `product_box`, the
`product_fidelity` dimension must score >= 85 on
`renders/autonomy_probe/composite/lifestyle_linen_composite.png`.

That number is only a fair test if it is reachable at all. This probe computes
the two inputs the dimension uses (identity axes for the correct box crop vs the
reference subject) without implementing the API, so the spike knows whether the
bar measures the lane or an arithmetic ceiling.

Writes nothing outside state/evidence/spike/.
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "Northstar_backend"
sys.path.insert(0, str(BACKEND))

COMPOSITE = ROOT / "renders/autonomy_probe/composite/lifestyle_linen_composite.png"
CUTOUT = ROOT / "renders/autonomy_probe/composite/lifestyle_linen_cutout.png"
PHOTO = ROOT / "renders/mogra_lions_mane/product_front.png"
BOX = (279, 308, 744, 1024)


def _crop_png(data: bytes, box) -> bytes:
    from PIL import Image

    with Image.open(BytesIO(data)) as im:
        crop = im.convert("RGB").crop(box)
        crop.thumbnail((320, 320))
        buf = BytesIO()
        crop.save(buf, format="PNG")
        return buf.getvalue()


def main() -> int:
    import picture_scorecard as ps
    import ship_gate

    composite = COMPOSITE.read_bytes()
    out = {"composite": str(COMPOSITE.relative_to(ROOT)), "box": list(BOX), "cases": {}}

    for label, ref_path in (("cutout", CUTOUT), ("photo", PHOTO)):
        ref_bytes = ref_path.read_bytes()
        ref_subject = ps._subject_png(ref_bytes)
        cand_subject = _crop_png(composite, BOX)
        ident = ship_gate.review_image(cand_subject, brief="", reference=ref_subject,
                                       surface=None, use_default_scorers=False)
        axis = (ident.get("axes") or {}).get("identity", {})
        ssim = float(axis.get("ssim") or 0.0)
        distance = axis.get("phash_distance")
        cfg = ps.load_config()["identity"]
        score = ps._scale(ssim, float(cfg["min_ssim"]), float(cfg["good_ssim"]))
        clamped = (min(score, 40.0)
                   if distance is not None and int(distance) > int(cfg["max_phash_distance"])
                   else score)
        out["cases"][label] = {
            "reference": str(ref_path.relative_to(ROOT)),
            "reference_subject_png_bytes": len(ref_subject or b""),
            "ssim": round(ssim, 4), "phash_distance": distance,
            "score_from_ssim": round(score, 1),
            "score_after_phash_clamp": round(clamped, 1),
        }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
