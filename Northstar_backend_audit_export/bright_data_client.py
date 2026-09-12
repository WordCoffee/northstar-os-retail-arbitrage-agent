"""Bright Data Web Unlocker client — primary discovery and enrichment source.

Both Amazon search (`search_products`) and per-ASIN product detail
(`get_product_detail`) go through the Web Unlocker: one POST to
`api.brightdata.com/request` per page (zone + url, raw HTML back). One
client, one HTTP layer, one 15-minute cache, one error narrative.

Billing: Bright Data's free tier = 5,000 credits/month drawn from a single
shared pool (Web Unlocker = 1 credit per request), renewing on the 1st,
no rollover, hard stop at 0 when unfunded (no surprise charges); standard
per-request rates apply only if funds are deposited. Bright Data exposes
the free-credit balance only in the Control Panel / CLI — no REST
endpoint — so `get_bright_data_credits_remaining()` returns None and
`get_bright_data_request_count()` tracks requests made this session.

Env: BRIGHTDATA_UNLOCKER_API_KEY (required — raises ValueError when
missing), BRIGHTDATA_UNLOCKER_ZONE (default northstaros),
BRIGHTDATA_REQUEST_URL, DEFAULT_MARKETPLACE.

Normalization rules (shared with every other provider):
  - missing/unparseable numeric fields are None, never 0
  - candidates are filtered by the shared Kirkland relevance rule
    (kirkland_filter.is_genuine_kirkland_candidate)
  - a page with zero cards stops paging for that keyword
  - any failure records LAST_ERROR and returns [] / {} — never raises
    into the scanner (except the missing-key ValueError contract).
"""

import os
import re
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from kirkland_filter import is_genuine_kirkland_candidate
from pricing import estimate_fba_fee

load_dotenv()

BRIGHTDATA_UNLOCKER_API_KEY = os.getenv("BRIGHTDATA_UNLOCKER_API_KEY")
BRIGHTDATA_UNLOCKER_ZONE = os.getenv("BRIGHTDATA_UNLOCKER_ZONE", "northstaros")
BRIGHTDATA_REQUEST_URL = os.getenv(
    "BRIGHTDATA_REQUEST_URL",
    "https://api.brightdata.com/request",
)
BRIGHTDATA_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_MARKETPLACE = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com")

_CACHE: Dict[str, Dict] = {}
_CACHE_LOCK = Lock()
TTL_SECONDS = 15 * 60

_REQUESTS_MADE = 0
_REQUESTS_LOCK = Lock()

LAST_ERROR = None

# --- Amazon search-result card patterns -------------------------------------
_CARD_ASIN_RE = re.compile(r"^([A-Z0-9]{10})")
_CARD_TITLE_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_CARD_PRICE_RE = re.compile(r"a-offscreen\">\$?([\d,]+(?:\.\d{1,2})?)<")
_CARD_RATING_RE = re.compile(r"a-icon-alt\">([\d.]+) out of 5 stars<")
_CARD_REVIEWS_RE = re.compile(r"aria-label=\"([\d,]+) ratings?\"")

