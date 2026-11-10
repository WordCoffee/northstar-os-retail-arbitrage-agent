"""Content Writer — ad copy, captions, email and brand story, keyword-tied.

Every piece is bound to the operator's keywords and the brand voice, and every
claim is screened. It writes copy; it never asserts a fact the Brand Kit does
not hold.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

SURFACES = ("ad", "social", "email", "brand_story", "listing_bullet")

#: Claims that must never be generated for a wellness/supplement brand.
CLAIM_RE = re.compile(
    r"\b(cures?|treats?|heals?|prevents?|reverses?|clinically proven|"
    r"fda approved|guaranteed results)\b", re.I)

STOPWORDS = {"the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on"}


def missing_inputs(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    gaps: List[Dict[str, str]] = []
    if not spec.get("product"):
        gaps.append({"field": "product", "question": "which product is this copy for?"})
    if not spec.get("surface"):
        gaps.append({"field": "surface",
                     "question": f"which surface? ({', '.join(SURFACES)})"})
    return gaps


def _coverage(text: str, keywords: Sequence[str]) -> Dict[str, Any]:
    low = str(text or "").lower()
    rows = [{"keyword": k, "present": k.lower() in low}
            for k in keywords if str(k).strip()]
    covered = sum(1 for r in rows if r["present"])
    return {"keywords": rows, "covered": covered, "total": len(rows),
            "coverage": round(covered / len(rows), 3) if rows else 0.0}


def _screen(text: str) -> List[Dict[str, str]]:
    return [{"match": m.group(0)} for m in CLAIM_RE.finditer(str(text or ""))]


def variants(*, product: str, surface: str, keywords: Sequence[str],
             tone: str = "balanced", benefits: Sequence[str] | None = None,
             brand: str = "") -> Dict[str, Any]:
    """Three deterministic variants per surface, each screened for claims."""
    kws = [str(k).strip() for k in keywords if str(k).strip()]
    primary = kws[0] if kws else ""
    benefits = [str(b) for b in (benefits or [])][:3] or ["[MISSING: benefits]"]
    b0 = benefits[0]

    if surface == "ad":
        drafts = [
            f"{product}: {b0}. {primary.title() if primary else ''}".strip(),
            f"Meet {product} — {b0}.",
            f"Your {primary or product} upgrade: {product}.",
        ]
    elif surface == "social":
        drafts = [
            f"{product} in the wild. {b0}.",
            f"Ask us anything about {product} — {b0}.",
            f"Small ritual, real difference: {product}.",
        ]
    elif surface == "email":
        drafts = [
            f"Subject: {product} — {b0}",
            f"Subject: the {primary or 'daily'} ritual worth keeping",
            f"Subject: {brand or 'New'}: {product} is here",
        ]
    elif surface == "brand_story":
        drafts = [
            f"{brand or 'We'} make {product} for people who read the label.",
            f"{brand or 'We'} started with one question: why is good {primary or 'powder'} hard to find?",
            f"{brand or 'We'} keep {product} simple on purpose.",
        ]
    else:  # listing_bullet
        drafts = [
            f"{b0.upper()}: {product}, made for a daily routine.",
            f"{primary.title() + ' READY' if primary else 'READY TO USE'}: {product}.",
            f"WHAT YOU GET: {product}, {b0.lower()}.",
        ]

    rows = []
    for text in drafts:
        hits = _screen(text)
        rows.append({
            "text": text,
            "words": len(text.split()),
            "coverage": _coverage(text, kws),
            "claim_hits": hits,
            "safe": not hits,
        })
    return {"surface": surface, "tone": tone, "variants": rows,
            "safe": all(r["safe"] for r in rows)}


def plan(*, spec: Dict[str, Any], allow_incomplete: bool = False) -> Dict[str, Any]:
    gaps = missing_inputs(spec)
    if gaps and not allow_incomplete:
        return {"ok": False, "status": "needs_input",
                "summary": f"{len(gaps)} thing(s) first.", "questions": gaps, "assets": []}
    surface = str(spec.get("surface") or "social")
    if surface not in SURFACES:
        return {"ok": False, "status": "rejected",
                "summary": f"{surface!r} is not a supported surface ({', '.join(SURFACES)}).",
                "error": "unsupported surface", "assets": []}
    out = variants(product=str(spec.get("product") or ""), surface=surface,
                   keywords=spec.get("keywords") or [],
                   tone=str(spec.get("tone") or "balanced"),
                   benefits=spec.get("benefits") or [],
                   brand=str(spec.get("brand") or ""))
    flagged = [v for v in out["variants"] if not v["safe"]]
    return {
        "ok": True,
        "status": "written",
        "summary": (f"{len(out['variants'])} {surface} variants. "
                    + (f"{len(flagged)} contain a flagged claim and need review."
                       if flagged else "No flagged claims.")),
        "variants": out["variants"],
        "claim_policy": "no disease/treatment claims; medical-sounding copy is flagged, never shipped",
        "assets": [],
    }
