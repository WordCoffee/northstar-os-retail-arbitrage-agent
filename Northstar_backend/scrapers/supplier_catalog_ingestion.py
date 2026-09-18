"""Supplier catalog price ingestion — public wholesale catalog -> products.

Ingests a wholesale supplier's public catalog (HTML scrape, JSON-LD product
markup, CSV/Excel download, or public API) into normalized ``supplier_products``
dicts that SuppliersDB.add_products() accepts directly.

Live/paid scraping is gated exactly like discovery:
  * ``SUPPLIER_CATALOG_LIVE_OPERATOR_APPROVED=1`` must be exactly "1" AND an
    explicit ``fetch_fn`` transport must be injected before any network call.
  * A built-in ``parse_csv`` parser is provided so operators can ingest a
    downloaded CSV/Excel price list immediately (the most common pre-account
    path) with zero live calls.

Normalization produced for every product dict:
    supplier_sku, product_name, brand, category_slug, pack_size,
    unit_count, wholesale_price, wholesale_currency, moq, availability,
    weight_lbs, scrape_confidence, source_file
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Defaults (mirror config/supplier_intelligence.json ingestion)
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_RPS = 1.0
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_PAGES = 100

# CSV column aliases accepted by the mapping parser (canonical -> aliases).
COLUMN_ALIASES: Dict[str, List[str]] = {
    "supplier_sku": ["sku", "item code", "item_code", "item #", "item number", "product code", "product_code", "upc"],
    "product_name": ["name", "product", "item name", "item_name", "product name", "product_name", "title", "description"],
    "brand": ["brand", "manufacturer", "mfgr", "vendor brand"],
    "category_slug": ["category", "department", "product category", "product_category"],
    "pack_size": ["pack", "pack size", "pack_size", "package size", "package_size", "size"],
    "unit_count": ["unit count", "unit_count", "units", "count", "quantity", "qty"],
    "wholesale_price": ["price", "wholesale price", "wholesale_price", "cost", "unit price", "unit_price", "list price"],
    "wholesale_currency": ["currency", "currency code", "currency_code"],
    "moq": ["moq", "minimum order quantity", "minimum_order_quantity", "min qty", "min_qty"],
    "availability": ["availability", "stock status", "stock_status", "status"],
    "weight_lbs": ["weight", "weight lbs", "weight_lbs", "ship weight", "ship_weight", "wt"],
}

LIFTGATE_ATTRS = ["liftgate", "tailgate", "ltl", "pallet", "dock"]


@dataclass
class CatalogIngestResult:
    """Outcome of one catalog ingestion run."""

    supplier_id: str
    products: List[Dict[str, Any]] = field(default_factory=list)
    rows_parsed: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    skip_reasons: List[str] = field(default_factory=list)
    source: Optional[str] = None
    live: bool = False
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "supplier_id": self.supplier_id,
            "products": self.products,
            "rows_parsed": self.rows_parsed,
            "rows_imported": self.rows_imported,
            "rows_skipped": self.rows_skipped,
            "skip_reasons": self.skip_reasons,
            "source": self.source,
            "live": self.live,
            "errors": self.errors,
        }


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "")
    if not s:
        return None
    m = re.match(r"^-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _to_int(v: Any) -> Optional[int]:
    f = _to_float(v)
    if f is None:
        return None
    try:
        return int(f)
    except (ValueError, TypeError):
        return None


def _strip_currency(v: Any) -> str:
    s = str(v or "").strip()
    if not s:
        return "USD"
    upper = s.upper()
    if upper in ("USD", "US", "$", "US$"):
        return "USD"
    if upper in ("CAD", "C$"):
        return "CAD"
    if upper in ("EUR", "€"):
        return "EUR"
    if upper in ("GBP", "£"):
        return "GBP"
    return upper[:3] if len(upper) == 3 else upper


def parse_pack_size(product_name: str, raw_pack: Any = None) -> Optional[str]:
    """Best-effort pack_size string (e.g. '360 ct' -> '360 ct')."""
    if raw_pack is not None and str(raw_pack).strip():
        return str(raw_pack).strip()[:60]
    if not product_name:
        return None
    m = re.search(r"(\d+)\s*(ct|count|cnt|pack|pk|tabs?|tablets?|capsules?|softgels?|oz|g|ml|pieces?|pcs?|bars?)\b", str(product_name), re.IGNORECASE)
    if m:
        return f"{m.group(1)} {m.group(2)}".lower()
    return None


def extract_unit_count(product_name: str, raw_count: Any = None) -> Optional[int]:
    """Best-effort unit count (number of sellable units)."""
    if raw_count is not None:
        n = _to_int(raw_count)
        if n is not None and n > 0:
            return n
    if not product_name:
        return None
    # '360 ct', '500 count', '24 pack'
    m = re.search(r"(\d{1,6})\s*(?:ct|count|cnt|pack|pk|tabs?|tablets?|capsules?|softgels?|pieces?|pcs?)\b", str(product_name), re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def detect_logistics(text: str) -> bool:
    """True when scraped text contains a liftgate/logistics signal."""
    t = str(text or "").lower()
    return any(kw in t for kw in LIFTGATE_ATTRS)


# ---------------------------------------------------------------------------
# CSV parsing (live-call-free; the primary pre-account path)
# ---------------------------------------------------------------------------

def matrix_to_products(
    rows: List[Dict[str, str]],
    supplier_id: str,
    source_file: Optional[str] = None,
) -> CatalogIngestResult:
    """Normalize a list of dict rows (CSV/Excel) into supplier products.

    Column mapping is alias-based (COLUMN_ALIASES) and case-insensitive;
    unknown columns are ignored. Rows missing a name or a positive price are
    skipped with a recorded reason.
    """
    if not rows:
        return CatalogIngestResult(supplier_id=supplier_id, source=source_file)

    # Build the canonical -> actual key map from the first row.
    first = rows[0]
    key_map: Dict[str, str] = {}
    if first:
        lowered = {str(k).strip().lower(): k for k in first.keys()}
        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in lowered:
                    key_map[canonical] = lowered[alias]
                    break

    result = CatalogIngestResult(supplier_id=supplier_id, source=source_file)
    for row in rows:
        result.rows_parsed += 1
        get = lambda k: row.get(key_map[k]) if k in key_map else None

        name = str(get("product_name") or "").strip()
        price = _to_float(get("wholesale_price"))
        if not name:
            result.rows_skipped += 1
            result.skip_reasons.append("missing product_name")
            continue
        if price is None or price <= 0:
            result.rows_skipped += 1
            result.skip_reasons.append(f"missing/zero price for '{name[:40]}'")
            continue

        unit_count = extract_unit_count(name, get("unit_count"))
        product: Dict[str, Any] = {
            "supplier_sku": str(get("supplier_sku") or "").strip() or None,
            "product_name": name,
            "brand": str(get("brand") or "").strip() or None,
            "category_slug": str(get("category_slug") or "").strip() or None,
            "pack_size": parse_pack_size(name, get("pack_size")),
            "unit_count": unit_count,
            "wholesale_price": round(price, 4),
            "wholesale_currency": _strip_currency(get("wholesale_currency")),
            "moq": _to_int(get("moq")),
            "availability": str(get("availability") or "").strip().lower() or "in_stock",
            "weight_lbs": _to_float(get("weight_lbs")),
            "scrape_confidence": 1.0,
            "source_file": source_file,
        }
        result.products.append(product)
        result.rows_imported += 1
    return result


def parse_csv_bytes(data: bytes, supplier_id: str, source_file: Optional[str] = None) -> CatalogIngestResult:
    """Parse raw CSV bytes (utf-8 / latin-1 tolerant) into products."""
    text = data.decode("utf-8-sig", errors="replace")
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(r) for r in reader]
    except Exception as exc:
        result = CatalogIngestResult(supplier_id=supplier_id, source=source_file)
        result.errors.append(f"CSV parse failed: {exc}")
        return result
    return matrix_to_products(rows, supplier_id, source_file)


# ---------------------------------------------------------------------------
# HTML / JSON-LD parsing (offline: operates on fetched bytes, never fetches)
# ---------------------------------------------------------------------------

def parse_html_catalog(
    html: str,
    supplier_id: str,
    source: Optional[str] = None,
    selectors: Optional[Dict[str, str]] = None,
) -> CatalogIngestResult:
    """Parse catalog HTML (BeautifulSoup) into supplier products.

    Pure parsing — the caller supplies the HTML bytes; this never fetches.
    Selector defaults come from config/supplier_intelligence.json.
    Best-effort: sites without recognizable product markup produce zero rows
    with a recorded error rather than garbage.
    """
    result = CatalogIngestResult(supplier_id=supplier_id, source=source, live=True)
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        result.errors.append("beautifulsoup4 not installed — install to parse HTML catalogs.")
        return result

    sel = selectors or {
        "product_card": ".product-item, .product-card, [itemtype*='Product']",
        "name": "h3, .product-title, [itemprop='name']",
        "price": ".price, [itemprop='price'], .wholesale-price",
        "sku": "[itemprop='sku'], .sku, .product-code",
    }
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        result.errors.append(f"HTML parse failed: {exc}")
        return result

    cards = soup.select(sel["product_card"])
    if not cards:
        # Fall back to JSON-LD product markup.
        return _parse_json_ld(html, supplier_id, source)

    for card in cards:
        result.rows_parsed += 1
        name_el = card.select_one(sel["name"])
        price_el = card.select_one(sel["price"])
        sku_el = card.select_one(sel["sku"])
        name = name_el.get_text(strip=True) if name_el else ""
        price = _to_float(price_el.get_text(strip=True) if price_el else None)
        if not name or price is None or price <= 0:
            result.rows_skipped += 1
            result.skip_reasons.append("card missing name/price")
            continue
        product: Dict[str, Any] = {
            "supplier_sku": sku_el.get_text(strip=True) if sku_el else None,
            "product_name": name[:200],
            "brand": None,
            "category_slug": None,
            "pack_size": parse_pack_size(name),
            "unit_count": extract_unit_count(name),
            "wholesale_price": round(price, 4),
            "wholesale_currency": "USD",
            "moq": None,
            "availability": "in_stock",
            "weight_lbs": _to_float(price_el.get("data-weight")) if price_el else None,
            "scrape_confidence": 0.85,
            "source_file": source,
        }
        result.products.append(product)
        result.rows_imported += 1
    return result


def _parse_json_ld(html: str, supplier_id: str, source: Optional[str]) -> CatalogIngestResult:
    result = CatalogIngestResult(supplier_id=supplier_id, source=source, live=True)
    import re as _re
    blocks = _re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        _re.DOTALL | _re.IGNORECASE,
    )
    for block in blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        items = data.get("@graph", [data]) if isinstance(data, dict) else data
        for item in items:
            if not isinstance(item, dict) or item.get("@type") not in ("Product", "ItemList", "OfferCatalog"):
                products_list = item.get("itemListElement") if isinstance(item, dict) else None
                if isinstance(products_list, list):
                    for entry in products_list:
                        if isinstance(entry, dict):
                            off = entry.get("item") or entry
                            result.rows_parsed += 1
                            _append_ld_product(result, off)
                continue
            # Direct product or a list embedded in itemListElement.
            if "itemListElement" in item:
                for entry in item["itemListElement"]:
                    if isinstance(entry, dict):
                        result.rows_parsed += 1
                        _append_ld_product(result, entry.get("item") or entry)
            elif isinstance(data, dict) and data.get("hasPart"):
                for part in data["hasPart"]:
                    if isinstance(part, dict):
                        result.rows_parsed += 1
                        _append_ld_product(result, part)
            else:
                result.rows_parsed += 1
                _append_ld_product(result, item)
    return result


def _append_ld_product(result: CatalogIngestResult, item: Dict[str, Any]) -> None:
    if not isinstance(item, dict):
        return
    name = str(item.get("name") or "").strip()
    offers = item.get("offers")
    if isinstance(offers, dict):
        price = _to_float(offers.get("price"))
    elif isinstance(offers, list) and offers:
        price = _to_float(offers[0].get("price"))
    else:
        price = _to_float(item.get("offers").get("price")) if isinstance(item.get("offers"), dict) else _to_float(item.get("price"))
    price = _to_float(price)
    sku = str(item.get("sku") or "").strip() or None
    if not name or price is None or price <= 0:
        result.rows_skipped += 1
        result.skip_reasons.append("json-ld missing name/price")
        return
    result.products.append({
        "supplier_sku": sku,
        "product_name": name[:200],
        "brand": str(item.get("brand", {}).get("name") or "") if isinstance(item.get("brand"), dict) else str(item.get("brand") or ""),
        "category_slug": None,
        "pack_size": parse_pack_size(name),
        "unit_count": extract_unit_count(name),
        "wholesale_price": round(price, 4),
        "wholesale_currency": "USD",
        "moq": None,
        "availability": "in_stock",
        "weight_lbs": None,
        "scrape_confidence": 0.9,
        "source_file": result.source,
    })
    result.rows_imported += 1


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class SupplierCatalogIngestion:
    """Ingest a supplier's public catalog into normalized products.

    ``mode="offline"`` (default): parse CSV/HTML/JSON-LD the caller provides —
    zero network. ``mode="live"``: fetch via the injected ``fetch_fn`` (URL ->
    bytes) and parse the result; only when the operator gate is armed.
    """

    def __init__(
        self,
        fetch_fn: Optional[Callable[[str], bytes]] = None,
        gate_env: str = "SUPPLIER_CATALOG_LIVE_OPERATOR_APPROVED",
    ) -> None:
        self.fetch_fn = fetch_fn
        self.gate_env = gate_env
        self.last_error: Optional[str] = None

    def live_armed(self) -> bool:
        return os.environ.get(self.gate_env, "").strip() == "1"

    def ingest_csv(
        self,
        supplier_id: str,
        csv_bytes: bytes,
        source_file: Optional[str] = None,
    ) -> CatalogIngestResult:
        return parse_csv_bytes(csv_bytes, supplier_id, source_file)

    def ingest_html(
        self,
        supplier_id: str,
        html: str,
        source: Optional[str] = None,
    ) -> CatalogIngestResult:
        return parse_html_catalog(html, supplier_id, source)

    def ingest_url(
        self,
        supplier_id: str,
        url: str,
    ) -> CatalogIngestResult:
        """Live URL fetch -> parse. Gated: never auto-fetches."""
        if not self.live_armed():
            self.last_error = (
                f"Live catalog fetch gated: set {self.gate_env}=1 with an injected fetch_fn."
            )
            return CatalogIngestResult(supplier_id=supplier_id, source=url, live=True)
        if not self.fetch_fn:
            self.last_error = "Live catalog fetch requires an injected fetch_fn transport."
            return CatalogIngestResult(supplier_id=supplier_id, source=url, live=True)
        try:
            data = self.fetch_fn(url)
        except Exception as exc:
            self.last_error = f"Catalog fetch error: {exc}"
            return CatalogIngestResult(supplier_id=supplier_id, source=url, live=True)
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = str(data)
        return parse_html_catalog(text, supplier_id, url)