"""Live catalog — stock-first reads + pull-on-miss writes into ProductsDB.

The "stock, then filter" model (docs/DATA_STREAMS.md):

1. Services read **stocked** live rows first — fast, $0 (``get_stocked``).
2. A miss can **pull fresh** through the free-tier router and stock the result
   (``stock`` / ``get_or_pull``).
3. Every pull is recorded in ``live_pulls`` (append-only audit) and the row is
   tagged with provider provenance + a freshness window.

Live pulls honor the §3 gate (``run_task(..., live_armed=...)``): nothing fires
unless the operator envelope is armed. Offline by default.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict, List, Optional

# Default freshness window for stocked rows (override: NORTHSTAR_STOCK_TTL_SECONDS).
STOCK_TTL_SECONDS = int(os.environ.get("NORTHSTAR_STOCK_TTL_SECONDS", str(24 * 3600)))


def _db():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data_layer import get_northstar_db
    return get_northstar_db()


def get_stocked(category: Optional[str] = None, limit: int = 500,
                fresh_only: bool = True) -> List[Dict[str, Any]]:
    """Stock-first read: fresh live rows from ProductsDB (no network)."""
    return _db().products.list_stocked(category=category, limit=limit, fresh_only=fresh_only)


def _normalize_row(raw: Any, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Map a provider search row to a products-table row (ASIN required)."""
    if not isinstance(raw, dict):
        return None
    asin = raw.get("asin") or raw.get("ASIN")
    if not asin:
        return None
    return {
        "asin": asin,
        "title": raw.get("title") or raw.get("name"),
        "brand": raw.get("brand"),
        "category": raw.get("category"),
        "amazon_price": raw.get("price") if raw.get("price") is not None else raw.get("amazon_price"),
        "rating": raw.get("rating"),
        "review_count": raw.get("review_count") or raw.get("reviews"),
        "data_sources": {"source": "live_search", "last_query": query},
    }


def stock(query: str, caller: Optional[Callable] = None, pages: int = 1,
          provider_id: Optional[str] = None, ttl_seconds: int = STOCK_TTL_SECONDS,
          live: bool = False, task_type: Optional[str] = None) -> Dict[str, Any]:
    """Pull live search results and upsert them into ProductsDB.

    Returns a summary dict. No network unless ``live=True`` and the §3 envelope
    is armed. ``caller`` may be injected for tests.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from agents.golden_goose_finder.free_tier_router import (
        run_task, TASK_AMAZON_SEARCH, is_live_approved,
    )
    from agents.golden_goose_finder import amazon_adapters

    if task_type is None:
        task_type = TASK_AMAZON_SEARCH
    if caller is None:
        caller = amazon_adapters.make_chocodata_search_caller(query, pages=pages)

    # §3: a live pull fires only when the operator envelope is armed.
    armed = bool(live) and is_live_approved()
    res = run_task(task_type, caller, live_armed=armed)
    result = getattr(res, "result", None)
    rows = result if isinstance(result, list) else ([result] if result else [])

    provider = provider_id or getattr(res, "chosen_provider_id", None)
    if not provider and getattr(res, "attempts", None):
        provider = res.attempts[-1].provider_id

    db = _db()
    stocked = 0
    for raw in rows:
        row = _normalize_row(raw, query=query)
        if not row:
            continue
        db.products.upsert_live(row, provider_id=provider or "unknown", ttl_seconds=ttl_seconds)
        stocked += 1

    mode = getattr(res, "mode", None)
    # Audit only real dispatch attempts (not blocked/gated no-ops).
    if mode not in ("blocked", "invalid_task") or stocked:
        db.live_pulls.record(
            query=query, task_type=task_type, provider_id=provider or "none",
            rows_returned=stocked, ok=bool(getattr(res, "ok", False)),
            error=getattr(res, "error", None),
        )
    return {
        "stocked": stocked, "provider": provider,
        "mode": mode, "ok": bool(getattr(res, "ok", False)),
        "error": getattr(res, "error", None),
    }


def _search_stock(query: str, category: Optional[str] = None,
                  limit: int = 50) -> List[Dict[str, Any]]:
    rows = get_stocked(category=category, limit=1000)
    q = (query or "").strip().lower()
    if q:
        terms = [t for t in q.split() if t]
        rows = [r for r in rows if all(t in ((r.get("title") or "").lower()) for t in terms)]
    return rows[:limit]


def get_or_pull(query: str, category: Optional[str] = None, limit: int = 50,
                live: bool = False, **stock_kwargs: Any) -> Dict[str, Any]:
    """Stock-first read; on an empty stock hit and ``live``, pull fresh + re-read.

    Honest states: ``source`` is ``stock`` | ``empty`` | ``live`` | ``live_empty``.
    """
    rows = _search_stock(query, category=category, limit=limit)
    if rows:
        return {"source": "stock", "rows": rows, "pulled": None}
    if not live:
        return {"source": "empty", "rows": [], "pulled": None}
    pulled = stock(query, live=True, **stock_kwargs)
    rows = _search_stock(query, category=category, limit=limit)
    return {"source": "live" if rows else "live_empty", "rows": rows, "pulled": pulled}
