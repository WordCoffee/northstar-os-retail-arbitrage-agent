"""Deterministic Amazon main-image checks.

A text skill can describe the rules; only code can enforce them. This module
turns the studied platform specs into measurable checks so an image either
passes or names the rule it broke.

Rules verified 2026-10-23 against `xianyu110/ecommerce-image-skills`,
`skills/amazon-white-background/SKILL.md` ("Platform specs (Amazon main image)"):

    background        pure white RGB 255,255,255 (#FFFFFF)
    product coverage  product fills >= 85% of the frame
    size              longest side >= 1000 px for zoom; 1600-2000 recommended
    format            JPEG preferred, sRGB
    content           only the product; no text, badges, borders, watermark, props

Citations: research/ecommerce-image-skills/evidence.md.

What is NOT checked here, and is reported as not_measured rather than assumed:
  • added text / badges / watermarks (needs OCR — the render lane's OCR gate
    exists but is not wired into this validator yet)
  • colour space (sRGB) — needs an ICC read
  • "whole product visible / in focus" — subjective, needs a human or a model
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
from PIL import Image

#: Amazon main-image rules, cited above.
WHITE_TOLERANCE = 6          # a channel within this of 255 still counts as white
MIN_COVERAGE = 0.85
MIN_LONG_EDGE = 1000
RECOMMENDED_LONG_EDGE = 1600
MAX_LONG_EDGE = 10000


def _background_mask(arr: np.ndarray) -> np.ndarray:
    """Pixels that read as pure white."""
    return np.all(arr >= (255 - WHITE_TOLERANCE), axis=2)


def check_main_image(path: str | Path) -> Dict[str, Any]:
    """Return {ok, violations, metrics, not_measured} for one image file."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "violations": [f"file not found: {p}"], "metrics": {},
                "not_measured": []}

    img = Image.open(p)
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info)
    rgb = img.convert("RGB")
    arr = np.asarray(rgb).astype(np.int16)
    h, w = arr.shape[:2]
    long_edge = max(w, h)

    white = _background_mask(arr)
    white_share = float(white.mean())

    # Product extent: the bounding box of everything that is not white.
    foreground = ~white
    violations: list[str] = []
    coverage = 0.0
    if foreground.any():
        ys = np.flatnonzero(foreground.any(axis=1))
        xs = np.flatnonzero(foreground.any(axis=0))
        box_w = int(xs[-1] - xs[0] + 1)
        box_h = int(ys[-1] - ys[0] + 1)
        # Amazon's "fills the frame" is about the product's own extent, so the
        # bounding box is the honest measurement (not the ink coverage).
        coverage = max(box_w / w, box_h / h)
    else:
        violations.append("the image is blank: no product found")

    # Corners must be white, otherwise the background is not seamless white.
    corners = [arr[0, 0], arr[0, -1], arr[-1, 0], arr[-1, -1]]
    dirty_corners = [i for i, c in enumerate(corners)
                     if not np.all(c >= (255 - WHITE_TOLERANCE))]
    if dirty_corners:
        violations.append(
            f"background is not pure white: corner(s) {dirty_corners} read "
            f"{[list(int(v) for v in corners[i]) for i in dirty_corners]}")

    if coverage < MIN_COVERAGE:
        violations.append(
            f"product fills {coverage:.0%} of the frame; Amazon expects "
            f">= {MIN_COVERAGE:.0%}")

    if long_edge < MIN_LONG_EDGE:
        violations.append(
            f"longest side is {long_edge}px; >= {MIN_LONG_EDGE}px is required for zoom")

    if long_edge > MAX_LONG_EDGE:
        violations.append(f"longest side {long_edge}px exceeds the {MAX_LONG_EDGE}px maximum")

    if has_alpha:
        violations.append("image carries an alpha channel; a JPEG on white is expected")

    warnings: list[str] = []
    if MIN_LONG_EDGE <= long_edge < RECOMMENDED_LONG_EDGE:
        warnings.append(
            f"longest side {long_edge}px is allowed but {RECOMMENDED_LONG_EDGE}-2000px is "
            f"recommended")

    return {
        "ok": not violations,
        "violations": violations,
        "warnings": warnings,
        "metrics": {
            "width": w, "height": h, "long_edge": long_edge,
            "white_share": round(white_share, 4),
            "coverage": round(coverage, 4),
            "has_alpha": bool(has_alpha),
            "format": img.format,
        },
        "not_measured": [
            "added text / badges / watermark (needs OCR)",
            "sRGB colour space (needs an ICC read)",
            "whole product visible and in focus (needs a human or a vision model)",
        ],
        "rules_source": ("xianyu110/ecommerce-image-skills "
                         "skills/amazon-white-background/SKILL.md"),
    }


def check_many(paths: Sequence[str | Path]) -> Dict[str, Any]:
    rows = [{"file": str(p), **check_main_image(p)} for p in paths]
    failed = [r for r in rows if not r["ok"]]
    return {
        "ok": not failed,
        "checked": len(rows),
        "failed": len(failed),
        "results": rows,
        "summary": (f"{len(rows) - len(failed)}/{len(rows)} images satisfy the Amazon "
                    f"main-image rules"),
    }
