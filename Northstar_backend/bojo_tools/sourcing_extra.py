"""Sourcing tools for Bojo, part two — the Product Finder / Prospector scan.

``scan_products`` wraps ``amazon_search``, the scanner's candidate search:

* ``load_cached_candidates`` reads the candidate cache the scanner persists
  (``data/scanner-search-cache.json``) — zero network, the cache-first half;
* ``search_products`` is the live keyword search. It refuses by itself unless
  the per-run live envelope is armed (``live_gate.live_enabled()`` plus the
  per-run arm/cap), so this tool cannot arm live spending; it can only ask;
* ``cache_meta`` reports the cache's honest provenance (fresh / stale /
  missing / corrupt).

The cache/live decision is the house rule, stated once: read the cache first,
go live only when the caller asks AND the envelope is already armed. No search
provider, no scraping and no Amazon request is performed by this module.

Contract::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — nothing cached for the query without a live request, a
live request the gate refused, a dependency that errors — return ``ok=False``.
Programmer errors in the argument contract raise ``TypeError``.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

from ._coerce import text

TOOL_SCAN_PRODUCTS = "scan_products"


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_backend_on_path() -> None:
    root = _backend_root()
    if root not in sys.path:
        sys.path.insert(0, root)


@lru_cache(maxsize=1)
def _default_scanner() -> Any:
    """The real scanner search module (cache + gated live dispatch)."""
    _ensure_backend_on_path()
    import amazon_search

    return amazon_search


def _bad(reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": TOOL_SCAN_PRODUCTS, "reason": reason}


def _terms(query: Any, keywords: Any) -> List[str]:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if keywords is None:
        raw: List[Any] = []
    elif isinstance(keywords, (list, tuple)):
        raw = list(keywords)
    else:
        raise TypeError("keywords must be a list of strings or None")
    out: List[str] = []
    for item in [query] + raw:
        if not isinstance(item, str):
            raise TypeError("keywords entries must be strings")
        written = item.strip()
        if written and written.lower() not in [t.lower() for t in out]:
            out.append(written)
    return out


def _matches(candidate: Mapping[str, Any], terms: List[str]) -> bool:
    """True when the term appears in the candidate's own title/brand/category.

    This is presentation filtering over rows the scanner already stored; the
    candidate selection itself is the cache's, not this tool's.
    """
    haystack = " ".join(
        text(candidate.get(key))
        for key in ("name", "title", "brand", "category", "product_url")
    ).lower()
    if not haystack.strip():
        return False
    return any(term.lower() in haystack for term in terms)


def scan_products(
    query: str = "",
    keywords: Optional[List[str]] = None,
    limit: int = 50,
    live: bool = False,
    pages: Optional[int] = None,
    match_all: bool = True,
    scanner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Find sourcing candidates for a query (cache first, live only when armed).

    ``query`` and ``keywords`` name what to look for; at least one is required.
    ``limit`` caps the rows returned. ``live=True`` asks for a fresh search, but
    the production ``search_products`` still refuses unless the live envelope is
    armed — that refusal is reported, never worked around. ``match_all`` keeps
    the category-agnostic search (the Product Finder path) rather than the
    Kirkland-only relevance filter.

    ``scanner`` is an injectable dependency: anything exposing
    ``load_cached_candidates()``, ``search_products(...)`` and ``cache_meta()``.
    It defaults to the real ``amazon_search`` module; tests pass a fake, so no
    network or Amazon call is made.
    """
    terms = _terms(query, keywords)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if limit < 1:
        return _bad("limit must be >= 1")
    if not isinstance(live, bool):
        raise TypeError("live must be a boolean")
    if not isinstance(match_all, bool):
        raise TypeError("match_all must be a boolean")
    if pages is not None:
        if isinstance(pages, bool) or not isinstance(pages, int):
            raise TypeError("pages must be an integer or None")
        if pages < 1:
            return _bad("pages must be >= 1")

    if not terms:
        return _bad("no query or keywords supplied")

    client = scanner if scanner is not None else _default_scanner()

    try:
        cache = dict(client.cache_meta() or {})
    except Exception as exc:  # noqa: BLE001 - provenance read, reported not raised
        cache = {"cache_status": "unreadable",
                 "cache_error": "%s: %s" % (type(exc).__name__, exc)}
    cache_status = text(cache.get("cache_status")) or "unknown"

    try:
        cached = list(client.load_cached_candidates() or [])
    except Exception as exc:  # noqa: BLE001 - dependency failure, honest
        return _bad(
            "candidate cache read failed: %s: %s" % (type(exc).__name__, exc)
        )

    matched = [
        row for row in cached
        if isinstance(row, Mapping) and _matches(row, terms)
    ]

    source = "cache"
    rows = matched
    search_error = None
    if not rows and live:
        try:
            rows = list(
                client.search_products(
                    keywords=terms, pages=pages, match_all=match_all
                )
                or []
            )
        except Exception as exc:  # noqa: BLE001 - dependency failure, honest
            return _bad(
                "live candidate search failed: %s: %s" % (type(exc).__name__, exc)
            )
        source = "live"
        search_error = getattr(client, "LAST_SEARCH_ERROR", None)

    if not rows:
        gate = getattr(getattr(client, "live_gate", None), "live_enabled", None)
        armed = bool(gate()) if callable(gate) else None
        detail = "cache=%s" % cache_status
        if not live:
            detail += "; no live request made (pass live=True to ask for one)"
        elif search_error:
            detail += "; live error: %s" % search_error
        elif armed is False:
            detail += "; the live envelope is not armed"
        return _bad(
            "no candidates for %s (%s)" % (repr(", ".join(terms)), detail)
        )

    rows = rows[:limit]
    return {
        "ok": True,
        "tool": TOOL_SCAN_PRODUCTS,
        "data": {
            "query": text(query) or None,
            "keywords": terms,
            "match_all": match_all,
            "live_requested": live,
            "source": source,
            "cache": cache,
            "count": len(rows),
            "candidates": [dict(row) for row in rows],
            "search_error": search_error,
            "note": (
                "Candidates as the scanner stored or returned them. Economics "
                "are not computed here; score them with golden_goose_scan."
            ),
        },
    }


TOOLS = {TOOL_SCAN_PRODUCTS: scan_products}
