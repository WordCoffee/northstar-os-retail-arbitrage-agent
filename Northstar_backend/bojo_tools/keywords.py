"""Keyword tools for Bojo — the Keyword Tracker's coverage maths.

``track_keywords`` wraps ``seo_score.score_listing``: the deterministic
content-to-profile scorer that every service already uses (ListingForge,
Creative Studio, AdPilot, SocialPulse, SourceScout). It reports which of the
brand profile's head/body keyword clusters appear in a listing and where, plus
any prohibited claims or competitor names present. It is NOT a rank or search
volume prediction, and it says so in ``caveats``.

Nothing here is re-implemented: the weighting (head 3.0, body 1.5), the
case-folding, the per-field ``where`` mapping and the ``None``-when-there-is-no
-denominator rule all come from ``seo_score``. Pure, offline, no model.

Contract::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — no profile, a profile with no keyword clusters, a listing
with no copy — return ``ok=False``. Programmer errors in the argument contract
raise ``TypeError``.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

from ._coerce import text

TOOL_TRACK_KEYWORDS = "track_keywords"


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_backend_on_path() -> None:
    root = _backend_root()
    if root not in sys.path:
        sys.path.insert(0, root)


@lru_cache(maxsize=1)
def _default_scorer() -> Any:
    """The real SEO scoring engine, imported once."""
    _ensure_backend_on_path()
    import seo_score

    return seo_score


def _bad(reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": TOOL_TRACK_KEYWORDS, "reason": reason}


def _listing(listing: Any) -> Dict[str, Any]:
    """Validate the listing shape and return the four scored fields."""
    if not isinstance(listing, Mapping):
        raise TypeError("listing must be a mapping")
    bullets = listing.get("bullets")
    if bullets is not None and not isinstance(bullets, (list, tuple, str)):
        raise TypeError("listing['bullets'] must be a list of strings, a string or None")
    for key in ("title", "backend_terms", "description"):
        value = listing.get(key)
        if value is not None and not isinstance(value, str):
            raise TypeError("listing[%r] must be a string or None" % key)
    return {
        "title": text(listing.get("title")),
        "bullets": bullets if bullets is not None else [],
        "backend_terms": text(listing.get("backend_terms")),
        "description": text(listing.get("description")),
    }


def _bullets_text(bullets: Any) -> str:
    if isinstance(bullets, (list, tuple)):
        return " ".join(str(b) for b in bullets)
    return str(bullets or "")


def track_keywords(
    listing: Mapping[str, Any],
    profile: Optional[Mapping[str, Any]] = None,
    brand_key: Optional[str] = None,
    profile_store: Optional[Any] = None,
    scorer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Score a listing's keyword coverage against a brand SEO profile.

    ``listing`` carries ``title``, ``bullets``, ``backend_terms`` and
    ``description`` (the four canonical fields). ``profile`` is the brand SEO
    profile body — the object whose ``keyword_clusters`` drive the score.

    When ``profile`` is omitted, ``profile_store`` (anything exposing
    ``get_profile(brand_key)``) is asked for it. No store and no profile is a
    business failure, never a fabricated empty profile.

    ``scorer`` is an injection seam; it defaults to the real ``seo_score``
    module and must expose ``score_listing(profile, listing)``.
    """
    fields = _listing(listing)
    if profile is not None and not isinstance(profile, Mapping):
        raise TypeError("profile must be a mapping or None")
    if brand_key is not None and not isinstance(brand_key, str):
        raise TypeError("brand_key must be a string or None")

    if not any(
        (
            fields["title"],
            _bullets_text(fields["bullets"]).strip(),
            fields["backend_terms"],
            fields["description"],
        )
    ):
        return _bad("the listing has no copy to score")

    resolved: Optional[Mapping[str, Any]]
    if profile is not None:
        resolved = profile
    elif profile_store is None:
        return _bad(
            "no brand SEO profile supplied (pass profile, or profile_store + brand_key)"
        )
    else:
        key = text(brand_key)
        if not key:
            return _bad("brand_key is required when using profile_store")
        try:
            resolved = profile_store.get_profile(key)
        except Exception as exc:  # noqa: BLE001 - dependency failure, honest
            return _bad(
                "profile lookup failed: %s: %s" % (type(exc).__name__, exc)
            )
        if not isinstance(resolved, Mapping):
            return _bad("no brand SEO profile for %r" % key)

    engine = scorer if scorer is not None else _default_scorer()
    try:
        scored = engine.score_listing(dict(resolved), fields)
    except Exception as exc:  # noqa: BLE001
        return _bad("keyword scoring failed: %s: %s" % (type(exc).__name__, exc))

    if not isinstance(scored, Mapping):
        return _bad(
            "scorer returned %s, expected a mapping" % type(scored).__name__
        )
    score = scored.get("score")
    if score is None:
        return _bad(
            "the profile has no keyword clusters, so there is no coverage to report"
        )

    head: List[str] = []
    body: List[str] = []
    negative: List[str] = []
    try:
        head, body, negative = engine.keyword_clusters(dict(resolved))
    except Exception:  # noqa: BLE001 - cluster listing is decoration, not the score
        pass

    missing = [dict(m) for m in (scored.get("missing") or [])]
    return {
        "ok": True,
        "tool": TOOL_TRACK_KEYWORDS,
        "data": {
            "brand_key": text(brand_key) or None,
            "coverage_pct": score,
            "matched_count": scored.get("matched_count"),
            "head_total": scored.get("head_total"),
            "body_total": scored.get("body_total"),
            "matched": [dict(m) for m in (scored.get("matched") or [])],
            "missing": missing,
            "gaps": [m.get("term") for m in missing if m.get("term")],
            "violations": list(scored.get("violations") or []),
            "competitor_mentions": list(scored.get("competitor_mentions") or []),
            "caveats": [str(c) for c in (scored.get("caveats") or [])],
            "clusters": {
                "head": list(head),
                "body": list(body),
                "negative": list(negative),
            },
        },
    }


TOOLS = {TOOL_TRACK_KEYWORDS: track_keywords}