# --- Amazon product-page patterns -------------------------------------------
_PRODUCT_TITLE_RE = re.compile(r'id="productTitle"[^>]*>(.*?)</span>', re.S)
_PRODUCT_PRICE_RE = re.compile(r'<span class="a-offscreen">\$?([\d,]+(?:\.\d{1,2})?)</span>')
_PRODUCT_PRICE_LEGACY_RE = re.compile(r'id="priceblock_ourprice"[^>]*>\s*\$?([\d,]+(?:\.\d{1,2})?)')
_PRODUCT_BYLINE_RE = re.compile(r'id="bylineInfo"[^>]*>(.*?)</(?:a|span)>', re.S)
_PRODUCT_IMAGE_RE = re.compile(r'id="landingImage"[^>]*src="([^"]+)"')
_PRODUCT_IMAGE_FALLBACK_RE = re.compile(r'id="imgTagWrapperId"[^>]*>.*?src="([^"]+)"', re.S)
_OFFERS_NEW_FROM_RE = re.compile(r"New\s*\((\d+)\)\s*from\s*\$?([\d,.]+)", re.IGNORECASE)
_PRODUCT_RATING_RE = re.compile(r'id="acrPopover"[^>]*title="([\d.]+) out of 5 stars"')
_PRODUCT_REVIEWS_RE = re.compile(r'id="acrCustomerReviewText"[^>]*>\s*([\d,]+)\s*ratings?')
_PRODUCT_WEIGHT_ROW_LABELS = ("Package Dimensions", "Item Weight")
_PRODUCT_RANK_RE = re.compile(r"Best\s*Sellers\s*Rank[^#]{0,200}#([\d,]+)", re.IGNORECASE)

# --- Amazon product-page category / breadcrumb patterns ---------------------
# The wayfinding breadcrumbs div carries the category path; every category
# link href embeds a real numeric browse-node id (node=NNN). Only links
# inside that div are parsed — never fabricated, and only a genuine
# numeric node id is kept.
_BREADCRUMB_DIV_RE = re.compile(r'id="wayfinding-breadcrumbs_feature_div"[^>]*>(.*?)</ul>', re.S)
_BREADCRUMB_LINK_RE = re.compile(r'<a[^>]*href="[^"]*node=(\d+)[^"]*"[^>]*>(.*?)</a>', re.S)

_SALES_VOLUME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([KM]?)\+?\s*bought in past\s+(month|week|day)",
    re.IGNORECASE,
)
_SALES_VOLUME_MULTIPLIERS = {"K": 1000.0, "M": 1_000_000.0, "": 1.0}
_SALES_VOLUME_PERIODS = {"month": 1.0, "week": 4.33, "day": 30.4}

_ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")
_ASIN_URL_PATTERN = re.compile(r"/(?:dp|gp/product|product)/([A-Za-z0-9]{10})")

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


def _parse_weight_lbs(raw: Optional[str]) -> Optional[float]:
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


def _extract_asin(identifier: Optional[str]) -> Optional[str]:
    if not identifier:
        return None
    if _ASIN_PATTERN.fullmatch(identifier):
        return identifier
    match = _ASIN_URL_PATTERN.search(identifier)
    return match.group(1) if match else None


def _extract_product_weight_lbs(html: Optional[str]) -> Optional[float]:
    """Find the listing weight in an Amazon product page.

    Amazon product pages carry two rows: "Item Weight" (often a per-unit /
    sample weight — e.g. 16.9 oz for a 40-pack of water) and "Package
    Dimensions" ("8.7 x 8.62 x 5.08 inches; 5.25 pounds" — the shippable
    weight of the package). FBA fees follow shipping weight, so Package
    Dimensions is preferred; Item Weight is the fallback. The weight
    follows the dimensions, so the last unit-bearing value in a row wins.
    Returns pounds or None.
    """
    if not html:
        return None
    for label in _PRODUCT_WEIGHT_ROW_LABELS:
        pattern = re.compile(rf"{re.escape(label)}(?:(?!</li>).)*?</li>", re.IGNORECASE | re.S)
        for row in pattern.finditer(html):
            for candidate in reversed(list(_WEIGHT_RE.finditer(row.group(0)))):
                lbs = _parse_weight_lbs(f"{candidate.group(1)} {candidate.group(2)}")
                if lbs is not None:
                    return lbs
    return None


def _extract_breadcrumbs(html: Optional[str]):
    """Parse Amazon product-page breadcrumb links into (text, browse_node)
    pairs.

    Only the wayfinding breadcrumbs feature div is parsed, and only links
    that carry a real numeric node= id are kept. Returns [] when the div
    or any valid node link is absent — no category is ever fabricated.
    """
    if not html:
        return []
    div = _BREADCRUMB_DIV_RE.search(html)
    if not div:
        return []
    crumbs = []
    for link in _BREADCRUMB_LINK_RE.finditer(div.group(1)):
        text = _clean_text(link.group(2))
        node_text = link.group(1)
        if not text or not node_text.isdigit():
            continue
        crumbs.append((text, int(node_text)))
    return crumbs


