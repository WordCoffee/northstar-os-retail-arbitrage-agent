"""Per-ASIN offer enrichment for the Kirkland Product Scout.

One opt-in flag selects the provider:

    SCANNER_OFFER_ENRICHMENT = unset/empty | 0 | false | no | off | OFF
                             | invalid text        -> disabled (cache-only)
                             | 1 | true | yes | on -> enabled, default provider
                             | AUTO | EASYPARSER | BRIGHTDATA | CHOCODATA
                             | UNWRANGLE            -> enabled, that provider

No provider is ever selected from an unset variable: unset means local/
cache-only with zero outbound calls.

- EASYPARSER (default when enabled): get_easyparser_offers(asin) — offer
  counts, observed FBA/FBM counts, Buy Box price and price range.
- BRIGHTDATA: enrich_product(asin or URL) — dataset results including any
  listing-reported FBA fee and monthly-sales signal the dataset provides.
- CHOCODATA: /amazon/product page (5 credits/ASIN) — Buy Box price, seller
  count, item weight -> FBA fee estimate, sales rank; gated to
  Costco-matched ASINs (see product_analysis).
- UNWRANGLE: amazon_detail (1 credit/ASIN for Amazon US, 2.5 elsewhere) —
  Buy Box price, buying offers, Item Weight from the details table -> FBA
  fee estimate, bestseller rank, past-month sales, rating; gated to
  Costco-matched ASINs like CHOCODATA.
- AUTO: try Easyparser first; use Bright Data only when the Easyparser
  result is missing fields the ranking model needs (seller counts, Buy Box
  price, price range) or the provider failed. Best effort wins.

Providers return the same safe offer shape product_analysis expects, with
nulls (never zeros) for anything unknown, and never raise. With the flag
off (or invalid), the offline placeholder is used, so the Scout keeps
working with zero network calls. Every result carries data provenance
(offer_data_provider, enrichment_status, enriched_at) so decisions can
always trace which source produced the values.

The FBA fee is only ever preserved from provider listing data (or the
legacy weight estimate in product_analysis). It is never invented: a fee
the provider does not supply stays None and the product stays in the
Needs Fee Verification review state.
"""

import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from bright_data_client import get_product_detail
from brightdata_client import enrich_product, get_offer_data
from easyparser_client import get_easyparser_offers
from env_flags import env_flag
import live_gate
import market_snapshot_store
from pricing import estimate_fba_fee
import competition_analytics

load_dotenv()

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_OFFER_CACHE_TTL_HOURS = 24.0

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")
ASIN_URL_PATTERN = re.compile(r"/(?:dp|gp/product|product)/([A-Za-z0-9]{10})")

CHOCODATA_API_KEY = os.getenv("CHOCODATA_API_KEY")
CHOCODATA_PRODUCT_URL = os.getenv(
    "CHOCODATA_PRODUCT_URL",
    "https://api.chocodata.com/api/v1/amazon/product",
)
CHOCODATA_REQUEST_TIMEOUT_SECONDS = 60

UNWRANGLE_API_KEY = os.getenv("UNWRANGLE_API_KEY")
UNWRANGLE_URL = os.getenv("UNWRANGLE_URL", "https://data.unwrangle.com/api/getter/")
UNWRANGLE_PLATFORM = "amazon_detail"
UNWRANGLE_REQUEST_TIMEOUT_SECONDS = 60


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _enrichment_mode() -> str:
    """Resolve SCANNER_OFFER_ENRICHMENT with strict parsing.

    Unset/empty, 0, false, no, off, OFF, and arbitrary invalid strings
    return "OFF" (cache-only, zero outbound calls). Explicit boolean
    values (1/true/yes/on) enable the default provider. Documented
    provider tokens (AUTO/EASYPARSER/BRIGHTDATA/CHOCODATA/UNWRANGLE) are
    explicit opt-ins for that provider. Never truthiness parsing.

    Hard containment boundary: when SCANNER_LIVE_ALLOWED is not an
    explicit opt-in this always returns "OFF", so every scan is
    cache-only regardless of SCANNER_OFFER_ENRICHMENT.
    """
    if not live_gate.live_enabled():
        return "OFF"
    raw = (os.getenv("SCANNER_OFFER_ENRICHMENT") or "").strip().upper()
    if raw in ("AUTO", "EASYPARSER", "BRIGHTDATA", "CHOCODATA", "UNWRANGLE"):
        return raw
    if env_flag("SCANNER_OFFER_ENRICHMENT"):
        return "BRIGHTDATA"
    return "OFF"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _completeness(shape: Dict) -> Dict[str, bool]:
    """Fields the ranking model depends on, and whether each is present."""
    return {
        "sellers": _is_number(shape.get("total_sellers")),
        "fba_sellers": _is_number(shape.get("fba_sellers")),
        "buy_box": _is_number(shape.get("buy_box_price")),
        "range": _is_number(shape.get("lowest_price")) and _is_number(shape.get("highest_price")),
    }


def _is_complete_for_ranking(shape: Dict) -> bool:
    return all(_completeness(shape).values())


def _provenance(provider: str, status: str, enriched_at: Optional[str]) -> Dict:
    return {
        "offer_data_provider": provider,
        "enrichment_status": status,
        "enriched_at": enriched_at,
    }


