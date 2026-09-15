"""Costco Data Importer

Reads Costco product data from local files:
- `data/costco-items.csv` — item list with UPC, title, price, category
- `data/costco-api-catalog.json` — API-enriched catalog (UPC→ASIN mappings)

Maps Costco items to Amazon ASINs by:
1. UPC lookup (exact match in Amazon catalog)
2. Title similarity matching
3. Category-based filtering

Updates the products table with COGS (cost of goods sold) data.

Usage:
    importer = CostcoImporter(db)
    result = importer.import_from_files()
    unmapped = importer.get_unmapped_items()
"""

import os
import csv
import json
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class CostcoImporter:
    """Import Costco catalog data and map to Amazon ASINs.

    Reads from local CSV and JSON files in the data directory. Maps
    Costco items to existing products in the Northstar database by
    UPC or title matching.

    Usage:
        importer = CostcoImporter(db)

        # Full import from default data files
        result = importer.import_from_files()

        # Import from specific files
        result = importer.import_from_files(
            csv_path="path/to/items.csv",
            json_path="path/to/catalog.json",
        )

        # Get items without ASIN mappings
        unmapped = importer.get_unmapped_items()
    """

    def __init__(self, db=None, data_dir: Optional[str] = None):
        from data_layer import get_db, NorthstarDB

        if db is None:
            db = get_db()
        self.db = db
        self.nsdb = NorthstarDB()
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._items_cache: List[Dict[str, Any]] = []
        self._upc_to_asin: Dict[str, str] = {}

    @property
    def is_configured(self) -> bool:
        """Check if Costco data files exist."""
        csv_path = self.data_dir / "costco-items.csv"
        json_path = self.data_dir / "costco-api-catalog.json"
        return csv_path.exists() or json_path.exists()

    # ---- Main Import ----

    def import_from_files(
        self,
        csv_path: Optional[str] = None,
        json_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Costco data from local files and map to ASINs.

        Args:
            csv_path: Path to costco-items.csv. If None, uses default.
            json_path: Path to costco-api-catalog.json. If None, uses default.

        Returns:
            {"imported": int, "mapped": int, "unmapped": int, "errors": int,
             "details": [...]}
        """
        result = {
            "imported": 0,
            "mapped": 0,
            "unmapped": 0,
            "errors": 0,
            "details": [],
        }

        # Load data from both sources
        items = []

        csv_file = Path(csv_path) if csv_path else self.data_dir / "costco-items.csv"
        if csv_file.exists():
            items.extend(self._load_csv(csv_file))
        else:
            logger.info(f"Costco CSV not found: {csv_file}")

        json_file = Path(json_path) if json_path else self.data_dir / "costco-api-catalog.json"
        if json_file.exists():
            items.extend(self._load_json(json_file))
        else:
            logger.info(f"Costco JSON not found: {json_file}")

        if not items:
            result["reason"] = "no_data_files_found"
            return result

        # Deduplicate items by UPC
        items = self._deduplicate_items(items)
        self._items_cache = items

        # Build UPC-to-ASIN lookup from existing products
        self._build_upc_index()

        # Process each item
        for item in items:
            try:
                upc = item.get("upc", "")
                title = item.get("title", "")
                price = item.get("price", 0)
                costco_cost = item.get("costco_cost", price)
                category = item.get("category", "")
                weight = item.get("weight_lbs")

                # Try to find matching ASIN
                asin = self._find_matching_asin(item)

                if asin:
                    # Update the product with Costco COGS data
                    update_data = {
                        "asin": asin,
                        "costco_cost": costco_cost,
                        "cost_basis_source": f"costco:{upc or title[:30]}",
                    }
                    if weight:
                        update_data["weight_lbs"] = weight

                    self.nsdb.products.upsert(update_data)
                    result["mapped"] += 1
                    result["details"].append(
                        {
                            "title": title,
                            "upc": upc,
                            "asin": asin,
                            "costco_cost": costco_cost,
                            "status": "mapped",
                        }
                    )
                else:
                    # Insert as a Costco-only item (no Amazon ASIN yet)
                    result["unmapped"] += 1
                    result["details"].append(
                        {
                            "title": title,
                            "upc": upc,
                            "costco_cost": costco_cost,
                            "category": category,
                            "status": "unmapped",
                        }
                    )

                result["imported"] += 1

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing Costco item '{item.get('title', '?')}': {e}")

        logger.info(
            f"Costco import: {result['imported']} items, "
            f"{result['mapped']} mapped, {result['unmapped']} unmapped, "
            f"{result['errors']} errors"
        )
        return result

    # ---- File Loaders ----

    def _load_csv(self, path: Path) -> List[Dict[str, Any]]:
        """Load Costco items from CSV file.

        Expected columns (flexible naming):
        - Product Name / Title / Item Name
        - UPC / UPC Code
        - Price / Retail Price / Costco Price
        - Category / Department
        - Weight / Weight (lbs)
        - Item Number / SKU
        """
        items = []
        try:
            content = path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))

            for row in reader:
                item = self._normalize_csv_row(row)
                if item.get("title"):
                    items.append(item)

        except Exception as e:
            logger.error(f"Error reading Costco CSV {path}: {e}")

        return items

    def _load_json(self, path: Path) -> List[Dict[str, Any]]:
        """Load Costco catalog from JSON file.

        Expected format:
        [
            {
                "upc": "012345678901",
                "title": "Kirkland Signature Water",
                "price": 4.99,
                "category": "Beverages",
                "weight_lbs": 32.0,
                "asin": "B0123456789"  // optional pre-mapped ASIN
            },
            ...
        ]
        """
        items = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            if isinstance(data, list):
                raw_items = data
            elif isinstance(data, dict):
                # Might be wrapped in a key
                raw_items = data.get("items", data.get("products", data.get("data", [])))
                if not raw_items and isinstance(data, dict):
                    raw_items = [data]
            else:
                logger.warning(f"Unexpected JSON structure in {path}")
                return items

            for raw in raw_items:
                item = {
                    "upc": str(raw.get("upc", raw.get("UPC", ""))).strip(),
                    "title": str(raw.get("title", raw.get("name", raw.get("productName", "")))).strip(),
                    "price": self._parse_float(raw.get("price", raw.get("retailPrice", 0))),
                    "costco_cost": self._parse_float(
                        raw.get("costco_cost", raw.get("costcoCost", raw.get("price", 0)))
                    ),
                    "category": str(raw.get("category", raw.get("department", ""))).strip(),
                    "weight_lbs": self._parse_float(raw.get("weight_lbs", raw.get("weight"))),
                    "item_number": str(raw.get("item_number", raw.get("itemNumber", raw.get("sku", "")))).strip(),
                    "asin": str(raw.get("asin", "")).strip(),
                }
                if item.get("title"):
                    items.append(item)

        except Exception as e:
            logger.error(f"Error reading Costco JSON {path}: {e}")

        return items

    def _normalize_csv_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Normalize a CSV row to standard Costco item format."""
        # Map various header names to standard fields
        field_aliases = {
            "upc": ["upc", "upc code", "barcode", "upc_number"],
            "title": [
                "product name", "title", "item name", "product", "name",
                "product_name", "item_name",
            ],
            "price": [
                "price", "retail price", "costco price", "cost",
                "retail_price", "costco_price",
            ],
            "costco_cost": [
                "costco cost", "costco_cost", "costco_cost_per_unit",
                "cost", "wholesale_price", "wholesale price",
            ],
            "category": [
                "category", "department", "product category",
                "product_category",
            ],
            "weight_lbs": ["weight", "weight_lbs", "weight (lbs)", "lbs"],
            "item_number": [
                "item number", "item_number", "sku", "item #",
                "item_#",
            ],
        }

        item = {}
        row_lower = {k.lower().strip(): v for k, v in row.items()}

        for field, aliases in field_aliases.items():
            for alias in aliases:
                if alias in row_lower:
                    value = row_lower[alias]
                    if field in ("price", "costco_cost", "weight_lbs"):
                        item[field] = self._parse_float(value)
                    else:
                        item[field] = str(value).strip() if value else ""
                    break

        # Default costco_cost to price if not set
        if not item.get("costco_cost") and item.get("price"):
            item["costco_cost"] = item["price"]

        return item

    # ---- ASIN Matching ----

    def _build_upc_index(self):
        """Build a UPC-to-ASIN lookup from existing products."""
        self._upc_to_asin = {}
        # This would normally come from a UPC index; for now we store
        # UPCs that were previously imported via the cost_basis_source field
        cur = self.db.execute(
            "SELECT asin, cost_basis_source FROM products WHERE cost_basis_source LIKE 'costco:%'"
        )
        for row in cur.fetchall():
            source = row["cost_basis_source"] or ""
            if source.startswith("costco:"):
                upc_part = source.replace("costco:", "")
                if upc_part.isdigit():
                    self._upc_to_asin[upc_part] = row["asin"]

    def _find_matching_asin(self, item: Dict[str, Any]) -> Optional[str]:
        """Find a matching Amazon ASIN for a Costco item.

        Matching priority:
        1. Pre-mapped ASIN from JSON data
        2. UPC exact match in existing products
        3. Title similarity match against existing products

        Returns:
            ASIN string or None.
        """
        # 1. Pre-mapped ASIN from JSON
        pre_mapped = item.get("asin", "")
        if pre_mapped:
            return pre_mapped

        upc = item.get("upc", "")

        # 2. UPC match
        if upc and upc in self._upc_to_asin:
            return self._upc_to_asin[upc]

        # Try querying products table for UPC in data_sources
        if upc and len(upc) >= 8:
            cur = self.db.execute(
                "SELECT asin FROM products WHERE data_sources LIKE ?",
                (f"%{upc}%",),
            )
            row = cur.fetchone()
            if row:
                return row["asin"]

        # 3. Title similarity (only for items with meaningful titles)
        title = item.get("title", "")
        if len(title) < 10:
            return None

        # Search for title-like products
        # Use first few significant words
        words = [w for w in title.split() if len(w) > 3][:5]
        if not words:
            return None

        search_pattern = "%".join(words[:3])
        cur = self.db.execute(
            "SELECT asin, title FROM products WHERE title LIKE ?",
            (f"%{search_pattern}%",),
        )

        best_match = None
        best_score = 0.0

        for row in cur.fetchall():
            db_title = row["title"] or ""
            score = SequenceMatcher(None, title.lower(), db_title.lower()).ratio()
            if score > best_score and score >= 0.75:
                best_score = score
                best_match = row["asin"]

        return best_match

    # ---- Unmapped Items ----

    def get_unmapped_items(self) -> List[Dict[str, Any]]:
        """Get Costco items that don't have ASIN mappings.

        Returns:
            List of items without matching ASINs.
        """
        if not self._items_cache:
            self._load_items_cache()

        unmapped = []
        for item in self._items_cache:
            asin = self._find_matching_asin(item)
            if not asin:
                unmapped.append(item)

        return unmapped

    def _load_items_cache(self):
        """Load items into cache if not already loaded."""
        if self._items_cache:
            return

        csv_path = self.data_dir / "costco-items.csv"
        json_path = self.data_dir / "costco-api-catalog.json"

        if csv_path.exists():
            self._items_cache.extend(self._load_csv(csv_path))
        if json_path.exists():
            self._items_cache.extend(self._load_json(json_path))

        self._items_cache = self._deduplicate_items(self._items_cache)

    def _deduplicate_items(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Deduplicate items by UPC (prefer JSON over CSV data)."""
        seen_upcs: Dict[str, Dict[str, Any]] = {}
        no_upc: List[Dict[str, Any]] = []

        for item in items:
            upc = item.get("upc", "")
            if upc:
                if upc not in seen_upcs:
                    seen_upcs[upc] = item
                else:
                    # Merge: prefer the entry with more data
                    existing = seen_upcs[upc]
                    if self._item_score(item) > self._item_score(existing):
                        seen_upcs[upc] = item
            else:
                no_upc.append(item)

        return list(seen_upcs.values()) + no_upc

    @staticmethod
    def _item_score(item: Dict[str, Any]) -> int:
        """Score an item by how many fields are populated."""
        score = 0
        for key in ("upc", "title", "price", "category", "weight_lbs", "asin"):
            if item.get(key):
                score += 1
        return score

    @staticmethod
    def _parse_float(val: Any) -> Optional[float]:
        """Safely parse a float."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            cleaned = str(val).replace(",", "").replace("$", "").strip()
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

