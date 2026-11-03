"""Ad formats: one validated canvas per placement, not a free width/height pair.

An ad brief that ends up 1024x1024 when the placement is a Reel is wasted work,
and a caller that passes `format=story` *and* `width=1024` is asking for two
things at once. This module owns the three canvases the pipeline sells and
refuses the contradiction instead of silently picking one.

Sizes are divisible by 8 (864, 1024, 1536) because the local sampler works on
8-pixel latents; a size that is not would be silently cropped by ComfyUI.
"""
from __future__ import annotations

from math import gcd
from typing import Any, Dict, Optional

FORMATS: Dict[str, Dict[str, Any]] = {
    "square": {"width": 1024, "height": 1024, "ratio": "1:1",
               "label": "Feed square", "placements": ["amazon-main", "meta-feed"]},
    "story": {"width": 864, "height": 1536, "ratio": "9:16",
              "label": "Story / Reel / Short", "placements": ["ig-story", "reels", "tiktok", "shorts"]},
    "wide": {"width": 1536, "height": 864, "ratio": "16:9",
             "label": "Widescreen banner", "placements": ["sponsored-brand", "display", "youtube-banner"]},
}

#: ComfyUI samples on 8-pixel latents; anything else is cropped behind our back.
LATENT_STEP = 8

#: Still placements: a canvas plus the area the platform's own UI does NOT cover.
#: These are the same class of contract as `video_formats.FORMATS`. Numbers that
#: come from the checked video presets say so; the rest are working estimates and
#: are marked `verified: False` rather than presented as platform facts. Amazon's
#: main-image rule (no text, no watermark, no props) is a placement property, not
#: a taste call, and it is marked unverified because reading Amazon's spec is a
#: standing gate.
PLACEMENTS: Dict[str, Dict[str, Any]] = {
    "amazon-main": {
        "label": "Amazon main image", "canvas": "square",
        "text_allowed": False, "safe_zones": {"top_pct": 2, "bottom_pct": 2,
                                               "left_pct": 2, "right_pct": 2},
        "source": "working assumption; Amazon's image spec is a standing gate and was NOT read",
        "verified": False,
    },
    "meta-feed": {
        "label": "Meta feed", "canvas": "square",
        "text_allowed": True, "safe_zones": {"top_pct": 6, "bottom_pct": 14,
                                              "left_pct": 6, "right_pct": 8},
        "source": "working UI-overlay estimate for this pass", "verified": False,
    },
    "ig-story": {
        "label": "Instagram story", "canvas": "story",
        "text_allowed": True, "safe_zones": {"top_pct": 12, "bottom_pct": 20,
                                              "left_pct": 8, "right_pct": 10},
        "source": "working UI-overlay estimate for this pass", "verified": False,
    },
    "reels": {
        "label": "Instagram Reels", "canvas": "story",
        "text_allowed": True, "safe_zones": {"top_pct": 10, "bottom_pct": 20,
                                              "left_pct": 6, "right_pct": 14},
        "source": "Instagram Reels limits (public help docs, checked 2026-11-03)",
        "verified": True,
    },
    "tiktok": {
        "label": "TikTok", "canvas": "story",
        "text_allowed": True, "safe_zones": {"top_pct": 8, "bottom_pct": 22,
                                              "left_pct": 6, "right_pct": 18},
        "source": "TikTok recommendations (public help docs, checked 2026-11-03)",
        "verified": True,
    },
    "shorts": {
        "label": "YouTube Shorts", "canvas": "story",
        "text_allowed": True, "safe_zones": {"top_pct": 10, "bottom_pct": 18,
                                              "left_pct": 6, "right_pct": 12},
        "source": "YouTube Shorts limits (public help docs, checked 2026-11-03)",
        "verified": True,
    },
    "sponsored-brand": {
        "label": "Sponsored Brands banner", "canvas": "wide",
        "text_allowed": True, "safe_zones": {"top_pct": 5, "bottom_pct": 10,
                                              "left_pct": 5, "right_pct": 5},
        "source": "working assumption; Amazon specs are a standing gate and were NOT read",
        "verified": False,
    },
    "display": {
        "label": "Display banner", "canvas": "wide",
        "text_allowed": True, "safe_zones": {"top_pct": 4, "bottom_pct": 8,
                                              "left_pct": 4, "right_pct": 4},
        "source": "working UI-overlay estimate for this pass", "verified": False,
    },
}


def placements() -> Dict[str, Any]:
    """Every still placement with its canvas size and safe-zone contract."""
    rows = []
    for key, row in PLACEMENTS.items():
        canvas = FORMATS[row["canvas"]]
        rows.append({"id": key, **row, "width": canvas["width"],
                     "height": canvas["height"], "ratio": canvas["ratio"]})
    return {"placements": rows,
            "note": ("A placement fixes the canvas and the area the platform's UI "
                     "covers. verified=false means the numbers are a working "
                     "estimate and must be reported as such.")}


def ratio_of(width: int, height: int) -> str:
    """Reduced ratio string, e.g. 864x1536 -> '9:16'."""
    w, h = int(width), int(height)
    if w <= 0 or h <= 0:
        raise ValueError("ad_format_invalid_size: width and height must be positive")
    divisor = gcd(w, h) or 1
    return f"{w // divisor}:{h // divisor}"


def resolve(name: Optional[str], width: Optional[int] = None,
            height: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """The canvas for a named format, or None when no format was requested.

    Raises ValueError (code-prefixed) for an unknown format, a conflicting
    width/height, or a size the sampler cannot render exactly.
    """
    key = (name or "").strip().lower()
    if not key:
        if width or height:
            for size in (width, height):
                if size and (int(size) <= 0 or int(size) % LATENT_STEP):
                    raise ValueError(
                        f"ad_format_invalid_size: {size} is not a positive multiple of "
                        f"{LATENT_STEP}")
        return None
    if key not in FORMATS:
        raise ValueError(f"ad_format_unknown: {name!r}; use one of {sorted(FORMATS)}")
    preset = FORMATS[key]
    for axis, given in (("width", width), ("height", height)):
        if given is not None and int(given) != preset[axis]:
            raise ValueError(
                f"ad_format_dimension_conflict: format {key!r} is "
                f"{preset['width']}x{preset['height']}, got {axis}={given}")
    return {"format": key, "width": preset["width"], "height": preset["height"],
            "ratio": preset["ratio"], "label": preset["label"],
            "placements": list(preset["placements"])}


def describe() -> Dict[str, Any]:
    """Everything the UI or an operator needs to choose a placement."""
    return {"formats": [{"format": key, **{k: v for k, v in preset.items()}}
                        for key, preset in FORMATS.items()],
            "latent_step": LATENT_STEP,
            "note": ("A format fixes the canvas. Passing a contradictory width or "
                     "height is refused rather than silently overridden.")}


__all__ = ["FORMATS", "LATENT_STEP", "PLACEMENTS", "placements", "ratio_of",
           "resolve", "describe"]
