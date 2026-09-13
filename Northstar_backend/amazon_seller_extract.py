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

Patterns based on live Amazon dp page captures (2026-09-13).
"""

import re
from typing import Dict, Optional

# --- Buy Box seller name patterns (live Amazon dp) ----------------------------

# Pattern 1: "Sold by [Seller Name] and ships from Amazon Fulfillment"
# This is the Buy Box winner text shown in the merchant info popover area
# Tag-tolerant: live HTML often has <br>/<span> between tokens, so allow
# tags or whitespace as separators (v2 fix for dirty "and ships from..."
# names that fell through to the broad fallback).
_SEP = r"(?:<[^>]+>|\s)+"
_SELLER_NAME_SOLD_BY_SHIPS_RE = re.compile(
    r"Sold\s+by" + _SEP + r"([^<]+?)" + _SEP + r"and" + _SEP + r"ships" + _SEP + r"from" + _SEP + r"Amazon" + _SEP + r"Fulfillment",
    re.IGNORECASE,
)

# Pattern 2: "Ships from and sold by [Seller Name]" — Amazon Retail or FBA
_SELLER_NAME_SHIPS_FROM_SOLD_BY_RE = re.compile(
    r'Ships\s+from\s+and\s+sold\s+by\s+([^<.\n]+)',
    re.IGNORECASE
)

# Pattern 3: sellerProfileTriggerId link contains the seller name
# <a id='sellerProfileTriggerId' ...>Loong & Sons</a>
_SELLER_NAME_PROFILE_TRIGGER_RE = re.compile(
    r"id=['\"]sellerProfileTriggerId['\"][^>]*>([^<]+)</a>",
    re.IGNORECASE
)

# Pattern 4: Legacy bylineInfo with "Sold by <a>Name</a>" (older page format)
_SELLER_NAME_BYLINE_LINK_RE = re.compile(
    r'id="bylineInfo"[^>]*>.*?Sold by\s+<a[^>]*>([^<]+)</a>',
    re.IGNORECASE | re.S
)

# Pattern 5: Legacy bylineInfo "Sold by Name" without link
_SELLER_NAME_BYLINE_TEXT_RE = re.compile(
    r'id="bylineInfo"[^>]*>.*?Sold by\s+([^<\n]+)',
    re.IGNORECASE | re.S
)

# Pattern 6: Broad "Sold by" fallback (last resort)
_SELLER_NAME_BROAD_RE = re.compile(
    r'Sold\s+by\s+([A-Za-z0-9&][^<\n]{1,80})',
    re.IGNORECASE
)


# --- Fulfillment patterns (live Amazon dp) ------------------------------------

# FBA: "ships from Amazon Fulfillment" or "Fulfilled by Amazon"
_FULFILLMENT_FBA_RE = re.compile(
    r'(?:ships\s+from\s+Amazon\s+Fulfillment|Fulfilled\s+by\s+Amazon)',
    re.IGNORECASE
)

# Amazon Retail: "Ships from and sold by Amazon.com"
_FULFILLMENT_AMAZON_RE = re.compile(
    r'Ships\s+from\s+and\s+sold\s+by\s+Amazon\.com',
    re.IGNORECASE
)

# FBM: "Ships from [Seller] and sold by [Seller]" — both same seller
# Also catches "Ships from [X] Sold by [Y]" patterns
_FULFILLMENT_FBM_RE = re.compile(
    r'Ships\s+from\s+[^<\n]*\s+sold\s+by',
    re.IGNORECASE | re.S
)


# --- Total sellers count patterns (expanded to cover variants) ----------------

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

# --- Other sellers presence (offer-listing / aod) -----------------------------

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


def _post_clean_seller_name(name: Optional[str]) -> Optional[str]:
    """Remove fulfillment-clause remnants the broad fallback can capture.

    v2 fix: broad pattern "Sold by X" with a 80-char window grabs
    "Loong & Sons and ships from Amazon Fulfillment." when Pattern 1
    misses due to markup. Cut any trailing fulfillment clause and
    trailing periods so the cache stores "Loong & Sons", not the sentence.
    """
    if not name:
        return None
    cut = re.split(
        r"\s+and\s+ships\s+from\s+.*$|\s+ships\s+from\s+.*$",
        name,
        flags=re.IGNORECASE,
    )[0].strip()
    cut = cut.rstrip(".").strip()
    return cut or None


# Merchant-info block: fulfillment signals are only trustworthy here.
# Whole-page search matches carousel "Ships from X sold by Y" text for
# OTHER products and mislabels FBA pages as FBM (v2 fix).
_MERCHANT_BLOCK_RE = re.compile(
    r'<(?:div|span|td)[^>]*(?:merchant-info|merchantInfo|tabular-buybox|offer-listing|aod-container)[^>]*>(.*?)</(?:div|span|td)>',
    re.IGNORECASE | re.S,
)


def _fulfillment_scope(html: str) -> str:
    """Narrow fulfillment regex scope to the merchant block when present."""
    m = _MERCHANT_BLOCK_RE.search(html)
    if not m:
        return html
    block = m.group(1)
    # If the matched block carries no fulfillment signal (e.g. a bare
    # aod-container with only "Other sellers" text), fall back to the
    # full page so availability/byline markers are not lost.
    if (
        _FULFILLMENT_FBA_RE.search(block)
        or _FULFILLMENT_AMAZON_RE.search(block)
        or _FULFILLMENT_FBM_RE.search(block)
    ):
        return block
    return html


def extract_buy_box_seller(html: str) -> Optional[str]:
    """Extract Buy Box seller name from live Amazon dp markup.

    Priority order based on live page observations:
    1. "Sold by X and ships from Amazon Fulfillment" (most common FBA)
    2. "Ships from and sold by X" (Amazon Retail or FBA)
    3. sellerProfileTriggerId link (popover trigger)
    4. Legacy bylineInfo with link
    5. Legacy bylineInfo text
    6. Broad "Sold by" fallback
    """
    # Pattern 1: "Sold by X and ships from Amazon Fulfillment"
    match = _SELLER_NAME_SOLD_BY_SHIPS_RE.search(html)
    if match:
        name = _post_clean_seller_name(_clean_text(match.group(1)))
        if name:
            return name

    # Pattern 2: "Ships from and sold by X"
    match = _SELLER_NAME_SHIPS_FROM_SOLD_BY_RE.search(html)
    if match:
        name = _post_clean_seller_name(_clean_text(match.group(1)))
        if name:
            return name.rstrip(".")  # Remove trailing period from "Amazon.com."

    # Pattern 3: sellerProfileTriggerId
    match = _SELLER_NAME_PROFILE_TRIGGER_RE.search(html)
    if match:
        name = _post_clean_seller_name(_clean_text(match.group(1)))
        if name:
            return name

    # Pattern 4: Legacy bylineInfo with link
    match = _SELLER_NAME_BYLINE_LINK_RE.search(html)
    if match:
        name = _post_clean_seller_name(_clean_text(match.group(1)))
        if name:
            return name

    # Pattern 5: Legacy bylineInfo text
    match = _SELLER_NAME_BYLINE_TEXT_RE.search(html)
    if match:
        name = _post_clean_seller_name(_clean_text(match.group(1)))
        if name:
            return name

    # Pattern 6: Broad fallback
    match = _SELLER_NAME_BROAD_RE.search(html)
    if match:
        name = _post_clean_seller_name(_clean_text(match.group(1)))
        if name:
            return name

    return None


def extract_buy_box_fulfillment(html: str, seller_name: Optional[str]) -> str:
    """Determine Buy Box fulfillment: Amazon | FBA | FBM | Unknown.

    Logic based on live page text (order matters - check most specific first):
    - "ships from Amazon Fulfillment" / "Fulfilled by Amazon" -> FBA
    - "Ships from and sold by Amazon.com" (in Buy Box area) -> Amazon Retail
    - "Ships from [Seller] and sold by [Seller]" -> FBM
    - Fallback: if seller_name is "Amazon.com" -> Amazon

    v2 fix: scope regexes to the merchant-info block when present so
    carousel text for OTHER products cannot flip an FBA page to FBM.
    FBA wins over FBM whenever its marker is in scope.
    """
    scope = _fulfillment_scope(html)
    # FBA: "ships from Amazon Fulfillment" or "Fulfilled by Amazon"
    # Check this FIRST - it's the most specific to the Buy Box seller
    if _FULFILLMENT_FBA_RE.search(scope):
        return "FBA"

    # Amazon Retail: explicit "Ships from and sold by Amazon.com"
    # This can appear in related product carousels, so check seller name too
    if _FULFILLMENT_AMAZON_RE.search(scope):
        # Only return Amazon if the seller name is also Amazon.com
        if isinstance(seller_name, str) and seller_name.strip().lower() == "amazon.com":
            return "Amazon"

    # Also check seller name directly
    if isinstance(seller_name, str) and seller_name.strip().lower() == "amazon.com":
        return "Amazon"

    # FBM: "Ships from X and sold by X" pattern (only when NO FBA marker)
    if _FULFILLMENT_FBM_RE.search(scope):
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
        "sold_by_ships_from": len(_SELLER_NAME_SOLD_BY_SHIPS_RE.findall(html)),
        "ships_from_sold_by": len(_SELLER_NAME_SHIPS_FROM_SOLD_BY_RE.findall(html)),
        "seller_profile_trigger": len(_SELLER_NAME_PROFILE_TRIGGER_RE.findall(html)),
        "byline_link": len(_SELLER_NAME_BYLINE_LINK_RE.findall(html)),
        "byline_text": len(_SELLER_NAME_BYLINE_TEXT_RE.findall(html)),
        "broad_sold_by": len(_SELLER_NAME_BROAD_RE.findall(html)),
        "fulfillment_fba": len(_FULFILLMENT_FBA_RE.findall(html)),
        "fulfillment_amazon": len(_FULFILLMENT_AMAZON_RE.findall(html)),
        "fulfillment_fbm": len(_FULFILLMENT_FBM_RE.findall(html)),
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