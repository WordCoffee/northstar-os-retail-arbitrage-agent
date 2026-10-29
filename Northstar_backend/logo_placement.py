"""Deterministic logo placement (REA 1.6 candidate U3).

Untreated gap this closes: 5 of 60 surveyed turns asked for the logo to be put
somewhere and **no tool served them** (reports/rea_probe/smui_intents.json).

What this does NOT do: guess. There is no ML placement model and no invented
"best spot". The anchor is either the operator's explicit choice or `auto`,
which measures local flatness on a 3×3 grid and picks the calmest region — and
reports the scores so the choice can be argued with.

    place(plate_png, logo_png, anchor="auto", scale=0.18, opacity=0.95)

Returns the composed PNG bytes plus the placement and the evidence behind it.
"""

from __future__ import annotations

import io
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

ANCHORS = ("auto", "top-left", "top-center", "top-right",
           "middle-left", "center", "middle-right",
           "bottom-left", "bottom-center", "bottom-right")

BLENDS = ("normal", "multiply")


def _prep_logo(logo: Image.Image, target_w: int) -> Image.Image:
    """Trim empty margins, scale to width, keep alpha."""
    logo = logo.convert("RGBA")
    bbox = logo.split()[-1].getbbox()
    if bbox:
        logo = logo.crop(bbox)
    if logo.width == 0 or logo.height == 0:
        raise ValueError("the logo image is empty")
    ratio = target_w / float(logo.width)
    return logo.resize((max(1, target_w), max(1, int(round(logo.height * ratio)))),
                       Image.LANCZOS)


def _flatness(plate: Image.Image) -> Dict[str, float]:
    """Mean gradient magnitude on a 3x3 grid. Lower is calmer (better to print on)."""
    grey = np.asarray(plate.convert("L").resize((96, 96), Image.BILINEAR), dtype=np.float32)
    gy, gx = np.gradient(grey)
    mag = np.hypot(gx, gy)
    scores: Dict[str, float] = {}
    h, w = mag.shape
    for row, vname in enumerate(("top", "middle", "bottom")):
        for col, hname in enumerate(("left", "center", "right")):
            cell = mag[row * h // 3:(row + 1) * h // 3, col * w // 3:(col + 1) * w // 3]
            key = "center" if (vname, hname) == ("middle", "center") else f"{vname}-{hname}"
            scores[key] = float(cell.mean())
    return scores


def _box(anchor: str, size: Tuple[int, int], logo: Tuple[int, int],
         margin: float) -> Tuple[int, int]:
    W, H = size
    lw, lh = logo
    mx, my = int(round(W * margin)), int(round(H * margin))
    x = {"left": mx, "center": (W - lw) // 2, "right": W - lw - mx}[anchor.split("-")[-1]]
    y = {"top": my, "middle": (H - lh) // 2, "bottom": H - lh - my}[anchor.split("-")[0]]
    return max(0, x), max(0, y)


def place(plate_bytes: bytes, logo_bytes: bytes, *, anchor: str = "auto",
          scale: float = 0.18, opacity: float = 0.95, margin: float = 0.04,
          blend: str = "normal") -> Dict[str, Any]:
    """Composite the logo onto the plate. Returns bytes + placement + evidence."""
    if anchor not in ANCHORS:
        raise ValueError(f"anchor must be one of {ANCHORS}, got {anchor!r}")
    if blend not in BLENDS:
        raise ValueError(f"blend must be one of {BLENDS}, got {blend!r}")
    if not (0.02 <= float(scale) <= 0.9):
        raise ValueError("scale must be between 0.02 and 0.9 of the short edge")
    if not (0.0 <= float(opacity) <= 1.0):
        raise ValueError("opacity must be between 0 and 1")

    plate = Image.open(io.BytesIO(plate_bytes)).convert("RGB")
    W, H = plate.size
    target_w = max(8, int(round(min(W, H) * float(scale))))
    logo = _prep_logo(Image.open(io.BytesIO(logo_bytes)), target_w)

    scores = _flatness(plate)
    chosen = anchor
    if anchor == "auto":
        # Never the dead centre: a logo there competes with the product. Pick the
        # calmest of the eight perimeter cells and report the scores behind it.
        perimeter = {k: v for k, v in scores.items() if k != "center"}
        chosen = min(perimeter, key=perimeter.get)

    x, y = _box(chosen, (W, H), logo.size, float(margin))
    if x + logo.width > W or y + logo.height > H:
        raise ValueError("the logo does not fit at that scale with that margin; "
                         "reduce scale or margin")

    alpha = logo.split()[-1].point(lambda v: int(v * float(opacity)))
    rgba = logo.copy()
    rgba.putalpha(alpha)

    base = plate.copy()
    if blend == "multiply":
        # Print-like seating: multiply keeps the surface's shading through the mark.
        from PIL import ImageChops
        patch = base.crop((x, y, x + logo.width, y + logo.height)).convert("RGB")
        mult = ImageChops.multiply(patch, rgba.convert("RGB"))
        base.paste(Image.composite(mult, patch, alpha), (x, y))
    else:
        base.paste(rgba, (x, y), rgba)

    # Measure what we just did: contrast between the logo's ink and its backdrop.
    patch = np.asarray(plate.crop((x, y, x + logo.width, y + logo.height)).convert("L"),
                       dtype=np.float32)
    ink = np.asarray(rgba.split()[-1].resize((logo.width, logo.height)), dtype=np.float32) > 128
    logo_luma = np.asarray(rgba.convert("L").resize((logo.width, logo.height)), dtype=np.float32)
    ink_mean = float(logo_luma[ink].mean()) if ink.any() else float(logo_luma.mean())
    back_mean = float(patch[~ink].mean()) if (~ink).any() else float(patch.mean())
    lo, hi = sorted([ink_mean, back_mean])
    ratio = round((hi + 5.0) / (lo + 5.0), 2)
    coverage = round(100.0 * (logo.width * logo.height) / (W * H), 2)

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    return {
        "bytes": buf.getvalue(),
        "size": [W, H],
        "placement": {"anchor": chosen, "x": int(x), "y": int(y),
                      "width": int(logo.width), "height": int(logo.height),
                      "scale": float(scale), "opacity": float(opacity),
                      "blend": blend, "margin": float(margin)},
        "quality": {
            "contrast_ratio": ratio,
            "contrast_ok": ratio >= 1.5,
            "coverage_pct": coverage,
            "flatness_scores": {k: round(v, 3) for k, v in scores.items()},
            "chosen_flatness": round(scores.get(chosen, scores.get("center", 0.0)), 3),
        },
        "note": ("Placed deterministically: the logo pixels were composited, never "
                 "generated. The anchor is measured (flattest perimeter cell) or the "
                 "operator's own; check the contract proof if this goes to print."),
    }
