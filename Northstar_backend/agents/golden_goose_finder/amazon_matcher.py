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

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .wholesale_scanner import WholesaleProduct

logger = logging.getLogger(__name__)


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
    # Seller identity — the "who sells it" gate. is_brand_seller True and
    # is_amazon_seller True are HARD BLOCKS (profile rule); None means the
    # seller analyzer could not verify identity (constant seller_identity_blocked
    # only returns True on observed/strong textual evidence; the scorer decides
    # whether unknown identity fails closed).
    seller_name: str | None = None
    is_brand_seller: bool | None = None
    is_amazon_seller: bool | None = None


# ---------------------------------------------------------------------------
# Seller-identity hard blocks
# ---------------------------------------------------------------------------

def seller_identity_blocked(
    seller_name: str | None,
    is_brand_seller: bool | None,
    is_amazon_seller: bool | None,
    product_brand: str | None = None,
) -> bool:
    """True when the listing's seller is a hard block for retail arbitrage.

    Hard blocks (profile rule):
      - ``is_brand_seller`` observed True (brand owner on the offer), OR
      - ``is_amazon_seller`` observed True (\"Sold by Amazon.com\"), OR
      - the seller text itself says \"Amazon.com\", OR
      - the seller text contains the product brand as a whole word
        (brand-owner heuristic for when the structured flag is missing).

    None / unknown flags are NOT a block here; the scorer independently
    decides that an UNVERIFIABLE identity fails the hard filter closed.
    """
    if is_brand_seller:
        return True
    if is_amazon_seller:
        return True
    if not seller_name or not str(seller_name).strip():
        return False
    seller = str(seller_name).strip().lower()
    if "amazon.com" in seller:
        return True
    if product_brand and str(product_brand).strip():
        brand = str(product_brand).strip().lower()
        if re.search(r"(?<!\w)" + re.escape(brand) + r"(?!\w)", seller):
            return True
    return False


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
    *,
    live_armed: bool = False,
) -> list[AmazonMatch]:
    """Search Amazon for individual / small-pack versions of a wholesale product.

    When ``live_armed=True`` and the §3 gate is satisfied, dispatches through
    the free-tier waterfall router (Chocodata search → EasyParser sellers).
    Otherwise returns deterministic mock data for testing.

    Strategy:
      1. Search by brand + product type keywords
      2. Filter to individual / small-pack size (exclude other multi-packs)
      3. Filter by brand match
      4. Enrich with seller identity (EasyParser)
      5. Rank by relevance
    """
    if live_armed:
        matches = _live_find_matches(wholesale_product, max_candidates)
        if matches:
            return matches
        # Live path returned nothing — fall through to mock for now
        logger.warning(
            "[AmazonMatcher] Live path returned no matches for '%s'; "
            "falling back to mock",
            wholesale_product.product_title,
        )

    # Mock path — deterministic for testing
    mock = get_mock_amazon_matches(wholesale_product)

    # Filter to individual listings
    filtered = [m for m in mock if is_individual_listing(m, wholesale_product.pack_count)]

    # Rank
    ranked = rank_candidates(filtered, wholesale_product)

    return ranked[:max_candidates]


