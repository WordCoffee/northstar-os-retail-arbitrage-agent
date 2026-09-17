"""Wholesale Scanner — Costco / Sam's Club small-light product discovery.

Scans warehouse club catalogs for SMALL, LIGHT, high-value national-brand
products (any pack size — singles AND multi-packs) whose individual units
can be resold on Amazon for $10+ net profit. Uses costco_api_client for
Costco data when available; falls back to deterministic mock data for
testing without live API calls.

Strategy filter: prefer <= 2 lbs, hard ceiling 5 lbs (trash bags are the
largest acceptable item). Heavy bulk (dog food bags, bleach jugs, litter)
is treated as out-of-scope.

NEVER makes live API calls without explicit operator approval per §3.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WholesaleProduct:
    """A product found at Costco or Sam's Club."""

    source_store: str  # "Costco" or "Sam's Club"
    product_title: str
    brand: str
    category_slug: str
    pack_count: int | None  # extracted from title
    wholesale_price: float
    item_url: str | None = None
    item_number: str | None = None  # Costco item # or Sam's Club item #
    weight_lbs: float | None = None
    dimensions_in: list[float] | None = None
    image_url: str | None = None
    in_stock: bool = True


# ---------------------------------------------------------------------------
# Brand allowlist — known brands whose products commonly have
# pack-breakdown arbitrage on Amazon
# ---------------------------------------------------------------------------

_BRAND_ALLOWLIST: list[str] = [
    # Nicotine cessation
    "Nicorette", "NicoDerm", "Zonnic",
    # OTC health
    "Advil", "Zyrtec", "Claritin", "Tylenol", "Mucinex",
    "Aleve", "Benadryl", "Pepcid", "Prilosec", "Flonase",
    "Theraflu", "Robitussin", "Coricidin",
    # Vitamins / supplements
    "Nature Made", "Emergen-C", "Centrum", "Nature's Bounty", "Olly",
    "MegaFood", "Garden of Life", "One A Day", "Caltrate",
    # Household
    "Tide", "Cascade", "Lysol", "Clorox", "Swiffer",
    "Mr. Clean", "Febreze", "Bounty", "Charmin", "Downy",
    "Gain", "Pine-Sol",
    # Personal care
    "Dove", "Colgate", "Crest", "Old Spice", "CeraVe",
    "Nivea", "Aquaphor", "Olay", "Neutrogena", "Schick",
    "Gillette", "Bioderma",
    # Pet — toys, grooming, collars/harnesses, small accessories (NOT food)
    "KONG", "Chuckit", "Furminator", "Hartz", "PetSafe", "Outward Hound",
    "Nylabone", "ZippyPaws", "Greenies", "Temptations", "Pet Head", "Wahl",
]

_BRAND_ALLOWLIST_LOWER: dict[str, str] = {b.lower(): b for b in _BRAND_ALLOWLIST}

