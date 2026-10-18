"""Deterministic listing↔profile SEO scoring (V3 S7 §5.3).

This is the ListingForge hook: score a listing revision against the brand's
canonical SEO profile. It is deliberately DETERMINISTIC and keyword-based — no
modelled "rank", no fabricated search volumes. What it reports is exactly what
it can prove from the two inputs:

  • coverage  — which profile keyword clusters appear in the listing copy, and
                where (title / bullets / backend terms / description);
  • violations — prohibited claims present in the copy;
  • competitor mentions — competitor names appearing in the copy;
  • caveats   — honest notes about what this score is and is NOT.

Nothing here calls a network or a paid service. Nothing is invented: with no
profile keywords there is no denominator, so the score is None (not zero).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

HEAD_WEIGHT = 3.0
BODY_WEIGHT = 1.5

FIELDS = ("title", "bullets", "backend_terms", "description")


def _norm_terms(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    out = []
    for v in value:
        s = str(v).strip().lower()
        if s:
            out.append(s)
    return out


def keyword_clusters(profile: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """Return (head, body, negative) terms from a profile body (case-folded)."""
    kc = (profile or {}).get("keyword_clusters")
    if isinstance(kc, dict):
        head = _norm_terms(kc.get("head") or kc.get("heads"))
        body = _norm_terms(kc.get("body") or kc.get("body_terms"))
        neg = _norm_terms(kc.get("negative") or kc.get("negatives"))
    elif isinstance(kc, list):
        head, body, neg = _norm_terms(kc), [], []
    else:
        head, body, neg = [], [], []
    return head, body, neg


def _listing_fields(listing: Dict[str, Any]) -> Dict[str, str]:
    bullets = listing.get("bullets")
    if isinstance(bullets, list):
        bullets_text = " \n ".join(str(b) for b in bullets)
    else:
        bullets_text = str(bullets or "")
    return {
        "title": str(listing.get("title") or "").lower(),
        "bullets": bullets_text.lower(),
        "backend_terms": str(listing.get("backend_terms") or "").lower(),
        "description": str(listing.get("description") or "").lower(),
    }


def score_listing(profile: Dict[str, Any], listing: Dict[str, Any]) -> Dict[str, Any]:
    """Score one listing against a profile body. Deterministic; never fabricates."""
    fields = _listing_fields(listing)
    full = " ".join(fields.values())
    head, body, negative = keyword_clusters(profile)

    weighted = [(t, HEAD_WEIGHT, "head") for t in head] + \
               [(t, BODY_WEIGHT, "body") for t in body]
    total_w = sum(w for _, w, _ in weighted)
    got_w = 0.0
    matched: List[Dict[str, str]] = []
    missing: List[Dict[str, str]] = []
    for term, weight, section in weighted:
        where = [f for f in FIELDS if term in fields[f]]
        if where:
            got_w += weight
            matched.append({"term": term, "section": section, "where": ",".join(where)})
        else:
            missing.append({"term": term, "section": section})

    score = round(100.0 * got_w / total_w) if total_w else None

    violations = [t for t in negative if t in full]
    competitors = [str(c) for c in ((profile or {}).get("competitors") or [])
                   if str(c).strip() and str(c).strip().lower() in full]

    caveats: List[str] = [
        "Deterministic keyword coverage — not a rank or volume prediction.",
    ]
    if score is None:
        caveats.append("No keyword clusters in the profile; nothing to score against.")
    if missing:
        caveats.append(f"{len(missing)} profile term(s) not found in the copy.")

    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "head_total": len(head),
        "body_total": len(body),
        "matched_count": len(matched),
        "violations": violations,
        "competitor_mentions": competitors,
        "caveats": caveats,
    }
