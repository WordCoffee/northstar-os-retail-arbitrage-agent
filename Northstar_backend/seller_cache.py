"""Seller cache writer — normalized per-ASIN seller data to data/seller-offer-cache.json.

Writes the seller data contract compatible with map_seller_offer_contract shape:
  - asin
  - offer_data_status: available | partial | provider_error | unavailable
  - offer_data_source: brightdata | scrapedo | firecrawl | browserbase
  - offer_data_fetched_at
  - offer_data_note
  - offer_data_cached
  - total_sellers
  - fba_sellers (null — not extractable from free dp HTML)
  - fbm_sellers (null)
  - amazon_sellers (null)
  - buy_box: { available, seller_name, seller_id (null), fulfillment, price, ... }
  - offers: [] (empty — no per-seller roster from free dp HTML)
  - offers_returned: 0
  - offers_complete: false
  - offer_count: total_sellers (for compatibility)
  - buy_box_price
  - request_zip_code: null (not from dp)
  - observed_at
  - title
  - credits_used: 1 per request
  - credits_remaining: null (no REST endpoint for free tier balance)
  - data_gaps: ["Seller IDs not extractable from dp page; FBA/FBM split unavailable from free sources"]
  - seller_marker_counts (diagnostic)

Separate from the scanner enrichment cache (data/enriched-offer-cache.json).
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SELLER_CACHE_TTL_HOURS = 24.0

SELLER_STATUS_AVAILABLE = "available"
SELLER_STATUS_PARTIAL = "partial"
SELLER_STATUS_UNAVAILABLE = "unavailable"
SELLER_STATUS_PROVIDER_ERROR = "provider_error"


def _seller_cache_path() -> str:
    """Seller-detail cache (data/seller-offer-cache.json)."""
    raw = os.getenv("SELLER_CACHE_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(os.path.dirname(_BACKEND_DIR), raw)
    return os.path.join(os.path.dirname(_BACKEND_DIR), "data", "seller-offer-cache.json")


def _seller_cache_ttl_hours() -> float:
    """Hours a cached seller detail stays fresh; <= 0 disables the cache."""
    raw = os.getenv("SELLER_CACHE_TTL_HOURS")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DEFAULT_SELLER_CACHE_TTL_HOURS
    return value


def _load_seller_cache() -> Dict[str, Any]:
    path = _seller_cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_seller_payload(
    asin: str,
    seller_data: Dict,
    provider: str,
    title: Optional[str] = None,
    buy_box_price: Optional[float] = None,
    credits_used: int = 1,
) -> Dict:
    """Build the seller cache payload in map_seller_offer_contract shape.

    Args:
        asin: 10-char ASIN
        seller_data: output from extract_seller_data()
        provider: "brightdata" | "scrapedo" | "firecrawl" | "browserbase"
        title: product title (optional)
        buy_box_price: Buy Box price (optional, from shared parse)
        credits_used: credits consumed (default 1 per request)
    """
    buy_box_seller_name = seller_data.get("buy_box_seller_name")
    buy_box_fulfillment = seller_data.get("buy_box_fulfillment", "Unknown")
    total_sellers = seller_data.get("total_sellers")
    other_sellers_present = seller_data.get("other_sellers_present", False)
    lowest_price = seller_data.get("lowest_price")
    marker_counts = seller_data.get("marker_counts", {})

    buy_box_available = bool(buy_box_seller_name or (buy_box_price is not None))

    # Data gaps (honest)
    gaps = [
        "Seller IDs not extractable from dp page; FBA/FBM split unavailable from free sources",
    ]
    if buy_box_seller_name is None:
        gaps.append("Buy Box seller name not found on page")
    if total_sellers is None:
        gaps.append("Total seller count not found on page")

    # Determine status
    if total_sellers is not None and buy_box_seller_name is not None:
        status = SELLER_STATUS_AVAILABLE
    elif total_sellers is not None or buy_box_seller_name is not None:
        status = SELLER_STATUS_PARTIAL
    else:
        status = SELLER_STATUS_UNAVAILABLE

    payload = {
        "asin": asin,
        "offer_data_status": status,
        "offer_data_source": provider,
        "offer_data_fetched_at": _now_iso(),
        "offer_data_note": "; ".join(gaps) if status != SELLER_STATUS_AVAILABLE else None,
        "offer_data_cached": False,
        "total_sellers": total_sellers,
        "fba_sellers": None,
        "fbm_sellers": None,
        "amazon_sellers": None,
        "buy_box": {
            "available": buy_box_available,
            "seller_name": buy_box_seller_name,
            "seller_id": None,
            "fulfillment": buy_box_fulfillment,
            "price": buy_box_price,
            "shipping": None,
            "landed_price": None,
            "condition": None,
            "prime": None,
            "note": None if buy_box_available else "Buy Box seller not identified on dp page",
        },
        "offers": [],
        "offers_returned": 0,
        "offers_complete": False,
        "offer_count": total_sellers,
        "buy_box_price": buy_box_price,
        "request_zip_code": None,
        "observed_at": _now_iso(),
        "title": title,
        "credits_used": credits_used,
        "credits_remaining": None,
        "data_gaps": gaps,
        "seller_marker_counts": marker_counts,
    }

    return payload


def _cache_seller_detail(asin: Optional[str], payload: Dict) -> None:
    """Persist a successful seller payload by ASIN. Best effort."""
    if not asin or _seller_cache_ttl_hours() <= 0:
        return
    try:
        cache = _load_seller_cache()
        cache[asin] = {"payload": payload, "cached_at": _now_iso()}
        path = _seller_cache_path()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=str)
    except OSError:
        pass


def get_cached_seller_detail(asin: Optional[str]) -> Optional[Dict]:
    """Fresh cached seller detail for the ASIN, or None. Zero network."""
    if not asin:
        return None
    ttl = _seller_cache_ttl_hours()
    if ttl <= 0:
        return None
    entry = _load_seller_cache().get(asin)
    if not isinstance(entry, dict):
        return None
    payload = entry.get("payload")
    cached_at = entry.get("cached_at")
    if not isinstance(payload, dict) or not isinstance(cached_at, str):
        return None
    try:
        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if datetime.now(timezone.utc) - cached_dt > timedelta(hours=ttl):
        return None
    out = dict(payload)
    out["offer_data_cached"] = True
    return out


# For convenience import
from datetime import timedelta