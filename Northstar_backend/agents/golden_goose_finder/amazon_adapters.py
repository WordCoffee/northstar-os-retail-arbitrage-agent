"""Golden Goose Finder — live Amazon adapters for the free-tier router.

Provides caller factories that the free-tier router's ``run_task`` invokes.
Each factory returns a ``caller(provider, task_type)`` closure that makes the
actual HTTP request to the selected provider and returns structured results.

Supported providers (add as needed):
  - Chocodata: keyword search → ASIN + title + brand + price + rating + sales
  - EasyParser: seller roster → FBA count + seller names + identity flags
  - Bright Data Web Unlocker: raw HTML (future)

§3 gate: these adapters only execute when called through ``run_task`` with
``live_armed=True``.  They never self-arm.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chocodata search adapter
# ---------------------------------------------------------------------------

CHOCODATA_SEARCH_URL = os.getenv(
    "CHOCODATA_SEARCH_URL",
    "https://api.chocodata.com/api/v1/amazon/search",
)
CHOCODATA_TIMEOUT = int(os.getenv("CHOCODATA_TIMEOUT", "30"))
CHOCODATA_MAX_RETRIES = int(os.getenv("CHOCODATA_MAX_RETRIES", "2"))
CHOCODATA_RETRY_DELAY = float(os.getenv("CHOCODATA_RETRY_DELAY", "8"))


def build_search_query(brand: str, product_title: str) -> str:
    """Build an Amazon search query from a wholesale product.

    Strips pack-count indicators and promotional language, keeping brand +
    core product type for individual-listing discovery.
    """
    import re as _re

    # Strip common multi-pack / bulk indicators
    strip_patterns = [
        r"\b\d+\s*[-–]\s*pack\b",
        r"\b\d+\s*pack\b",
        r"\bpack\s+of\s+\d+\b",
        r"\bbulk\b",
        r"\bclub\s+size\b",
        r"\bvalue\s+pack\b",
        r"\bfamily\s+pack\b",
        r"\beconomy\s+size\b",
        r"\blarge\s+size\b",
        r"\bjumbo\b",
    ]
    cleaned = product_title
    for pat in strip_patterns:
        cleaned = _re.sub(pat, "", cleaned, flags=_re.IGNORECASE)

    # Collapse whitespace
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()

    # Prepend brand if not already in the title
    if brand and brand.lower() not in cleaned.lower():
        query = f"{brand} {cleaned}"
    else:
        query = cleaned

    # Add "individual" hint to bias toward single-unit listings
    query = f"{query} individual"

    return query.strip()[:200]  # Amazon search bar limit


def make_chocodata_search_caller(query: str, pages: int = 1):
    """Return a ``caller(provider, task_type)`` closure for Chocodata search.

    The closure fetches Amazon search results from Chocodata and returns a
    list of raw product dicts.  Raises on failure so the router falls through.
    """

    def caller(provider, task_type: str) -> List[Dict[str, Any]]:
        api_key = os.getenv(provider.key_env, "")
        if not api_key:
            raise RuntimeError(f"{provider.key_env} not set")

        import requests as _req

        params = {
            "api_key": api_key,
            "query": query,
            "domain": "amazon.com",
            "sort_by": "best_match",
            "start_page": 1,
        }

        last_error = None
        for attempt in range(1, CHOCODATA_MAX_RETRIES + 2):
            try:
                resp = _req.get(
                    CHOCODATA_SEARCH_URL,
                    params=params,
                    timeout=CHOCODATA_TIMEOUT,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get("products") or []
                    logger.info(
                        "[Chocodata] query='%s' products=%d", query, len(products)
                    )
                    return products  # list of raw dicts

                # 502 is retryable (provider-side upstream fetch)
                if resp.status_code == 502 and attempt <= CHOCODATA_MAX_RETRIES:
                    logger.warning(
                        "[Chocodata] 502 retry %d/%d for '%s'",
                        attempt, CHOCODATA_MAX_RETRIES, query,
                    )
                    time.sleep(CHOCODATA_RETRY_DELAY)
                    continue

                raise RuntimeError(
                    f"Chocodata HTTP {resp.status_code}: {resp.text[:200]}"
                )

            except _req.exceptions.Timeout:
                last_error = "timeout"
                if attempt <= CHOCODATA_MAX_RETRIES:
                    time.sleep(CHOCODATA_RETRY_DELAY)
                    continue
                raise RuntimeError(f"Chocodata timeout after {attempt} attempts")
            except _req.exceptions.RequestException as exc:
                raise RuntimeError(f"Chocodata request error: {exc}") from exc

        raise RuntimeError(f"Chocodata failed: {last_error}")

    return caller


def parse_chocodata_results(
    raw_products: List[Dict[str, Any]],
    brand_filter: str | None = None,
) -> List[Dict[str, Any]]:
    """Parse raw Chocodata search results into a normalized candidate list.

    Filters by brand if specified.  Returns dicts with keys matching the
    fields needed to construct AmazonMatch objects.
    """
    candidates = []
    brand_lower = (brand_filter or "").lower()

    for item in raw_products:
        if not isinstance(item, dict):
            continue

        asin = item.get("asin")
        if not asin:
            continue

        title = item.get("title") or item.get("name") or ""
        brand = item.get("brand") or ""

        # Brand filter (case-insensitive partial match)
        if brand_lower and brand_lower not in brand.lower():
            continue

        # Parse price
        price_raw = item.get("price")
        price_val = None
        if isinstance(price_raw, (int, float)) and not isinstance(price_raw, bool) and price_raw > 0:
            price_val = float(price_raw)
        elif isinstance(price_raw, str):
            try:
                parsed = float(price_raw.strip().replace("$", "").replace(",", ""))
                if parsed > 0:
                    price_val = parsed
            except ValueError:
                pass

        if price_val is None:
            continue  # can't score without a price

        # Parse rating
        rating_raw = item.get("rating")
        rating = None
        if isinstance(rating_raw, (int, float)):
            rating = float(rating_raw)
        elif isinstance(rating_raw, str):
            try:
                rating = float(rating_raw.strip())
            except ValueError:
                pass

        # Parse review count
        reviews_raw = item.get("reviews_count") or item.get("num_reviews")
        reviews = None
        if isinstance(reviews_raw, (int, float)):
            reviews = int(reviews_raw)
        elif isinstance(reviews_raw, str):
            try:
                reviews = int(reviews_raw.strip().replace(",", ""))
            except ValueError:
                pass

        # Parse monthly sales
        sales_raw = item.get("sales_volume") or item.get("monthly_sales")
        monthly_sales = None
        if isinstance(sales_raw, (int, float)):
            monthly_sales = int(sales_raw)
        elif isinstance(sales_raw, str):
            # Chocodata often returns "1K+ bought in past month" style
            import re as _re
            m = _re.search(r"([\d,.]+)\s*[Kk]?", str(sales_raw))
            if m:
                num_str = m.group(1).replace(",", "")
                try:
                    val = float(num_str)
                    if "k" in str(sales_raw).lower():
                        val *= 1000
                    monthly_sales = int(val)
                except ValueError:
                    pass

        candidates.append({
            "asin": asin,
            "title": title,
            "brand": brand,
            "amazon_price": price_val,
            "url": item.get("url") or item.get("link"),
            "image_url": item.get("image_url") or item.get("image"),
            "review_rating": rating,
            "review_count": reviews,
            "monthly_sales_estimate": monthly_sales,
            "bsr": None,  # Chocodata doesn't return BSR
            "weight_oz": None,  # requires product detail lookup
            "fba_sellers": None,  # requires offers lookup
            "seller_name": None,
            "is_brand_seller": None,
            "is_amazon_seller": None,
        })

    return candidates


# ---------------------------------------------------------------------------
# EasyParser seller roster adapter
# ---------------------------------------------------------------------------

EASYPARSER_TIMEOUT = int(os.getenv("EASYPARSER_TIMEOUT", "30"))


def make_easy_parser_seller_caller(asin: str):
    """Return a ``caller(provider, task_type)`` closure for EasyParser sellers.

    The closure fetches the seller roster for an ASIN and returns a dict with
    seller identity information.  Raises on failure so the router falls through.
    """

    def caller(provider, task_type: str) -> Dict[str, Any]:
        api_key = os.getenv(provider.key_env, "")
        if not api_key:
            raise RuntimeError(f"{provider.key_env} not set")

        import requests as _req

        url = f"https://api.easyparser.com/v1/amazon/sellers"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = _req.get(
                url,
                headers=headers,
                params={"asin": asin},
                timeout=EASYPARSER_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info("[EasyParser] ASIN=%s sellers fetched", asin)
                return data
            elif resp.status_code == 402:
                raise RuntimeError("EasyParser credits exhausted (402)")
            elif resp.status_code == 429:
                raise RuntimeError("EasyParser rate limited (429)")
            else:
                raise RuntimeError(
                    f"EasyParser HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except _req.exceptions.RequestException as exc:
            raise RuntimeError(f"EasyParser request error: {exc}") from exc

    return caller


def parse_easy_parser_sellers(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse EasyParser seller roster response into seller identity fields.

    Returns a dict with:
      - fba_sellers: int or None
      - seller_name: str or None (buy box seller)
      - is_brand_seller: bool or None
      - is_amazon_seller: bool or None
      - total_sellers: int or None
    """
    if not raw_data or not isinstance(raw_data, dict):
        return {
            "fba_sellers": None,
            "seller_name": None,
            "is_brand_seller": None,
            "is_amazon_seller": None,
            "total_sellers": None,
        }

    # EasyParser may return data in different shapes depending on version
    sellers_list = (
        raw_data.get("sellers")
        or raw_data.get("data", {}).get("sellers")
        or []
    )

    if not isinstance(sellers_list, list):
        sellers_list = []

    # Count FBA sellers and identify buy box seller
    fba_count = 0
    buy_box_seller = None
    buy_box_is_fba = False
    total_sellers = len(sellers_list)

    for seller in sellers_list:
        if not isinstance(seller, dict):
            continue
        is_fba = seller.get("is_fba") or seller.get("fulfillment") == "FBA"
        is_buy_box = seller.get("is_buy_box_winner") or seller.get("buy_box")
        seller_name = seller.get("seller_name") or seller.get("name") or ""

        if is_fba:
            fba_count += 1
        if is_buy_box:
            buy_box_seller = seller_name
            buy_box_is_fba = bool(is_fba)

    # If EasyParser provides a summary instead of per-seller data
    if fba_count == 0 and "fba_sellers" in raw_data:
        fba_count = raw_data["fba_sellers"] or 0
    if buy_box_seller is None and "buy_box_seller" in raw_data:
        buy_box_seller = raw_data["buy_box_seller"]
    if "total_sellers" in raw_data:
        total_sellers = raw_data["total_sellers"] or total_sellers

    # Determine seller identity flags
    is_brand_seller = None
    is_amazon_seller = None

    if buy_box_seller:
        name_lower = buy_box_seller.lower()
        is_amazon_seller = (
            "amazon" in name_lower
            and "marketplace" not in name_lower
        )
        # Brand seller detection is left to the scorer's seller_identity_blocked()
        # since we don't know the wholesale brand here.  The caller will check.
        is_brand_seller = None  # deferred to caller

    return {
        "fba_sellers": fba_count if fba_count > 0 else None,
        "seller_name": buy_box_seller,
        "is_brand_seller": is_brand_seller,
        "is_amazon_seller": is_amazon_seller,
        "total_sellers": total_sellers,
    }
