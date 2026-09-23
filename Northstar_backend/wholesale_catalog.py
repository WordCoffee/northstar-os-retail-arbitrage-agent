"""Wholesale catalog — stock wholesaler SKUs into the supplier warehouse.

Feeds the Golden Goose sourcing engine: pull a wholesaler catalog (primary
candidate: **Tundra**, a free B2B wholesale marketplace) via ``generic_scrape``,
normalize the rows, and persist them to ``suppliers`` + ``supplier_products``.
Golden Goose then scores stocked SKUs against Amazon sell-through.

No network unless ``live=True`` and the §3 envelope is armed. ``caller`` is
injectable for tests. Offline by default.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict, List, Optional

# Primary wholesaler candidate (docs/DATA_STREAMS.md §3).
TUNDRA = {
    "id": "tundra",
    "name": "Tundra",
    "public_catalog_url": "https://www.tundra.com",
    "api_auth_type": "none",
    "account_friction_level": "low",
    "requires_liftgate": 0,
    "categories_supplied": ["general merchandise", "home", "beauty", "consumables"],
    "decision_flag": "needs_manual_review",
    "logistics_notes": "Free B2B wholesale marketplace; no membership fee; scrapeable catalog.",
}


def _db():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data_layer import get_northstar_db
    return get_northstar_db()


def normalize_wholesale_row(raw: Any) -> Optional[Dict[str, Any]]:
    """Map a wholesaler catalog row to a supplier_products row (SKU or name required)."""
    if not isinstance(raw, dict):
        return None
    sku = raw.get("supplier_sku") or raw.get("sku")
    name = raw.get("product_name") or raw.get("name") or raw.get("title")
    if not sku and not name:
        return None
    price = raw.get("wholesale_price")
    if price is None:
        price = raw.get("price")
    return {
        "supplier_sku": sku,
        "product_name": name,
        "brand": raw.get("brand"),
        "category_slug": raw.get("category_slug") or raw.get("category"),
        "pack_size": raw.get("pack_size"),
        "unit_count": raw.get("unit_count") or raw.get("count"),
        "wholesale_price": price,
        "wholesale_currency": raw.get("wholesale_currency", "USD"),
        "moq": raw.get("moq"),
        "availability": raw.get("availability", "in_stock"),
        "weight_lbs": raw.get("weight_lbs"),
        "scrape_confidence": raw.get("scrape_confidence", 0.6),
        "source_file": raw.get("source_file"),
    }


def stock_supplier_catalog(supplier: Dict[str, Any],
                           rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Upsert the supplier then add its normalized products. Returns a summary."""
    db = _db()
    sup = dict(supplier)
    db.suppliers.upsert(sup)
    supplier_id = sup.get("id")
    normalized = [r for r in (normalize_wholesale_row(x) for x in rows) if r]
    added = db.suppliers.add_products(supplier_id, normalized) if normalized else 0
    return {"supplier_id": supplier_id, "added": added, "skipped": len(rows) - len(normalized)}


def stock_wholesale(query: str, supplier: Optional[Dict[str, Any]] = None,
                    caller: Optional[Callable] = None, live: bool = False,
                    pages: int = 1) -> Dict[str, Any]:
    """Pull a wholesaler catalog page via generic_scrape and stock it.

    No network unless ``live=True`` and the §3 envelope is armed. ``caller`` is
    required for a live pull (there is no default Tundra scraper yet).
    """
    sup = dict(supplier or TUNDRA)
    if caller is None:
        return {"supplier_id": sup.get("id"), "added": 0, "skipped": 0,
                "ok": False, "mode": "no_caller",
                "error": "no wholesaler caller configured (Tundra scraper pending)"}

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from agents.golden_goose_finder.free_tier_router import run_task, TASK_GENERIC_SCRAPE
    from agents.golden_goose_finder import free_tier_registry  # noqa: F401

    res = run_task(TASK_GENERIC_SCRAPE, caller, live_armed=live)
    result = getattr(res, "result", None)
    rows = result if isinstance(result, list) else ([result] if result else [])
    normalized = [r for r in (normalize_wholesale_row(x) for x in rows) if r]

    db = _db()
    db.suppliers.upsert(sup)
    added = db.suppliers.add_products(sup.get("id"), normalized) if normalized else 0

    provider = getattr(res, "chosen_provider_id", None)
    db.live_pulls.record(query=query, task_type=TASK_GENERIC_SCRAPE,
                         provider_id=provider or "none", rows_returned=added,
                         ok=bool(getattr(res, "ok", False)), error=getattr(res, "error", None))
    return {"supplier_id": sup.get("id"), "added": added,
            "skipped": len(rows) - len(normalized), "provider": provider,
            "mode": getattr(res, "mode", None), "ok": bool(getattr(res, "ok", False)),
            "error": getattr(res, "error", None)}


def list_stocked_supplier_products(supplier_id: Optional[str] = None,
                                   limit: int = 500) -> List[Dict[str, Any]]:
    """Stock-first read of supplier_products (for Golden Goose scoring)."""
    db = _db()
    if supplier_id:
        return db.suppliers.get_products(supplier_id, limit=limit)
    cur = db._layer.execute(
        "SELECT * FROM supplier_products ORDER BY scraped_at DESC LIMIT ?", (limit,)
    )
    return [dict(r) for r in cur.fetchall()]
