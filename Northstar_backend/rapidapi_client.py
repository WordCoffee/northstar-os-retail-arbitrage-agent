"""RapidAPI Amazon adapter (replaces the deprecated Easyparser integration).

Reads RAPIDAPI_KEY / RAPIDAPI_HOST from the environment (.env, gitignored).
The key is never printed. Live calls happen ONLY inside get_rapidapi_product /
get_rapidapi_offers when explicitly invoked; nothing here runs at import time.

Honesty invariants (shared with intel_schema):
  - Unknown values are null (None); 0 is never a substitute for unknown.
  - BSR / Buy Box / FBA-FBM are captured ONLY when the provider response
    actually carries them. RapidAPI's amazon-product-data4 host is currently
    UNVERIFIED (a prior run returned a "No such app" error page), so the field
    paths below are defensive: any absent field stays null and is recorded in
    data_gaps. The exact JSON contract must be confirmed by a controlled live
    1-ASIN probe before trusting any non-null value.
  - This module returns the SAME normalized result shape as
    easyparser_client.get_easyparser_offers so market_snapshot_store.build_snapshot
    consumes it unchanged.

Endpoint paths (common RapidAPI Amazon shape; verify on live probe):
  GET /products/{asin}          -> product (title, price, sales_rank/bsr)
  GET /products/{asin}/offers   -> offer roster (price, seller, fba/fbm, buybox)
"""

import os
import re
import json
import requests
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from intel_schema import normalize_bsr
except Exception:  # pragma: no cover - allows import outside full env
    normalize_bsr = None

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "amazon-product-data4.p.rapidapi.com")
REQUEST_TIMEOUT_SECONDS = 60
ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

# Planning-only fallback. RapidAPI bills per the marketplace plan; the real
# per-call cost (if returned by the API) overrides this. Expressed in CENTS so
# it reuses the existing --max-credits budget machinery.
RAPIDAPI_ESTIMATED_COST_CENTS = 100


# ---------------------------------------------------------------------------
# Config / transport
# ---------------------------------------------------------------------------
def load_config() -> Dict[str, Any]:
    """Return runtime config without exposing the key value."""
    return {
        "enabled": bool(RAPIDAPI_KEY),
        "host": RAPIDAPI_HOST,
        "has_key": bool(RAPIDAPI_KEY),
    }


