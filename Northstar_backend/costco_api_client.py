"""Kirkland Signature discovery catalog (Costco.com / Business Delivery).

Only permitted/authorized access is used: the OpenWebNinja Real-Time
Costco Data API (Costco.com US/CA, one request per query) and, when an
Unwrangle key is configured, the Unwrangle Costco Business Delivery Search
API (one page = up to 96 products, 10 credits per page). Select the
provider with:

    COSTCO_CATALOG_SOURCE = OPENWEBNINJA | UNWRANGLE | (unset/invalid = OFF)

- OFF (default): the local CSV (data/costco-items.csv) is the only cost
  input; this module performs zero network calls.
- OPENWEBNINJA / UNWRANGLE: `refresh_catalog()` fetches, archives, and
  exports. Catalog builds are explicit (CLI or scheduled) and never run
  inside the scanner.

Discovery catalog contract:

- Append-only archive at data/costco-discovery-catalog.json. Existing
  records are NEVER overwritten or mutated; every fetch appends a new
  record (with its own fetched_at) for each clean item.
- Every record captures: product name, raw title (verbatim), Costco item
  ID, URL, current price, regular/sale status, pack size, unit count,
  source, location (defined delivery ZIP + Business Center), timestamp.
- Deduplication is conservative: within-run duplicate item IDs are
  skipped; pack-size and title conflicts (against the archive or existing
  CSV rows) are flagged for review and never attached a cost.
- Requests are rate-limited (COSTCO_CATALOG_REQUEST_DELAY_SECONDS between
  requests) and the run stops on blocks/errors (HTTP 401/403/429/5xx,
  timeouts, malformed responses); a stopped run preserves the last-good
  archive, snapshot, and CSV.
- Every cost is labeled cost_basis="costco_online" (OpenWebNinja) or
  "business_delivery_online" (Unwrangle) with cost_status="discovery_only":
  discovery and preliminary ROI only, never invoice-confirmed and never
  purchase authorization. A margin buffer (COSTCO_API_COST_BUFFER_PERCENT,
  default 10) is baked into the exported CSV cost until a Business Center
  invoice / confirmed walk-in price replaces it.
- Each run writes a run report (data/costco-catalog-run-report.json) with
  fetched / updated / skipped / held-for-review / failed counts.

Three-layer cost catalog:

- Layer 1 costco_catalog_live: the discovery snapshot above (search /
  category pull). Every record also carries the structured schema
  (costco_item_id, upc_or_ean, brand, product_line, formula_or_flavor,
  net_weight, unit_of_measure, pack_count, case_count, current_price,
  price_basis, warehouse_or_zip, product_url, last_seen_at, source).
- Layer 2 costco_product_detail (data/costco-product-detail.json): a
  per-item detail fetch (costco_item_id) that is only run for items that
  are potential Amazon matches. Research only (cost_status="detail_only"):
  an exact fingerprint here enables net/ROI but never authorizes a buy.
  Network refresh is gated by COSTCO_CATALOG_DETAIL_ENABLED=1 and is
  UNWRANGLE-only; offline imports are always available.
- Layer 3 costco_invoice_confirmed (data/costco-invoice-confirmed.json):
  Business Center invoice / order-history rows with real paid unit costs
  (cost_basis="invoice_confirmed"). Only an invoice-confirmed row that
  fingerprint-matches exactly may authorize a purchase (after Amazon
  listing checks). Imported via CLI, never fetched by the scanner.
- resolve_costco_cost() resolves an Amazon name across the three layers:
  exact invoice_confirmed > exact product_detail > exact CSV, then any
  non-exact (candidate/mismatch/unknown) from the same priority order as
  candidate_match (research view only, never COGS/ROI).
"""

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import requests

import costco_client

_ASIN_RE = re.compile(r"^[A-Za-z0-9]{10}$")

UNWRANGLE_URL = "https://data.unwrangle.com/api/getter/"
UNWRANGLE_PLATFORM = "costco_search"
UNWRANGLE_DETAIL_PLATFORM = "costco_detail"
OPENWEBNINJA_URL = "https://api.openwebninja.com/realtime-costco-data/search"
CREDITS_PER_PAGE = 10
REQUEST_TIMEOUT_SECONDS = 60
MATCH_RATIO_THRESHOLD = 0.70
DEFAULT_MAX_PAGES = 1
DEFAULT_QUERY = "kirkland"
DEFAULT_BUFFER_PERCENT = 10.0
DEFAULT_REQUEST_DELAY_SECONDS = 2.0
DEFAULT_DELIVERY_ZIP = "75201"
DEFAULT_BUSINESS_CENTER = "Dallas Business Center"

# Typed failure classification (Batch 08 contract). The 5 client-side
# failure states are exhaustive for the Costco/Unwrangle client; "success"
# is the only non-failure state. These values are added to the result
# dicts as `failure_type` so callers can distinguish auth/not_found/
# rate_limit/transport/malformed without parsing the `data_gaps` string.
FAILURE_TYPE_AUTH_ERROR = "auth_error"
FAILURE_TYPE_RATE_LIMITED = "rate_limited"
FAILURE_TYPE_NOT_FOUND = "not_found"
FAILURE_TYPE_TRANSPORT_ERROR = "transport_error"
FAILURE_TYPE_MALFORMED_RESPONSE = "malformed_response"
FAILURE_TYPE_SUCCESS = "success"

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