def _apply_provenance(shape: Dict, provider: str, status: str, enriched_at: Optional[str]) -> Dict:
    shape.update(_provenance(provider, status, enriched_at))
    return shape


def _extract_asin(identifier: Optional[str]) -> Optional[str]:
    if not identifier:
        return None
    if ASIN_PATTERN.fullmatch(identifier):
        return identifier
    match = ASIN_URL_PATTERN.search(identifier)
    return match.group(1) if match else None


def _offer_price_value(offer: Dict) -> Optional[float]:
    price = offer.get("price")
    if isinstance(price, dict):
        value = price.get("value")
        if _is_number(value):
            return float(value)
        return None
    if _is_number(price):
        return float(price)
    return None


def _seller_type_label(offer: Dict) -> str:
    if offer.get("is_fba") is True:
        return "FBA"
    if offer.get("is_fbm") is True:
        return "FBM"
    return "unknown"


def _map_easyparser_offer(data: Dict, asin: Optional[str]) -> Dict:
    shape = get_offer_data(asin or "")
    if not data:
        return shape

    offers = [o for o in (data.get("offers") or []) if isinstance(o, dict)]
    prices = [_offer_price_value(o) for o in offers]
    prices = [p for p in prices if p is not None]

    lowest = min(prices) if prices else None
    highest = max(prices) if prices else None

    def type_at(price_value):
        if price_value is None:
            return "unknown"
        for o in offers:
            if _offer_price_value(o) == price_value:
                return _seller_type_label(o)
        return "unknown"

    buy_box = data.get("buy_box_price")
    amazon_price = buy_box if _is_number(buy_box) and buy_box > 0 else None

    shape.update(
        {
            "amazon_price": amazon_price,
            "buy_box_price": buy_box,
            "lowest_price": lowest,
            "highest_price": highest,
            "total_sellers": data.get("offer_count"),
            "fba_sellers": data.get("observed_fba_offer_count"),
            "fba_sellers_estimated": False,
            "lowest_price_seller_type": type_at(lowest),
            "highest_price_seller_type": type_at(highest),
            "monthly_sales_estimate": None,
            "monthly_sales_estimated": False,
            "fba_fee": None,
            "title": data.get("title"),
        }
    )

    any_data = any(_completeness(shape).values()) or _is_number(shape.get("amazon_price")) and shape["amazon_price"] > 0
    if not any_data:
        return _apply_provenance(shape, "easyparser", "failed", data.get("observed_at"))
    status = "complete" if _is_complete_for_ranking(shape) else "partial"
    return _apply_provenance(shape, "easyparser", status, data.get("observed_at") or _now_iso())


def _map_brightdata_offer(data: Dict, identifier: str) -> Dict:
    shape = get_offer_data(identifier)
    if not data:
        return shape

    offers = [o for o in (data.get("sellers") or []) if isinstance(o, dict)]
    prices = [_offer_price_value(o) for o in offers]
    prices = [p for p in prices if p is not None]

    lowest = data.get("lowest_price")
    highest = data.get("highest_price")
    if lowest is None and prices:
        lowest = min(prices)
    if highest is None and prices:
        highest = max(prices)

    fba_sellers = data.get("fba_sellers")
    if fba_sellers is None and offers:
        fba_sellers = sum(
            1
            for o in offers
            if o.get("is_fba") is True
            or (isinstance(o.get("fulfillment"), str) and "fba" in o.get("fulfillment", "").lower())
        )

    amazon_price = data.get("amazon_price")
    amazon_price = amazon_price if _is_number(amazon_price) and amazon_price > 0 else None

    shape.update(
        {
            "amazon_price": amazon_price,
            "buy_box_price": data.get("buy_box_price"),
            "lowest_price": lowest,
            "highest_price": highest,
            "total_sellers": data.get("seller_count"),
            "fba_sellers": fba_sellers,
            "fba_sellers_estimated": False,
            "lowest_price_seller_type": "unknown",
            "highest_price_seller_type": "unknown",
            "monthly_sales_estimate": data.get("monthly_sales_estimate"),
            "monthly_sales_estimated": data.get("monthly_sales_estimated", False),
            "fba_fee": data.get("fba_fee"),
            "title": data.get("title"),
            # Category / browse-node metadata from the product-page parser.
            # Without this passthrough the fee engine would keep falling
            # back to Default 15% even when the HTML carried breadcrumbs.
            "amazon_category": data.get("amazon_category"),
            "browse_node_id": data.get("browse_node_id"),
            "breadcrumb": data.get("breadcrumb"),
            "category_source_hint": data.get("category_source_hint"),
        }
    )
    status = "complete" if _is_complete_for_ranking(shape) else "partial"
    return _apply_provenance(shape, "brightdata", status, _now_iso())


_WEIGHT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(pounds?|lbs?\.?|ounces?|oz\.?|kilograms?|kg\.?|\bg\b)",
    re.IGNORECASE,
)
_POUNDS_PER_UNIT = {
    "pound": 1.0,
    "lbs": 1.0,
    "lb": 1.0,
    "ounce": 1 / 16.0,
    "oz": 1 / 16.0,
    "kilogram": 2.20462,
    "kg": 2.20462,
}
_OFFER_COUNT_RE = re.compile(r"\((\d+)\)\s*from", re.IGNORECASE)
_PRICE_FROM_RE = re.compile(r"from\s*\$?([\d,.]+)", re.IGNORECASE)