def _parse_sales_volume(raw) -> Optional[float]:
    """Parse an Amazon sales_volume string into a monthly estimate."""
    if not raw or not isinstance(raw, str):
        return None
    match = _SALES_VOLUME_RE.search(raw)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = _SALES_VOLUME_MULTIPLIERS.get(match.group(2).upper(), 1.0)
    period = _SALES_VOLUME_PERIODS.get(match.group(3).lower(), 1.0)
    return number * multiplier * period


def _clean_text(raw: Optional[str]) -> Optional[str]:
    """Strip tags and HTML entities from a title fragment."""
    if not raw:
        return None
    import html as html_module

    clean = html_module.unescape(re.sub(r"<[^>]+>", "", raw))
    return " ".join(clean.split()) or None


def _parse_card(html_chunk: str) -> Optional[Dict]:
    """Parse one Amazon search-result card HTML chunk into a candidate.

    Each card chunk starts with the ASIN right after data-asin=". Returns
    None for non-card chunks (widgets, pagination) and malformed cards.
    """
    asin_match = _CARD_ASIN_RE.match(html_chunk)
    if not asin_match:
        return None
    asin = asin_match.group(1)

    headings = [
        _clean_text(match.group(1))
        for match in _CARD_TITLE_RE.finditer(html_chunk)
        if _clean_text(match.group(1))
    ]
    if not headings:
        return None
    # The first h2 is the brand row when the card carries one ("KIRKLAND");
    # the last h2 is the product title (brand often omitted from the title).
    brand = headings[0] if len(headings) > 1 else None
    title = headings[-1]

    price = None
    price_match = _CARD_PRICE_RE.search(html_chunk)
    if price_match:
        try:
            parsed = float(price_match.group(1).replace(",", ""))
            if parsed > 0:
                price = parsed
        except ValueError:
            price = None

    rating = None
    rating_match = _CARD_RATING_RE.search(html_chunk)
    if rating_match:
        try:
            rating = float(rating_match.group(1))
        except ValueError:
            rating = None

    reviews_count = None
    reviews_match = _CARD_REVIEWS_RE.search(html_chunk)
    if reviews_match:
        try:
            reviews_count = int(reviews_match.group(1).replace(",", ""))
        except ValueError:
            reviews_count = None

    sales_volume = _SALES_VOLUME_RE.search(html_chunk)
    sales_text = sales_volume.group(0) if sales_volume else None

    return {
        "asin": asin,
        "name": title,
        "amazon_price": price,
        "product_url": f"{DEFAULT_MARKETPLACE.rstrip('/')}/dp/{asin}",
        "brand": brand,
        "sales_volume": sales_text,
        "monthly_sales_estimate": _parse_sales_volume(sales_text),
        "monthly_sales_estimated": True,
        "rating": rating,
        "reviews_count": reviews_count,
    }