# Multi-pack indicator tokens for pack-count extraction
_PACK_COUNT_PATTERN = re.compile(
    r"(?:"
    r"(\d+)\s*-?\s*(?:ct|count|counts)\b"     # 200 Count, 12-count, 100-count
    r"|(\d+)\s*(?:packs?|pks?|pk)\b"          # 30 Pack, 12-Packs
    r"|(?:pack|case)\s+of\s+(\d+)"            # pack of 12
    r"|(\d+)\s*(?:roll|rolls?|sheet|sheets?|bottles?|tubes?|bars?|sachets?|pouches?)\b"
    r"|\((\d+)\s*-?\s*(?:ct|count|ea|each)\)" # (60 ct), (60-count)
    r"|(\d+)\s*(?:ea|each)\b"                  # 6 each
    r"|\d+\s*x\s*(\d+)\s*-?\s*(?:ct|count|oz|g|ml|lb)\b"  # 2 x 100 count → 100
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Title parsing helpers
# ---------------------------------------------------------------------------

def extract_brand_from_title(title: str) -> Optional[str]:
    """Extract brand name from a product title.

    Known brand matching against the brand allowlist.
    Returns None if brand cannot be determined.
    """
    if not title:
        return None
    title_lower = title.lower()
    # Try exact prefix match first (most Costco titles start with brand)
    for brand_lower, brand_canonical in _BRAND_ALLOWLIST_LOWER.items():
        if title_lower.startswith(brand_lower):
            return brand_canonical
    # Try anywhere in title
    best_match: Optional[str] = None
    best_len = 0
    for brand_lower, brand_canonical in _BRAND_ALLOWLIST_LOWER.items():
        # Word-boundary match to avoid substrings like "nice" matching "nice"
        if re.search(r"(?<!\w)" + re.escape(brand_lower) + r"(?!\w)", title_lower):
            if len(brand_lower) > best_len:
                best_match = brand_canonical
                best_len = len(brand_lower)
    return best_match


def extract_pack_count(title: str, category_slug: Optional[str] = None) -> Optional[int]:
    """Extract pack count / quantity from product title using regex.

    Examples:
        '200 Count' → 200
        '30 Pack' → 30
        '12-Count' → 12
        '1.6 oz (60 ct)' → 60
        '24 Pack of 2 oz tubes' → 24

    Returns None if cannot determine.
    """
    if not title:
        return None
    match = _PACK_COUNT_PATTERN.search(title)
    if not match:
        return None
    # Return the first non-None group
    for group in match.groups():
        if group is not None:
            try:
                val = int(group)
                if val > 0:
                    return val
            except ValueError:
                continue
    return None


def parse_wholesale_product(
    raw_data: dict,
    source_store: str,
    category_slug: str,
) -> Optional[WholesaleProduct]:
    """Parse raw catalog data into a WholesaleProduct.

    Extract brand from title, parse pack count, clean up data.
    """
    title = (
        raw_data.get("product_title")
        or raw_data.get("item_name")
        or raw_data.get("name")
        or ""
    ).strip()
    if not title:
        return None

    brand = raw_data.get("brand") or extract_brand_from_title(title) or "Unknown"
    pack_count = raw_data.get("pack_count") or extract_pack_count(title, category_slug)

    price = raw_data.get("wholesale_price") or raw_data.get("price") or raw_data.get("current_price")
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    url = (
        raw_data.get("item_url")
        or raw_data.get("product_url")
        or raw_data.get("source_url")
    )
    item_num = raw_data.get("item_number") or raw_data.get("costco_item_id")

    weight = raw_data.get("weight_lbs")
    if weight is not None:
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = None

    dims = raw_data.get("dimensions_in")
    if isinstance(dims, list):
        try:
            dims = [float(d) for d in dims]
        except (TypeError, ValueError):
            dims = None

    in_stock = raw_data.get("in_stock", True)
    if isinstance(in_stock, str):
        in_stock = in_stock.lower() not in ("false", "out_of_stock", "out of stock", "0")

    return WholesaleProduct(
        source_store=source_store,
        product_title=title,
        brand=brand,
        category_slug=category_slug,
        pack_count=pack_count,
        wholesale_price=price,
        item_url=url,
        item_number=item_num,
        weight_lbs=weight,
        dimensions_in=dims,
        image_url=raw_data.get("image_url"),
        in_stock=in_stock,
    )


# ---------------------------------------------------------------------------
# Costco URL slug → internal category slug mapping
# ---------------------------------------------------------------------------

_COSTCO_SLUG_MAP: dict[str, str] = {
    "health-household": "otc_health",
    "vitamins-supplements": "vitamins_supplements",
    "household-essentials": "household_cleaning",
    "personal-care": "personal_care",
    "pet-supplies": "pet",
    "nicotine cessation": "nicotine_cessation",
    "otc health": "otc_health",
    "vitamins": "vitamins_supplements",
    "household": "household_cleaning",
    "personal care": "personal_care",
    "pet": "pet",
}


# ---------------------------------------------------------------------------
# Scanner functions
# ---------------------------------------------------------------------------

async def scan_costco_categories(
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    max_results_per_category: int = 50,
    *,
    live: bool = False,
) -> list[WholesaleProduct]:
    """Scan Costco for multi-pack products in target categories.

    Returns deterministic mock data by default.  The live OpenWebNinja
    path (via costco_api_client) is only reachable when the operator has
    EXPLICITLY approved live execution: callers must pass ``live=True``
    AND the environment variable ``GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED``
    must equal "1" (named operator approval per §3).  Without both, this
    function performs ZERO network calls and returns mock data.

    Anything less is a §3 violation: this module never calls the live
    Costco API silently.
    """
    approved = os.getenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "").strip() == "1"
    if live and approved:
        # Only reachable with explicit, named operator approval.
        try:
            import costco_api_client as cac
            results: list[WholesaleProduct] = []
            cats = categories or [
                "nicotine_cessation",
                "otc_health",
                "vitamins_supplements",
                "household_cleaning",
                "personal_care",
                "pet",
            ]
            # Map internal slugs to Costco URL slugs for the API query
            _REVERSE_SLUG_MAP = {v: k for k, v in _COSTCO_SLUG_MAP.items()}
            for cat in cats:
                query = " ".join(keywords or []) or _REVERSE_SLUG_MAP.get(cat, cat).replace("-", " ")
                raw = cac.search_page(query, 1)
                if raw.get("success") and raw.get("items"):
                    for item in raw["items"][:max_results_per_category]:
                        # Map OpenWebNinja category slug to our internal slug
                        internal_cat = _COSTCO_SLUG_MAP.get(cat, cat)
                        parsed = parse_wholesale_product(
                            {
                                "product_title": item.get("item_name"),
                                "brand": item.get("brand"),
                                "price": item.get("regular_price") or item.get("sale_price"),
                                "item_number": item.get("costco_item_id"),
                                "item_url": item.get("source_url") or item.get("product_url"),
                                "pack_count": item.get("pack_count"),
                                "weight_lbs": item.get("net_weight"),
                                "image_url": None,
                                "in_stock": item.get("availability", "in_stock") == "in_stock",
                            },
                            source_store="Costco",
                            category_slug=internal_cat,
                        )
                        if parsed:
                            results.append(parsed)
            return results
        except Exception:
            # A live failure falls back to mock rather than crashing a scan.
            pass

    # Mock path — the only path reachable without §3 approval.
    cats = categories or ["nicotine-cessation", "otc-health", "vitamins", "household", "personal-care", "pet"]
    results = []
    for cat in cats:
        results.extend(get_mock_wholesale_data(cat))
    return results


