"""Social & Ad Graphics — aspect-ratio layout plans with safe zones.

Deterministic planning only: it decides the canvases, the safe zones, the copy
slots and one prompt per aspect. Rendering stays with the local image lane.

Sizes are the current industry standards for the major placements; they are
recorded as our own choice (not attributed to a studied tool, because no hosted
creative tool was observed this pass).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

#: aspect label -> (width, height, placements, safe-zone note)
ASPECTS: Dict[str, Dict[str, Any]] = {
    "1:1": {"w": 1080, "h": 1080, "use": "Instagram/Facebook feed, Amazon post",
            "safe": "keep text inside the central 80%"},
    "4:5": {"w": 1080, "h": 1350, "use": "Instagram portrait feed (highest feed reach)",
            "safe": "keep text inside the central 80%"},
    "9:16": {"w": 1080, "h": 1920, "use": "Reels / TikTok / Stories",
             "safe": "keep critical copy out of the top 14% and bottom 20% (UI overlays)"},
    "16:9": {"w": 1200, "h": 628, "use": "link preview / horizontal banner",
             "safe": "keep text inside the central 80%"},
    "2:3": {"w": 1000, "h": 1500, "use": "Pinterest pin", "safe": "logo in the top third"},
}

CONTENT_TYPES = {
    "ad": {"slots": ("hook", "product", "proof", "cta"),
           "note": "one idea per ad; the hook carries the first 1.5 seconds"},
    "social": {"slots": ("hook", "product", "cta"),
               "note": "conversational, no hard sell"},
    "banner": {"slots": ("headline", "product", "cta"),
               "note": "headline must survive at 50% scale"},
    "aplus": {"slots": ("headline", "benefit", "product"),
              "note": "A+ rules apply — see the A+ agent"},
}


def missing_inputs(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    gaps: List[Dict[str, str]] = []
    if not spec.get("product"):
        gaps.append({"field": "product", "question": "which product is the creative for?"})
    if not spec.get("content_type"):
        gaps.append({"field": "content_type",
                     "question": "is this an ad, a social post, a banner or A+ content?"})
    return gaps


def plan(*, spec: Dict[str, Any], allow_incomplete: bool = False) -> Dict[str, Any]:
    gaps = missing_inputs(spec)
    if gaps and not allow_incomplete:
        return {"ok": False, "status": "needs_input",
                "summary": f"{len(gaps)} thing(s) first.", "questions": gaps, "assets": []}

    ctype = str(spec.get("content_type") or "social")
    cspec = CONTENT_TYPES.get(ctype, CONTENT_TYPES["social"])
    wanted: Sequence[str] = spec.get("aspects") or ["1:1", "4:5", "9:16"]
    product = str(spec.get("product") or "")
    headline = str(spec.get("headline") or "")

    layouts: List[Dict[str, Any]] = []
    for aspect in wanted:
        a = ASPECTS.get(aspect)
        if not a:
            continue
        layouts.append({
            "aspect": aspect,
            "size": f"{a['w']}x{a['h']}",
            "placements": a["use"],
            "safe_zone": a["safe"],
            "slots": list(cspec["slots"]),
            "copy": {"headline": headline or "[MISSING: headline]"},
            "prompt": (f"{ctype} creative for {product} at {aspect}. {a['use']}. "
                       f"Leave clean space for {', '.join(cspec['slots'])}. "
                       f"No text baked into the image."),
        })

    return {
        "ok": True,
        "status": "planned",
        "summary": (f"{len(layouts)} layout(s) for a {ctype}: "
                    + ", ".join(f"{l['aspect']} {l['size']}" for l in layouts)),
        "content_type": ctype,
        "note": cspec["note"],
        "layouts": layouts,
        "rules": ["copy is authored as a layer, never painted",
                  "claims must trace to the Brand Kit"],
        "assets": [],
    }