def _parse_weight_lbs(raw) -> Optional[float]:
    """Parse '11.2 ounces' / '2.8 pounds' / '1.5 kg' into pounds, or None."""
    if not raw or not isinstance(raw, str):
        return None
    match = _WEIGHT_RE.search(raw)
    if not match:
        return None
    unit = match.group(2).lower().rstrip(".")
    if unit.endswith("s") and unit not in ("lbs",):
        unit = unit[:-1]
    if unit in ("pound", "lbs", "lb"):
        unit = "lb"
    elif unit in ("ounce", "oz"):
        unit = "oz"
    elif unit in ("kilogram", "kg"):
        unit = "kg"
    elif unit == "g":
        return float(match.group(1)) / 453.592
    else:
        return None
    return float(match.group(1)) * _POUNDS_PER_UNIT[unit]


def _extract_seller_count(pricing_str: Optional[str]) -> Optional[int]:
    if not pricing_str:
        return None
    match = _OFFER_COUNT_RE.search(pricing_str)
    if match:
        return int(match.group(1))
    return None


def _extract_price_from(pricing_str: Optional[str]) -> Optional[float]:
    if not pricing_str:
        return None
    match = _PRICE_FROM_RE.search(pricing_str)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def _map_chocodata_offer(data: Dict, asin: Optional[str]) -> Dict:
    """Map a ChocoData /amazon/product response to the safe offer shape.

    The product page carries Buy Box price, price range, seller count
    (from the 'New (N) from $X' line), item weight (product_details) and
    sales rank. The weight is converted to an FBA fee estimate via
    pricing.estimate_fba_fee so Net Profit / ROI can populate for ASINs
    that also have a Costco cost. Anything missing stays None.
    """
    shape = get_offer_data(asin or "")
    if not data:
        return shape

    details = data.get("product_details") or {}
    weight_lbs = _parse_weight_lbs(details.get("item_weight"))
    fba_fee = estimate_fba_fee(weight_lbs) if weight_lbs else None

    buy_box = data.get("price_buybox") or data.get("price")
    buy_box = buy_box if _is_number(buy_box) and buy_box > 0 else None

    pricing_str = data.get("other_sellers") or data.get("pricing_str")
    lowest = _extract_price_from(pricing_str)
    if lowest is None and buy_box:
        lowest = buy_box
    highest = data.get("highest_price")
    highest = highest if _is_number(highest) and highest > 0 else (buy_box or None)
    total_sellers = _extract_seller_count(pricing_str)

    sales_rank = data.get("sales_rank")
    if isinstance(sales_rank, dict):
        rank = sales_rank.get("rank")
        rank = rank if _is_number(rank) else None
    else:
        rank = None

    shape.update(
        {
            "amazon_price": buy_box if buy_box else None,
            "buy_box_price": buy_box,
            "lowest_price": lowest,
            "highest_price": highest,
            "total_sellers": total_sellers,
            "fba_sellers": None,
            "fba_sellers_estimated": True,
            "lowest_price_seller_type": "unknown",
            "highest_price_seller_type": "unknown",
            "monthly_sales_estimate": None,
            "monthly_sales_estimated": False,
            "fba_fee": fba_fee,
            "weight_lbs": weight_lbs,
            "sales_rank": rank,
            "rating": data.get("rating"),
            "reviews_count": data.get("reviews_count"),
            "title": data.get("title") or data.get("product_name"),
        }
    )

    any_data = any(_completeness(shape).values()) or buy_box is not None
    if not any_data:
        return _apply_provenance(shape, "chocodata", "failed", _now_iso())
    status = "complete" if _is_complete_for_ranking(shape) else "partial"
    return _apply_provenance(shape, "chocodata", status, _now_iso())


def _fetch_chocodata_product(asin: str) -> Dict:
    """Fetch one ChocoData product page; never raises."""
    if not CHOCODATA_API_KEY:
        return {}
    try:
        response = requests.get(
            CHOCODATA_PRODUCT_URL,
            params={"api_key": CHOCODATA_API_KEY, "query": asin},
            timeout=CHOCODATA_REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_SALES_VOLUME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([KM]?)\+?\s*bought\s*in\s*past\s+(month|week|day)",
    re.IGNORECASE,
)
_SALES_VOLUME_MULTIPLIERS = {"K": 1000.0, "M": 1_000_000.0, "": 1.0}
_SALES_VOLUME_PERIODS = {"month": 1.0, "week": 4.33, "day": 30.4}


def _parse_monthly_sales(raw) -> Optional[float]:
    """Parse an Unwrangle past_month_sales string into a monthly estimate."""
    if not raw or not isinstance(raw, str):
        return None
    match = _SALES_VOLUME_RE.search(raw)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = _SALES_VOLUME_MULTIPLIERS.get(match.group(2).upper(), 1.0)
    period = _SALES_VOLUME_PERIODS.get(match.group(3).lower(), 1.0)
    return number * multiplier * period