_PACK_PATTERN = re.compile(
    r"(\d+\s*x\s*)?\d+\s*(?:ct|count|counts?|packs?|pks?|pk|lb|lbs|oz|fl\s*\.?\s*oz|g|kg|l|ml|lt|rolls?|sheets?|ea|each|pairs?)",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> str:
    return os.path.dirname(_BACKEND_DIR)


def _snapshot_path() -> str:
    raw = os.getenv("COSTCO_CATALOG_SNAPSHOT_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(_project_root(), raw)
    return os.path.join(_project_root(), "data", "costco-api-catalog.json")


def catalog_source() -> str:
    raw = (os.getenv("COSTCO_CATALOG_SOURCE") or "").strip().upper()
    return raw if raw in ("OPENWEBNINJA", "UNWRANGLE") else "OFF"


def _buffer_percent() -> float:
    raw = os.getenv("COSTCO_API_COST_BUFFER_PERCENT")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DEFAULT_BUFFER_PERCENT
    return value if value >= 0 else DEFAULT_BUFFER_PERCENT


def _max_pages() -> int:
    raw = os.getenv("COSTCO_CATALOG_MAX_PAGES")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_MAX_PAGES
    return max(1, min(value, 20))


def _query() -> str:
    raw = os.getenv("COSTCO_CATALOG_QUERY")
    return raw.strip() if raw and raw.strip() else DEFAULT_QUERY


def _path_env(env_name: str, fallback_relative: str) -> str:
    raw = os.getenv(env_name)
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(_project_root(), raw)
    return os.path.join(_project_root(), fallback_relative)


def _archive_path() -> str:
    """Append-only discovery archive; records are never overwritten."""
    return _path_env("COSTCO_CATALOG_ARCHIVE_PATH", "data/costco-discovery-catalog.json")


def _run_report_path() -> str:
    return _path_env("COSTCO_CATALOG_RUN_REPORT_PATH", "data/costco-catalog-run-report.json")


def _detail_path() -> str:
    """Layer-2 product-detail research store; research only, never
    purchase authorization."""
    return _path_env("COSTCO_CATALOG_DETAIL_PATH", "data/costco-product-detail.json")


def _invoice_path() -> str:
    """Layer-3 invoice-confirmed store; exact paid COGS from Business
    Center invoices / order history."""
    return _path_env("COSTCO_INVOICE_PATH", "data/costco-invoice-confirmed.json")


def _detail_enabled() -> bool:
    return os.getenv("COSTCO_CATALOG_DETAIL_ENABLED", "").strip() == "1"


def _delivery_zip() -> str:
    raw = os.getenv("COSTCO_DELIVERY_ZIP")
    return raw.strip() if raw and raw.strip() else DEFAULT_DELIVERY_ZIP


def _business_center() -> str:
    raw = os.getenv("COSTCO_BUSINESS_CENTER")
    return raw.strip() if raw and raw.strip() else DEFAULT_BUSINESS_CENTER


def _location() -> Dict[str, str]:
    return {
        "delivery_zip": _delivery_zip(),
        "business_center": _business_center(),
    }


def _request_delay() -> float:
    """Seconds to sleep between catalog requests (rate limiting)."""
    raw = os.getenv("COSTCO_CATALOG_REQUEST_DELAY_SECONDS")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DEFAULT_REQUEST_DELAY_SECONDS
    return value if value >= 0 else DEFAULT_REQUEST_DELAY_SECONDS


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _safe_float(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _first_str(value) -> Optional[str]:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _first_int(value) -> Optional[int]:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def search_page(query: str, page: int) -> Dict[str, Any]:
    """Fetch one catalog page from the configured provider.

    Dispatches to the OpenWebNinja or Unwrangle fetch functions per
    COSTCO_CATALOG_SOURCE. Returns the documented safe shape for every
    outcome (missing key, network/HTTP failure, invalid JSON, success
    false, malformed results) and never raises.
    """
    source = catalog_source()
    if source == "OPENWEBNINJA":
        return _search_openwebninja(query)
    if source == "UNWRANGLE":
        return _search_unwrangle(query, page)
    result: Dict[str, Any] = {
        "source": "off",
        "platform": None,
        "search": query,
        "page": page,
        "success": False,
        "no_of_pages": None,
        "total_results": None,
        "result_count": 0,
        "items": [],
        "data_gaps": ["COSTCO_CATALOG_SOURCE is off; no catalog provider is configured."],
    }
    return result


def _search_openwebninja(query: str) -> Dict[str, Any]:
    """One OpenWebNinja Real-Time Costco Data request.

    Costco.com (US/Canada) search; one request per query. Free tier is 100
    requests/month. Auth is the x-api-key header.
    """
    result: Dict[str, Any] = {
        "source": "openwebninja",
        "platform": "costco_search",
        "search": query,
        "page": 1,
        "success": False,
        "failure_type": FAILURE_TYPE_TRANSPORT_ERROR,  # updated below on first success path
        "no_of_pages": 1,
        "total_results": None,
        "result_count": 0,
        "items": [],
        "data_gaps": [],
        "http_status": None,
    }

    api_key = os.getenv("OPENWEBNINJA_API_KEY")
    if not api_key:
        result["failure_type"] = FAILURE_TYPE_AUTH_ERROR
        result["data_gaps"].append("OpenWebNinja API key is not configured.")
        return result

    headers = {"X-API-Key": api_key}
    params = {"query": query, "country": "US", "count": 10}

    try:
        resp = requests.get(OPENWEBNINJA_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        result["failure_type"] = FAILURE_TYPE_TRANSPORT_ERROR
        result["data_gaps"].append("OpenWebNinja request timed out.")
        return result
    except requests.exceptions.RequestException:
        result["failure_type"] = FAILURE_TYPE_TRANSPORT_ERROR
        result["data_gaps"].append("OpenWebNinja request failed at the network level.")
        return result

    result["http_status"] = resp.status_code
    if resp.status_code in (401, 403):
        result["failure_type"] = FAILURE_TYPE_AUTH_ERROR
        result["data_gaps"].append(f"OpenWebNinja API returned HTTP {resp.status_code} (auth rejected).")
        return result
    if resp.status_code == 404:
        result["failure_type"] = FAILURE_TYPE_NOT_FOUND
        result["data_gaps"].append("OpenWebNinja API returned HTTP 404 (not found).")
        return result
    if resp.status_code == 429:
        result["failure_type"] = FAILURE_TYPE_RATE_LIMITED
        result["data_gaps"].append("OpenWebNinja API returned HTTP 429 (rate limited).")
        return result
    if resp.status_code != 200:
        result["failure_type"] = FAILURE_TYPE_TRANSPORT_ERROR
        result["data_gaps"].append(f"OpenWebNinja API returned HTTP {resp.status_code}.")
        return result

    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("OpenWebNinja response was not valid JSON.")
        return result

    if not isinstance(payload, dict):
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("OpenWebNinja response had an unexpected structure.")
        return result

    result["total_results"] = payload.get("total_products")
    raw_products = payload.get("products")
    data_block = payload.get("data")
    if not isinstance(raw_products, list) and isinstance(data_block, dict):
        raw_products = data_block.get("products")
        if result["total_results"] is None:
            result["total_results"] = data_block.get("total_products")
    if not isinstance(raw_products, list):
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("OpenWebNinja response was missing products.")
        return result

    result["success"] = True
    result["failure_type"] = FAILURE_TYPE_SUCCESS
    fetched_at = _now_iso()
    location = _location()
    for raw in raw_products:
        if isinstance(raw, dict):
            result["items"].append(_normalize_openwebninja_item(raw, fetched_at, location))
    result["result_count"] = len(result["items"])
    return result


def _search_unwrangle(query: str, page: int) -> Dict[str, Any]:
    """One Unwrangle Costco Business Delivery search page request.

    One page returns up to 96 products and costs 10 credits per successful
    page, so this is a catalog-refresh workflow â€” never per-ASIN enrichment.
    """
    result: Dict[str, Any] = {
        "source": "unwrangle",
        "platform": UNWRANGLE_PLATFORM,
        "search": query,
        "page": page,
        "success": False,
        "failure_type": FAILURE_TYPE_TRANSPORT_ERROR,  # updated below on first success path
        "no_of_pages": None,
        "total_results": None,
        "result_count": 0,
        "items": [],
        "data_gaps": [],
        "http_status": None,
    }

    api_key = os.getenv("UNWRANGLE_API_KEY")
    if not api_key:
        result["failure_type"] = FAILURE_TYPE_AUTH_ERROR
        result["data_gaps"].append("Unwrangle API key is not configured.")
        return result

    params = {
        "platform": UNWRANGLE_PLATFORM,
        "search": query,
        "page": str(page),
        "api_key": api_key,
    }

    try:
        resp = requests.get(UNWRANGLE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        result["failure_type"] = FAILURE_TYPE_TRANSPORT_ERROR
        result["data_gaps"].append("Unwrangle request timed out.")
        return result
    except requests.exceptions.RequestException:
        result["failure_type"] = FAILURE_TYPE_TRANSPORT_ERROR
        result["data_gaps"].append("Unwrangle request failed at the network level.")
        return result

    result["http_status"] = resp.status_code
    if resp.status_code in (401, 403):
        result["failure_type"] = FAILURE_TYPE_AUTH_ERROR
        result["data_gaps"].append(f"Unwrangle API returned HTTP {resp.status_code} (auth rejected).")
        return result
    if resp.status_code == 404:
        result["failure_type"] = FAILURE_TYPE_NOT_FOUND
        result["data_gaps"].append("Unwrangle API returned HTTP 404 (not found).")
        return result
    if resp.status_code == 429:
        result["failure_type"] = FAILURE_TYPE_RATE_LIMITED
        result["data_gaps"].append("Unwrangle API returned HTTP 429 (rate limited).")
        return result
    if resp.status_code != 200:
        result["failure_type"] = FAILURE_TYPE_TRANSPORT_ERROR
        result["data_gaps"].append(f"Unwrangle API returned HTTP {resp.status_code}.")
        return result

    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("Unwrangle response was not valid JSON.")
        return result

    if not isinstance(payload, dict):
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("Unwrangle response had an unexpected structure.")
        return result

    if payload.get("success") is not True:
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("Unwrangle reported request failure (success is false).")
        return result

    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        result["failure_type"] = FAILURE_TYPE_MALFORMED_RESPONSE
        result["data_gaps"].append("Unwrangle response was missing results.")
        return result

    result["success"] = True
    result["failure_type"] = FAILURE_TYPE_SUCCESS
    result["no_of_pages"] = payload.get("no_of_pages")
    result["total_results"] = payload.get("total_results")
    fetched_at = _now_iso()
    location = _location()
    for raw in raw_results:
        if isinstance(raw, dict):
            result["items"].append(_normalize_item(raw, fetched_at, location))
    result["result_count"] = len(result["items"])
    return result


def _normalize_item(
    raw: Dict[str, Any],
    fetched_at: str,
    location: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Full-field internal record from one Unwrangle result.

    The exported cost basis is the reduced (sale) price when present, else
    the regular price. The margin buffer is applied at export time, not
    here, so the snapshot keeps the raw online prices for audit.
    """
    regular_price = _safe_float(raw.get("price"))
    sale_price = _safe_float(raw.get("price_reduced"))
    availability = "in_stock" if raw.get("in_stock") is True else "out_of_stock"
    if raw.get("is_warehouse_only") is True:
        availability = "warehouse_only"

    variants = raw.get("variants")
    variants = variants if isinstance(variants, list) else []

    name = (raw.get("name") or "").strip()
    pack_size = raw.get("pack_size") or raw.get("size") or raw.get("quantity")
    item_id = str(raw.get("id") or "").strip()
    structured = _parse_structured_pack(pack_size)

    return {
        "item_name": name,
        "raw_title": name,
        "costco_item_id": item_id,
        "source_url": raw.get("url"),
        "url_derived": False,
        "regular_price": regular_price,
        "sale_price": sale_price,
        "price_basis": "sale" if sale_price is not None else ("regular" if regular_price is not None else None),
        "price_status": "sale" if sale_price is not None else ("regular" if regular_price is not None else None),
        "pack_size": (str(pack_size).strip() if pack_size else None),
        "unit_count": _parse_unit_count(pack_size),
        "cost_basis": "business_delivery_online",
        "cost_status": "discovery_only",
        "source": "business_delivery",
        "location": location or _location(),
        "availability": availability,
        "promo": raw.get("promo"),
        "variants_count": len(variants),
        "variants_max_price": _safe_float(raw.get("variants_max_price")),
        "brand": raw.get("brand"),
        "model_number": raw.get("model_number"),
        "upc_or_ean": _first_str(raw.get("upc") or raw.get("upc_code") or raw.get("ean")),
        "product_line": _first_str(raw.get("product_line")),
        "formula_or_flavor": _first_str(raw.get("flavor") or raw.get("formula")),
        "net_weight": structured["net_weight"],
        "unit_of_measure": structured["unit_of_measure"],
        "pack_count": structured["pack_count"],
        "case_count": structured["case_count"],
        "warehouse_or_zip": (location or _location()).get("delivery_zip"),
        "product_url": raw.get("url"),
        "fetched_at": fetched_at,
        "last_seen_at": fetched_at,
    }


def _normalize_openwebninja_item(
    raw: Dict[str, Any],
    fetched_at: str,
    location: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Full-field internal record from one OpenWebNinja Costco product.

    Sale price is only the price basis when it actually differs from the
    list price; otherwise the item is treated as regular-priced so sale
    price is never fabricated.
    """
    def first(value):
        if isinstance(value, list):
            return value[0] if value else None
        return value

    name = (
        raw.get("item_product_name")
        or raw.get("item_name")
        or raw.get("name")
        or raw.get("description")
        or ""
    ).strip()

    item_id = str(raw.get("item_number") or "").strip()
    if not item_id:
        item_id = str(raw.get("id") or "").split("!")[0].strip()

    regular_price = _safe_float(raw.get("item_location_pricing_listPrice"))
    sale_price = _safe_float(raw.get("item_location_pricing_salePrice"))

    if sale_price is not None and regular_price is not None and abs(sale_price - regular_price) < 0.005:
        price_basis = "regular"
    elif sale_price is not None:
        price_basis = "sale"
    else:
        price_basis = "regular" if regular_price is not None else None

    availability_raw = (
        raw.get("item_location_availability")
        or raw.get("item_location_stockStatus")
        or raw.get("deliveryStatus")
    )
    availability = "in_stock" if availability_raw == "in stock" else str(availability_raw or "out_of_stock")

    source_url = (
        first(raw.get("item_product_url"))
        or first(raw.get("item_url"))
        or first(raw.get("Item_URL_attr"))
        or raw.get("url")
    )
    url_derived = False
    if not source_url and item_id:
        source_url = f"https://www.costco.com/.product.{item_id}.html"
        url_derived = True

    pack_size = (
        first(raw.get("Container_Size_attr"))
        or first(raw.get("Pack_Size_attr"))
        or first(raw.get("Item_Size_attr"))
        or first(raw.get("Quantity_attr"))
        or first(raw.get("Size_attr"))
        or raw.get("pack_size")
    )
    structured = _parse_structured_pack(pack_size)

    return {
        "item_name": name,
        "raw_title": name,
        "costco_item_id": item_id,
        "source_url": source_url,
        "url_derived": url_derived,
        "regular_price": regular_price,
        "sale_price": sale_price,
        "price_basis": price_basis,
        "price_status": price_basis,
        "pack_size": (str(pack_size).strip() if pack_size else None),
        "unit_count": _parse_unit_count(pack_size),
        "cost_basis": "costco_online",
        "cost_status": "discovery_only",
        "source": "costco_online",
        "location": location or _location(),
        "availability": availability,
        "promo": raw.get("item_product_marketing_statement"),
        "variants_count": 0,
        "variants_max_price": None,
        "brand": first(raw.get("Brand_attr")),
        "model_number": None,
        "upc_or_ean": _first_str(raw.get("upc") or raw.get("upc_code") or raw.get("ean")),
        "product_line": _first_str(raw.get("product_line")),
        "formula_or_flavor": _first_str(raw.get("flavor") or raw.get("formula")),
        "net_weight": structured["net_weight"],
        "unit_of_measure": structured["unit_of_measure"],
        "pack_count": structured["pack_count"],
        "case_count": structured["case_count"],
        "warehouse_or_zip": (location or _location()).get("delivery_zip"),
        "product_url": source_url,
        "fetched_at": fetched_at,
        "last_seen_at": fetched_at,
    }


def _parse_unit_count(value) -> Optional[int]:
    """First integer quantity from strings like '3-count' or '6 ct'."""
    if value is None:
        return None
    match = re.search(r"(\d+)", str(value))
    return int(match.group(1)) if match else None


_WEIGHT_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(fl\s*\.?\s*oz|gal|lbs?|oz|kg|g|ml|lt|l)", re.IGNORECASE
)
_COUNT_UNIT_RE = re.compile(
    r"(\d+)\s*-?\s*(ct|count|packs?|pk|each|ea|sheets?|rolls?|bottles?)", re.IGNORECASE
)
_CASE_UNIT_RE = re.compile(r"(\d+)\s*(?:case|cases)", re.IGNORECASE)
_UNIT_OF_MEASURE_MAP = {
    "lb": "lb", "lbs": "lb", "oz": "oz", "g": "g", "kg": "kg",
    "ml": "ml", "l": "l", "lt": "l", "gal": "gal", "floz": "floz",
}


def _parse_structured_pack(value) -> Dict[str, Any]:
    """Derive net_weight / unit_of_measure / pack_count / case_count from
    a pack-size string when unambiguous; all None otherwise. Never invents
    values the source did not state."""
    empty = {"net_weight": None, "unit_of_measure": None, "pack_count": None, "case_count": None}
    if value is None:
        return empty
    text = str(value).strip()
    weight = _WEIGHT_UNIT_RE.search(text)
    count = _COUNT_UNIT_RE.search(text)
    case = _CASE_UNIT_RE.search(text)
    if not weight and not count and not case:
        return empty
    net_weight = None
    unit_of_measure = None
    if weight:
        net_weight = float(weight.group(1))
        raw_unit = re.sub(r"\s+", "", weight.group(2).lower())
        unit_of_measure = _UNIT_OF_MEASURE_MAP.get(raw_unit)
    return {
        "net_weight": net_weight,
        "unit_of_measure": unit_of_measure,
        "pack_count": int(count.group(1)) if count else None,
        "case_count": int(case.group(1)) if case else None,
    }


# ---------------------------------------------------------------------------
# Layer 2: product detail store (research only)
# ---------------------------------------------------------------------------


def _normalize_detail_item(raw: Dict[str, Any], fetched_at: str) -> Dict[str, Any]:
    """Full-field record for one product-detail fetch / import (layer 2)."""
    item_id = _first_str(raw.get("id") or raw.get("item_number") or raw.get("item_id"))
    name = _first_str(raw.get("name") or raw.get("item_name"))
    price = _safe_float(raw.get("price") or raw.get("current_price") or raw.get("regular_price"))
    sale = _safe_float(raw.get("price_reduced") or raw.get("sale_price"))
    pack_size = raw.get("pack_size") or raw.get("size")
    structured = _parse_structured_pack(pack_size)
    return {
        "item_name": name,
        "raw_title": name,
        "costco_item_id": item_id,
        "upc_or_ean": _first_str(raw.get("upc") or raw.get("upc_code") or raw.get("ean")),
        "brand": _first_str(raw.get("brand")),
        "product_line": _first_str(raw.get("product_line")),
        "formula_or_flavor": _first_str(raw.get("flavor") or raw.get("formula")),
        "net_weight": structured["net_weight"],
        "unit_of_measure": structured["unit_of_measure"],
        "pack_count": structured["pack_count"],
        "case_count": structured["case_count"],
        "current_price": price,
        "sale_price": sale,
        "price_basis": "sale" if sale is not None else ("regular" if price is not None else None),
        "warehouse_or_zip": _delivery_zip(),
        "product_url": _first_str(raw.get("url") or raw.get("product_url")),
        "cost_basis": "business_delivery_online" if catalog_source() == "UNWRANGLE" else "costco_online",
        "cost_status": "detail_only",
        "source": "business_delivery_detail",
        "fetched_at": fetched_at,
        "last_seen_at": fetched_at,
    }


def _load_product_details() -> List[Dict[str, Any]]:
    return _load_json_store(_detail_path(), [])


def _save_product_details(records: List[Dict[str, Any]]) -> str:
    path = _detail_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)
    return path


def refresh_product_details(item_ids) -> Dict[str, Any]:
    """Fetch product-detail records for specific Costco item IDs (layer 2).

    Gated by COSTCO_CATALOG_DETAIL_ENABLED=1 and only for item IDs that
    are potential Amazon matches (the caller selects them). UNWRANGLE has
    a per-item detail platform; OPENWEBNINJA has no detail endpoint here,
    so that request is reported as a data gap, never fabricated. Requests
    are rate-limited (COSTCO_CATALOG_REQUEST_DELAY_SECONDS) and the run
    stops on the first block (401/403/429/5xx). Writes only the detail
    store; never touches the discovery archive or snapshot.
    """
    ids = [str(i).strip() for i in (item_ids or []) if str(i).strip()]
    if not _detail_enabled():
        return {
            "status": "disabled",
            "failure_type": FAILURE_TYPE_NOT_FOUND,  # surface as "feature not available" (closest typed bucket)
            "message": "COSTCO_CATALOG_DETAIL_ENABLED is not 1; no requests were made.",
            "item_ids_requested": len(ids),
            "fetched": 0,
            "path": _detail_path(),
        }
    if catalog_source() != "UNWRANGLE":
        return {
            "status": "data_gap",
            "failure_type": FAILURE_TYPE_NOT_FOUND,
            "message": "Product-detail refresh is only implemented for UNWRANGLE; current source: %s." % catalog_source(),
            "item_ids_requested": len(ids),
            "fetched": 0,
        }
    api_key = os.getenv("UNWRANGLE_API_KEY")
    if not api_key:
        return {
            "status": "failed",
            "failure_type": FAILURE_TYPE_AUTH_ERROR,
            "message": "Unwrangle API key is not configured.",
            "fetched": 0,
        }

    fetched = []
    failures = []
    for item_id in ids:
        params = {"platform": UNWRANGLE_DETAIL_PLATFORM, "item": item_id, "api_key": api_key}
        try:
            resp = requests.get(UNWRANGLE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            failures.append({"item_id": item_id, "reason": "timeout",
                             "failure_type": FAILURE_TYPE_TRANSPORT_ERROR})
            break
        except requests.exceptions.RequestException:
            failures.append({"item_id": item_id, "reason": "network_error",
                             "failure_type": FAILURE_TYPE_TRANSPORT_ERROR})
            break
        if resp.status_code in (401, 403):
            failures.append({"item_id": item_id, "reason": "http_%d" % resp.status_code,
                             "failure_type": FAILURE_TYPE_AUTH_ERROR})
            break
        if resp.status_code == 404:
            failures.append({"item_id": item_id, "reason": "http_404",
                             "failure_type": FAILURE_TYPE_NOT_FOUND})
            break
        if resp.status_code == 429:
            failures.append({"item_id": item_id, "reason": "http_429",
                             "failure_type": FAILURE_TYPE_RATE_LIMITED})
            break
        if resp.status_code >= 500:
            failures.append({"item_id": item_id, "reason": "http_%d" % resp.status_code,
                             "failure_type": FAILURE_TYPE_TRANSPORT_ERROR})
            break
        if resp.status_code != 200:
            failures.append({"item_id": item_id, "reason": "http_%d" % resp.status_code,
                             "failure_type": FAILURE_TYPE_TRANSPORT_ERROR})
            continue
        try:
            payload = resp.json()
        except (json.JSONDecodeError, ValueError):
            failures.append({"item_id": item_id, "reason": "invalid_json",
                             "failure_type": FAILURE_TYPE_MALFORMED_RESPONSE})
            break
        raw = payload.get("result") if isinstance(payload, dict) else None
        if isinstance(raw, dict) and (raw.get("id") or raw.get("item_number") or raw.get("name")):
            record = _normalize_detail_item(raw, _now_iso())
            if not record.get("costco_item_id"):
                record["costco_item_id"] = item_id
            fetched.append(record)
        else:
            failures.append({"item_id": item_id, "reason": "no_result",
                             "failure_type": FAILURE_TYPE_NOT_FOUND})
        if len(ids) > 1:
            time.sleep(_request_delay())

    if fetched:
        fresh_ids = {r.get("costco_item_id") for r in fetched}
        merged = [r for r in _load_product_details() if r.get("costco_item_id") not in fresh_ids]
        merged.extend(fetched)
        _save_product_details(merged)

    return {
        "status": "ok" if (fetched or not failures) else "failed",
        "item_ids_requested": len(ids),
        "fetched": len(fetched),
        "failures": failures,
        "detail_count": len(_load_product_details()),
        "path": _detail_path(),
    }


# ---------------------------------------------------------------------------
# Layer 3: invoice-confirmed store (exact paid COGS)
# ---------------------------------------------------------------------------


def _load_invoices() -> List[Dict[str, Any]]:
    return _load_json_store(_invoice_path(), [])


def _save_invoices(records: List[Dict[str, Any]]) -> str:
    path = _invoice_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# Cross-layer resolution
# ---------------------------------------------------------------------------


_COLUMN_ALIASES = {
    "costco_item_number": ("costco_item_number", "costco_item_id", "item_number", "item_id"),
    "upc_or_ean": ("upc_or_ean", "upc", "ean", "barcode"),
    "item_name": ("item_name", "name", "product_name", "title"),
    "paid_cost": ("paid_cost", "unit_cost", "cost", "costco_cost"),
    "current_price": ("current_price", "price", "regular_price"),
    "quantity": ("quantity", "qty", "units"),
    "purchase_date": ("purchase_date", "date", "invoice_date", "order_date"),
    "invoice_number": ("invoice_number", "invoice", "receipt_number", "receipt"),
    "warehouse_or_zip": ("warehouse_or_zip", "location", "zip", "delivery_zip"),
    "product_line": ("product_line", "line"),
    "formula_or_flavor": ("formula_or_flavor", "flavor", "formula"),
    "net_weight": ("net_weight", "weight"),
    "unit_of_measure": ("unit_of_measure", "uom"),
    "pack_count": ("pack_count", "pack"),
    "case_count": ("case_count", "case"),
    "brand": ("brand",),
    "product_url": ("product_url", "url"),
}


def _map_row(row: Dict[str, Any]) -> Dict[str, Any]:
    mapped: Dict[str, Any] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in row and row[alias] is not None and str(row[alias]).strip() != "":
                value = row[alias]
                break
        mapped[canonical] = value
    return mapped


def _read_import_rows(path: str) -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(path):
        return None
    lower = path.lower()
    try:
        if lower.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("records") or []
            if not isinstance(data, list):
                return None
            return [r for r in data if isinstance(r, dict)]
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except (json.JSONDecodeError, OSError, csv.Error):
        return None


def import_product_detail(path: str) -> Dict[str, Any]:
    """Import analyst-provided product-detail records (CSV or JSON list).

    Research only: cost_status stays detail_only and a detail price never
    authorizes a purchase. Records are keyed by costco_item_id; duplicate
    ids and rows without an id/name/price are held for review.
    """
    rows = _read_import_rows(path)
    if not rows:
        return {"status": "failed", "message": "Unreadable or empty import file: %s" % path, "imported": 0}

    imported = []
    held = []
    existing = {r.get("costco_item_id") for r in _load_product_details() if r.get("costco_item_id")}
    now = _now_iso()
    for row in rows:
        m = _map_row(row)
        item_id = _first_str(m.get("costco_item_number"))
        name = _first_str(m.get("item_name"))
        price = _safe_float(m.get("current_price"))
        if not item_id or not name or price is None:
            held.append({"item_id": item_id, "reason": "missing costco_item_number / item_name / current_price"})
            continue
        if item_id in existing:
            held.append({"item_id": item_id, "reason": "duplicate costco_item_id"})
            continue
        existing.add(item_id)
        imported.append({
            "item_name": name,
            "raw_title": name,
            "costco_item_id": item_id,
            "upc_or_ean": _first_str(m.get("upc_or_ean")),
            "brand": _first_str(m.get("brand")),
            "product_line": _first_str(m.get("product_line")),
            "formula_or_flavor": _first_str(m.get("formula_or_flavor")),
            "net_weight": _safe_float(m.get("net_weight")),
            "unit_of_measure": _first_str(m.get("unit_of_measure")),
            "pack_count": _first_int(m.get("pack_count")),
            "case_count": _first_int(m.get("case_count")),
            "current_price": price,
            "price_basis": "imported",
            "warehouse_or_zip": _first_str(m.get("warehouse_or_zip")),
            "product_url": _first_str(m.get("product_url")),
            "cost_basis": "costco_online",
            "cost_status": "detail_only",
            "source": "product_detail_import",
            "fetched_at": now,
            "last_seen_at": now,
        })

    merged = _load_product_details() + imported
    saved = _save_product_details(merged)
    return {
        "status": "ok",
        "imported": len(imported),
        "held_for_review": len(held),
        "held": held,
        "detail_count": len(merged),
        "path": saved,
    }


def import_invoices(path: str) -> Dict[str, Any]:
    """Import Business Center invoice / order-history rows (layer 3).

    Every row carries a real paid unit cost and becomes the authoritative
    COGS when it fingerprint-matches exactly. Duplicate
    (invoice_number, costco_item_number) pairs and rows missing an
    invoice number / item / name / paid cost are held for review.
    """
    rows = _read_import_rows(path)
    if not rows:
        return {"status": "failed", "message": "Unreadable or empty import file: %s" % path, "imported": 0}

    imported = []
    held = []
    existing = {
        (r.get("invoice_number"), r.get("costco_item_id"))
        for r in _load_invoices()
        if r.get("invoice_number") and r.get("costco_item_id")
    }
    now = _now_iso()
    for row in rows:
        m = _map_row(row)
        invoice_number = _first_str(m.get("invoice_number"))
        item_id = _first_str(m.get("costco_item_number"))
        name = _first_str(m.get("item_name"))
        paid_cost = _safe_float(m.get("paid_cost"))
        if not invoice_number or not item_id or not name or paid_cost is None:
            held.append({
                "invoice_number": invoice_number,
                "item_id": item_id,
                "reason": "missing invoice_number / costco_item_number / item_name / paid_cost",
            })
            continue
        key = (invoice_number, item_id)
        if key in existing:
            held.append({"invoice_number": invoice_number, "item_id": item_id, "reason": "duplicate (invoice, item)"})
            continue
        existing.add(key)
        imported.append({
            "invoice_number": invoice_number,
            "item_name": name,
            "raw_title": name,
            "costco_item_id": item_id,
            "upc_or_ean": _first_str(m.get("upc_or_ean")),
            "brand": _first_str(m.get("brand")),
            "product_line": _first_str(m.get("product_line")),
            "formula_or_flavor": _first_str(m.get("formula_or_flavor")),
            "net_weight": _safe_float(m.get("net_weight")),
            "unit_of_measure": _first_str(m.get("unit_of_measure")),
            "pack_count": _first_int(m.get("pack_count")),
            "case_count": _first_int(m.get("case_count")),
            "paid_cost": paid_cost,
            "quantity": _first_int(m.get("quantity")),
            "purchase_date": _first_str(m.get("purchase_date")),
            "warehouse_or_zip": _first_str(m.get("warehouse_or_zip")),
            "cost_basis": "invoice_confirmed",
            "cost_status": "invoice_confirmed",
            "source": "business_center_invoice",
            "imported_at": now,
        })

    merged = _load_invoices() + imported
    _save_invoices(merged)
    return {
        "status": "ok",
        "imported": len(imported),
        "held_for_review": len(held),
        "held": held,
        "invoice_count": len(merged),
        "path": _invoice_path(),
    }


def _ledger_path() -> str:
    """Verified ASIN -> Costco item_name mapping store."""
    raw = os.getenv("COSTCO_AMAZON_MAPPING_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(_project_root(), raw)
    return os.path.join(_project_root(), "data", "costco-amazon-mapping.json")


def _load_ledger() -> Dict[str, str]:
    """Read-only ledger {ASIN (upper): costco item_name}. Missing/corrupt
    file = empty ledger, never an error."""
    path = _ledger_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip().upper(): str(v).strip() for k, v in data.items() if str(v).strip()}


def _save_ledger(ledger: Dict[str, str]) -> str:
    path = _ledger_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)
    os.replace(tmp, path)
    return path


def ledger_lookup(asin: Optional[str]) -> Optional[str]:
    """Verified mapping for an ASIN, or None. Read-only."""
    if not asin:
        return None
    return _load_ledger().get(str(asin).strip().upper())


def _flat_ledger_rows(path: str) -> List[Dict[str, str]]:
    """A flat JSON object {"ASIN": "item name"} -> import rows."""
    if not path.lower().endswith(".json"):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    return [{"asin": str(k), "item_name": str(v)} for k, v in data.items()]


def import_ledger(path: str) -> Dict[str, Any]:
    """Import verified ASIN -> Costco item_name mappings (layer: ledger).

    JSON: a flat {"ASIN": "item name"} object. CSV: header
    asin,item_name. Append-only: existing ASINs with a DIFFERENT name are
    held for review (never silently overwritten); rows with invalid ASINs
    or empty names are held. This file never changes the matching
    contracts — it only ADDS exact identity matches.
    """
    rows = _read_import_rows(path)
    if not rows:
        rows = _flat_ledger_rows(path)
    if not rows:
        return {"status": "failed", "message": "Unreadable or empty import file: %s" % path, "imported": 0}

    imported: Dict[str, str] = {}
    held: List[Dict[str, Any]] = []
    invalid = 0
    for row in rows:
        asin = _first_str(row.get("asin"))
        name = _first_str(row.get("item_name")) or _first_str(row.get("name"))
        if not asin or not _ASIN_RE.fullmatch(asin.strip()):
            invalid += 1
            held.append({"asin": asin, "reason": "invalid ASIN (expected 10 alphanumeric characters)"})
            continue
        asin = asin.strip().upper()
        if not name:
            invalid += 1
            held.append({"asin": asin, "reason": "missing item_name"})
            continue
        if asin in imported:
            held.append({"asin": asin, "reason": "duplicate within import file"})
            continue
        imported[asin] = name.strip()

    existing = _load_ledger()
    conflict = []
    fresh = {}
    for asin, name in imported.items():
        if asin in existing and existing[asin] != name:
            conflict.append({"asin": asin, "existing": existing[asin], "new": name,
                             "reason": "existing mapping differs; held for review"})
            continue
        if asin not in existing:
            fresh[asin] = name
    merged = dict(existing)
    merged.update(fresh)

    saved = False
    if fresh:
        _save_ledger(merged)
        saved = True

    return {
        "status": "ok",
        "imported": len(fresh),
        "held_for_review": len(conflict) + len(held),
        "conflicts": conflict,
        "held": held,
        "ledger_entries": len(merged),
        "saved": saved,
        "path": _ledger_path(),
    }


def _ledger_cost(target_name: str) -> Optional[Dict[str, Any]]:
    """Cost for a ledger-confirmed item_name across the layers, in priority
    order (invoice > detail > CSV). The mapping is the identity evidence —
    the cost still comes from real paid/online/local rows only."""
    target = (target_name or "").casefold()
    for record in _load_invoices():
        if (record.get("item_name") or "").casefold() != target:
            continue
        paid = _safe_float(record.get("paid_cost"))
        if paid is not None:
            return {
                "item_name": record.get("item_name"),
                "costco_cost": paid,
                "costco_cost_basis": "invoice_confirmed",
                "match_quality": "invoice_confirmed",
                "match_reason": "Verified mapping (ledger) + %s confirms the exact item." % (
                    "Invoice %s" % (record.get("invoice_number") or "?")
                ),
                "cost_status": "invoice_confirmed",
                "source": "ledger:invoice",
                "cost_is_purchase_authorized": True,
            }
    for record in _load_product_details():
        if (record.get("item_name") or "").casefold() != target:
            continue
        price = _safe_float(record.get("current_price"))
        if price is not None:
            return {
                "item_name": record.get("item_name"),
                "costco_cost": price,
                "costco_cost_basis": record.get("cost_basis") or "costco_online",
                "match_quality": "exact",
                "match_reason": "Verified mapping (ledger) identifies the exact item (detail layer, research only).",
                "cost_status": record.get("cost_status") or "detail_only",
                "source": "ledger:detail",
                "cost_is_purchase_authorized": False,
            }
    csv_match = costco_client.get_costco_price(target_name)
    if csv_match and csv_match.get("match_quality") in ("exact", "high_confidence"):
        row = dict(csv_match)
        row["match_quality"] = "exact"
        row["match_reason"] = "Verified mapping (ledger) identifies the exact item (local CSV cost)."
        row["source"] = "ledger:csv"
        return row
    return None


_HARD_CONFLICT_MARKERS = (
    "Net weight differs",
    "Pack/count differs",
    "UPC/EAN differs",
    "Unit dimension differs",
    "Brand differs",
)


def _dimensions_agree(amazon_name: str, costco_item_name: str) -> bool:
    """True when both titles carry equal fingerprint evidence in at least
    one dimension (net weight/volume or pack count). Shared equal dimension
    evidence is the strongest title-only signal that both titles describe
    the same pack — it is what lets a core/formula word difference be read
    as marketing-copy variance rather than a proven different product."""
    a_w = set(costco_client._weight_fingerprint(amazon_name))
    c_w = set(costco_client._weight_fingerprint(costco_item_name))
    a_c = set(costco_client._count_fingerprint(amazon_name))
    c_c = set(costco_client._count_fingerprint(costco_item_name))
    return bool(
        (a_w and c_w and a_w == c_w) or (a_c and c_c and a_c == c_c)
    )


def _research_surfacing_candidate(
    amazon_name: str, record_item_name: str, eq: Dict[str, Any]
) -> bool:
    """Research-view eligibility for a non-exact pair.

    Only pairs that are plausible renamings of the same product may surface
    their cost in the research view, always as candidate_match (never
    purchase-authorizing):
      - quality "candidate": no known conflict, one side carries evidence;
      - quality "mismatch": tolerated ONLY when every hard identity check
        passes (no weight/pack/UPC/brand/cross-dimension conflict), the two
        titles share at least one product-identity core token, AND either a
        fingerprint dimension agrees between the titles or one side carries
        fingerprint evidence the other lacks entirely. Core/formula word
        differences that survive these guards are marketing-copy variance,
        not a proven different product.
    Quality "unknown" and any pair carrying a hard identity conflict never
    surface — surfacing those would silently pass a failed match.
    """
    mq = eq.get("match_quality")
    if mq == "unknown":
        return False
    reason = eq.get("match_reason") or ""
    if any(marker in reason for marker in _HARD_CONFLICT_MARKERS):
        return False
    if mq == "candidate":
        return True
    if mq != "mismatch":
        return False

    # Core/formula wording conflict: tolerable only with shared product
    # identity plus non-conflicting dimension evidence.
    a_core = costco_client._core_tokens(amazon_name)
    c_core = costco_client._core_tokens(record_item_name)
    if not (a_core & c_core):
        return False
    a_w = set(costco_client._weight_fingerprint(amazon_name))
    c_w = set(costco_client._weight_fingerprint(record_item_name))
    a_c = set(costco_client._count_fingerprint(amazon_name))
    c_c = set(costco_client._count_fingerprint(record_item_name))
    dimensions_agree = _dimensions_agree(amazon_name, record_item_name)
    evidence_on_one_side = bool(
        (not (a_w or a_c) and bool(c_w or c_c))
        or (not (c_w or c_c) and bool(a_w or a_c))
    )
    if dimensions_agree:
        return True
    # One-sided evidence (count/weight on exactly one title) is only a
    # research signal when the titles share MULTIPLE identity tokens — a
    # single generic category word (e.g. "organic") plus an accidental
    # pack count is coincidence, not identity.
    return evidence_on_one_side and len(a_core & c_core) >= 2


def resolve_costco_cost(amazon_name: str, amazon_asin: Optional[str] = None,
                        amazon_upc: Optional[str] = None,
                        amazon_brand: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Resolve the strongest Costco cost basis for an Amazon product name
    across the three catalog layers (invoice_confirmed > product_detail >
    CSV), plus the verified ASIN ledger (identity evidence, checked first).

    The ledger maps a verified ASIN to a Costco item_name: the mapping is
    the identity evidence, the cost still comes from real layers only.
    amazon_upc / amazon_brand strengthen (or honestly conflict) the
    fingerprint on every layer when supplied.

    Pass 1: EXACT fingerprint matches in priority order — invoice confirmed
    (real paid COGS, match_quality="invoice_confirmed", purchase-authorized),
    product detail (research price, "exact"), legacy CSV ("exact").
    HIGH-CONFIDENCE matches surface the same paid cost as research input
    only: match_quality stays "high_confidence", costco_cost_basis is
    "invoice_confirmed" (provenance of the paid number), and
    cost_is_purchase_authorized is always False — invoices never authorize
    or gate a high-confidence candidate.
    Pass 2: research candidates from the same priority order, surfaced as
    candidate_match for the research view only — never COGS/ROI. Eligible
    pairs are genuine "candidate" classifications plus core-only
    "mismatches" where a fingerprint dimension agrees between the titles.
    Hard identity conflicts (weight/pack/UPC/brand/cross-dimension) and
    "unknown" pairs are never surfaced as costs. Returns None when no layer
    has any usable match.
    Never performs network calls and never invents costs.
    """
    ledger_name = ledger_lookup(amazon_asin)
    if ledger_name:
        ledger_cost = _ledger_cost(ledger_name)
        if ledger_cost is not None:
            return ledger_cost
        return {
            "item_name": ledger_name,
            "costco_cost": None,
            "costco_cost_basis": "unavailable",
            "match_quality": "exact",
            "match_reason": "Verified mapping (ledger) identifies the item, but no local layer carries a cost yet.",
            "cost_status": "ledger_only",
            "source": "ledger",
            "cost_is_purchase_authorized": False,
        }

    def fingerprint(record: Dict[str, Any]) -> Dict[str, Any]:
        return costco_client.product_equivalence(
            amazon_name,
            record.get("item_name") or "",
            amazon_upc=amazon_upc,
            costco_upc=record.get("upc_or_ean") or None,
            amazon_brand=amazon_brand,
        )

    _PASS1 = ("exact", "high_confidence")

    non_exact = []

    for record in _load_invoices():
        eq = fingerprint(record)
        if eq["match_quality"] == "exact":
            paid = _safe_float(record.get("paid_cost"))
            if paid is not None:
                invoice_label = "Invoice %s" % (record.get("invoice_number") or "?")
                if record.get("purchase_date"):
                    invoice_label += " (%s)" % record.get("purchase_date")
                return {
                    "item_name": record.get("item_name"),
                    "costco_cost": paid,
                    "costco_cost_basis": "invoice_confirmed",
                    "match_quality": "invoice_confirmed",
                    "match_reason": "%s confirms the exact item (fingerprint match)." % invoice_label,
                    "cost_status": "invoice_confirmed",
                    "source": "business_center_invoice",
                    "cost_is_purchase_authorized": True,
                }
        elif eq["match_quality"] == "high_confidence":
            paid = _safe_float(record.get("paid_cost"))
            if paid is not None:
                invoice_label = "Invoice %s" % (record.get("invoice_number") or "?")
                if record.get("purchase_date"):
                    invoice_label += " (%s)" % record.get("purchase_date")
                return {
                    "item_name": record.get("item_name"),
                    "costco_cost": paid,
                    "costco_cost_basis": "invoice_confirmed",
                    "match_quality": "high_confidence",
                    "match_reason": "%s carries a paid cost, but the fingerprint match is high-confidence only (research input — never purchase-authorized): %s" % (
                        invoice_label,
                        eq.get("match_reason") or "title identity only",
                    ),
                    "cost_status": "invoice_confirmed",
                    "source": "business_center_invoice",
                    "cost_is_purchase_authorized": False,
                }
        non_exact.append({"record": record, "eq": eq, "layer": "invoice_confirmed"})

    for record in _load_product_details():
        eq = fingerprint(record)
        if eq["match_quality"] in _PASS1:
            price = _safe_float(record.get("current_price"))
            if price is not None:
                return {
                    "item_name": record.get("item_name"),
                    "costco_cost": price,
                    "costco_cost_basis": record.get("cost_basis") or "costco_online",
                    "match_quality": eq["match_quality"],
                    "match_reason": eq.get("match_reason"),
                    "cost_status": record.get("cost_status") or "detail_only",
                    "source": record.get("source") or "product_detail",
                }
        non_exact.append({"record": record, "eq": eq, "layer": "product_detail"})

    csv_match = costco_client.get_costco_price(amazon_name, amazon_upc=amazon_upc, amazon_brand=amazon_brand)
    if csv_match:
        if csv_match.get("match_quality") in _PASS1:
            return csv_match
        non_exact.append({
            "record": csv_match,
            "eq": {
                "match_quality": csv_match.get("match_quality"),
                "match_reason": csv_match.get("match_reason"),
            },
            "layer": "csv",
        })

    # Research fallback: only pairs that are plausible renamings of the same
    # product may surface a research cost (candidate_match basis). Hard
    # identity conflicts (weight/pack/UPC/brand/cross-dimension) and
    # evidence-lacking "unknown" pairs never surface — those would silently
    # pass a failed match. Core/formula word differences are tolerated at
    # the research tier ONLY when a fingerprint dimension agrees between the
    # titles (marketing-copy variance, not a proven different product).
    # The strongest normalized title identity wins over store order.
    candidates = []
    for entry in non_exact:
        eq = entry["eq"]
        record = entry["record"]
        if not _research_surfacing_candidate(
            amazon_name, record.get("item_name") or "", eq
        ):
            continue
        if entry["layer"] == "csv":
            cost = record.get("costco_cost")
        elif entry["layer"] == "invoice_confirmed":
            cost = record.get("paid_cost")
        else:
            cost = record.get("current_price")
        if cost is None:
            continue
        candidates.append((entry, cost))

    if candidates:
        def _sim(item: Tuple[Dict[str, Any], Any]) -> float:
            return costco_client._title_similarity(
                amazon_name, item[0]["record"].get("item_name") or ""
            )

        entry, cost = max(candidates, key=_sim)
        prefix = ""
        if entry["layer"] == "invoice_confirmed":
            prefix = "Invoice %s: " % (entry["record"].get("invoice_number") or "?")
        return {
            "item_name": entry["record"].get("item_name"),
            "costco_cost": cost,
            "costco_cost_basis": "candidate_match",
            "match_quality": "candidate",
            "match_reason": prefix + (entry["eq"].get("match_reason") or "Exact product equivalence unverified."),
            "cost_status": "candidate_match",
            "source": entry["layer"],
        }

    # Invoice blocked-surface: a mismatched / evidence-lacking INVOICE row is
    # rare operator-paid evidence, so its cost is surfaced for the research
    # view with the conflict EXPLICITLY preserved (match_quality stays
    # mismatch; basis candidate_match) — never invoice_confirmed, never
    # purchase-authorized. Product-detail and CSV rows are never surfaced
    # this way: a broad store would flood unrelated costs.
    for entry in non_exact:
        if entry["layer"] != "invoice_confirmed":
            continue
        cost = entry["record"].get("paid_cost")
        if cost is None:
            continue
        return {
            "item_name": entry["record"].get("item_name"),
            "costco_cost": cost,
            "costco_cost_basis": "candidate_match",
            "match_quality": entry["eq"].get("match_quality"),
            "match_reason": "Invoice %s: %s" % (
                entry["record"].get("invoice_number") or "?",
                entry["eq"].get("match_reason") or "Exact product equivalence unverified.",
            ),
            "cost_status": "candidate_match",
            "source": "invoice_confirmed",
        }
    return None


def _load_json_store(path: str, default: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return default
    return data if isinstance(data, list) else default


def _cost_to_export(record: Dict[str, Any]) -> Optional[float]:
    price = record.get("sale_price")
    if price is None:
        price = record.get("regular_price")
    if not _is_number(price) or price <= 0:
        return None
    buffered = price * (1.0 + _buffer_percent() / 100.0)
    return round(buffered, 2)


def _pack_tokens(name: str) -> set:
    if not name:
        return set()
    tokens = set()
    for match in _PACK_PATTERN.finditer(name):
        tokens.add(re.sub(r"\s+", "", match.group(0)).casefold())
    return tokens


def _normalize_name(value) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


def _match_existing(record: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Map one API item to an existing CSV row without guessing.

    Priority: Costco item id (when the CSV carries one), then a single
    normalized exact title match, then a pack-size-aware fuzzy match
    (>= 0.70). Pack-size conflicts and ambiguous exact matches are
    returned as unmatched for analyst review.
    """
    item_id = record.get("costco_item_id")
    if item_id:
        by_id = [r for r in rows if str(r.get("costco_item_id") or "").strip() == item_id]
        if len(by_id) == 1:
            return {"action": "update", "matched_by": "item_id", "matched_row": by_id[0]}
        if len(by_id) > 1:
            return {"action": "unmatched", "reason": "ambiguous_item_id", "matched_row": None}

    target = _normalize_name(record.get("item_name"))
    exact = [r for r in rows if _normalize_name(r.get("item_name")) == target]
    if len(exact) == 1:
        return {"action": "update", "matched_by": "exact_title", "matched_row": exact[0]}
    if len(exact) > 1:
        return {"action": "unmatched", "reason": "ambiguous_exact_title", "matched_row": None}

    best_row = None
    best_ratio = MATCH_RATIO_THRESHOLD
    item_tokens = _pack_tokens(record.get("item_name"))
    for row in rows:
        ratio = SequenceMatcher(None, target, _normalize_name(row.get("item_name"))).ratio()
        if ratio >= best_ratio:
            best_ratio = ratio
            best_row = row

    if best_row is None:
        return {"action": "append", "matched_by": "none", "matched_row": None}

    row_tokens = _pack_tokens(best_row.get("item_name"))
    if item_tokens and row_tokens and item_tokens.isdisjoint(row_tokens):
        return {"action": "unmatched", "reason": "pack_size_conflict", "matched_row": best_row}

    return {"action": "update", "matched_by": "fuzzy_title", "matched_row": best_row}


def _reconcile(items: List[Dict[str, Any]], existing_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge fresh API items into CSV rows: update, append, or preserve."""
    rows = [dict(r) for r in existing_rows]
    updated_idx = set()
    appended: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    seen_names: Dict[str, str] = {}

    for record in items:
        if not record.get("item_name"):
            unmatched.append({**record, "reason": "missing_name"})
            continue

        normalized = _normalize_name(record["item_name"])
        if normalized in seen_names:
            record = {**record, "reason": "duplicate_name"}
            record["_duplicate_of"] = seen_names[normalized]
            unmatched.append(record)
            continue
        seen_names[normalized] = record.get("costco_item_id") or normalized

        cost = _cost_to_export(record)
        if cost is None:
            unmatched.append({**record, "reason": "no_price"})
            continue

        match = _match_existing(record, rows)
        if match["action"] == "unmatched":
            unmatched.append({**record, "reason": match["reason"]})
            continue

        export_row = {
            "item_name": record["item_name"],
            "costco_cost": cost,
        }

        if match["action"] == "update":
            row = match["matched_row"]
            row_index = rows.index(row)
            rows[row_index] = export_row
            updated_idx.add(row_index)
            record["match"] = "updated"
            record["matched_by"] = match["matched_by"]
        else:
            appended.append(export_row)
            record["match"] = "appended"
            record["matched_by"] = "none"

        record["costco_cost"] = cost
        record["cost_exported_at"] = _now_iso()

    stale = [rows[i] for i in range(len(rows)) if i not in updated_idx and rows[i] not in appended]
    return {"rows": rows + appended, "unmatched": unmatched, "stale": stale}


def _write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(costco_client.REQUIRED_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in costco_client.REQUIRED_COLUMNS})


def _load_existing_rows() -> List[Dict[str, Any]]:
    csv_path = costco_client._resolve_csv_path()
    if not csv_path or not os.path.exists(csv_path):
        return []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row.get("item_name")]


def _load_archive() -> List[Dict[str, Any]]:
    """Append-only discovery archive (list of discovery records)."""
    path = _archive_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    records = data if isinstance(data, list) else data.get("records", [])
    return records if isinstance(records, list) else []


def _save_archive(records: List[Dict[str, Any]]) -> str:
    path = _archive_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "catalog": "kirkland-signature-discovery",
        "updated_at": _now_iso(),
        "record_count": len(records),
        "records": records,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def _archive_key(record: Dict[str, Any]) -> tuple:
    location = record.get("location") or {}
    return (str(record.get("costco_item_id") or ""), str(location.get("delivery_zip") or ""))


def _latest_archive_records(archive: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    latest: Dict[tuple, Dict[str, Any]] = {}
    for record in archive:
        latest[_archive_key(record)] = record
    return latest


def _write_run_report(report: Dict[str, Any]) -> str:
    path = _run_report_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return path


def _stop_reason(response: Dict[str, Any]) -> str:
    """Why a run stopped: 401/403 = blocked, 429 = rate_limited, else failed."""
    status_code = response.get("http_status")
    if status_code in (401, 403):
        return "blocked"
    if status_code == 429:
        return "rate_limited"
    return "failed"


def _freshness_threshold_days() -> int:
    raw = os.getenv("COSTCO_FRESHNESS_THRESHOLD_DAYS")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 8
    return value if value > 0 else 8


def last_run_status() -> Dict[str, Any]:
    """Lightweight catalog freshness status for the Scout UI (no network).

    Reads the latest run report and discovery archive. Never calls any
    provider and never writes files. freshness is:
    - "fresh": latest run completed cleanly (status ok) within the
      COSTCO_FRESHNESS_THRESHOLD_DAYS window (default 8),
    - "stale": latest run was blocked / rate-limited / failed / partial /
      disabled, or is older than the threshold,
    - "unknown": no run report exists yet (e.g. before the first scheduled
      run).
    """
    path = _run_report_path()
    report = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except (json.JSONDecodeError, OSError):
            report = None

    location = (report or {}).get("location") or _location()
    threshold = _freshness_threshold_days()
    result: Dict[str, Any] = {
        "run_report_exists": report is not None,
        "archive_path": _archive_path(),
        "archive_record_count": len(_load_archive()),
        "threshold_days": threshold,
        "location": location,
        "freshness": "unknown",
        "last_run_at": None,
        "last_fetched_at": None,
        "status": None,
        "stop_reason": None,
        "last_fetched_count": None,
    }

    if not report:
        result["message"] = "No catalog run report yet; the weekly scheduled run will establish the baseline."
        return result

    run_at = report.get("generated_at") or report.get("fetched_at")
    result["last_run_at"] = run_at
    result["last_fetched_at"] = run_at
    result["status"] = report.get("status")
    result["stop_reason"] = report.get("stop_reason")
    counts = report.get("counts") or {}
    result["last_fetched_count"] = counts.get("fetched")

    if not run_at:
        result["freshness"] = "stale"
        result["message"] = "Latest run report has no timestamp; freshness cannot be verified."
        return result

    try:
        run_dt = datetime.fromisoformat(str(run_at))
    except ValueError:
        run_dt = None
    if run_dt is None or run_dt.tzinfo is None:
        result["freshness"] = "stale"
        result["message"] = "Latest run report timestamp is invalid; freshness cannot be verified."
        return result

    now = datetime.now(timezone.utc)
    if run_dt.tzinfo is not None:
        run_dt = run_dt.astimezone(timezone.utc)
    age_days = max(0.0, (now - run_dt).total_seconds() / 86400.0)
    result["staleness_days"] = round(age_days, 2)

    if report.get("status") == "ok":
        if age_days <= threshold:
            result["freshness"] = "fresh"
            result["message"] = "Latest run completed cleanly and is within the freshness window."
        else:
            result["freshness"] = "stale"
            result["message"] = (
                f"Latest run completed cleanly but is {result['staleness_days']} days old "
                f"(threshold {threshold} days)."
            )
    else:
        reason = report.get("stop_reason") or report.get("status") or "unknown"
        result["freshness"] = "stale"
        result["message"] = f"Latest run did not complete cleanly (status {report.get('status')}, reason {reason})."
    return result


def refresh_catalog(query: Optional[str] = None, max_pages: Optional[int] = None) -> Dict[str, Any]:
    """Fetch catalog pages, append to the discovery archive, export CSV.

    Requires COSTCO_CATALOG_SOURCE=OPENWEBNINJA or UNWRANGLE; otherwise
    returns a disabled report and performs zero network calls. Pages are
    capped at COSTCO_CATALOG_MAX_PAGES (default 1). OpenWebNinja has no
    documented pagination, so it is always a single request per query;
    Unwrangle pages are 10 credits each.

    Discovery catalog contract:

    - The archive (data/costco-discovery-catalog.json) is append-only:
      existing records are never overwritten or mutated; every clean item
      from a run appends a new record with its own fetched_at.
    - Requests are rate-limited (COSTCO_CATALOG_REQUEST_DELAY_SECONDS
      between requests) and the run stops on the first block/error
      (HTTP 401/403 = blocked, 429 = rate_limited, anything else = failed).
    - A stopped run preserves the last-good archive, snapshot, and CSV.
    - Within-run duplicate item IDs are skipped; pack-size/title conflicts
      against the archive and existing CSV rows are held for review and
      never attached a cost.
    - Every run writes a run report (data/costco-catalog-run-report.json)
      with fetched / updated / skipped / held-for-review / failed counts.
    """
    source = catalog_source()
    archive_path = _archive_path()
    snapshot_path = _snapshot_path()
    run_report_path = _run_report_path()
    location = _location()
    delay = _request_delay()

    if source == "OFF":
        report = {
            "status": "disabled",
            "generated_at": _now_iso(),
            "message": "COSTCO_CATALOG_SOURCE is not OPENWEBNINJA or UNWRANGLE; catalog refresh is off.",
            "pages_fetched": 0,
            "items_fetched": 0,
            "credits_estimate": 0,
            "requests_used": 0,
            "counts": {"fetched": 0, "updated": 0, "skipped": 0, "held_for_review": 0, "failed": 0},
            "snapshot_path": snapshot_path,
            "archive_path": archive_path,
            "run_report_path": run_report_path,
            "location": location,
            "request_delay_seconds": delay,
        }
        _write_run_report(report)
        return report

    search = (query or _query()).strip()
    limit = max_pages or _max_pages()
    if source == "OPENWEBNINJA":
        limit = 1

    archive = _load_archive()
    latest_archive = _latest_archive_records(archive)

    pages_fetched = 0
    items: List[Dict[str, Any]] = []
    gaps: List[str] = []
    stop = None
    stop_reason = None
    total_results: Optional[int] = None
    run_started_at = _now_iso()

    for page in range(1, limit + 1):
        if page > 1 and delay > 0:
            time.sleep(delay)
        response = search_page(search, page)
        if response["success"]:
            pages_fetched += 1
            if total_results is None:
                total_results = response.get("total_results")
            items.extend(response["items"])
            no_of_pages = response.get("no_of_pages")
            if isinstance(no_of_pages, int) and page >= no_of_pages:
                stop = no_of_pages
                break
        else:
            gaps.extend(response.get("data_gaps") or [])
            stop_reason = _stop_reason(response)
            break

    if not pages_fetched:
        report = {
            "status": "failed",
            "generated_at": _now_iso(),
            "stop_reason": stop_reason or "failed",
            "query": search,
            "pages_fetched": 0,
            "items_fetched": 0,
            "requests_used": 0,
            "credits_estimate": 0,
            "csv_rows_written": 0,
            "fetched": [],
            "updated": [],
            "skipped": [],
            "held_for_review": [],
            "failed": list(gaps),
            "counts": {"fetched": 0, "updated": 0, "skipped": 0, "held_for_review": 0, "failed": len(gaps)},
            "snapshot_path": snapshot_path,
            "archive_path": archive_path,
            "run_report_path": run_report_path,
            "location": location,
            "request_delay_seconds": delay,
            "data_gaps": gaps,
            "message": "Last-good archive, snapshot, and CSV were preserved; no catalog files were overwritten.",
        }
        _write_run_report(report)
        return report

    fetched_records, skipped, held = _classify_items(items, latest_archive)
    for record in fetched_records:
        archive.append(dict(record))
    _save_archive(archive)

    report = _build_report(
        search=search,
        pages_fetched=pages_fetched,
        items=fetched_records,
        gaps=gaps,
        total_results=total_results,
        skipped=skipped,
        held=held,
        failed_requests=gaps,
        stop_reason=stop_reason,
        location=location,
        request_delay_seconds=delay,
        run_started_at=run_started_at,
        archive_record_count=len(archive),
        archive_path=archive_path,
        run_report_path=run_report_path,
    )
    if stop_reason:
        report["status"] = "partial"
        report["message"] = f"Run stopped after {pages_fetched} page(s); stop reason: {stop_reason}."
    else:
        report["status"] = "ok"
    report["stopped_at_page"] = stop
    _write_run_report(report)
    return report


def _classify_items(
    items: List[Dict[str, Any]],
    latest_archive: Dict[tuple, Dict[str, Any]],
) -> tuple:
    """Conservative within-run/archive dedupe: fetched / skipped / held."""
    fetched: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    held: List[Dict[str, Any]] = []
    seen_ids: Dict[str, str] = {}
    seen_names: set = set()

    for item in items:
        if not item.get("item_name"):
            held.append({**item, "reason": "missing_name"})
            continue
        price = item.get("sale_price")
        if price is None:
            price = item.get("regular_price")
        if not _is_number(price) or price <= 0:
            held.append({**item, "reason": "no_price"})
            continue

        normalized = _normalize_name(item["item_name"])
        item_id = item.get("costco_item_id")

        if item_id:
            if item_id in seen_ids:
                if _normalize_name(seen_ids[item_id]) == normalized:
                    skipped.append({**item, "reason": "duplicate_item_id"})
                else:
                    held.append({**item, "reason": "title_conflict"})
                continue
            seen_ids[item_id] = item["item_name"]
        elif normalized in seen_names:
            skipped.append({**item, "reason": "duplicate_name"})
            continue
        else:
            seen_names.add(normalized)

        prior = latest_archive.get(_archive_key(item))
        if prior is not None:
            if _normalize_name(prior.get("item_name")) != normalized:
                held.append({
                    **item,
                    "reason": "title_conflict",
                    "prior_item_name": prior.get("item_name"),
                })
                continue
            prior_pack = _normalize_pack(prior.get("pack_size"))
            item_pack = _normalize_pack(item.get("pack_size"))
            if prior_pack and item_pack and prior_pack != item_pack:
                held.append({
                    **item,
                    "reason": "pack_size_conflict",
                    "prior_pack_size": prior.get("pack_size"),
                })
                continue

        fetched.append(item)
    return fetched, skipped, held


def _normalize_pack(value) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", str(value)).casefold()


def _build_report(
    search: str,
    pages_fetched: int,
    items: List[Dict[str, Any]],
    gaps: List[str],
    total_results: Optional[int],
    skipped: Optional[List[Dict[str, Any]]] = None,
    held: Optional[List[Dict[str, Any]]] = None,
    failed_requests: Optional[List[str]] = None,
    stop_reason: Optional[str] = None,
    location: Optional[Dict[str, str]] = None,
    request_delay_seconds: float = 0.0,
    run_started_at: Optional[str] = None,
    archive_record_count: Optional[int] = None,
    archive_path: Optional[str] = None,
    run_report_path: Optional[str] = None,
) -> Dict[str, Any]:
    fetched_at = _now_iso()
    skipped = skipped or []
    held = held or []
    failed_requests = failed_requests or []
    existing_rows = _load_existing_rows()
    reconciled = _reconcile(items, existing_rows)

    snapshot_path = _snapshot_path()
    parent = os.path.dirname(snapshot_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    snapshot = {
        "generated_at": fetched_at,
        "run_started_at": run_started_at,
        "query": search,
        "pages_fetched": pages_fetched,
        "credits_estimate": pages_fetched * CREDITS_PER_PAGE,
        "total_results": total_results,
        "items": items,
        "skipped": skipped,
        "held_for_review": held,
        "unmatched": reconciled["unmatched"],
        "stale_rows": reconciled["stale"],
        "data_gaps": gaps,
        "location": location,
        "stop_reason": stop_reason,
    }
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)

    csv_path = costco_client._resolve_csv_path()
    if reconciled["rows"] and csv_path:
        _write_csv(csv_path, reconciled["rows"])

    updated_names = [i.get("item_name") for i in items if i.get("match") == "updated"]
    report = {
        "status": "ok",
        "generated_at": fetched_at,
        "stop_reason": stop_reason,
        "query": search,
        "pages_fetched": pages_fetched,
        "items_fetched": len(items),
        "requests_used": pages_fetched,
        "credits_estimate": pages_fetched * CREDITS_PER_PAGE,
        "csv_rows_written": len(reconciled["rows"]),
        "rows_updated": sum(1 for i in items if i.get("match") == "updated"),
        "rows_appended": sum(1 for i in items if i.get("match") == "appended"),
        "fetched": [i.get("item_name") for i in items],
        "updated": updated_names,
        "skipped": [i.get("item_name") for i in skipped],
        "held_for_review": held,
        "failed": list(failed_requests),
        "counts": {
            "fetched": len(items),
            "updated": len(updated_names),
            "skipped": len(skipped),
            "held_for_review": len(held),
            "failed": len(failed_requests),
        },
        "stale_rows_count": len(reconciled["stale"]),
        "unmatched_count": len(reconciled["unmatched"]),
        "snapshot_path": snapshot_path,
        "csv_path": csv_path,
        "archive_path": archive_path or _archive_path(),
        "archive_record_count": archive_record_count,
        "run_report_path": run_report_path or _run_report_path(),
        "location": location or _location(),
        "request_delay_seconds": request_delay_seconds,
        "cost_basis": "costco_online" if catalog_source() == "OPENWEBNINJA" else "business_delivery_online",
        "cost_status": "discovery_only",
        "cost_buffer_percent": _buffer_percent(),
        "data_gaps": gaps,
    }
    return report


def export_catalog() -> Dict[str, Any]:
    """Re-export the CSV from the latest discovery archive records.

    No network calls. Falls back to the last snapshot when the archive is
    missing. Only the latest record per (item id, delivery zip) is
    exported; stale CSV rows are preserved for review.
    """
    archive = _load_archive()
    snapshot_path = _snapshot_path()
    csv_path = costco_client._resolve_csv_path()

    if archive:
        latest = _latest_archive_records(archive)
        records = list(latest.values())
        source = "archive"
    elif os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        records = snapshot.get("items") or []
        source = "snapshot"
    else:
        return {
            "status": "missing_snapshot",
            "message": f"No archive or snapshot found. Run a refresh first.",
            "csv_rows_written": 0,
            "archive_path": _archive_path(),
            "snapshot_path": snapshot_path,
        }

    reconciled = _reconcile([dict(r) for r in records], _load_existing_rows())
    if reconciled["rows"] and csv_path:
        _write_csv(csv_path, reconciled["rows"])

    return {
        "status": "ok",
        "source": source,
        "records_used": len(records),
        "csv_rows_written": len(reconciled["rows"]),
        "unmatched_count": len(reconciled["unmatched"]),
        "stale_rows_count": len(reconciled["stale"]),
        "csv_path": csv_path,
        "archive_path": _archive_path(),
        "snapshot_path": snapshot_path,
        "cost_buffer_percent": _buffer_percent(),
        "cost_status": "discovery_only",
    }


def status() -> Dict[str, Any]:
    source = catalog_source()
    key_env = {"OPENWEBNINJA": "OPENWEBNINJA_API_KEY", "UNWRANGLE": "UNWRANGLE_API_KEY"}.get(source)
    snapshot_path = _snapshot_path()
    archive_path = _archive_path()
    snapshot = None
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except (json.JSONDecodeError, OSError):
            snapshot = None

    archive = _load_archive()
    return {
        "catalog_source": source,
        "api_key_configured": bool(os.getenv(key_env)) if key_env else False,
        "snapshot_exists": os.path.exists(snapshot_path),
        "snapshot_generated_at": (snapshot or {}).get("generated_at"),
        "snapshot_items": len((snapshot or {}).get("items") or []),
        "archive_exists": os.path.exists(archive_path),
        "archive_record_count": len(archive),
        "archive_path": archive_path,
        "detail_path": _detail_path(),
        "detail_enabled": _detail_enabled(),
        "detail_record_count": len(_load_product_details()),
        "invoice_path": _invoice_path(),
        "invoice_record_count": len(_load_invoices()),
        "ledger_path": _ledger_path(),
        "ledger_entries": len(_load_ledger()),
        "run_report_path": _run_report_path(),
        "location": _location(),
        "request_delay_seconds": _request_delay(),
        "cost_buffer_percent": _buffer_percent(),
        "csv_path": costco_client._resolve_csv_path(),
        "csv_state": costco_client.catalog_state(),
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Costco discovery catalog refresh (OpenWebNinja / Unwrangle)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show connector status")
    refresh = sub.add_parser("refresh", help="fetch, snapshot, and export the catalog")
    refresh.add_argument("--query", help="search query (default: COSTCO_CATALOG_QUERY or kirkland)")
    refresh.add_argument("--max-pages", type=int, help="page cap (default: COSTCO_CATALOG_MAX_PAGES)")
    sub.add_parser("export", help="re-export CSV from the last snapshot (no network)")
    details = sub.add_parser("details", help="layer-2 product-detail store operations")
    details_sub = details.add_subparsers(dest="details_command", required=True)
    details_import = details_sub.add_parser("import", help="import analyst product-detail records (CSV/JSON)")
    details_import.add_argument("--path", required=True, help="CSV or JSON import file")
    details_refresh = details_sub.add_parser("refresh", help="fetch detail records for specific Costco item IDs (UNWRANGLE, gated)")
    details_refresh.add_argument("--item-ids", required=True, help="comma-separated Costco item IDs")
    invoices = sub.add_parser("invoices", help="layer-3 invoice-confirmed store operations")
    invoices_sub = invoices.add_subparsers(dest="invoices_command", required=True)
    invoices_import = invoices_sub.add_parser("import", help="import Business Center invoice rows (CSV/JSON)")
    invoices_import.add_argument("--path", required=True, help="CSV or JSON import file")
    mapping = sub.add_parser("mapping", help="verified ASIN -> Costco item_name ledger operations (offline)")
    mapping_sub = mapping.add_subparsers(dest="mapping_command", required=True)
    mapping_import = mapping_sub.add_parser("import", help="import verified mappings (CSV/JSON)")
    mapping_import.add_argument("--path", required=True, help="CSV (asin,item_name) or JSON {\"ASIN\": \"item name\"} import file")
    mapping_sub.add_parser("status", help="show ledger path and entry count (read-only)")
    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(status(), indent=2, default=str))
        return

    if args.command == "refresh":
        report = refresh_catalog(query=args.query, max_pages=args.max_pages)
        print(json.dumps(report, indent=2, default=str))
        return

    if args.command == "export":
        report = export_catalog()
        print(json.dumps(report, indent=2, default=str))
        return

    if args.command == "details":
        if args.details_command == "import":
            report = import_product_detail(args.path)
        else:
            report = refresh_product_details(args.item_ids.split(","))
        print(json.dumps(report, indent=2, default=str))
        return

    if args.command == "invoices":
        report = import_invoices(args.path)
        print(json.dumps(report, indent=2, default=str))
        return

    if args.command == "mapping":
        if args.mapping_command == "import":
            report = import_ledger(args.path)
        else:
            report = {"status": "ok", "ledger_entries": len(_load_ledger()),
                      "ledger_path": _ledger_path(), "exists": os.path.exists(_ledger_path())}
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    _cli()