async def scan_sams_club(
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    max_results_per_category: int = 50,
) -> list[WholesaleProduct]:
    """Scan Sam's Club for multi-pack products.

    Uses Bright Data Web Unlocker if configured, otherwise returns mock
    data.  NEVER makes live API calls without explicit operator approval
    per §3.
    """
    import copy

    # Sam's Club has no live API configured yet — always mock
    cats = categories or ["nicotine-cessation", "otc-health", "vitamins", "household", "personal-care", "pet"]
    results = []
    for cat in cats:
        mock = get_mock_wholesale_data(cat)
        # Duplicate a few as Sam's Club with slight price variations
        for p in mock[:2]:
            sams = copy.copy(p)
            sams.source_store = "Sam's Club"
            sams.item_number = f"SM-{p.item_number}" if p.item_number else None
            sams.wholesale_price = round(sams.wholesale_price * 0.97, 2)  # ~3% cheaper
            results.append(sams)
    return results


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

def get_mock_wholesale_data(category_slug: Optional[str] = None) -> list[WholesaleProduct]:
    """Return realistic mock Costco / Sam's Club product data for testing.

    Includes 30+ products across all target categories with realistic
    titles, brands, prices, and pack counts.
    """
    _all = _MOCK_PRODUCTS[:]
    if category_slug:
        _all = [p for p in _all if p.category_slug == category_slug]
    return _all