def _parse_product_page(html: str, asin: str) -> Dict:
    """Parse a raw Amazon product-detail page into the normalized contract.

    Buy Box price from the a-offscreen span, seller count / lowest price
    from the 'New (N) from $X' line, weight from the Item Weight detail
    row (-> FBA fee estimate via pricing.estimate_fba_fee), best-seller
    rank, rating, review count, monthly-sales signal, brand and image.
    Anything missing stays None (never 0).
    """
    title_match = _PRODUCT_TITLE_RE.search(html)
    title = _clean_text(title_match.group(1)) if title_match else None

    price = None
    price_match = _PRODUCT_PRICE_RE.search(html)
    if not price_match:
        price_match = _PRODUCT_PRICE_LEGACY_RE.search(html)
    if price_match:
        try:
            parsed = float(price_match.group(1).replace(",", ""))
            if parsed > 0:
                price = parsed
        except ValueError:
            price = None

    brand = None
    byline = _PRODUCT_BYLINE_RE.search(html)
    if byline:
        brand = _clean_text(byline.group(1))
        if brand and "visit the" in brand.lower():
            brand = brand.split("Store", 1)[0].replace("Visit the", "").strip() or None
        elif brand and brand.lower().startswith("brand:"):
            brand = brand.split(":", 1)[1].strip() or None

    image_url = None
    image_match = _PRODUCT_IMAGE_RE.search(html)
    if not image_match:
        image_match = _PRODUCT_IMAGE_FALLBACK_RE.search(html)
    if image_match:
        image_url = image_match.group(1)

    total_sellers = None
    lowest = None
    offers_match = _OFFERS_NEW_FROM_RE.search(html)
    if offers_match:
        total_sellers = int(offers_match.group(1))
        try:
            lowest = float(offers_match.group(2).replace(",", ""))
        except ValueError:
            lowest = None
    if lowest is None and price is not None:
        lowest = price

    weight_lbs = _extract_product_weight_lbs(html)
    fba_fee = estimate_fba_fee(weight_lbs) if weight_lbs else None

    sales_rank = None
    rank_match = _PRODUCT_RANK_RE.search(html)
    if rank_match:
        try:
            sales_rank = int(rank_match.group(1).replace(",", ""))
        except ValueError:
            sales_rank = None

    rating = None
    rating_match = _PRODUCT_RATING_RE.search(html)
    if rating_match:
        try:
            rating = float(rating_match.group(1))
        except ValueError:
            rating = None

    reviews_count = None
    reviews_match = _PRODUCT_REVIEWS_RE.search(html)
    if reviews_match:
        try:
            reviews_count = int(reviews_match.group(1).replace(",", ""))
        except ValueError:
            reviews_count = None

    sales_volume = _SALES_VOLUME_RE.search(html)
    sales_text = sales_volume.group(0) if sales_volume else None
    monthly = _parse_sales_volume(sales_text)

    crumbs = _extract_breadcrumbs(html)
    breadcrumb = [text for text, _ in crumbs] or None
    browse_node_id = crumbs[0][1] if crumbs else None
    amazon_category = breadcrumb[0] if breadcrumb else None
    category_source_hint = "breadcrumb" if breadcrumb else None

    return {
        "asin": asin,
        "name": title,
        "title": title,
        "amazon_price": price,
        "buy_box_price": price,
        "total_sellers": total_sellers,
        "seller_count": total_sellers,
        "fba_sellers": None,
        "fba_sellers_estimated": False,
        "lowest_price": lowest,
        "highest_price": None,
        "lowest_price_seller_type": "unknown",
        "highest_price_seller_type": "unknown",
        "monthly_sales_estimate": monthly,
        "monthly_sales_estimated": monthly is not None,
        "fba_fee": fba_fee,
        "weight_lbs": weight_lbs,
        "sales_rank": sales_rank,
        "rating": rating,
        "reviews_count": reviews_count,
        "brand": brand,
        "image_url": image_url,
        "amazon_category": amazon_category,
        "browse_node_id": browse_node_id,
        "breadcrumb": breadcrumb,
        "category_source_hint": category_source_hint,
        "product_url": f"{DEFAULT_MARKETPLACE.rstrip('/')}/dp/{asin}",
    }


