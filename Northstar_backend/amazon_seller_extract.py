"""Shared Amazon seller data extraction from product page HTML.

Single source of truth for seller data parsing: Buy Box seller name,
fulfillment type, total seller count, other-sellers presence. Used by
all transport adapters (Bright Data, scrape.do, Firecrawl, Browserbase)
so records are byte-compatible regardless of provider.

Contract mirrors map_seller_offer_contract shape for seller fields:
  - buy_box.seller_name
  - buy_box.fulfillment
  - total_sellers
  - other_sellers_present
  - (roster fields left null/honest: fba_sellers, fbm_sellers, amazon_sellers,
    offers[], seller_id, offers_complete)
"""

import re
from typing import Dict, Optional

# --- Buy Box / byline patterns ----------------------------------------------

# Primary: bylineInfo contains "Sold by X" often with a link to the seller profile
# Must handle nested tags: <div id="bylineInfo"><span>Sold by <a>Name</a></span></div>
_SELLER_NAME_RE = re.compile(
    r'id="bylineInfo"[^>]*>.*?Sold by\s+<a[^>]*>([^<]+)</a>', re.IGNORECASE | re.S
)
# Fallback 1: "Sold by Name" without link
_SELLER_NAME_FALLBACK1_RE = re.compile(
    r'id="bylineInfo"[^>]*>.*?Sold by\s+([^<\n]+)', re.IGNORECASE | re.S
)
# Fallback 2: broader "Sold by" pattern anywhere on page
_SELLER_NAME_FALLBACK2_RE = re.compile(
    r'Sold\s+by\s+([A-Za-z0-9][^<\n]{1,80})', re.IGNORECASE
)

# Fulfillment: "Fulfilled by Amazon" / "Ships from Amazon" / "Ships from X"
_FULFILLMENT_FBA_RE = re.compile(
    r'Fulfilled\s+by\s+Amazon', re.IGNORECASE
)
_FULFILLMENT_FBM_RE = re.compile(
    r'Ships\s+from.*?Sold\s+by', re.IGNORECASE | re.S
)

# --- Total sellers count patterns (expanded to cover variants) --------------

# Primary: "New (N) from $X" — exact pattern from current parser
_OFFERS_NEW_FROM_RE = re.compile(
    r"New\s*\((\d+)\)\s*from\s*\$?([\d,.]+)", re.IGNORECASE
)
# Variants observed in wild:
_OFFERS_NEW_FROM_VARIANT1 = re.compile(
    r"\((\d+)\s*new\s+offers?\)", re.IGNORECASE
)
_OFFERS_NEW_FROM_VARIANT2 = re.compile(
    r"(\d+)\s+new\s+from", re.IGNORECASE
)
_OFFERS_NEW_FROM_VARIANT3 = re.compile(
    r"New\s*\((\d+)\)", re.IGNORECASE
)
_OFFERS_NEW_FROM_VARIANT4 = re.compile(
    r"\((\d+)\)\s*new", re.IGNORECASE
)

# --- Other sellers presence (offer-listing / aod) ---------------------------

_OTHER_SELLERS_RE = re.compile(
    r"Other\s+sellers\s+on\s+Amazon", re.IGNORECASE
)
_AOD_OFFER_RE = re.compile(r"aod-offer", re.IGNORECASE)
_OFFER_LIST_RE = re.compile(r"aod-container|aod-list|offer-list", re.IGNORECASE)
_BUYING_OPTIONS_RE = re.compile(r"See\s+All\s+Buying\s+Options|All\s+Buying\s+Options", re.IGNORECASE)


def _clean_text(raw: Optional[str]) -> Optional[str]:
    """Strip tags and HTML entities from a seller/brand fragment."""
    if not raw:
        return None
    import html as html_module
    clean = html_module.unescape(re.sub(r"<[^>]+>", "", raw))
    return " ".join(clean.split()) or None


def extract_buy_box_seller(html: str) -> Optional[str]:
    """Extract Buy Box seller name from byline or nearby markup."""
    # Primary: bylineInfo with "Sold by <a>Name</a>"
    match = _SELLER_NAME_RE.search(html)
    if match:
        name = _clean_text(match.group(1))
        if name:
            return name
    # Fallback 1: bylineInfo with "Sold by Name" (no link)
    match = _SELLER_NAME_FALLBACK1_RE.search(html)
    if match:
        name = _clean_text(match.group(1))
        if name:
            return name
    # Fallback 2: broader "Sold by" pattern anywhere
    match = _SELLER_NAME_FALLBACK2_RE.search(html)
    if match:
        name = _clean_text(match.group(1))
        if name:
            return name
    return None


