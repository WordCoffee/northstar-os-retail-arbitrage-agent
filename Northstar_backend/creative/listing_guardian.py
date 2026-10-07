"""Listing Guardian — local listing-health audit.

No live Amazon source is required: this audits operator-supplied listing text
against Amazon-style best practices and compliance rules using the local
ListingForge engine. Deterministic, offline, honest about what it can and cannot
see (it never claims to observe live Amazon state).
"""

from __future__ import annotations

from typing import Any, Dict, List

import listing_forge

MAX_TITLE = 200


def _chk(name: str, ok: bool, detail: str, *, weight: int = 1) -> Dict[str, Any]:
    return {"check": name, "ok": bool(ok), "detail": detail, "weight": weight}


def audit(listing: Dict[str, Any]) -> Dict[str, Any]:
    product = listing.get("product") or {}
    title = listing.get("title", "") or ""
    bullets = listing.get("bullets") or []
    description = listing.get("description", "") or ""
    keywords = [k for k in (listing.get("keywords") or []) if k]

    score = listing_forge.score_listing(product, title=title, bullets=bullets,
                                        description=description, keywords=keywords)
    compliance = listing_forge.check_compliance(title=title, bullets=bullets,
                                                brand=str(product.get("brand", "")))

    haystack = (title + " " + " ".join(bullets)).lower()
    matched = [k for k in keywords if k.lower() in haystack]

    checks: List[Dict[str, Any]] = [
        _chk("title_length", 0 < len(title) <= MAX_TITLE, f"{len(title)}/{MAX_TITLE} chars", weight=2),
        _chk("bullet_count", len(bullets) >= 3, f"{len(bullets)} bullet(s) (want >= 3)", weight=2),
        _chk("description_present", len(description) >= 80, f"{len(description)} chars", weight=1),
        _chk("keyword_coverage",
             (len(matched) / len(keywords) >= 0.5) if keywords else True,
             f"{len(matched)}/{len(keywords)} keyword(s) matched" if keywords else "no keywords supplied",
             weight=1),
        _chk("compliance", compliance["ok"],
             f"{len(compliance['violations'])} violation(s)", weight=3),
    ]
    total_w = sum(c["weight"] for c in checks)
    got_w = sum(c["weight"] for c in checks if c["ok"])
    ratio = got_w / total_w if total_w else 0.0
    status = "healthy" if ratio >= 0.99 else ("attention" if ratio >= 0.7 else "needs_work")

    return {
        "ok": True,
        "status": status,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "weighted_ratio": round(ratio, 3),
        "checks": checks,
        "score": score,
        "compliance": compliance,
        "matched_keywords": matched,
        "basis": "local rules (ListingForge engine) — no live Amazon observation",
    }
