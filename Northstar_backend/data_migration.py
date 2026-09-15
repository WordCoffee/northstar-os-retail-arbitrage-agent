"""Northstar OS - CSV/JSON -> Database Migration Script

Reads existing data files (CSV, JSON) and imports them into the database
(SQLite for local dev, PostgreSQL when configured). Designed to be idempotent:
running it multiple times never duplicates data.

Data sources:
  - data/costco-items.csv          -> products (costco_cost)
  - data/costco-api-catalog.json   -> products (enriched Costco fields)
  - data/seller-offer-cache.json   -> products (amazon_price, bsr, seller data)
  - data/enriched-offer-cache.json -> products (enrichment layer)
  - data/amazon-market-snapshots.json -> products (market snapshot data)
  - data/costco-amazon-mapping.json   -> products (ASIN↔Costco linkage)

Usage:
    python data_migration.py --all
    python data_migration.py --costco
    python data_migration.py --seller-cache
    python data_migration.py --market-snapshots
    python data_migration.py --mapping
    python data_migration.py --review-queue
    python data_migration.py --status
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Project imports - resolve paths relative to this file
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_DATA_DIR = _REPO_ROOT / "data"

# Import the data layer (SQLite / Postgres abstraction)
sys.path.insert(0, str(_BACKEND_DIR))
from data_layer import DataLayer, get_db, ProductsDB, AuditDB  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("data_migration")

# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1", "cp1252")


def _read_text_file(path: Path) -> str:
    """Read a text file, trying multiple encodings."""
    for enc in _CSV_ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise UnicodeError(
        f"Could not decode {path} with any of: {_CSV_ENCODINGS}"
    )


def _load_json(path: Path) -> Any:
    """Load a JSON file with encoding fallback."""
    raw = _read_text_file(path)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Migration result tracking
# ---------------------------------------------------------------------------

class MigrationResult:
    """Tracks what was imported, skipped, or errored during migration."""

    def __init__(self, source: str):
        self.source = source
        self.inserted = 0
        self.updated = 0
        self.skipped = 0
        self.errors: List[str] = []
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None

    def mark_finished(self):
        self.finished_at = datetime.now(timezone.utc)

    @property
    def total_processed(self) -> int:
        return self.inserted + self.updated + self.skipped

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def summary(self) -> str:
        return (
            f"[{self.source}] "
            f"inserted={self.inserted} updated={self.updated} "
            f"skipped={self.skipped} errors={len(self.errors)} "
            f"duration={self.duration_seconds:.2f}s"
        )


# ---------------------------------------------------------------------------
# Helper: upsert product (merge, don't overwrite non-null with null)
# ---------------------------------------------------------------------------

def _safe_upsert_product(
    products_db: ProductsDB,
    data: Dict[str, Any],
    result: MigrationResult,
    source_label: str,
) -> None:
    """Upsert a product, merging fields (non-null overwrites, null skips)."""
    asin = data.get("asin", "").strip()
    if not asin:
        result.errors.append(f"Missing ASIN in {source_label}: {data.get('item_name', '?')}")
        return

    # Check existing product
    existing = products_db.get_by_asin(asin)

    if existing:
        # Merge: only overwrite fields that are explicitly non-null in new data
        merged: Dict[str, Any] = {}
        for key, new_val in data.items():
            if key in ("asin", "id", "created_at"):
                continue
            old_val = existing.get(key)
            # Overwrite if new value is non-None and (old was None or different)
            if new_val is not None and new_val != "" and new_val != old_val:
                merged[key] = new_val
        if merged:
            products_db.upsert({"asin": asin, **merged})
            result.updated += 1
        else:
            result.skipped += 1
    else:
        # New product - insert
        products_db.upsert(data)
        result.inserted += 1


# ---------------------------------------------------------------------------
# Source-specific migration functions
# ---------------------------------------------------------------------------

def migrate_costco_csv(
    db: DataLayer, product_upserts: List[Dict[str, Any]] | None = None
) -> MigrationResult:
    """Migrate data/costco-items.csv -> products table.

    CSV columns: item_name, costco_cost
    We create a pseudo-ASIN from the item name hash for unmatched items,
    or link via costco-amazon-mapping.json when available.
    """
    result = MigrationResult("costco-csv")
    csv_path = _DATA_DIR / "costco-items.csv"
    mapping_path = _DATA_DIR / "costco-amazon-mapping.json"

    if not csv_path.exists():
        result.errors.append(f"File not found: {csv_path}")
        result.mark_finished()
        return result

    # Load ASIN↔Costco mapping if available
    asin_map: Dict[str, str] = {}  # costco_title -> asin
    if mapping_path.exists():
        raw_map = _load_json(mapping_path)
        asin_map = {v.lower().strip(): k for k, v in raw_map.items()}

    products_db = ProductsDB(db)
    content = _read_text_file(csv_path)

    reader = csv.DictReader(io.StringIO(content))
    for row_num, row in enumerate(reader, start=2):
        try:
            item_name = (row.get("item_name") or "").strip()
            cost_str = (row.get("costco_cost") or "").strip()

            if not item_name:
                result.skipped += 1
                continue

            costco_cost = None
            if cost_str:
                costco_cost = float(cost_str.replace("$", "").replace(",", ""))

            # Try to find ASIN via title mapping
            asin = asin_map.get(item_name.lower().strip())

            product_data: Dict[str, Any] = {
                "costco_cost": costco_cost,
                "title": item_name,
                "brand": _extract_brand(item_name),
                "category": _infer_category(item_name),
                "cost_basis_source": "costco_csv",
                "data_sources": json.dumps(["costco_csv"]),
            }

            if asin:
                product_data["asin"] = asin
            else:
                # Generate deterministic pseudo-ASIN for unmapped items
                pseudo_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"costco:{item_name}")
                product_data["asin"] = f"COST{str(pseudo_id)[:6].upper()}"

            _safe_upsert_product(products_db, product_data, result, f"csv:{row_num}")

        except Exception as exc:
            result.errors.append(f"Row {row_num}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_costco_api_catalog(db: DataLayer) -> MigrationResult:
    """Migrate data/costco-api-catalog.json -> products table.

    Richer Costco data: price, brand, pack_size, unit_of_measure, UPC, etc.
    """
    result = MigrationResult("costco-api-catalog")
    catalog_path = _DATA_DIR / "costco-api-catalog.json"

    if not catalog_path.exists():
        result.errors.append(f"File not found: {catalog_path}")
        result.mark_finished()
        return result

    catalog = _load_json(catalog_path)
    items = catalog.get("items", [])

    products_db = ProductsDB(db)

    # Load existing ASIN mapping for linkage
    mapping_path = _DATA_DIR / "costco-amazon-mapping.json"
    asin_map: Dict[str, str] = {}
    if mapping_path.exists():
        raw_map = _load_json(mapping_path)
        asin_map = {v.lower().strip(): k for k, v in raw_map.items()}

    for idx, item in enumerate(items):
        try:
            item_name = item.get("item_name", "").strip()
            if not item_name:
                result.skipped += 1
                continue

            asin = asin_map.get(item_name.lower().strip())

            product_data: Dict[str, Any] = {
                "title": item_name,
                "brand": item.get("brand") or _extract_brand(item_name),
                "costco_cost": item.get("costco_cost") or item.get("regular_price"),
                "category": _infer_category(item_name),
                "cost_basis_source": "costco_online",
                "data_sources": json.dumps(["costco_api_catalog"]),
            }

            # Map additional fields
            if item.get("costco_item_id"):
                product_data["cost_basis_source"] = "costco_online"
            if item.get("pack_size"):
                product_data.setdefault("weight_lbs", None)
            if item.get("upc_or_ean"):
                product_data["upc"] = item["upc_or_ean"]
            if item.get("source_url"):
                product_data["costco_url"] = item["source_url"]
            if item.get("availability"):
                product_data["availability"] = item["availability"]
            if item.get("product_url"):
                product_data["product_url"] = item["product_url"]

            if asin:
                product_data["asin"] = asin
            else:
                pseudo_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"costco:{item_name}")
                product_data["asin"] = f"COST{str(pseudo_id)[:6].upper()}"

            _safe_upsert_product(products_db, product_data, result, f"api-catalog:{idx}")

        except Exception as exc:
            result.errors.append(f"Item {idx}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_seller_offer_cache(db: DataLayer) -> MigrationResult:
    """Migrate data/seller-offer-cache.json -> products table.

    Enriches products with Amazon pricing, seller counts, buy box data.
    """
    result = MigrationResult("seller-offer-cache")
    cache_path = _DATA_DIR / "seller-offer-cache.json"

    if not cache_path.exists():
        result.errors.append(f"File not found: {cache_path}")
        result.mark_finished()
        return result

    cache = _load_json(cache_path)
    products_db = ProductsDB(db)

    for asin, entry in cache.items():
        try:
            payload = entry.get("payload", {})
            if not payload:
                result.skipped += 1
                continue

            buy_box = payload.get("buy_box") or {}
            product_data: Dict[str, Any] = {
                "asin": asin,
                "seller_count": payload.get("total_sellers"),
                "data_sources": json.dumps(["seller_offer_cache"]),
            }

            # Map buy box price
            bb_price = buy_box.get("price")
            if bb_price is not None:
                product_data["buy_box_price"] = float(bb_price)
                product_data["amazon_price"] = float(bb_price)

            # Title from offer data
            title = payload.get("title")
            if title:
                product_data["title"] = title

            # Seller breakdown
            if payload.get("fba_sellers") is not None:
                product_data["fba_sellers"] = payload["fba_sellers"]

            # Enriched timestamp
            fetched_at = payload.get("offer_data_fetched_at")
            if fetched_at:
                product_data["last_enriched_at"] = fetched_at

            _safe_upsert_product(products_db, product_data, result, f"seller-cache:{asin}")

        except Exception as exc:
            result.errors.append(f"ASIN {asin}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_enriched_offer_cache(db: DataLayer) -> MigrationResult:
    """Migrate data/enriched-offer-cache.json -> products table.

    Secondary enrichment layer with price estimates and category data.
    """
    result = MigrationResult("enriched-offer-cache")
    cache_path = _DATA_DIR / "enriched-offer-cache.json"

    if not cache_path.exists():
        result.errors.append(f"File not found: {cache_path}")
        result.mark_finished()
        return result

    cache = _load_json(cache_path)
    products_db = ProductsDB(db)

    for asin, entry in cache.items():
        try:
            offer = entry.get("offer", {})
            if not offer:
                result.skipped += 1
                continue

            product_data: Dict[str, Any] = {"asin": asin}

            # Map enriched fields - only non-null values
            price = offer.get("amazon_price") or offer.get("buy_box_price")
            if price is not None:
                product_data["amazon_price"] = float(price)

            if offer.get("monthly_sales_estimate") is not None:
                product_data["monthly_sales_estimate"] = int(offer["monthly_sales_estimate"])

            if offer.get("fba_fee") is not None:
                product_data["fba_fee_estimate"] = float(offer["fba_fee"])

            if offer.get("amazon_category"):
                product_data["category"] = offer["amazon_category"]

            if offer.get("title"):
                product_data["title"] = offer["title"]

            enriched_at = offer.get("enriched_at")
            if enriched_at:
                product_data["last_enriched_at"] = enriched_at

            product_data["data_sources"] = json.dumps(["enriched_offer_cache"])

            _safe_upsert_product(products_db, product_data, result, f"enriched:{asin}")

        except Exception as exc:
            result.errors.append(f"ASIN {asin}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_market_snapshots(db: DataLayer) -> MigrationResult:
    """Migrate data/amazon-market-snapshots.json -> products table.

    Per-ASIN market snapshot with BSR, seller counts, and pricing.
    Also populates a market_snapshots table if it exists.
    """
    result = MigrationResult("market-snapshots")
    snap_path = _DATA_DIR / "amazon-market-snapshots.json"

    if not snap_path.exists():
        # Also check Northstar_backend/data/
        snap_path = _BACKEND_DIR / "data" / "amazon-market-snapshots.json"
        if not snap_path.exists():
            result.errors.append("File not found: amazon-market-snapshots.json")
            result.mark_finished()
            return result

    snap_data = _load_json(snap_path)
    asins_data = snap_data.get("asins", {})
    products_db = ProductsDB(db)

    # Ensure market_snapshots table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id TEXT PRIMARY KEY,
            asin TEXT NOT NULL,
            source TEXT,
            data_status TEXT,
            buy_box_price REAL,
            buy_box_seller TEXT,
            buy_box_fulfillment TEXT,
            total_sellers INTEGER,
            fba_sellers INTEGER,
            fbm_sellers INTEGER,
            amazon_sellers INTEGER,
            title TEXT,
            observed_at TEXT,
            recorded_at TEXT DEFAULT (datetime('now')),
            raw_payload TEXT
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_mkt_snap_asin ON market_snapshots(asin)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_mkt_snap_observed ON market_snapshots(observed_at)"
    )
    db.commit()

    for asin, snap in asins_data.items():
        try:
            buy_box = snap.get("buy_box") or {}
            seller_counts = snap.get("seller_counts") or {}

            # Update products table
            product_data: Dict[str, Any] = {
                "asin": asin,
                "data_sources": json.dumps(["market_snapshot"]),
            }
            if snap.get("title"):
                product_data["title"] = snap["title"]
            if buy_box.get("price") is not None:
                product_data["amazon_price"] = float(buy_box["price"])
                product_data["buy_box_price"] = float(buy_box["price"])
            if seller_counts.get("claimed_total") is not None:
                product_data["seller_count"] = int(seller_counts["claimed_total"])
            if snap.get("observed_at"):
                product_data["last_enriched_at"] = snap["observed_at"]

            _safe_upsert_product(products_db, product_data, result, f"snapshot:{asin}")

            # Insert into market_snapshots table for historical tracking
            snap_id = str(uuid.uuid4())
            raw_payload = json.dumps(snap, default=str)
            db.execute(
                """INSERT INTO market_snapshots
                   (id, asin, source, data_status, buy_box_price, buy_box_seller,
                    buy_box_fulfillment, total_sellers, fba_sellers, fbm_sellers,
                    amazon_sellers, title, observed_at, raw_payload)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snap_id,
                    asin,
                    snap.get("source"),
                    snap.get("data_status"),
                    buy_box.get("price"),
                    buy_box.get("seller_name"),
                    buy_box.get("fulfillment"),
                    seller_counts.get("claimed_total"),
                    seller_counts.get("fba_observed"),
                    seller_counts.get("fbm_observed"),
                    seller_counts.get("amazon_observed"),
                    snap.get("title"),
                    snap.get("observed_at"),
                    raw_payload,
                ),
            )

        except Exception as exc:
            result.errors.append(f"ASIN {asin}: {exc}")

    db.commit()
    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_asin_mapping(db: DataLayer) -> MigrationResult:
    """Migrate data/costco-amazon-mapping.json -> products table.

    Links Costco product titles to Amazon ASINs.
    """
    result = MigrationResult("asin-mapping")
    mapping_path = _DATA_DIR / "costco-amazon-mapping.json"

    if not mapping_path.exists():
        result.errors.append(f"File not found: {mapping_path}")
        result.mark_finished()
        return result

    raw_map = _load_json(mapping_path)
    products_db = ProductsDB(db)

    for asin, costco_title in raw_map.items():
        try:
            asin = asin.strip()
            if not asin or not costco_title:
                result.skipped += 1
                continue

            product_data: Dict[str, Any] = {
                "asin": asin,
                "title": costco_title.strip(),
                "brand": _extract_brand(costco_title),
                "costco_product_title": costco_title.strip(),
                "data_sources": json.dumps(["costco_amazon_mapping"]),
            }

            _safe_upsert_product(products_db, product_data, result, f"mapping:{asin}")

        except Exception as exc:
            result.errors.append(f"ASIN {asin}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_review_queue(db: DataLayer) -> MigrationResult:
    """Migrate data/enrich/costco-cogs-fill/review_queue.json.

    Imports items pending manual review into products with authorization_status.
    """
    result = MigrationResult("review-queue")
    queue_path = _BACKEND_DIR / "data" / "enrich" / "costco-cogs-fill" / "review_queue.json"

    if not queue_path.exists():
        result.errors.append(f"File not found: {queue_path}")
        result.mark_finished()
        return result

    queue_data = _load_json(queue_path)
    items = queue_data.get("review_queue", [])
    products_db = ProductsDB(db)

    for idx, item in enumerate(items):
        try:
            asin = item.get("asin", "").strip()
            if not asin:
                result.skipped += 1
                continue

            # Pick the best scoring option as the costco_cost
            options = item.get("options", [])
            best_cost = None
            best_costco_item = None
            if options:
                best = max(options, key=lambda o: o.get("score", 0))
                best_cost = best.get("price")
                best_costco_item = best.get("costco_item")

            product_data: Dict[str, Any] = {
                "asin": asin,
                "authorization_status": "needs_review",
                "costco_cost": best_cost,
                "data_sources": json.dumps(["review_queue"]),
            }
            if best_costco_item:
                product_data["title"] = best_costco_item
                product_data["brand"] = _extract_brand(best_costco_item)
                product_data["costco_product_title"] = best_costco_item

            _safe_upsert_product(products_db, product_data, result, f"review:{idx}")

        except Exception as exc:
            result.errors.append(f"Item {idx}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


def migrate_scored_snapshots(db: DataLayer) -> MigrationResult:
    """Migrate latest data/scored/*.json -> products table.

    Picks the most recent scored file and imports normalized Amazon data
    (price, rating, review count, monthly sales estimate).
    """
    result = MigrationResult("scored-snapshots")
    scored_dir = _DATA_DIR / "scored"

    if not scored_dir.exists() or not scored_dir.is_dir():
        result.errors.append(f"Directory not found: {scored_dir}")
        result.mark_finished()
        return result

    # Find latest scored file
    scored_files = sorted(scored_dir.glob("scored-*.json"), reverse=True)
    if not scored_files:
        result.errors.append("No scored files found")
        result.mark_finished()
        return result

    latest = scored_files[0]
    log.info(f"Using latest scored file: {latest.name}")

    scored_data = _load_json(latest)
    rows = scored_data.get("rows", [])
    products_db = ProductsDB(db)

    for idx, row in enumerate(rows):
        try:
            asin = row.get("asin", "").strip()
            if not asin:
                result.skipped += 1
                continue

            product_data: Dict[str, Any] = {
                "asin": asin,
                "data_sources": json.dumps(["scored_snapshot"]),
            }
            if row.get("title"):
                product_data["title"] = row["title"]
            if row.get("brand"):
                product_data["brand"] = row["brand"]
            if row.get("price") is not None:
                product_data["amazon_price"] = float(row["price"])
            if row.get("rating") is not None:
                product_data["rating"] = float(row["rating"])
            if row.get("reviewCount") is not None:
                product_data["review_count"] = int(row["reviewCount"])
            if row.get("monthlySold") is not None:
                product_data["monthly_sales_estimate"] = int(row["monthlySold"])

            _safe_upsert_product(products_db, product_data, result, f"scored:{idx}")

        except Exception as exc:
            result.errors.append(f"Row {idx}: {exc}")

    result.mark_finished()
    log.info(result.summary())
    return result


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _extract_brand(title: str) -> str:
    """Extract a rough brand name from a product title."""
    if not title:
        return ""
    lower = title.lower()
    if "kirkland" in lower:
        return "Kirkland Signature"
    # Take first 1-2 words as brand heuristic
    words = title.split()
    if len(words) >= 2:
        return words[0]
    return title


def _infer_category(title: str) -> str:
    """Rough category inference from product title keywords."""
    if not title:
        return ""
    lower = title.lower()
    category_map = [
        ("vitamin", "Health & Wellness"),
        ("minoxidil", "Health & Wellness"),
        ("fish oil", "Health & Wellness"),
        ("supplement", "Health & Wellness"),
        ("multivitamin", "Health & Wellness"),
        ("glucosamine", "Health & Wellness"),
        ("laundry", "Household"),
        ("dishwasher", "Household"),
        ("paper towel", "Household"),
        ("trash bag", "Household"),
        ("fabric softener", "Household"),
        ("tissue", "Household"),
        ("coffee", "Food & Beverage"),
        ("olive oil", "Food & Beverage"),
        ("almond", "Food & Beverage"),
        ("cashew", "Food & Beverage"),
        ("shrimp", "Food & Beverage"),
        ("applesauce", "Food & Beverage"),
        ("dog food", "Pet Supplies"),
        ("sock", "Apparel"),
        ("polo", "Apparel"),
        ("tee", "Apparel"),
        ("pant", "Apparel"),
        ("boxer", "Apparel"),
        ("jacket", "Apparel"),
        ("short", "Apparel"),
        ("pillow", "Home & Bedding"),
        ("mattress", "Home & Bedding"),
        ("golf", "Sports & Outdoors"),
    ]
    for keyword, category in category_map:
        if keyword in lower:
            return category
    return ""


# ---------------------------------------------------------------------------
# Status reporter
# ---------------------------------------------------------------------------

def report_status(db: DataLayer) -> None:
    """Print current database migration status."""
    cur = db.execute("SELECT COUNT(*) as cnt FROM products")
    total_products = cur.fetchone()["cnt"]

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE asin LIKE 'COST%'"
    )
    costco_only = cur.fetchone()["cnt"]

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE amazon_price IS NOT NULL"
    )
    with_price = cur.fetchone()["cnt"]

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE costco_cost IS NOT NULL"
    )
    with_cost = cur.fetchone()["cnt"]

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE net_profit IS NOT NULL"
    )
    scored = cur.fetchone()["cnt"]

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE authorization_status = 'needs_review'"
    )
    needs_review = cur.fetchone()["cnt"]

    # Check market_snapshots table
    try:
        cur = db.execute("SELECT COUNT(*) as cnt FROM market_snapshots")
        snapshots = cur.fetchone()["cnt"]
    except Exception:
        snapshots = 0

    # Data source breakdown
    cur = db.execute(
        """SELECT
            SUM(CASE WHEN data_sources LIKE '%costco_csv%' THEN 1 ELSE 0 END) as costco_csv,
            SUM(CASE WHEN data_sources LIKE '%costco_api_catalog%' THEN 1 ELSE 0 END) as costco_api,
            SUM(CASE WHEN data_sources LIKE '%seller_offer_cache%' THEN 1 ELSE 0 END) as seller_cache,
            SUM(CASE WHEN data_sources LIKE '%market_snapshot%' THEN 1 ELSE 0 END) as market_snap,
            SUM(CASE WHEN data_sources LIKE '%scored_snapshot%' THEN 1 ELSE 0 END) as scored,
            SUM(CASE WHEN data_sources LIKE '%costco_amazon_mapping%' THEN 1 ELSE 0 END) as mapping
           FROM products"""
    )
    sources = dict(cur.fetchone())

    print("\n" + "=" * 60)
    print("NORTHSTAR DATA MIGRATION STATUS")
    print("=" * 60)
    print(f"  Total products in DB:      {total_products}")
    print(f"  Costco-only (no ASIN):     {costco_only}")
    print(f"  With Amazon price:         {with_price}")
    print(f"  With Costco cost:          {with_cost}")
    print(f"  Scored (net_profit set):   {scored}")
    print(f"  Needs manual review:       {needs_review}")
    print(f"  Market snapshot records:   {snapshots}")
    print()
    print("  Data source coverage:")
    for src, count in sources.items():
        label = src.replace("_", " ").title() if src else "Unknown"
        print(f"    {label:30s} {count or 0}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main migration orchestrator
# ---------------------------------------------------------------------------

class DataMigration:
    """Orchestrates CSV/JSON -> database migration.

    Attributes:
        db: DataLayer instance (SQLite or Postgres).
        results: List of MigrationResult from each source.
    """

    def __init__(self, db: Optional[DataLayer] = None):
        self.db = db or get_db()
        self.results: List[MigrationResult] = []

    def run_all(self) -> List[MigrationResult]:
        """Run all migration sources in dependency order."""
        log.info("Starting full data migration (all sources)")
        self.results.clear()

        # Order matters: mapping first, then CSV, then API catalog,
        # then enrichment layers (each merges, never overwrites)
        self.results.append(migrate_asin_mapping(self.db))
        self.results.append(migrate_costco_csv(self.db))
        self.results.append(migrate_costco_api_catalog(self.db))
        self.results.append(migrate_seller_offer_cache(self.db))
        self.results.append(migrate_enriched_offer_cache(self.db))
        self.results.append(migrate_market_snapshots(self.db))
        self.results.append(migrate_review_queue(self.db))
        self.results.append(migrate_scored_snapshots(self.db))

        # Log summary
        AuditDB(self.db).log(
            action="data_migration_full",
            entity_type="system",
            details={
                "sources_run": len(self.results),
                "total_inserted": sum(r.inserted for r in self.results),
                "total_updated": sum(r.updated for r in self.results),
                "total_skipped": sum(r.skipped for r in self.results),
                "total_errors": sum(len(r.errors) for r in self.results),
            },
        )

        return self.results

    def run_costco(self) -> List[MigrationResult]:
        """Run Costco-specific migrations (CSV + API catalog + mapping)."""
        log.info("Running Costco data migration")
        self.results.clear()
        self.results.append(migrate_asin_mapping(self.db))
        self.results.append(migrate_costco_csv(self.db))
        self.results.append(migrate_costco_api_catalog(self.db))
        return self.results

    def run_seller_cache(self) -> MigrationResult:
        """Run seller offer cache migration."""
        result = migrate_seller_offer_cache(self.db)
        self.results = [result]
        return result

    def run_market_snapshots(self) -> MigrationResult:
        """Run market snapshot migration."""
        result = migrate_market_snapshots(self.db)
        self.results = [result]
        return result

    def run_mapping(self) -> MigrationResult:
        """Run ASIN mapping migration."""
        result = migrate_asin_mapping(self.db)
        self.results = [result]
        return result

    def run_review_queue(self) -> MigrationResult:
        """Run review queue migration."""
        result = migrate_review_queue(self.db)
        self.results = [result]
        return result

    def print_summary(self) -> None:
        """Print a human-readable summary of all migration results."""
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        for r in self.results:
            print(f"  {r.summary()}")
            for err in r.errors[:5]:  # Show first 5 errors per source
                print(f"    [!] {err}")
            if len(r.errors) > 5:
                print(f"    ... and {len(r.errors) - 5} more errors")
        print()

        total_ins = sum(r.inserted for r in self.results)
        total_upd = sum(r.updated for r in self.results)
        total_skip = sum(r.skipped for r in self.results)
        total_err = sum(len(r.errors) for r in self.results)
        print(f"  TOTAL: inserted={total_ins} updated={total_upd} "
              f"skipped={total_skip} errors={total_err}")
        print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for data migration."""
    parser = argparse.ArgumentParser(
        description="Northstar OS - Data Migration (CSV/JSON -> Database)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_migration.py --all           Run all migrations
  python data_migration.py --costco        Migrate Costco data only
  python data_migration.py --seller-cache  Migrate seller offer cache
  python data_migration.py --market-snapshots  Migrate market snapshots
  python data_migration.py --mapping       Migrate ASIN↔Costco mapping
  python data_migration.py --review-queue  Migrate review queue items
  python data_migration.py --scored        Migrate scored snapshot data
  python data_migration.py --status        Show current DB status
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all migrations")
    group.add_argument("--costco", action="store_true", help="Costco CSV + API catalog + mapping")
    group.add_argument("--seller-cache", action="store_true", help="Seller offer cache")
    group.add_argument("--market-snapshots", action="store_true", help="Market snapshot data")
    group.add_argument("--mapping", action="store_true", help="ASIN↔Costco mapping")
    group.add_argument("--review-queue", action="store_true", help="Review queue items")
    group.add_argument("--scored", action="store_true", help="Scored snapshot data")
    group.add_argument("--status", action="store_true", help="Show database status")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    migration = DataMigration()

    if args.status:
        report_status(migration.db)
        return

    if args.all:
        migration.run_all()
    elif args.costco:
        migration.run_costco()
    elif args.seller_cache:
        migration.run_seller_cache()
    elif args.market_snapshots:
        migration.run_market_snapshots()
    elif args.mapping:
        migration.run_mapping()
    elif args.review_queue:
        migration.run_review_queue()
    elif args.scored:
        result = migrate_scored_snapshots(migration.db)
        migration.results = [result]

    migration.print_summary()
    report_status(migration.db)


if __name__ == "__main__":
    main()