def extract_buy_box_fulfillment(html: str, seller_name: Optional[str]) -> str:
    """Determine Buy Box fulfillment: Amazon | FBA | FBM | Unknown."""
    # Amazon Retail (not FBA/FBM)
    if isinstance(seller_name, str) and seller_name.strip().lower() == "amazon.com":
        return "Amazon"
    # Fulfilled by Amazon
    if _FULFILLMENT_FBA_RE.search(html):
        return "FBA"
    # Ships from X / Sold by Y (FBM pattern)
    if _FULFILLMENT_FBM_RE.search(html):
        return "FBM"
    return "Unknown"


def extract_total_sellers(html: str) -> Optional[int]:
    """Extract total seller count from the 'New (N) from' line and variants."""
    # Primary
    match = _OFFERS_NEW_FROM_RE.search(html)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, IndexError):
            pass
    # Variants
    for rx in (
        _OFFERS_NEW_FROM_VARIANT1,
        _OFFERS_NEW_FROM_VARIANT2,
        _OFFERS_NEW_FROM_VARIANT3,
        _OFFERS_NEW_FROM_VARIANT4,
    ):
        match = rx.search(html)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue
    return None


def extract_other_sellers_present(html: str) -> bool:
    """Check for Other Sellers / AOD / offer-list markers on the page."""
    if _OTHER_SELLERS_RE.search(html):
        return True
    if _AOD_OFFER_RE.search(html):
        return True
    if _OFFER_LIST_RE.search(html):
        return True
    if _BUYING_OPTIONS_RE.search(html):
        return True
    return False


def extract_lowest_price(html: str, buy_box_price: Optional[float]) -> Optional[float]:
    """Extract lowest price from 'New (N) from $X' line.

    Only returns a price when the 'New (N) from $X' pattern is found.
    Does NOT fall back to buy_box_price — that would conflate the
    Buy Box price with the lowest competing offer price.
    """
    match = _OFFERS_NEW_FROM_RE.search(html)
    if match:
        try:
            return float(match.group(2).replace(",", ""))
        except (ValueError, IndexError):
            pass
    return None


def extract_seller_markers(html: str) -> Dict[str, int]:
    """Count all seller-related marker hits (for diagnostics/evidence)."""
    return {
        "byline_sold_by": len(_SELLER_NAME_RE.findall(html)),
        "fallback1_sold_by": len(_SELLER_NAME_FALLBACK1_RE.findall(html)),
        "fallback2_sold_by": len(_SELLER_NAME_FALLBACK2_RE.findall(html)),
        "fulfilled_by_amazon": len(_FULFILLMENT_FBA_RE.findall(html)),
        "ships_from_sold_by": len(_FULFILLMENT_FBM_RE.findall(html)),
        "new_from_count": len(_OFFERS_NEW_FROM_RE.findall(html)),
        "new_offers_variants": sum(
            len(rx.findall(html))
            for rx in (
                _OFFERS_NEW_FROM_VARIANT1,
                _OFFERS_NEW_FROM_VARIANT2,
                _OFFERS_NEW_FROM_VARIANT3,
                _OFFERS_NEW_FROM_VARIANT4,
            )
        ),
        "other_sellers_text": len(_OTHER_SELLERS_RE.findall(html)),
        "aod_offer": len(_AOD_OFFER_RE.findall(html)),
        "offer_list": len(_OFFER_LIST_RE.findall(html)),
        "buying_options": len(_BUYING_OPTIONS_RE.findall(html)),
    }


def extract_seller_data(html: str, buy_box_price: Optional[float] = None) -> Dict:
    """Full seller data extraction — single entry point for all transports.

    Returns dict with:
      - buy_box_seller_name
      - buy_box_fulfillment
      - total_sellers
      - other_sellers_present
      - lowest_price
      - marker_counts (diagnostic)
    """
    seller_name = extract_buy_box_seller(html)
    fulfillment = extract_buy_box_fulfillment(html, seller_name)
    total_sellers = extract_total_sellers(html)
    other_sellers = extract_other_sellers_present(html)
    lowest = extract_lowest_price(html, buy_box_price)
    markers = extract_seller_markers(html)

    return {
        "buy_box_seller_name": seller_name,
        "buy_box_fulfillment": fulfillment,
        "total_sellers": total_sellers,
        "other_sellers_present": other_sellers,
        "lowest_price": lowest,
        "marker_counts": markers,
    }