def _fetch_unwrangle_amazon_detail(asin: str) -> Dict:
    """Fetch one Unwrangle amazon_detail page; never raises.

    Amazon US costs 1 credit per successful request (2.5 elsewhere). The
    provider accepts the ASIN directly, so no product URL is needed.
    """
    if not UNWRANGLE_API_KEY:
        return {}
    try:
        response = requests.get(
            UNWRANGLE_URL,
            params={
                "platform": UNWRANGLE_PLATFORM,
                "asin": asin,
                "country_code": "us",
                "api_key": UNWRANGLE_API_KEY,
            },
            timeout=UNWRANGLE_REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        detail = payload.get("detail")
        return detail if isinstance(detail, dict) else {}
    except Exception:
        return {}


def _map_unwrangle_offer(data: Dict, asin: Optional[str]) -> Dict:
    """Map an Unwrangle amazon_detail response to the safe offer shape.

    The product page carries price (price_reduced = the sale price when on
    deal), buying offers, item weight (details_table), bestseller ranks and
    past-month sales. The weight is converted to an FBA fee estimate via
    pricing.estimate_fba_fee so Net Profit / ROI can populate for ASINs
    that also have a Costco cost. Anything missing stays None.
    """
    shape = get_offer_data(asin or "")
    if not data:
        return shape

    price = data.get("price")
    price_reduced = data.get("price_reduced")
    price = price if _is_number(price) and price > 0 else None
    price_reduced = price_reduced if _is_number(price_reduced) and price_reduced > 0 else None
    if price_reduced is not None and (price is None or price_reduced < price):
        buy_box = price_reduced
    else:
        buy_box = price

    weight_lbs = None
    for row in data.get("details_table") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").lower()
        if "weight" in name or "dimension" in name:
            weight_lbs = _parse_weight_lbs(row.get("value"))
            if weight_lbs:
                break
    fba_fee = estimate_fba_fee(weight_lbs) if weight_lbs else None

    offers = [o for o in (data.get("buying_offers") or []) if isinstance(o, dict)]
    offer_prices = [float(o["price"]) for o in offers if _is_number(o.get("price"))]
    lowest = min(offer_prices) if offer_prices else None
    other_sellers = data.get("other_sellers")
    other_text = other_sellers.get("text") if isinstance(other_sellers, dict) else None
    if lowest is None:
        lowest = _extract_price_from(other_text) or buy_box
    total_sellers = len(offers) if offers else _extract_seller_count(other_text)
    list_prices = [p for p in (price, price_reduced) if p is not None]
    highest = max(list_prices) if list_prices else buy_box

    sales_rank = None
    ranks = [
        r.get("rank")
        for r in (data.get("bestseller_ranks") or [])
        if isinstance(r, dict) and _is_number(r.get("rank"))
    ]
    if ranks:
        sales_rank = min(ranks)

    shape.update(
        {
            "amazon_price": buy_box,
            "buy_box_price": buy_box,
            "lowest_price": lowest,
            "highest_price": highest,
            "total_sellers": total_sellers,
            "fba_sellers": None,
            "fba_sellers_estimated": True,
            "lowest_price_seller_type": "unknown",
            "highest_price_seller_type": "unknown",
            "monthly_sales_estimate": _parse_monthly_sales(data.get("past_month_sales")),
            "monthly_sales_estimated": True,
            "fba_fee": fba_fee,
            "weight_lbs": weight_lbs,
            "sales_rank": sales_rank,
            "rating": data.get("rating"),
            "reviews_count": data.get("total_ratings"),
            "title": data.get("name"),
        }
    )

    any_data = any(_completeness(shape).values()) or buy_box is not None
    if not any_data:
        return _apply_provenance(shape, "unwrangle", "failed", _now_iso())
    status = "complete" if _is_complete_for_ranking(shape) else "partial"
    return _apply_provenance(shape, "unwrangle", status, _now_iso())


def _offline_offer(identifier: Optional[str], status: str = "offline") -> Dict:
    shape = get_offer_data(identifier or "")
    return _apply_provenance(shape, "offline", status, None)


def _offline_offer_from_candidate(
    identifier: Optional[str], candidate: Optional[Dict]
) -> Dict:
    """Offline offer shape overlaid with manually imported market data.

    Activates ONLY for candidate rows carrying the manual-import marker
    (``imported_at``). Provider-generated cache rows (no ``imported_at``)
    keep the bare offline placeholder behavior exactly — unchanged.
    Imported values are labeled with the import source and keep
    enrichment_status "offline": they are never presented as live,
    verified, or provider-fetched. Zero network calls. Fields the import
    did not supply stay null — nothing is invented, and shipping is never
    folded into economics (the unit-economics model keeps using its
    current price/fee inputs only).
    """
    shape = _offline_offer(identifier)
    if not isinstance(candidate, dict):
        return shape
    if not isinstance(candidate.get("imported_at"), str):
        return shape

    def _positive(value):
        return float(value) if _is_number(value) and value > 0 else None

    def _count(value):
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    def _text(value):
        return value if isinstance(value, str) and value.strip() else None

    fields = {
        "amazon_price": _positive(candidate.get("amazon_price")),
        "buy_box_price": _positive(candidate.get("buy_box_price")),
        "lowest_price": None,
        "highest_price": None,
        "total_sellers": _count(candidate.get("total_sellers")),
        "fba_sellers": _count(candidate.get("fba_sellers")),
        "fba_sellers_estimated": False,
        "monthly_sales_estimate": _positive(candidate.get("monthly_sales_estimate")),
        "monthly_sales_estimated": bool(candidate.get("monthly_sales_estimated", False)),
        "fba_fee": _positive(candidate.get("fba_fee")),
        "title": _text(candidate.get("name")),
    }
    if _text(candidate.get("amazon_category")) or _count(candidate.get("browse_node_id")):
        fields["amazon_category"] = _text(candidate.get("amazon_category"))
        fields["browse_node_id"] = _count(candidate.get("browse_node_id"))
        fields["category_source_hint"] = (
            _text(candidate.get("category_source_hint")) or "structured_category"
        )

    if not any(value is not None for value in fields.values()):
        return shape
    for key, value in fields.items():
        if value is not None:
            shape[key] = value

    source_label = _text(candidate.get("source")) or "manual_import"
    shape["offer_data_provider"] = source_label
    shape["enrichment_status"] = "offline"
    observed = candidate.get("observed_at")
    shape["enriched_at"] = (
        observed if isinstance(observed, str) and observed else candidate.get("imported_at")
    )
    return shape


def _snapshot_merge_enabled() -> bool:
    """Strict opt-in flag for merging local market snapshots into the
    cache-only scanner output (SCANNER_LOCAL_SNAPSHOT_MERGE). Unset or
    invalid text disables the merge entirely — current behavior unchanged."""
    return env_flag("SCANNER_LOCAL_SNAPSHOT_MERGE")


def _offline_offer_merged(
    identifier: Optional[str], candidate: Optional[Dict], snapshot: Optional[Dict]
) -> Dict:
    """Offline placeholder overlaid with a local market snapshot (read-only).

    Activates ONLY when SCANNER_LOCAL_SNAPSHOT_MERGE is enabled AND a
    snapshot exists for the ASIN. Zero network: the snapshot store is
    local. The merge never invents values: fields the snapshot does not
    carry stay null, seller counts come only from the returned offer
    roster (never the claimed offer_count), and the Buy Box winner/price
    are only used when the provider identified them. The snapshot never
    forces or upgrades a Costco match. Provenance stays honest: provider
    remains "offline" with snapshot_* metadata attached so snapshot data
    is never presented as a live fetch.
    """
    shape = _offline_offer_from_candidate(identifier, candidate)
    if not isinstance(snapshot, dict):
        return shape

    status = snapshot.get("data_status")
    fetched_at = snapshot.get("fetched_at")
    observed_at = snapshot.get("observed_at")
    freshness = (
        market_snapshot_store.snapshot_freshness_status(snapshot)
        if isinstance(snapshot.get("freshness"), dict)
        else "unknown"
    )
    gaps = [g for g in (snapshot.get("data_gaps") or []) if isinstance(g, str)]

    shape["snapshot_status"] = status or "unknown"
    shape["snapshot_source"] = snapshot.get("source")
    shape["snapshot_fetched_at"] = fetched_at
    shape["snapshot_observed_at"] = observed_at
    shape["snapshot_freshness"] = freshness
    shape["snapshot_offers_complete"] = snapshot.get("offers_complete")
    shape["snapshot_offers_returned"] = snapshot.get("offers_returned")
    shape["snapshot_data_gaps"] = gaps
    if isinstance(fetched_at, str) and fetched_at:
        shape["enriched_at"] = observed_at if isinstance(observed_at, str) and observed_at else fetched_at

    seller_counts = snapshot.get("seller_counts") or {}
    offers = [o for o in (snapshot.get("offers") or []) if isinstance(o, dict)]
    # Seller counts only come from actual returned offer rows, or from an
    # explicit complete zero-offer report. Any other empty/partial/failed/
    # unavailable roster leaves them Unknown (never 0 sellers).
    roster_known = bool(offers) or competition_analytics.explicit_zero_offer_evidence(snapshot)
    if roster_known:
        shape["snapshot_fbm_sellers"] = seller_counts.get("fbm_observed")
        shape["snapshot_amazon_sellers"] = seller_counts.get("amazon_observed")

    buy_box = snapshot.get("buy_box") or {}
    shape["snapshot_buy_box_available"] = bool(buy_box.get("available"))
    shape["snapshot_buy_box_price"] = buy_box.get("price")
    shape["snapshot_buy_box_fulfillment"] = buy_box.get("fulfillment")
    shape["snapshot_buy_box_seller"] = buy_box.get("seller_name")

    if status not in (market_snapshot_store.DATA_STATUS_AVAILABLE, market_snapshot_store.DATA_STATUS_PARTIAL):
        return shape

    price = buy_box.get("price")
    if _is_number(price) and price > 0:
        price_value = float(price)
        shape["amazon_price"] = price_value
        shape["buy_box_price"] = price_value

    prices = [_offer_price_value(o) for o in offers]
    prices = [p for p in prices if p is not None]
    if prices:
        shape["lowest_price"] = min(prices)
        shape["highest_price"] = max(prices)

    if roster_known:
        shape["total_sellers"] = seller_counts.get("observed_total")
        shape["fba_sellers"] = seller_counts.get("fba_observed")
        shape["fba_sellers_estimated"] = False
    if isinstance(snapshot.get("title"), str) and snapshot["title"].strip():
        shape["title"] = snapshot["title"]
    if _is_number(snapshot.get("monthly_sales_estimate")):
        shape["monthly_sales_estimate"] = snapshot["monthly_sales_estimate"]
        shape["monthly_sales_estimated"] = bool(snapshot.get("monthly_sales_estimated", True))
    return shape


def _cache_path() -> str:
    """Per-ASIN enrichment cache (data/enriched-offer-cache.json)."""
    raw = os.getenv("SCANNER_OFFER_CACHE_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(os.path.dirname(_BACKEND_DIR), raw)
    return os.path.join(os.path.dirname(_BACKEND_DIR), "data", "enriched-offer-cache.json")


def _cache_ttl_hours() -> float:
    """Hours a cached offer stays fresh; <= 0 disables the cache."""
    raw = os.getenv("SCANNER_OFFER_CACHE_TTL_HOURS")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DEFAULT_OFFER_CACHE_TTL_HOURS
    return value


def _load_cache() -> Dict[str, Any]:
    path = _cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _cached_offer(asin: Optional[str]) -> Optional[Dict]:
    """Fresh cached live offer for the ASIN, or None. Zero network."""
    if not asin:
        return None
    ttl = _cache_ttl_hours()
    if ttl <= 0:
        return None
    entry = _load_cache().get(asin)
    if not isinstance(entry, dict):
        return None
    offer = entry.get("offer")
    cached_at = entry.get("cached_at")
    if not isinstance(offer, dict) or not isinstance(cached_at, str):
        return None
    try:
        cached_dt = datetime.fromisoformat(cached_at)
    except ValueError:
        return None
    if datetime.now(timezone.utc) - cached_dt > timedelta(hours=ttl):
        return None
    return dict(offer)


def _cache_offer(asin: Optional[str], shape: Dict) -> None:
    """Persist a successful live offer (complete/partial) by ASIN. Never
    called for offline placeholders or failed fetches. Best effort."""
    if not asin or _cache_ttl_hours() <= 0:
        return
    try:
        cache = _load_cache()
        cache[asin] = {"offer": shape, "cached_at": _now_iso()}
        path = _cache_path()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=str)
    except OSError:
        pass


def _fetch_live_offer(identifier: Optional[str], asin: Optional[str], mode: str) -> Dict:
    """Provider dispatch used by get_scanner_offer (cache miss)."""
    if mode == "EASYPARSER":
        if not asin:
            return _offline_offer(identifier, "invalid_asin")
        return _map_easyparser_offer(get_easyparser_offers(asin), asin)

    if mode == "BRIGHTDATA":
        if not asin:
            return _offline_offer(identifier, "invalid_asin")
        try:
            data = get_product_detail(identifier)
        except ValueError as e:
            print(f"[Bright Data] enrichment skipped: {e}")
            data = {}
        return _map_brightdata_offer(data, asin)

    if mode == "CHOCODATA":
        if not asin:
            return _offline_offer(identifier, "invalid_asin")
        return _map_chocodata_offer(_fetch_chocodata_product(asin), asin)

    if mode == "UNWRANGLE":
        if not asin:
            return _offline_offer(identifier, "invalid_asin")
        return _map_unwrangle_offer(_fetch_unwrangle_amazon_detail(asin), asin)

    if mode == "AUTO":
        if not asin:
            return _offline_offer(identifier, "invalid_asin")
        easy = _map_easyparser_offer(get_easyparser_offers(asin), asin)
        if easy.get("enrichment_status") == "complete":
            return easy
        bd_data = enrich_product(identifier)
        if bd_data:
            mapped = _map_brightdata_offer(bd_data, identifier or "")
            if mapped.get("enrichment_status") != "complete":
                mapped["enrichment_status"] = "partial"
            return mapped
        return easy

    return _offline_offer(identifier)


def get_scanner_offer(identifier: Optional[str]) -> Dict:
    """Best available per-ASIN offer data, in the product_analysis shape.

    EASYPARSER maps the easyparser offer response; BRIGHTDATA maps the
    Bright Data normalized result; CHOCODATA maps the /amazon/product page;
    UNWRANGLE maps the amazon_detail page (1 credit/ASIN for Amazon US);
    AUTO tries Easyparser first and falls back to Bright Data only when the
    Easyparser result is missing fields the ranking model needs (sellers,
    FBA sellers, Buy Box price, range) or the provider failed. Anything
    else returns the offline placeholder (zero network calls, nulls for
    unknown fields). Never raises: provider failures degrade to the
    placeholder/best-effort shape.

    Credit savings: a fresh cached offer (SCANNER_OFFER_CACHE_TTL_HOURS,
    default 24) is served without any provider call; only successful live
    fetches (complete/partial) are cached — never offline placeholders or
    failed fetches. Provenance (provider, enriched_at) is preserved from
    the original fetch.
    """
    mode = _enrichment_mode()
    asin = _extract_asin(identifier)

    if mode == "OFF":
        return _offline_offer(identifier)

    cached = _cached_offer(asin)
    if cached is not None:
        return cached

    shape = _fetch_live_offer(identifier, asin, mode)
    if shape.get("enrichment_status") in ("complete", "partial"):
        _cache_offer(asin, shape)
    return shape


# ---------------------------------------------------------------------------
# On-demand seller / Buy Box detail (per-ASIN, one provider request max).
#
# The Easyparser OFFER operation is the only configured provider with a
# genuine per-seller roster (seller names/IDs, buybox_winner flags, per-offer
# price/condition/Prime/rating). Seller detail is credit-expensive, so it is
# never fetched by the scanner pipeline: it runs only when the UI calls the
# dedicated endpoint for one ASIN. The normalized contract below is what the
# UI renders; aggregates are never synthesized from offers and offers are
# never synthesized from aggregates.
# ---------------------------------------------------------------------------

DEFAULT_SELLER_CACHE_TTL_HOURS = 24.0

SELLER_STATUS_AVAILABLE = "available"
SELLER_STATUS_PARTIAL = "partial"
SELLER_STATUS_UNAVAILABLE = "unavailable"
SELLER_STATUS_NOT_REQUESTED = "not_requested"
SELLER_STATUS_PROVIDER_ERROR = "provider_error"

_SELLER_PROVIDER_FETCH_GAP_HINTS = (
    "timed out",
    "network level",
    "HTTP ",
    "not valid JSON",
    "unexpected structure",
    "request_info.success is false",
)


def _seller_cache_path() -> str:
    """Seller-detail cache (data/seller-offer-cache.json). Kept separate from
    the scanner enrichment cache: the two payload shapes must never mix."""
    raw = os.getenv("SCANNER_SELLER_CACHE_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(os.path.dirname(_BACKEND_DIR), raw)
    return os.path.join(os.path.dirname(_BACKEND_DIR), "data", "seller-offer-cache.json")


def _seller_cache_ttl_hours() -> float:
    """Hours a cached seller roster stays fresh; <= 0 disables the cache."""
    raw = os.getenv("SCANNER_SELLER_CACHE_TTL_HOURS")
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


def _cached_seller_detail(asin: Optional[str]) -> Optional[Dict]:
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
        cached_dt = datetime.fromisoformat(cached_at)
    except ValueError:
        return None
    if datetime.now(timezone.utc) - cached_dt > timedelta(hours=ttl):
        return None
    out = dict(payload)
    out["offer_data_cached"] = True
    return out


def _cache_seller_detail(asin: Optional[str], payload: Dict) -> None:
    """Persist a successful seller roster (available/partial) by ASIN. Never
    called for provider errors, unavailable results, or failures. Best effort."""
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


_SELLER_LOCKS_GUARD = threading.Lock()
_SELLER_LOCKS: Dict[str, threading.Lock] = {}


def _fulfillment_label(is_fba, is_fbm, seller_name) -> str:
    """One consistent fulfillment vocabulary: FBA | FBM | Amazon | Unknown.
    Amazon Retail is Amazon, never FBA/FBM."""
    if isinstance(seller_name, str) and seller_name.strip().lower() == "amazon.com":
        return "Amazon"
    if is_fba is True:
        return "FBA"
    if is_fbm is True:
        return "FBM"
    return "Unknown"


def _condition_text(value) -> Optional[str]:
    if isinstance(value, dict):
        title = value.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        if value.get("is_new") is True:
            return "New"
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def map_seller_offer_contract(data: Optional[Dict], asin: Optional[str]) -> Dict:
    """Normalize an Easyparser OFFER response into the seller/Buy Box contract.

    Every unknown stays null internally (renders as Unavailable/Unknown in the
    UI, never 0). A provider response with only aggregate counts never
    synthesizes offer rows; the Buy Box winner is never inferred from the
    lowest price. Field presence follows the provider's actual normalized
    keys (see easyparser_client.get_easyparser_offers).
    """
    contract = {
        "asin": asin,
        "offer_data_status": SELLER_STATUS_UNAVAILABLE,
        "offer_data_source": None,
        "offer_data_fetched_at": None,
        "offer_data_note": None,
        "offer_data_cached": False,
        "total_sellers": None,
        "fba_sellers": None,
        "fbm_sellers": None,
        "amazon_sellers": None,
        "buy_box": {
            "available": False,
            "seller_name": None,
            "seller_id": None,
            "fulfillment": "Unavailable",
            "price": None,
            "shipping": None,
            "landed_price": None,
            "condition": None,
            "prime": None,
            "note": None,
        },
        "offers": [],
        "offers_returned": None,
        "offers_complete": None,
    }

    if not isinstance(data, dict) or data.get("source") != "easyparser":
        contract["offer_data_status"] = SELLER_STATUS_PROVIDER_ERROR
        contract["offer_data_note"] = (
            "Seller roster provider unavailable (EASYPARSER_API_KEY not configured)."
        )
        return contract

    gaps = [g for g in (data.get("data_gaps") or []) if isinstance(g, str)]
    contract["offer_data_source"] = "easyparser"
    contract["offer_data_fetched_at"] = data.get("observed_at")
    contract["total_sellers"] = data.get("offer_count")
    contract["fba_sellers"] = data.get("observed_fba_offer_count")
    contract["fbm_sellers"] = data.get("observed_fbm_offer_count")
    contract["amazon_sellers"] = data.get("observed_amazon_offer_count")
    contract["offers_returned"] = data.get("offers_returned_count")
    # Legacy convenience fields (kept so the existing route contract holds).
    contract["offer_count"] = data.get("offer_count")
    contract["buy_box_price"] = data.get("buy_box_price")
    contract["request_zip_code"] = data.get("request_zip_code")
    contract["observed_at"] = data.get("observed_at")
    contract["title"] = data.get("title")
    contract["credits_used"] = data.get("credits_used")
    contract["credits_remaining"] = data.get("credits_remaining")
    contract["data_gaps"] = gaps

    offers = [o for o in (data.get("offers") or []) if isinstance(o, dict)]
    for o in offers:
        contract["offers"].append(
            {
                "seller_name": o.get("seller_name"),
                "seller_id": o.get("seller_id"),
                "fulfillment": _fulfillment_label(
                    o.get("is_fba"), o.get("is_fbm"), o.get("seller_name")
                ),
                "is_buy_box_winner": o.get("buybox_winner"),
                "price": _offer_price_value(o),
                "shipping": None,
                "landed_price": None,
                "condition": _condition_text(o.get("condition")),
                "prime": o.get("is_prime"),
                "rating": o.get("seller_rating"),
                "feedback_count": o.get("seller_ratings_total"),
                "availability": None,
                # Provider-supported extras (numeric shipping is not returned).
                "shipping_free": o.get("shipping_is_free"),
                "shipping_text": o.get("shipping_text"),
            }
        )

    buy_box_price = data.get("buy_box_price")
    buy_box_seller = data.get("buy_box_seller")
    contract["buy_box"] = {
        "available": (
            _is_number(buy_box_price) or isinstance(buy_box_seller, str) and buy_box_seller.strip()
        ),
        "seller_name": buy_box_seller,
        "seller_id": data.get("buy_box_seller_id"),
        "fulfillment": _fulfillment_label(
            data.get("buy_box_is_fba"), data.get("buy_box_is_fbm"), buy_box_seller
        ),
        "price": buy_box_price if _is_number(buy_box_price) else None,
        "shipping": None,
        "landed_price": None,
        "condition": _condition_text(data.get("buy_box_condition")),
        "prime": data.get("buy_box_is_prime"),
        "note": None,
    }
    if not contract["buy_box"]["available"]:
        contract["buy_box"]["note"] = (
            "Provider did not identify the Buy Box winner; it is never inferred "
            "from the lowest price."
        )

    if not offers:
        if any("API key is not configured" in g for g in gaps):
            contract["offer_data_status"] = SELLER_STATUS_PROVIDER_ERROR
            contract["offer_data_note"] = (
                "Seller roster provider unavailable (EASYPARSER_API_KEY not configured)."
            )
        elif any(hint in g for g in gaps for hint in _SELLER_PROVIDER_FETCH_GAP_HINTS):
            contract["offer_data_status"] = SELLER_STATUS_PROVIDER_ERROR
            contract["offer_data_note"] = "; ".join(gaps)
        elif contract["total_sellers"] is not None:
            contract["offer_data_status"] = SELLER_STATUS_PARTIAL
            contract["offers_complete"] = False
            contract["offer_data_note"] = (
                "Provider returned only aggregate seller counts; individual offer "
                "rows were not included in the response."
            )
        else:
            contract["offer_data_status"] = SELLER_STATUS_UNAVAILABLE
            contract["offer_data_note"] = "; ".join(gaps) or (
                "Provider returned no seller data for this ASIN."
            )
        return contract

    returned = contract["offers_returned"]
    total = contract["total_sellers"]
    if isinstance(returned, int) and isinstance(total, int) and total > 0:
        contract["offers_complete"] = returned >= total
    else:
        contract["offers_complete"] = False
    if contract["offers_complete"]:
        contract["offer_data_status"] = SELLER_STATUS_AVAILABLE
        contract["offer_data_note"] = None
    else:
        contract["offer_data_status"] = SELLER_STATUS_PARTIAL
        total_text = str(total) if isinstance(total, int) else "unknown"
        contract["offer_data_note"] = (
            "Provider returned " + str(returned if isinstance(returned, int) else 0)
            + " of " + total_text + " offers; the roster may be paginated or truncated."
        )
    return contract


def get_seller_offer_contract(asin: Optional[str]) -> Dict:
    """On-demand seller/Buy Box detail for exactly one ASIN.

    Cache hit: served without a provider call. Cache miss: at most ONE
    provider request (Easyparser OFFER) — no fallback chain that could fire
    multiple paid providers. Concurrent requests for the same ASIN share one
    fetch via a per-ASIN lock (in-flight deduplication). Only successful
    available/partial responses are cached; provider errors, unavailable
    results, and failures are never cached. Invalid ASINs are rejected
    safely with zero provider calls.
    """
    if not asin or not ASIN_PATTERN.fullmatch(str(asin)):
        payload = map_seller_offer_contract(None, asin)
        payload["offer_data_status"] = SELLER_STATUS_PROVIDER_ERROR
        payload["offer_data_note"] = "Invalid ASIN: seller roster cannot be requested."
        return payload

    with _SELLER_LOCKS_GUARD:
        lock = _SELLER_LOCKS.setdefault(asin, threading.Lock())
    with lock:
        cached = _cached_seller_detail(asin)
        if cached is not None:
            return cached
        if not live_gate.live_enabled():
            payload = map_seller_offer_contract(None, asin)
            payload["offer_data_status"] = SELLER_STATUS_UNAVAILABLE
            payload["offer_data_note"] = live_gate.live_disabled_note()
            return payload
        payload = map_seller_offer_contract(get_easyparser_offers(asin), asin)
        if payload.get("offer_data_status") in (
            SELLER_STATUS_AVAILABLE,
            SELLER_STATUS_PARTIAL,
        ):
            _cache_seller_detail(asin, payload)
        return payload