def _fetch(url: str) -> Optional[str]:
    """Fetch one URL through the Web Unlocker; returns raw HTML or None.

    Caches per-URL for TTL_SECONDS. On success LAST_ERROR is cleared; any
    non-200 or network failure records LAST_ERROR and returns None.
    Raises ValueError only when the API key is missing (contract).
    """
    global LAST_ERROR

    if not BRIGHTDATA_UNLOCKER_API_KEY:
        raise ValueError("BRIGHTDATA_UNLOCKER_API_KEY not set")

    now = datetime.now()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and (now - cached["ts"]) < timedelta(seconds=TTL_SECONDS):
            return cached["html"]

    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_UNLOCKER_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            BRIGHTDATA_REQUEST_URL,
            json={
                "zone": BRIGHTDATA_UNLOCKER_ZONE,
                "url": url,
                "format": "raw",
            },
            headers=headers,
            timeout=BRIGHTDATA_REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as e:
        LAST_ERROR = str(e)
        print(f"[Bright Data] Exception: {e}")
        return None

    with _REQUESTS_LOCK:
        global _REQUESTS_MADE
        _REQUESTS_MADE += 1

    if response.status_code != 200:
        LAST_ERROR = f"HTTP {response.status_code}"
        print(f"[Bright Data] {response.status_code} {response.text[:300]}")
        return None

    html = response.text or ""
    LAST_ERROR = None
    with _CACHE_LOCK:
        _CACHE[url] = {"ts": datetime.now(), "html": html}
    return html


def search_products(keyword: str, pages: int = 1) -> List[Dict]:
    """Fetch Amazon search results for one keyword via the Web Unlocker.

    Returns normalized candidates (asin, name, amazon_price, product_url,
    brand, sales signals, rating) filtered by the shared Kirkland relevance
    rule. A page with zero cards stops paging; any failure records
    LAST_ERROR and stops the loop. Never raises (except missing-key).
    """
    if not keyword or not str(keyword).strip():
        return []
    keyword = str(keyword).strip()

    results: List[Dict] = []
    exhausted = False
    for page in range(1, max(1, pages) + 1):
        if exhausted:
            break
        url = f"{DEFAULT_MARKETPLACE.rstrip('/')}/s?k={quote(keyword)}&page={page}"
        html = _fetch(url)
        if html is None:
            break
        chunks = html.split('data-asin="')
        card_count = 0
        for chunk in chunks[1:]:
            candidate = _parse_card(chunk)
            if candidate is None:
                continue
            card_count += 1
            if not is_genuine_kirkland_candidate(candidate):
                continue
            results.append(candidate)
        print(
            f"[Bright Data] keyword='{keyword}' page={page}/{pages} "
            f"cards={card_count} kept={len(results)}"
        )
        if card_count == 0:
            exhausted = True

    return results


def get_product_detail(asin_or_url: str) -> Dict:
    """Fetch full product detail for one ASIN/URL via the Web Unlocker.

    Returns the normalized contract: asin, name/amazon_price, total_sellers,
    fba_sellers, fba_sellers_estimated, lowest_price, highest_price, brand,
    image_url, plus weight-derived FBA fee, sales rank, rating, reviews and
    monthly-sales signal. Missing/unparseable numeric fields are None, never
    0. Returns {} on any failure (LAST_ERROR set). Raises ValueError only
    when the API key is missing (contract).
    """
    asin = _extract_asin(asin_or_url)
    if not asin:
        LAST_ERROR = "invalid ASIN or URL"
        return {}
    url = f"{DEFAULT_MARKETPLACE.rstrip('/')}/dp/{asin}"
    html = _fetch(url)
    if html is None:
        return {}
    return _parse_product_page(html, asin)


def get_bright_data_request_count() -> int:
    """Requests made to the Web Unlocker this session."""
    with _REQUESTS_LOCK:
        return _REQUESTS_MADE


def get_bright_data_credits_remaining():
    """Free-tier credit balance (5,000/month shared pool, 1 credit/request).

    Bright Data exposes this only in the Control Panel and `brightdata
    budget` CLI — there is no REST endpoint for the free-credit balance —
    so this returns None. Watch the Control Panel (Billing Overview) or
    the CLI for the real number; request count is the session-side proxy.
    """
    return None