"""DataForSEO Amazon Merchant adapter (exclusive primary enrichment provider).

Live transport is armed ONLY when BOTH:
  DATAFORSEO_ENABLED = "true"          (feature flag)
  DATAFORSEO_TRANSPORT_ENABLED = "true" (runtime arm)
  DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD are set
Without the arm, every call returns a disabled shape (no network).

What DataForSEO actually returns (verified against the live Merchant API docs):
  * asin task  -> amazon_product_info: title, price_from/price_to (current
    listing price), rating {value, votes_count}, categories, and a
    `product_information` block whose "Item details" body contains a
    "Best Sellers Rank" TEXT string (e.g. "#1,291 in Video Games ...").
    It does NOT return a structured Buy Box winner/seller.
  * sellers task -> list of amazon_seller_item: seller_name, seller_url
    (carries `isAmazonFulfilled=0|1` and `seller=...`), price {current,
    regular, currency}, condition, rating.

Mapping (null-first; nothing invented):
  * buy_box_price      <- asin.price_from (current listing price proxy)
  * bsr                <- parsed from "Best Sellers Rank" text via intel_schema
  * title / rating / categories <- asin task
  * offers[]           <- sellers task; FBA/FBM derived from isAmazonFulfilled
                          in seller_url (and Amazon as seller => FBA)
 * buy_box_seller     <- sellers item flagged buybox_winner when present,
                           else null (DataForSEO does not reliably flag it)
 * cost_usd           <- sum of raw provider-reported task cost (fractional USD)
 * credits_used       <- None (DataForSEO does not report a separate credit
                          field; cost and credits must not be conflated)

The normalized result shape mirrors easyparser_client / rapidapi_client so
market_snapshot_store.build_snapshot consumes it unchanged.
"""

import os
import re
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

from proof_batch_contracts import (
    merchant_task_post_url,
    merchant_task_get_url,
    evaluate_dataforseo_task_post,
    evaluate_dataforseo_task_get,
    GuardError,
)


class AmbiguousTransportError(Exception):
    """Raised when a DataForSEO transport call returns an ambiguous outcome
    (e.g., a POST timeout) where success/failure cannot be determined, so the
    run must NOT be auto-retried or silently marked successful."""

    pass


class DataForSEOStandardTransport:
    """Standard DataForSEO transport. Construction makes zero network calls.

    A real call only occurs when ``allow_live`` is True AND the runtime arm
    (``DATAFORSEO_TRANSPORT_ENABLED``) and credentials are present. Otherwise
    ``submit`` fails closed with ``GuardError`` (no network, no fabricated
    result). On an ambiguous timeout it raises ``AmbiguousTransportError`` so
    the caller reconciles manually instead of retrying blindly.
    """

    def __init__(self, allow_live: bool = False):
        self.allow_live = bool(allow_live)

    def submit(self, *args, **kwargs):
        if not self.allow_live or not DATAFORSEO_TRANSPORT_ENABLED or not _auth():
            raise GuardError("DataForSEO transport not armed; no network call made")
        url = kwargs.get("url") or (args[0] if args else merchant_task_post_url())
        payload = kwargs.get("payload") or (args[1] if len(args) > 1 else {})
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
                auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD),
            )
        except requests.exceptions.Timeout:
            raise AmbiguousTransportError("POST timeout, outcome unknown")
        except requests.exceptions.RequestException as exc:
            raise GuardError("dataforseo transport error: %s" % exc)
        if resp.status_code != 200:
            raise GuardError("dataforseo transport HTTP %d" % resp.status_code)
        return resp.json()


try:
    load_dotenv()
except Exception:
    pass

try:
    from intel_schema import normalize_bsr  # type: ignore
except Exception:
    normalize_bsr = None  # type: ignore

DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")
DATAFORSEO_ENABLED = os.getenv("DATAFORSEO_ENABLED", "").lower() == "true"
DATAFORSEO_TRANSPORT_ENABLED = os.getenv("DATAFORSEO_TRANSPORT_ENABLED", "").lower() == "true"

REQUEST_TIMEOUT_SECONDS = 60
ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")
MAX_POLL_SECONDS = 120
POLL_INTERVAL_SECONDS = 5


def load_config() -> Dict[str, Any]:
    return {
        "enabled": DATAFORSEO_ENABLED,
        "transport_armed": DATAFORSEO_TRANSPORT_ENABLED
        and bool(DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD),
        "has_credentials": bool(DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD),
    }


def _empty_result(asin: Optional[str]) -> Dict[str, Any]:
    return {
        "source": "dataforseo",
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
        "categories": None,
        "data_gaps": [],
        "provider_endpoint": None,
    }


def _auth() -> Optional[tuple]:
    if not (DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD):
        return None
    return (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)


