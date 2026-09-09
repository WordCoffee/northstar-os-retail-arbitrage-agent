#!/usr/bin/env python3
"""
Kirkland Costco Evidence Merge

Consolidates the freshest Costco product evidence captured by the Bright Data
Web Unlocker stage-3 catalog pull (frozen per-item run dirs under
`Northstar_backend/data/costco-discovery-runs/*/normalized/`) into the
layer-2 product-detail store (`data/costco-product-detail.json`) that the
discovery pipeline's `resolve_costco_cost` reads during Costco
cross-reference.

Merge rules (identical to `refresh_product_details`):
  - Latest evidence wins per costco_item_id (by captured/requested time).
  - Only items with a parsed `item` dict and a positive `listed_price` are
    imported; parse failures / URL-not-found / zero-price records are skipped.
  - Existing detail-store records whose costco_item_id is refreshed are
    replaced; all other existing records are preserved.

Offline only: reads local run-dir JSON, writes the local detail store.
Never performs network calls and never fabricates costs.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import costco_api_client as cac

RUNS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "costco-discovery-runs")

# Prices at or below this are capture artifacts (out-of-stock placeholders,
# $0.01 "available online" tokens), not sellable unit costs. Records below
# this floor are never imported and are purged if already in the store.
MIN_PLAUSIBLE_PRICE = 1.0

# Evidence platform -> (layer-2 source, cost_basis) mapping. Provenance must
# reflect the provider that ACTUALLY served the page (Bright Data vs the
# Firecrawl fallback), not a hard-coded vendor label.
SOURCE_BY_PLATFORM = {
    "web_unlocker_costco_page": ("brightdata_web_unlocker", "brightdata_costco_page"),
    "firecrawl_scrape": ("firecrawl_scrape", "firecrawl_costco_page"),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_normalized_files(runs_root: str = RUNS_ROOT) -> List[str]:
    found = []
    if not os.path.isdir(runs_root):
        return found
    for run_dir in os.listdir(runs_root):
        normalized = os.path.join(runs_root, run_dir, "normalized")
        if not os.path.isdir(normalized):
            continue
        for name in os.listdir(normalized):
            if name.startswith("items_") and name.endswith(".json"):
                found.append(os.path.join(normalized, name))
    return sorted(found)


def latest_wins_by_item(files: List[str]) -> Dict[str, Dict[str, Any]]:
    """Latest evidence per costco_item_id. A file with the more recent
    captured/requested timestamp and a populated item wins over an older or
    empty one."""
    best: Dict[str, Dict[str, Any]] = {}
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        item = rec.get("item") or {}
        if not item:
            continue
        item_id = item.get("returned_costco_item_id") or item.get("requested_item_id")
        if not item_id:
            continue
        item_id = str(item_id).strip()
        ts = item.get("captured_at") or rec.get("requested_at") or ""
        prev = best.get(item_id)
        if prev is None or ts > (prev.get("_evidence_ts") or ""):
            rec["_evidence_ts"] = ts
            best[item_id] = rec
    return best


def to_detail_record(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert one normalized detail-evidence file into a layer-2
    product-detail record (schema of `_normalize_detail_item`). Provenance
    (source/cost_basis) follows the platform that actually served the page."""
    item = rec.get("item") or {}
    price = item.get("listed_price")
    if price is None or not isinstance(price, (int, float)) or price < MIN_PLAUSIBLE_PRICE:
        return None
    name = item.get("exact_title")
    if not name:
        return None
    item_id = str(item.get("returned_costco_item_id") or item.get("requested_item_id") or "").strip()
    captured = item.get("captured_at") or rec.get("requested_at") or _iso_now()
    source, cost_basis = SOURCE_BY_PLATFORM.get(
        rec.get("platform"),
        (
            str(rec.get("provider") or "unknown").lower(),
            "costco_online",
        ),
    )
    return {
        "item_name": name,
        "raw_title": name,
        "costco_item_id": item_id,
        "upc_or_ean": item.get("UPC_GTIN_EAN") or None,
        "brand": item.get("brand"),
        "product_line": None,
        "formula_or_flavor": None,
        "net_weight": None,
        "unit_of_measure": None,
        "pack_count": None,
        "case_count": None,
        "current_price": float(price),
        "sale_price": None,
        "price_basis": "regular",
        "warehouse_or_zip": None,
        "product_url": item.get("product_url"),
        "quantity_or_pack": item.get("quantity_or_pack"),
        "cost_basis": cost_basis,
        "cost_status": "detail_only",
        "source": source,
        "identity_match_status": item.get("identity_match_status"),
        "fetched_at": captured,
        "last_seen_at": captured,
    }


def run_merge(runs_root: str = RUNS_ROOT) -> Dict[str, Any]:
    files = iter_normalized_files(runs_root)
    winners = latest_wins_by_item(files)
    fresh: List[Dict[str, Any]] = []
    skipped = {"no_item": 0, "no_price": 0, "not_imported_above": 0}
    for item_id in sorted(winners):
        rec = winners[item_id]
        item = rec.get("item") or {}
        if not item:
            skipped["no_item"] += 1
            continue
        record = to_detail_record(rec)
        if record is None:
            skipped["no_price"] += 1
            continue
        if not record["costco_item_id"]:
            skipped["not_imported_above"] += 1
            continue
        fresh.append(record)

    existing = cac._load_product_details()
    fresh_ids = {r["costco_item_id"] for r in fresh}
    # Invalid-price rows are purged ONLY when they are not being replaced by
    # fresh evidence for the same id (a refreshed id is fully replaced below).
    existing = [
        r for r in existing
        if r.get("costco_item_id") in fresh_ids
        or (r.get("current_price") or 0) >= MIN_PLAUSIBLE_PRICE
    ]
    merged = [r for r in existing if r.get("costco_item_id") not in fresh_ids]
    merged.extend(fresh)
    merged.sort(key=lambda r: (r.get("item_name") or ""))

    path = cac._save_product_details(merged)

    summary = {
        "status": "ok",
        "run_at": _iso_now(),
        "evidence_files_scanned": len(files),
        "unique_item_ids_with_evidence": len(winners),
        "records_imported": len(fresh),
        "records_preserved": len(merged) - len(fresh),
        "records_total": len(merged),
        "skipped": skipped,
        "path": path,
    }
    return summary


def main() -> int:
    summary = run_merge()
    print(json.dumps(summary, indent=2))
    if summary["records_total"]:
        detail = cac._load_product_details()
        print("\nSample imported records:")
        for r in detail[-5:]:
            print("  %s | %s | $%s" % (r.get("costco_item_id"), (r.get("item_name") or "")[:70], r.get("current_price")))
    return 0 if summary["records_imported"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())