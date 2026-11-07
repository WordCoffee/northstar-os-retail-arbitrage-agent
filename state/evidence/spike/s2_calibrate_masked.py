"""Second S2 calibration: is >= 85 reachable by a *correct* implementation?

The first probe showed the generic subject-crop comparison scores 0.11 even with
the right box, because the box crop carries line background in its corners while
the reference crop is tight on the product. The composite's own identity check
scores 0.93 because it masks to the product's alpha.

So the question this probe answers: if a fix compared ONLY the product pixels
(mask the composite by the cutout alpha, flatten both onto white), what score
would the existing scoring arithmetic produce? If that number is < 85, S2's
target check is unattainable and the case cannot fairly measure the lane.

Measurement only: nothing here is a candidate patch.
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "Northstar_backend"
sys.path.insert(0, str(BACKEND))

COMPOSITE = ROOT / "renders/autonomy_probe/composite/lifestyle_linen_composite.png"
CUTOUT = ROOT / "renders/autonomy_probe/composite/lifestyle_linen_cutout.png"
BOX = (279, 308, 744, 1024)
SIDE = 320


def _trim_alpha(im: Image.Image) -> Image.Image:
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox) if bbox else im


def main() -> int:
    import ship_gate

    composite = Image.open(COMPOSITE).convert("RGB")
    cutout = _trim_alpha(Image.open(CUTOUT).convert("RGBA"))
    region = composite.crop(BOX)
    mask = cutout.resize(region.size, Image.LANCZOS).getchannel("A")
    product = cutout.convert("RGB").resize(region.size, Image.LANCZOS)

    white = Image.new("RGB", region.size, (255, 255, 255))
    cand_masked = Image.composite(region, white, mask)
    ref_masked = Image.composite(product, white, mask)
    # A tight view of the product only, both sides, as a correct implementation
    # would hand to the identity axis.
    tight = mask.point(lambda v: 255 if v > 127 else 0).getbbox()
    if tight:
        cand_masked = cand_masked.crop(tight)
        ref_masked = ref_masked.crop(tight)

    ssim = ship_gate.ssim(cand_masked, ref_masked)
    dist = ship_gate.phash_distance(cand_masked, ref_masked)
    cfg = json.loads((ROOT / "config/picture_scorecard.json").read_text(
        encoding="utf-8"))["identity"] if (ROOT / "config/picture_scorecard.json").is_file() else {}
    ik = {"min_ssim": 0.40, "good_ssim": 0.55, "max_phash_distance": 24, **cfg}
    score = max(0.0, min(100.0, (ssim - ik["min_ssim"]) / (ik["good_ssim"] - ik["min_ssim"]) * 100))
    after = min(score, 40.0) if dist > ik["max_phash_distance"] else score

    # Also report the unmasked frame comparison for contrast.
    plain_ssim = ship_gate.ssim(region, product)

    payload = {
        "check": "S2-calibration",
        "box": list(BOX),
        "masked": {"ssim": round(ssim, 4), "phash_distance": dist,
                   "score_from_ssim": round(score, 1),
                   "score_after_phash_clamp": round(after, 1),
                   "reaches_85": after >= 85.0},
        "unmasked_frame": {"ssim": round(plain_ssim, 4),
                           "would_score": round(max(0.0, min(100.0, (
                               plain_ssim - ik["min_ssim"]) / (ik["good_ssim"] - ik["min_ssim"]) * 100)), 1)},
        "identity_thresholds": ik,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