def _live_find_matches(
    wholesale_product: WholesaleProduct,
    max_candidates: int,
) -> list[AmazonMatch]:
    """Live Amazon search via free-tier router.

    Builds a search query from the wholesale product, dispatches through the
    router's Chocodata adapter, parses results into AmazonMatch objects, and
    enriches each candidate with seller identity data from EasyParser.

    Returns an empty list on any failure (caller falls back to mock).
    """
    try:
        from .amazon_adapters import (
            build_search_query,
            make_chocodata_search_caller,
            make_easy_parser_seller_caller,
            parse_chocodata_results,
            parse_easy_parser_sellers,
        )
        from .free_tier_router import (
            TASK_AMAZON_OFFERS,
            TASK_AMAZON_SEARCH,
            run_task,
        )
    except ImportError as exc:
        logger.debug("[AmazonMatcher] Import error for live path: %s", exc)
        return []

    # Step 1: Build query and search Amazon
    query = build_search_query(wholesale_product.brand, wholesale_product.product_title)
    search_caller = make_chocodata_search_caller(query, pages=1)

    search_result = run_task(
        TASK_AMAZON_SEARCH,
        search_caller,
        live_armed=True,
    )

    if not search_result.ok or not search_result.result:
        return []

    # Parse search results into candidate dicts
    candidates = parse_chocodata_results(
        search_result.result,
        brand_filter=wholesale_product.brand,
    )

    if not candidates:
        return []

    # Step 2: Convert to AmazonMatch (pre-enrichment)
    matches: list[AmazonMatch] = []
    for cand in candidates[:max_candidates * 3]:  # fetch extra for filtering
        try:
            match = AmazonMatch(
                asin=cand["asin"],
                title=cand["title"],
                brand=cand["brand"],
                amazon_price=cand["amazon_price"],
                bsr=cand.get("bsr"),
                review_rating=cand.get("review_rating"),
                review_count=cand.get("review_count"),
                fba_sellers=cand.get("fba_sellers"),
                weight_oz=cand.get("weight_oz"),
                url=cand.get("url"),
                image_url=cand.get("image_url"),
                monthly_sales_estimate=cand.get("monthly_sales_estimate"),
                seller_name=cand.get("seller_name"),
                is_brand_seller=cand.get("is_brand_seller"),
                is_amazon_seller=cand.get("is_amazon_seller"),
            )
            matches.append(match)
        except Exception:
            continue

    if not matches:
        return []

    # Step 3: Enrich top candidates with seller identity (EasyParser)
    # Only enrich the first few to conserve credits
    enrich_count = min(len(matches), max_candidates + 2)
    for match in matches[:enrich_count]:
        try:
            seller_caller = make_easy_parser_seller_caller(match.asin)
            seller_result = run_task(
                TASK_AMAZON_OFFERS,
                seller_caller,
                live_armed=True,
            )
            if seller_result.ok and seller_result.result:
                seller_data = parse_easy_parser_sellers(seller_result.result)
                match.fba_sellers = seller_data.get("fba_sellers") or match.fba_sellers
                match.seller_name = seller_data.get("seller_name") or match.seller_name
                match.is_amazon_seller = seller_data.get("is_amazon_seller")
                # Check if seller name matches wholesale brand
                if seller_data.get("seller_name") and wholesale_product.brand:
                    brand_lower = wholesale_product.brand.lower()
                    seller_lower = seller_data["seller_name"].lower()
                    match.is_brand_seller = brand_lower in seller_lower
        except Exception as exc:
            logger.debug(
                "[AmazonMatcher] Seller enrichment failed for %s: %s",
                match.asin, exc,
            )

    # Step 4: Filter to individual listings
    filtered = [m for m in matches if is_individual_listing(m, wholesale_product.pack_count)]

    # Step 5: Rank
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
    _seed_best = brand + "best"
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(_seed_best)[:8],
        title=f"{brand} {product_type}{suffix}, {small_count} Count",
        brand=brand,
        amazon_price=_price(2.5),
        amazon_category="Health & Household",
        bsr=_stable_int(_seed_best, 500, 15000),
        review_rating=4.5,
        review_count=_stable_int(brand + "rv", 200, 8000),
        fba_sellers=_stable_int(brand + "fba", 0, 3),
        is_prime=True,
        url=f"https://www.amazon.com/dp/B0{''.join(str(ord(c))[-1] for c in brand[:5])}",
        monthly_sales_estimate=_stable_int(brand + "sales", 100, 3000),
        weight_oz=_mock_weight_oz(_seed_best),
        seller_name="Meritline Fulfillment",  # clean third-party primary
        is_brand_seller=False,
        is_amazon_seller=False,
    ))

    # --- Second match: slightly different size/variation ---
    _seed_v2 = brand + "v2"
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(_seed_v2)[:8],
        title=f"{brand} {product_type}{suffix}, {small_count * 2} Count",
        brand=brand,
        amazon_price=_price(2.0),
        amazon_category="Health & Household",
        bsr=_stable_int(_seed_v2, 2000, 40000),
        review_rating=4.3,
        review_count=_stable_int(brand + "rv2", 50, 3000),
        fba_sellers=_stable_int(brand + "fba2", 0, 2),
        is_prime=True,
        monthly_sales_estimate=_stable_int(brand + "sales2", 50, 1500),
        weight_oz=_mock_weight_oz(_seed_v2),
        seller_name="EchoSupply FBA",
        is_brand_seller=False,
        is_amazon_seller=False,
    ))

    # --- Third match: higher price, more reviews (may be seller-blocked) ---
    _seed_v3 = brand + "v3"
    _seller_name, _brand_sel, _amz_sel = _mock_seller_identity(_seed_v3, brand)
    matches.append(AmazonMatch(
        asin="B0" + _stable_hash(_seed_v3)[:8],
        title=f"{brand} {product_type}{suffix}, {small_count} Count Value",
        brand=brand,
        amazon_price=_price(3.5),
        amazon_category="Health & Household",
        bsr=_stable_int(_seed_v3, 1000, 25000),
        review_rating=4.6,
        review_count=_stable_int(brand + "rv3", 500, 12000),
        fba_sellers=_stable_int(brand + "fba3", 0, 2),
        is_prime=True,
        monthly_sales_estimate=_stable_int(brand + "sales3", 200, 5000),
        weight_oz=_mock_weight_oz(_seed_v3),
        seller_name=_seller_name,
        is_brand_seller=_brand_sel,
        is_amazon_seller=_amz_sel,
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
        weight_oz=_mock_weight_oz(brand + "gen"),
        seller_name="Periwinkle Trading",
        is_brand_seller=False,
        is_amazon_seller=False,
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
        weight_oz=_mock_weight_oz(brand + "mp"),
        seller_name="Bulk Value Outlet",
        is_brand_seller=False,
        is_amazon_seller=False,
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

def _mock_weight_oz(seed: str) -> float:
    """Deterministic small/light weight (8–32 oz → 0.5–2 lbs, preferred band)."""
    return float(_stable_int(seed + "wt", 8, 32))


def _mock_seller_identity(seed: str, brand: str, *, third_party_only: bool = False):
    """Deterministic mock seller identity per ASIN seed.

    Rolls 0/1/2 → brand-owner / Amazon.com / third-party so the mock
    pipeline exercises the seller-identity hard block. ``third_party_only``
    forces a clean third-party seller (used for the primary candidate).
    """
    if third_party_only:
        return "Meritline Fulfillment", False, False
    roll = _stable_int(seed + "seller", 0, 2)
    if roll == 0:
        return f"{brand} Consumer Care", True, False
    if roll == 1:
        return "Amazon.com", False, True
    return "EchoSupply FBA", False, False

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