def _headers() -> Dict[str, str]:
    return {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _price_value(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        digits = re.sub(r"[^0-9.]", "", v)
        if digits:
            try:
                return float(digits)
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# Normalized result shape (mirrors easyparser_client.get_easyparser_offers)
# ---------------------------------------------------------------------------
def _empty_result(asin: Optional[str]) -> Dict[str, Any]:
    return {
        "source": "rapidapi",
        "asin": asin,
        "provider_asin": None,
        "request_id": None,
        "title": None,
        "offer_count": None,
        "offers_returned_count": 0,
        "buy_box_price": None,
        "buy_box_price_raw": None,
        "buy_box_seller": None,
        "buy_box_seller_id": None,
        "buy_box_is_fba": None,
        "buy_box_is_fbm": None,
        "buy_box_is_prime": None,
        "buy_box_condition": None,
        "observed_fba_offer_count": 0,
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": 0,
        "offers": [],
        "request_zip_code": None,
        "observed_at": None,
        "credits_used": None,
        "credits_remaining": None,
        "cost_usd": None,
        "data_gaps": [],
        "provider_endpoint": None,
    }


def _safe_offer(o: Any) -> Optional[Dict[str, Any]]:
    """Normalize one RapidAPI offer dict into the shared offer shape."""
    if not isinstance(o, dict):
        return None
    price = _price_value(
        o.get("price") or o.get("price_lower") or o.get("current_price")
        or o.get("buybox_price")
    )
    fba = bool(o.get("is_fba") or o.get("fulfillment_channel") == "AMAZON")
    fbm = bool(
        o.get("is_fbm")
        or o.get("fulfillment_channel") in ("MERCHANT", "FBM", "SELLER")
    )
    if fba:
        fulfillment = "FBA"
    elif fbm:
        fulfillment = "FBM"
    else:
        fulfillment = "Unknown"
    return {
        "position": o.get("position"),
        "buybox_winner": bool(o.get("is_buybox_winner") or o.get("buybox_winner")),
        "price": price,
        "condition": o.get("condition"),
        "seller_id": o.get("seller_id"),
        "seller_name": o.get("seller_name"),
        "seller_rating": o.get("seller_rating"),
        "seller_positive_percentage": o.get("seller_positive_percentage"),
        "seller_ratings_total": o.get("seller_ratings_total"),
        "is_prime": o.get("is_prime"),
        "is_fba": fba,
        "is_fbm": fbm,
        "fulfillment": fulfillment,
        "ships_from": o.get("ships_from"),
        "minimum_order_quantity": o.get("minimum_order_quantity"),
        "maximum_order_quantity": o.get("maximum_order_quantity"),
    }


def _parse_bsr(product: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
    """Best-effort BSR extraction. Null-first; never invents a rank."""
    if normalize_bsr is None:
        return {
            "bsr_raw": None, "bsr_primary_rank": None, "bsr_primary_category": None,
            "bsr_secondary_rank": None, "bsr_secondary_category": None,
            "bsr_capture_status": "unavailable", "bsr_source": "rapidapi",
            "bsr_captured_at": None,
        }
    raw = (
        product.get("bsr")
        or product.get("sales_rank")
        or product.get("salesRank")
    )
    if isinstance(raw, dict):
        # RapidAPI sometimes nests sales_rank as {category_id: {rank, category}}
        try:
            first = next(iter(raw.values()))
            if isinstance(first, dict):
                raw = "%s in %s" % (first.get("rank"), first.get("category"))
            else:
                raw = str(first)
        except Exception:
            raw = None
    if raw is None:
        gaps.append("BSR not returned by RapidAPI product endpoint")
        return normalize_bsr(None, source="rapidapi")
    return normalize_bsr(raw, source="rapidapi")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_rapidapi_product(asin: str) -> Dict[str, Any]:
    """GET /products/{asin}. Normalized product + BSR (null-first)."""
    result = _empty_result(asin)
    result["provider_endpoint"] = "/products/{asin}"
    if not RAPIDAPI_KEY:
        result["data_gaps"].append("RapidAPI API key is not configured.")
        return result
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        result["data_gaps"].append("Invalid ASIN. Expected exactly 10 alphanumeric characters.")
        return result
    try:
        resp = requests.get(
            "https://%s/products/%s" % (RAPIDAPI_HOST, asin),
            headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        result["data_gaps"].append("RapidAPI product request timed out.")
        return result
    except requests.exceptions.RequestException:
        result["data_gaps"].append("RapidAPI product request failed at the network level.")
        return result
    if resp.status_code != 200:
        result["data_gaps"].append("RapidAPI product API returned HTTP %s." % resp.status_code)
        return result
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        result["data_gaps"].append("RapidAPI product response was not valid JSON.")
        return result
    if not isinstance(payload, dict):
        result["data_gaps"].append("RapidAPI product response had an unexpected structure.")
        return result

    product = payload.get("product") if isinstance(payload.get("product"), dict) else payload
    result["title"] = product.get("title") or product.get("name") or None
    result["provider_asin"] = product.get("asin") or asin
    price = _price_value(product.get("price") or product.get("buybox_price"))
    if price is not None:
        result["buy_box_price"] = price
        result["buy_box_price_raw"] = price
    bsr = _parse_bsr(product, result["data_gaps"])
    result["bsr"] = bsr
    _capture_cost(payload, result)
    return result


def get_rapidapi_offers(asin: str) -> Dict[str, Any]:
    """GET /products/{asin}/offers -> shared normalized offer shape."""
    result = _empty_result(asin)
    result["provider_endpoint"] = "/products/{asin}/offers"
    if not RAPIDAPI_KEY:
        result["data_gaps"].append("RapidAPI API key is not configured.")
        return result
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        result["data_gaps"].append("Invalid ASIN. Expected exactly 10 alphanumeric characters.")
        return result
    try:
        resp = requests.get(
            "https://%s/products/%s/offers" % (RAPIDAPI_HOST, asin),
            headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        result["data_gaps"].append("RapidAPI offers request timed out.")
        return result
    except requests.exceptions.RequestException:
        result["data_gaps"].append("RapidAPI offers request failed at the network level.")
        return result
    if resp.status_code != 200:
        result["data_gaps"].append("RapidAPI offers API returned HTTP %s." % resp.status_code)
        return result
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        result["data_gaps"].append("RapidAPI offers response was not valid JSON.")
        return result
    if not isinstance(payload, dict):
        result["data_gaps"].append("RapidAPI offers response had an unexpected structure.")
        return result

    product = payload.get("product") if isinstance(payload.get("product"), dict) else payload
    result["title"] = product.get("title") or product.get("name") or None
    result["provider_asin"] = product.get("asin") or asin

    raw_offers = (
        product.get("offers")
        or product.get("sellers")
        or payload.get("offers")
        or []
    )
    if not isinstance(raw_offers, list):
        raw_offers = []

    offers = [o for o in (_safe_offer(x) for x in raw_offers) if isinstance(o, dict)]
    result["offers"] = offers
    result["offers_returned_count"] = len(offers)
    result["offer_count"] = product.get("total_offers") or len(offers) or None

    fba = sum(1 for o in offers if o.get("is_fba") is True)
    fbm = sum(1 for o in offers if o.get("is_fbm") is True)
    amazon = sum(1 for o in offers if o.get("fulfillment") == "Amazon")
    result["observed_fba_offer_count"] = fba
    result["observed_fbm_offer_count"] = fbm
    result["observed_amazon_offer_count"] = amazon

    buy_box = None
    for o in offers:
        if o.get("buybox_winner") is True:
            buy_box = o
            break
    if buy_box is None and offers:
        # Fall back to the top/lowest-priced offer for display only.
        buy_box = offers[0]
        result["data_gaps"].append("No explicit Buy Box winner flagged by RapidAPI; using first offer.")
    if buy_box is not None:
        result["buy_box_price"] = buy_box.get("price")
        result["buy_box_price_raw"] = buy_box.get("price")
        result["buy_box_seller"] = buy_box.get("seller_name")
        result["buy_box_seller_id"] = buy_box.get("seller_id")
        result["buy_box_is_fba"] = buy_box.get("is_fba")
        result["buy_box_is_fbm"] = buy_box.get("is_fbm")
        result["buy_box_condition"] = buy_box.get("condition")
    else:
        result["data_gaps"].append("RapidAPI returned no offers / no Buy Box winner.")

    _capture_cost(payload, result)
    return result


def _capture_cost(payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Record provider cost in USD; mirror into credits_used (cents)."""
    cost = payload.get("cost")
    if _is_number(cost):
        result["cost_usd"] = float(cost)
        result["credits_used"] = round(float(cost) * 100)
    else:
        result["credits_used"] = RAPIDAPI_ESTIMATED_COST_CENTS


# ---------------------------------------------------------------------------
# intel_schema mapping (offline-test / comparison-engine helper)
# ---------------------------------------------------------------------------
def to_intel_market(result: Dict[str, Any]) -> Dict[str, Any]:
    """Map a normalized RapidAPI result into an intel_schema facts.market dict."""
    bsr = result.get("bsr")
    if not isinstance(bsr, dict) and normalize_bsr is not None:
        bsr = normalize_bsr(None, source="rapidapi")
    bb = result.get("buy_box") or {}
    if not isinstance(bb, dict):
        bb = {}
    return {
        "amazon_price": result.get("buy_box_price"),
        "bsr": bsr or {
            "bsr_raw": None, "bsr_primary_rank": None, "bsr_primary_category": None,
            "bsr_secondary_rank": None, "bsr_secondary_category": None,
            "bsr_capture_status": "unavailable", "bsr_source": "rapidapi",
            "bsr_captured_at": None,
        },
        "buy_box": {
            "available": result.get("buy_box_price") is not None
            or bool(result.get("buy_box_seller")),
            "price": result.get("buy_box_price"),
            "seller_name": result.get("buy_box_seller"),
            "seller_id": result.get("buy_box_seller_id"),
            "fulfillment": _fulfillment_from_flags(
                result.get("buy_box_is_fba"), result.get("buy_box_is_fbm")
            ),
            "source": "rapidapi",
            "observed_at": result.get("observed_at"),
        },
        "seller_counts": {
            "total_observed": result.get("offers_returned_count"),
            "fba_observed": result.get("observed_fba_offer_count"),
            "fbm_observed": result.get("observed_fbm_offer_count"),
            "amazon_observed": result.get("observed_amazon_offer_count"),
            "claimed_total": result.get("offer_count"),
        },
        "coverage": {
            "offer_list_available": result.get("offers_returned_count", 0) > 0,
            "offers_complete_status": "full" if result.get("offers_returned_count", 0) > 0 else "unknown",
            "coverage_reason": "rapidapi live roster" if result.get("offers_returned_count", 0) > 0
            else "no rapidapi offers returned",
        },
        "offers": result.get("offers", []),
    }


def _fulfillment_from_flags(is_fba, is_fbm) -> Optional[str]:
    if is_fba is True:
        return "FBA"
    if is_fbm is True:
        return "FBM"
    return None
