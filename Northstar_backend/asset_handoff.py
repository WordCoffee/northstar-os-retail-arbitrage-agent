"""Asset -> Listing Forge hand-off (Phase 3, item 2).

A generated asset is useless to the copywriter unless it arrives with its role,
its aspect ratio and the keyword it serves. This module turns a render manifest
plus a RenderBrief into the exact fields Listing Forge needs, and it REFUSES to
promote a hero image that is not pure-white - the main-image rule is not a
suggestion the hand-off may average away.

Pure functions: no I/O, no network.
"""
from __future__ import annotations

from math import gcd
from typing import Any, Dict, Iterable, List, Optional

MAX_SECONDARY = 6
ROLE_ORDER = {"hero": -1, "lifestyle": 0, "scale": 1, "detail": 2, "packaging": 3, "other": 4}


def aspect(width: Any, height: Any) -> str:
    """Reduced ratio string, e.g. 2000x2000 -> '1:1', 970x600 -> '97:60'."""
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return "unknown"
    if w <= 0 or h <= 0:
        return "unknown"
    g = gcd(w, h) or 1
    return f"{w // g}:{h // g}"


def _clean(asset: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = str(asset.get("url") or "").strip()
    if not url:
        return None
    w, h = asset.get("width"), asset.get("height")
    role = str(asset.get("role") or "other").strip().lower()
    return {
        "url": url,
        "role": role if role in ROLE_ORDER else "other",
        "aspect": aspect(w, h),
        "square": aspect(w, h) == "1:1",
        "pure_white": bool(asset.get("pure_white")),
        "alt": str(asset.get("alt") or "").strip(),
    }


def handoff(brief: Any, assets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the Listing Forge payload. `brief` is a RenderBrief (or its dict)."""
    brief_dict = brief.to_dict() if hasattr(brief, "to_dict") else dict(brief or {})
    product_id = str(brief_dict.get("product_id") or "")
    keywords: List[str] = list(brief_dict.get("keywords") or [])
    blocked: List[str] = list(brief_dict.get("blocked") or [])

    cleaned = [c for c in (_clean(a or {}) for a in assets or []) if c]

    hero = next((a for a in cleaned if a["role"] == "hero"), None)
    if hero is None:
        blocked.append("hero_missing")
    elif not hero["pure_white"]:
        blocked.append("hero_not_pure_white")
    elif not hero["square"]:
        blocked.append("hero_not_square")

    secondary = [a for a in cleaned if a is not hero]
    secondary.sort(key=lambda a: (ROLE_ORDER[a["role"]], a["url"]))
    secondary = secondary[:MAX_SECONDARY]

    alt = ""
    if hero:
        lead = keywords[0] if keywords else "product"
        alt = (f"{lead} photograph on a pure white background")[:120]

    return {
        "product_id": product_id,
        "hero_image": hero["url"] if hero else None,
        "hero_aspect": hero["aspect"] if hero else None,
        "secondary_images": [a["url"] for a in secondary],
        "secondary_meta": [
            {"url": a["url"], "role": a["role"], "aspect": a["aspect"]} for a in secondary
        ],
        "keywords": keywords,
        "alt_text": alt,
        "blocked": blocked,
        "ready": not blocked,
        "material_tier": brief_dict.get("material_tier"),
        "environment": brief_dict.get("environment"),
    }


__all__ = ["handoff", "aspect", "ROLE_ORDER", "MAX_SECONDARY"]