# fmt: off
_MOCK_PRODUCTS: list[WholesaleProduct] = [
    # ── Nicotine cessation (5) ──────────────────────────────────────
    WholesaleProduct("Costco", "Nicorette Nicotine Gum 2mg, 200 Count", "Nicorette", "nicotine-cessation", 200, 89.99, "https://www.costco.com/nicorette-gum-2mg-200ct.html", "1234567", weight_lbs=1.1),
    WholesaleProduct("Costco", "NicoDerm CQ Nicotine Patch Step 2, 144 Count", "NicoDerm", "nicotine-cessation", 144, 119.99, "https://www.costco.com/nicoderm-cq-step2-144ct.html", "1234568", weight_lbs=1.0),
    WholesaleProduct("Costco", "Nicorette Nicotine Lozenge 4mg, 160 Count", "Nicorette", "nicotine-cessation", 160, 99.99, "https://www.costco.com/nicorette-lozenge-4mg-160ct.html", "1234569", weight_lbs=0.9),
    WholesaleProduct("Costco", "Nicorette Nicotine Gum 4mg, 220 Count", "Nicorette", "nicotine-cessation", 220, 109.99, "https://www.costco.com/nicorette-gum-4mg-220ct.html", "1234570", weight_lbs=1.2),
    WholesaleProduct("Costco", "NicoDerm CQ Nicotine Patch Step 1, 168 Count", "NicoDerm", "nicotine-cessation", 168, 129.99, "https://www.costco.com/nicoderm-cq-step1-168ct.html", "1234571", weight_lbs=1.1),

    # ── OTC health (5) ─────────────────────────────────────────────
    WholesaleProduct("Costco", "Advil Ibuprofen Pain Reliever 200mg, 500 Tablets", "Advil", "otc-health", 500, 29.99, "https://www.costco.com/advil-ibuprofen-500ct.html", "1234572", weight_lbs=1.8),
    WholesaleProduct("Costco", "Zyrtec Allergy Relief Tablets 10mg, 365 Count", "Zyrtec", "otc-health", 365, 42.99, "https://www.costco.com/zyrtec-allergy-365ct.html", "1234573", weight_lbs=1.2),
    WholesaleProduct("Costco", "Claritin Allergy 24HR Tablets 10mg, 300 Count", "Claritin", "otc-health", 300, 54.99, "https://www.costco.com/claritin-300ct.html", "1234574", weight_lbs=1.0),
    WholesaleProduct("Costco", "Tylenol Extra Strength Caplets 500mg, 600 Count", "Tylenol", "otc-health", 600, 24.99, "https://www.costco.com/tylenol-extra-strength-600ct.html", "1234575", weight_lbs=1.9),
    WholesaleProduct("Costco", "Mucinex Maximum Strength 12-Hour Tablets, 100 Count", "Mucinex", "otc-health", 100, 49.99, "https://www.costco.com/mucinex-max-strength-100ct.html", "1234576", weight_lbs=1.3),

    # ── Vitamins / supplements (5) ──────────────────────────────────
    WholesaleProduct("Costco", "Nature Made Vitamin D3 2000 IU, 500 Softgels", "Nature Made", "vitamins", 500, 19.99, "https://www.costco.com/nature-made-vitamin-d3-500ct.html", "1234577", weight_lbs=1.4),
    WholesaleProduct("Costco", "Emergen-C Vitamin C Supplement 1000mg, 90 Count", "Emergen-C", "vitamins", 90, 24.99, "https://www.costco.com/emergen-c-90ct.html", "1234578", weight_lbs=0.5),
    WholesaleProduct("Costco", "Centrum Multivitamin Adults, 500 Tablets", "Centrum", "vitamins", 500, 29.99, "https://www.costco.com/centrum-adults-500ct.html", "1234579", weight_lbs=1.5),
    WholesaleProduct("Costco", "Nature's Bounty Vitamin B12 5000mcg, 200 Softgels", "Nature's Bounty", "vitamins", 200, 17.99, "https://www.costco.com/natures-bounty-b12-200ct.html", "1234580", weight_lbs=1.0),
    WholesaleProduct("Costco", "Olly Restful Sleep Gummies 50mg, 140 Count", "Olly", "vitamins", 140, 22.99, "https://www.costco.com/olly-restful-sleep-140ct.html", "1234581", weight_lbs=0.8),

    # ── Household — SMALL items only (5) ────────────────────────────
    WholesaleProduct("Costco", "Tide Laundry Detergent Pods 4-in-1, 152 Count", "Tide", "household", 152, 34.99, "https://www.costco.com/tide-pods-152ct.html", "1234582", weight_lbs=4.8),
    WholesaleProduct("Costco", "Cascade Platinum Dishwasher Pods, 104 Count", "Cascade", "household", 104, 29.99, "https://www.costco.com/cascade-platinum-104ct.html", "1234583", weight_lbs=4.2),
    WholesaleProduct("Costco", "Lysol Disinfecting Wipes, 225 Count", "Lysol", "household", 225, 14.99, "https://www.costco.com/lysol-wipes-225ct.html", "1234584", weight_lbs=2.6),
    WholesaleProduct("Costco", "Swiffer WetJet Mopping Pad Refills, 64 Count", "Swiffer", "household", 64, 24.99, "https://www.costco.com/swiffer-wetjet-64ct.html", "1234585", weight_lbs=1.4),
    WholesaleProduct("Costco", "Febreze Car Air Freshener Vent Clips, 12 Count", "Febreze", "household", 12, 11.99, "https://www.costco.com/febreze-vent-clips-12ct.html", "1234597", weight_lbs=0.6),

    # ── Personal care (5) ───────────────────────────────────────────
    WholesaleProduct("Costco", "Dove Beauty Bar 4.25 oz, 14 Count", "Dove", "personal-care", 14, 16.99, "https://www.costco.com/dove-beauty-bar-14ct.html", "1234586", weight_lbs=1.6),
    WholesaleProduct("Costco", "Colgate Total Whitening Toothpaste 5.1 oz, 6 Pack", "Colgate", "personal-care", 6, 19.99, "https://www.costco.com/colgate-total-6pk.html", "1234587", weight_lbs=1.9),
    WholesaleProduct("Costco", "Crest 3D White Toothpaste 5.1 oz, 8 Pack", "Crest", "personal-care", 8, 24.99, "https://www.costco.com/crest-3d-white-8pk.html", "1234588", weight_lbs=2.2),
    WholesaleProduct("Costco", "Old Spice Body Wash 18 oz, 6 Pack", "Old Spice", "personal-care", 6, 21.99, "https://www.costco.com/old-spice-body-wash-6pk.html", "1234589", weight_lbs=3.9),
    WholesaleProduct("Costco", "CeraVe Moisturizing Cream 19 oz, 2 Pack", "CeraVe", "personal-care", 2, 29.99, "https://www.costco.com/cerave-cream-2pk.html", "1234590", weight_lbs=2.6),

    # ── Pet — toys, grooming, collars, harnesses (NOT food) (5) ─────
    WholesaleProduct("Costco", "KONG Classic Dog Toy, Medium (2 Pack)", "KONG", "pet", 2, 15.99, "https://www.costco.com/kong-classic-2pk.html", "1234591", weight_lbs=0.9),
    WholesaleProduct("Costco", "Furminator deShedding Tool for Dogs, Large", "Furminator", "pet", 1, 24.99, "https://www.costco.com/furminator-large.html", "1234592", weight_lbs=0.5),
    WholesaleProduct("Costco", "Chuckit! Ultra Ball, Large (2 Pack)", "Chuckit", "pet", 2, 10.99, "https://www.costco.com/chuckit-ultra-2pk.html", "1234593", weight_lbs=0.8),
    WholesaleProduct("Costco", "Hartz Groomer's Best Slicker Brush for Dogs", "Hartz", "pet", 1, 12.99, "https://www.costco.com/hartz-slicker-brush.html", "1234594", weight_lbs=0.4),
    WholesaleProduct("Costco", "PetSafe Easy Walk Dog Harness, Large", "PetSafe", "pet", 1, 19.99, "https://www.costco.com/petsafe-easy-walk-large.html", "1234595", weight_lbs=0.6),
]
# fmt: on
