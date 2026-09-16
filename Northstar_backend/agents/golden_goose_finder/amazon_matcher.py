"""Amazon Matcher — find individual / small-pack Amazon listings for a
wholesale multi-pack product.

Strategy:
  1. Build a search query from the wholesale product (strip pack indicators)
  2. Search Amazon via provider_waterfall_router if available, otherwise mock
  3. Filter to individual / small-pack listings
  4. Rank by relevance (brand match, price proximity, BSR, reviews)

NEVER makes live API calls without explicit operator approval per §3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .wholesale_scanner import WholesaleProduct


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class AmazonMatch:
    """An Amazon individual listing matched to a wholesale product."""

    asin: str
    title: str
    brand: str
    amazon_price: float
    amazon_category: str | None = None
    browse_node: int | None = None
    bsr: int | None = None
    review_rating: float | None = None
    review_count: int | None = None
    fba_sellers: int | None = None
    is_prime: bool = False
    weight_oz: float | None = None
    dimensions_in: list[float] | None = None
    listing_fba_fee: float | None = None
    url: str | None = None
    image_url: str | None = None
    monthly_sales_estimate: int | None = None


# ---------------------------------------------------------------------------
# Multi-pack indicator tokens to strip from search queries
# ---------------------------------------------------------------------------

_STRIP_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d+\s*(?:ct|count|counts|packs?|pks?|pk|rolls?|sheets?|each|ea|bottles?|tubes?|bars?|sachets?)\b", re.I),
    re.compile(r"\(\d+\s*(?:ct|count|ea|each)\)", re.I),
    re.compile(r"\bpack\s+of\s+\d+\b", re.I),
    re.compile(r"\b\d+\s*x\s*\d+\b", re.I),
    re.compile(r"\b\d+\s*count\b", re.I),
]

# Tokens that signal a multi-pack listing on Amazon
_MULTI_PACK_SIGNALS = re.compile(
    r"(?:\b(\d+)\s*(?:ct|count|packs?|pks?|pk|rolls?|sheets?|each|ea|bottles?)\b"
    r"|\bpack\s+of\s+(\d+)"
    r"|\(\d+\s*(?:ct|count|ea|each)\)"
    r"|\bmulti[- ]?pack\b"
    r"|\b\d+\s*x\s*\d+\b)",
    re.I,
)

# Count at or above this threshold is considered a multi-pack indicator
_MULTI_PACK_THRESHOLD = 20


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def build_search_query(wholesale_product: WholesaleProduct) -> str:
    """Build an Amazon search query from a wholesale product.

    Strip multi-pack indicators, focus on brand + product name.

    Example:
        'Nicorette Nicotine Gum 4mg 220 Count'
        → 'Nicorette Nicotine Gum 4mg'
    """
    title = wholesale_product.product_title
    if not title:
        return wholesale_product.brand

    query = title
    for pat in _STRIP_PATTERNS:
        query = pat.sub("", query)

    # Collapse whitespace, remove empty parentheses and trailing separators
    query = re.sub(r"\s*\(\s*\)\s*", " ", query)
    query = re.sub(r"\s{2,}", " ", query).strip()
    query = re.sub(r"[,;:\-]+$", "", query).strip()
    query = re.sub(r"\s{2,}", " ", query).strip()

    # If we stripped too much, fall back to brand + category
    if len(query) < len(wholesale_product.brand) + 3:
        query = wholesale_product.brand

    return query


# ---------------------------------------------------------------------------
# Individual-listing filter
# ---------------------------------------------------------------------------

def is_individual_listing(
    amazon_match: AmazonMatch,
    wholesale_pack_count: Optional[int],
) -> bool:
    """Determine if an Amazon listing is for an individual / small pack.

    Heuristics:
      - Literal multi-pack phrases ("multi-pack", "pack of N", "N x M")
        always reject the listing.
      - If the wholesale pack count is known, the listing is an individual
        pack when its implied count is SMALLER than the club pack (e.g. an
        Amazon 60-count bottle IS the individual listing for a club
        500-count). Same-or-larger counts are another multi-pack → reject.
      - When the wholesale pack count is unknown, fall back to a generous
        absolute ceiling (>= 100) as a bulk/value-listing warning.
    """
    title = amazon_match.title
    if not title:
        return True  # can't tell; let it through

    # Literal multi-pack phrase: always reject regardless of count context.
    if re.search(r"\bmulti[- ]?pack\b|\bpack\s+of\s+\d+|\b\d+\s*x\s*\d+\b", title, re.I):
        return False

    amazon_count = _quick_count(title)

    # Relative check: known wholesale pack count → the listing must be
    # meaningfully smaller (<= half the club pack) to be an individual pack.
    if wholesale_pack_count is not None and wholesale_pack_count > 1:
        if amazon_count is not None and amazon_count >= wholesale_pack_count:
            return False
        if amazon_count is not None and amazon_count > wholesale_pack_count / 2:
            return False
        return True

    # Unknown wholesale context: generous absolute bulk ceiling.
    if amazon_count is not None and amazon_count >= 100:
        return False

    return True


def _quick_count(title: str) -> Optional[int]:
    """Quick pack-count extraction from an Amazon title."""
    match = re.search(
        r"(?:\b(\d+)\s*(?:ct|count|counts|packs?|pks?|pk|rolls?|sheets?|each|ea|bottles?|tubes?|bars?)\b"
        r"|\((\d+)\s*(?:ct|count|ea|each)\)"
        r"|\bpack\s+of\s+(\d+))",
        title, re.I,
    )
    if not match:
        return None
    for g in match.groups():
        if g is not None:
            try:
                return int(g)
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Candidate ranker
# ---------------------------------------------------------------------------

def rank_candidates(
    candidates: list[AmazonMatch],
    wholesale_product: WholesaleProduct,
) -> list[AmazonMatch]:
    """Rank Amazon match candidates by relevance.

    Factors (weighted score, higher = better):
      - Brand match (exact)  +10 pts
      - Price reasonableness  +0–8 pts (max when price ≈ wholesale_price / pack_count)
      - BSR (lower = better) +0–5 pts
      - Reviews (more = better) +0–3 pts
      - Is Prime               +1 pt
      - FBA sellers 0-2       +1 pt (competitive)
    """
    if not candidates:
        return []

    pack_count = wholesale_product.pack_count or 1
    expected_individual_price = wholesale_product.wholesale_price / max(pack_count, 1)

    def _score(m: AmazonMatch) -> float:
        s = 0.0
        # Brand match
        if m.brand and wholesale_product.brand:
            if m.brand.lower() == wholesale_product.brand.lower():
                s += 10.0
        # Price reasonableness — quadratic penalty for deviation
        if m.amazon_price > 0 and expected_individual_price > 0:
            ratio = m.amazon_price / expected_individual_price
            # Sweet spot: ratio 1.5 – 8.0 (individual sells for 1.5x–8x cost)
            if 1.5 <= ratio <= 8.0:
                s += 8.0
            elif 1.0 <= ratio < 1.5:
                s += 5.0  # tight margin
            elif ratio > 8.0:
                s += max(0.0, 8.0 - (ratio - 8.0))  # diminishing
            # ratio < 1.0 means Amazon price < Costco unit cost → 0 pts
        # BSR (lower is better)
        if m.bsr is not None:
            if m.bsr <= 1000:
                s += 5.0
            elif m.bsr <= 5000:
                s += 4.0
            elif m.bsr <= 25000:
                s += 3.0
            elif m.bsr <= 100000:
                s += 1.0
        # Reviews
        if m.review_count is not None:
            if m.review_count >= 1000:
                s += 3.0
            elif m.review_count >= 100:
                s += 2.0
            elif m.review_count >= 10:
                s += 1.0
        # Prime
        if m.is_prime:
            s += 1.0
        # FBA sellers (0–2 is competitive)
        if m.fba_sellers is not None and 0 <= m.fba_sellers <= 2:
            s += 1.0
        return s

    return sorted(candidates, key=_score, reverse=True)


# ---------------------------------------------------------------------------
# Main finder
# ---------------------------------------------------------------------------

async def find_individual_listing(
    wholesale_product: WholesaleProduct,
    max_candidates: int = 5,
) -> list[AmazonMatch]:
    """Search Amazon for individual / small-pack versions of a wholesale product.

    Uses provider_waterfall_router if available, otherwise returns mock data.
    NEVER makes live API calls without explicit operator approval per §3.

    Strategy:
      1. Search by brand + product type keywords
      2. Filter to individual / small-pack size (exclude other multi-packs)
      3. Filter by brand match
      4. Rank by relevance
    """
    # Attempt live path via provider waterfall — only when configured
    try:
        import provider_waterfall_router as pwr  # noqa: F401
        # Live path would go here; for now, provider_waterfall_router
        # requires a specific ASIN-based route_asin call, not keyword
        # search.  We fall through to mock for keyword search.
        pass
    except ImportError:
        pass

    # Mock path — deterministic for testing
    mock = get_mock_amazon_matches(wholesale_product)

    # Filter to individual listings
    filtered = [m for m in mock if is_individual_listing(m, wholesale_product.pack_count)]

    # Rank
    ranked = rank_candidates(filtered, wholesale_product)

    return ranked[:max_candidates]


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

# Realistic ASIN-like generators per product category
_ASIN_PREFIXES = ["B0", "B1", "B09", "B07", "B08"]


def get_mock_amazon_matches(wholesale_product: WholesaleProduct) -> list[AmazonMatch]:
    """Return realistic mock Amazon individual listing data.

    Generates 2–5 matches per wholesale product with realistic ASINs,
    prices, BSR values, FBA seller counts, and review data.

    Pricing model: Amazon individual/small-packs sell at a per-unit premium
    over wholesale per-unit COGS — e.g. Costco sells 500ct Advil for $24.99
    ($0.05/unit) while Amazon sells a 60ct bottle at ~$7.99 ($0.13/unit).
    The mock therefore prices a SMALL PACK (not a single count) at
    ``unit_cogs × small_pack_count × markup``.
    """
    brand = wholesale_product.brand
    title = wholesale_product.product_title
    pack = wholesale_product.pack_count or 1
    expected_unit = wholesale_product.wholesale_price / max(pack, 1)
    small_count = _small_pack_count(pack)

    # Determine product type from title for mock title generation
    product_type = _extract_product_type(title)
    strength = _extract_strength(title)
    suffix = f", {strength}" if strength else ""

    def _price(markup: float) -> float:
        """Individual-pack price = unit COGS × small count × Amazon markup."""
        return round(expected_unit * small_count * markup, 2)

    matches: list[AmazonMatch] = []

    # --- Best match: brand match, individual pack, good price ---
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(brand + "best")[:8],
        title=f"{brand} {product_type}{suffix}, {small_count} Count",
        brand=brand,
        amazon_price=_price(2.5),
        amazon_category="Health & Household",
        bsr=_stable_int(brand + "best", 500, 15000),
        review_rating=4.5,
        review_count=_stable_int(brand + "rv", 200, 8000),
        fba_sellers=_stable_int(brand + "fba", 0, 3),
        is_prime=True,
        url=f"https://www.amazon.com/dp/B0{''.join(str(ord(c))[-1] for c in brand[:5])}",
        monthly_sales_estimate=_stable_int(brand + "sales", 100, 3000),
    ))

    # --- Second match: slightly different size/variation ---
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(brand + "v2")[:8],
        title=f"{brand} {product_type}{suffix}, {small_count * 2} Count",
        brand=brand,
        amazon_price=_price(2.0),
        amazon_category="Health & Household",
        bsr=_stable_int(brand + "v2", 2000, 40000),
        review_rating=4.3,
        review_count=_stable_int(brand + "rv2", 50, 3000),
        fba_sellers=_stable_int(brand + "fba2", 0, 2),
        is_prime=True,
        monthly_sales_estimate=_stable_int(brand + "sales2", 50, 1500),
    ))

    # --- Third match: higher price, more reviews ---
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(brand + "v3")[:8],
        title=f"{brand} {product_type}{suffix}, {small_count} Count Value",
        brand=brand,
        amazon_price=_price(3.5),
        amazon_category="Health & Household",
        bsr=_stable_int(brand + "v3", 1000, 25000),
        review_rating=4.6,
        review_count=_stable_int(brand + "rv3", 500, 12000),
        fba_sellers=_stable_int(brand + "fba3", 0, 2),
        is_prime=True,
        monthly_sales_estimate=_stable_int(brand + "sales3", 200, 5000),
    ))

    # --- Possible non-brand match (competitor / generic) ---
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(brand + "generic")[:8],
        title=f"Generic {product_type}{suffix}, {small_count} Count",
        brand="Generic",
        amazon_price=_price(1.8),
        amazon_category="Health & Household",
        bsr=_stable_int(brand + "gen", 10000, 80000),
        review_rating=4.0,
        review_count=_stable_int(brand + "genv", 10, 500),
        fba_sellers=_stable_int(brand + "genfba", 1, 3),
        is_prime=False,
        monthly_sales_estimate=_stable_int(brand + "gensales", 20, 400),
    ))

    # --- Multi-pack that should be filtered OUT ---
    mp_count = pack  # use the actual wholesale pack count
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(brand + "mp")[:8],
        title=f"{brand} {product_type}{suffix}, {mp_count} Count",
        brand=brand,
        amazon_price=_price(mp_count * 1.8),
        amazon_category="Health & Household",
        bsr=_stable_int(brand + "mp", 3000, 30000),
        review_rating=4.4,
        review_count=_stable_int(brand + "mpv", 100, 2000),
        fba_sellers=_stable_int(brand + "mpfba", 0, 2),
        is_prime=True,
        monthly_sales_estimate=_stable_int(brand + "mpsales", 30, 600),
    ))

    return matches


def _small_pack_count(pack_count: int) -> int:
    """Derive a realistic Amazon small-pack count from the wholesale pack.

    Real-world small packs are roughly 1/4 to 1/5 of the club pack, but
    clamped to sensible consumer sizes (e.g. 4–60 per unit for OTC/vitamins;
    whole-item categories like a 30 lb dog food bag stay at 1).
    """
    if pack_count <= 1:
        return 1
    small = max(4, pack_count // 4)
    # Round to a friendly consumer count (10s / 20s / 25s / 30s / 60s / 90s)
    for target in (10, 20, 25, 30, 40, 60, 90, 100, 120, 150, 200, 250):
        if small <= target:
            return target
    return round(small / 10) * 10


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _extract_product_type(title: str) -> str:
    """Pull the core product type from a title for mock generation."""
    # Remove brand and numeric quantities
    cleaned = re.sub(r"\b(Nicorette|NicoDerm|Advil|Zyrtec|Claritin|Tylenol|Mucinex|Nature Made|Emergen.C|Centrum|Nature.s Bounty|Olly|Tide|Cascade|Lysol|Clorox|Swiffer|Dove|Colgate|Crest|Old Spice|CeraVe|Royal Canin|Blue Buffalo|Greenies|Temptations|Purina)\b", "", title, flags=re.I)
    cleaned = re.sub(r"\b\d+\s*(?:mg|ct|count|pack|oz|lb|g|ml)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
    words = [w for w in cleaned.split() if len(w) > 2][:4]
    return " ".join(words) if words else "Product"


def _extract_strength(title: str) -> str:
    """Extract dosage/strength like '2mg', '200mg', '10mg'."""
    match = re.search(r"(\d+(?:\.\d+)?\s*(?:mg|mcg|iu|ml|g))\b", title, re.I)
    return match.group(1) if match else ""


def _stable_hash(key: str) -> str:
    """Deterministic pseudo-hash for ASIN generation."""
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


def _stable_int(key: str, lo: int, hi: int) -> int:
    """Deterministic int in [lo, hi]."""
    h = 0
    for ch in key:
        h = (h * 13 + ord(ch)) & 0xFFFFFFFF
    return lo + (h % (hi - lo + 1))