def _post_task(family: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Merchant task; returns the acceptance verdict dict."""
    url = merchant_task_post_url(family)
    try:
        resp = requests.post(
            url, json=payload, auth=_auth(), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as exc:
        raise GuardError("dataforseo transport error: %s" % exc)
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        raise GuardError("dataforseo response was not valid JSON")
    return evaluate_dataforseo_task_post(body, family)


def _get_task(family: str, task_id: str) -> Dict[str, Any]:
    """Poll a Merchant task to completion; returns the acceptance verdict dict."""
    url = merchant_task_get_url(family, task_id)
    deadline = time.monotonic() + MAX_POLL_SECONDS
    last = None
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, auth=_auth(), timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as exc:
            raise GuardError("dataforseo transport error: %s" % exc)
        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError):
            raise GuardError("dataforseo response was not valid JSON")
        verdict = evaluate_dataforseo_task_get(body, family, task_id)
        last = verdict
        if verdict.get("accepted"):
            return verdict
        if not verdict.get("pending"):
            return verdict
        time.sleep(POLL_INTERVAL_SECONDS)
    return last or {"accepted": False, "classification": "provider_rejected_unknown",
                    "reason": "poll timeout"}


def _extract_items(result_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull the inner items[] list from a task_get result_item."""
    if not isinstance(result_item, dict):
        return []
    items = result_item.get("items")
    if isinstance(items, list):
        return items
    return []


def _parse_bsr_from_product_info(item: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
    """Extract the 'Best Sellers Rank' TEXT from product_information and parse."""
    raw = None
    for section in item.get("product_information") or []:
        if not isinstance(section, dict):
            continue
        body = section.get("body")
        if isinstance(body, dict) and body.get("Best Sellers Rank"):
            raw = body.get("Best Sellers Rank")
            break
    if raw is None:
        gaps.append("BSR not present in DataForSEO product_information")
        if normalize_bsr is None:
            return {"bsr_raw": None, "bsr_primary_rank": None,
                    "bsr_primary_category": None, "bsr_capture_status": "unavailable",
                    "bsr_source": "dataforseo", "bsr_captured_at": None}
        return normalize_bsr(None, source="dataforseo")
    if normalize_bsr is not None:
        return normalize_bsr(raw, source="dataforseo")
    return {"bsr_raw": raw, "bsr_primary_rank": None, "bsr_primary_category": None,
            "bsr_capture_status": "unavailable", "bsr_source": "dataforseo",
            "bsr_captured_at": None}


def _seller_fulfillment(seller_url: Optional[str]):
    """Return (is_fba, is_fbm) derived from isAmazonFulfilled in seller_url."""
    if not isinstance(seller_url, str) or "isAmazonFulfilled=" not in seller_url:
        return (None, None)
    try:
        qs = parse_qs(urlparse(seller_url).query)
        flag = qs.get("isAmazonFulfilled", [None])[0]
    except Exception:
        return (None, None)
    if flag == "1":
        return (True, False)
    if flag == "0":
        return (False, True)
    return (None, None)


def _normalize_asin(asin: str, item: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
    result = _empty_result(asin)
    result["title"] = item.get("title") or item.get("name") or None
    result["provider_asin"] = item.get("data_asin") or item.get("asin") or asin
    result["categories"] = [c.get("category") for c in (item.get("categories") or [])
                             if isinstance(c, dict) and c.get("category")]

    price = item.get("price_from")
    if isinstance(price, (int, float)) and not isinstance(price, bool):
        result["buy_box_price"] = float(price)
        result["buy_box_price_raw"] = float(price)
    else:
        gaps.append("DataForSEO asin task missing current price (price_from)")

    rating = item.get("rating")
    if isinstance(rating, dict):
        result["rating_value"] = rating.get("value")
        result["rating_votes"] = rating.get("votes_count")

    result["bsr"] = _parse_bsr_from_product_info(item, gaps)
    return result


def _normalize_sellers(result: Dict[str, Any], items: List[Dict[str, Any]],
                       gaps: List[str]) -> None:
    offers = []
    fba = fbm = amazon = 0
    buy_box_seller = None
    for s in items:
        if not isinstance(s, dict):
            continue
        price = s.get("price")
        if isinstance(price, dict):
            price_val = price.get("current")
        else:
            price_val = price if isinstance(price, (int, float)) and not isinstance(price, bool) else None
        seller_url = s.get("seller_url")
        # DataForSEO sellers tasks frequently include an all-None header/aggregate
        # row as the first item. Drop rows that carry no usable information so they
        # don't pollute fba/fbm counts or the offers list.
        if s.get("seller_name") is None and seller_url is None and price is None:
            continue
        is_fba, is_fbm = _seller_fulfillment(seller_url)
        seller_name = s.get("seller_name")
        if seller_name == "Amazon":
            is_fba, is_fbm = True, False
        if is_fba:
            fba += 1
        elif is_fbm:
            fbm += 1
        if seller_name == "Amazon":
            amazon += 1
        if s.get("buybox_winner") is True and buy_box_seller is None:
            buy_box_seller = seller_name
        offers.append({
            "position": s.get("rank_group") or s.get("position"),
            "buybox_winner": bool(s.get("buybox_winner")),
            "price": float(price_val) if isinstance(price_val, (int, float)) else None,
            "condition": s.get("condition"),
            "seller_id": _seller_id_from_url(seller_url),
            "seller_name": seller_name,
            "is_prime": None,
            "is_fba": is_fba,
            "is_fbm": is_fbm,
            "fulfillment": "FBA" if is_fba else ("FBM" if is_fbm else "Unknown"),
            "ships_from": s.get("ships_from"),
        })
    result["offers"] = offers
    result["offers_returned_count"] = len(offers)
    result["offer_count"] = len(offers) or None
    result["observed_fba_offer_count"] = fba
    result["observed_fbm_offer_count"] = fbm
    result["observed_amazon_offer_count"] = amazon
    if buy_box_seller is not None:
        result["buy_box_seller"] = buy_box_seller
    else:
        gaps.append("DataForSEO sellers task does not flag a Buy Box winner")


def _seller_id_from_url(seller_url: Optional[str]) -> Optional[str]:
    if not isinstance(seller_url, str) or "seller=" not in seller_url:
        return None
    try:
        qs = parse_qs(urlparse(seller_url).query)
        return qs.get("seller", [None])[0]
    except Exception:
        return None


def get_dataforseo_offers(asin: str) -> Dict[str, Any]:
    """Merchant asin + sellers tasks -> shared normalized offer shape."""
    gaps: List[str] = []
    result = _empty_result(asin)
    result["provider_endpoint"] = "/v3/merchant/amazon/asin|sellers/task_post"
    if not DATAFORSEO_ENABLED:
        gaps.append("DataForSEO adapter not enabled (DATAFORSEO_ENABLED not true)")
        result["data_gaps"] = gaps
        return result
    if not DATAFORSEO_TRANSPORT_ENABLED or not _auth():
        gaps.append("DataForSEO transport not armed (DATAFORSEO_TRANSPORT_ENABLED/"
                    "credentials missing); no network call made")
        result["data_gaps"] = gaps
        return result
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        gaps.append("Invalid ASIN. Expected exactly 10 alphanumeric characters.")
        result["data_gaps"] = gaps
        return result

    cost_usd = 0.0
    try:
        asin_post = _post_task("asin", [{"asin": asin, "location_code": 2840,
                                         "language_code": "en_US"}])
        cost_usd += float(asin_post.get("provider_cost_cents") or 0.0)
        if not asin_post.get("accepted"):
            gaps.append("DataForSEO asin task rejected: %s" % asin_post.get("reason"))
            result["data_gaps"] = gaps
            result["credits_used"] = None
            result["cost_usd"] = cost_usd
            return result
        asin_get = _get_task("asin", asin_post["task_id"])
        asin_items = _extract_items(asin_get.get("result_item"))
        result = _normalize_asin(asin, asin_items[0] if asin_items else {}, gaps)

        sellers_post = _post_task("sellers", [{"asin": asin, "location_code": 2840,
                                               "language_code": "en_US"}])
        cost_usd += float(sellers_post.get("provider_cost_cents") or 0.0)
        if sellers_post.get("accepted"):
            sellers_get = _get_task("sellers", sellers_post["task_id"])
            sellers_items = _extract_items(sellers_get.get("result_item"))
            _normalize_sellers(result, sellers_items, gaps)
        else:
            gaps.append("DataForSEO sellers task rejected: %s" % sellers_post.get("reason"))
    except GuardError as exc:
        gaps.append("DataForSEO guard error: %s" % exc)

    result["credits_used"] = None
    result["cost_usd"] = cost_usd
    result["data_gaps"] = gaps
    return result


# ---------------------------------------------------------------------------
# Route-facing validation entry (used by main.py /api/dataforseo/validate)
# ---------------------------------------------------------------------------
def execute_validation(body: Dict[str, Any], operator_token: str = "") -> Dict[str, Any]:
    """Guarded single-ASIN DataForSEO Standard-queue cross-check."""
    cfg = load_config()
    if not cfg.get("enabled"):
        raise GuardError("DataForSEO adapter not available (DATAFORSEO_ENABLED not set)")
    if not cfg.get("transport_armed"):
        raise GuardError("DataForSEO transport not armed; no network call made")
    asin = (body or {}).get("asin")
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        raise GuardError("invalid asin")
    return get_dataforseo_offers(asin)
