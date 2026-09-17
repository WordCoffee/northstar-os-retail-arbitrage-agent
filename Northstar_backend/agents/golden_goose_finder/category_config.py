"""Golden Goose Finder — brand/category registry.

Registry of national brands and the categories the Golden Goose Finder scans
for retail-arbitrage opportunities (buy a small, light, high-value product at
Costco / Sam's Club, resell the individual units on Amazon).

Strategy rules (profile-level, NOT master-brain defaults):
- ANY small, light item with >= $10 NET profit per unit after all Amazon fees
  is a target — multi-pack breakdown is one path, not the only path.
- Preferred weight <= 2 lbs; hard ceiling 5 lbs (trash bags are the largest
  acceptable item, and most of those are already too heavy).
- 1,000+ monthly sales on Amazon is the demand floor.
- Competition floor: 0 FBA sellers (gold), or 1-2 FBA sellers whose Buy Box
  price is high enough that undercutting by 2% still clears the profit floor.
  Brand-owner sellers and Amazon.com as a seller are HARD BLOCKS.
- NATIONAL BRANDS ONLY. Store brands / private labels (Kirkland Signature,
  Member's Mark, Great Value, Equate, ...) are excluded by BRAND_EXCLUSION_LIST
  and never appear in BRAND_ALLOWLIST.
- ``amazon_category_name`` matches the fee_engine category names in
  ``Northstar_backend/amazon_us_fee_rules_2026.py`` / ``fee_engine.py`` so the
  referral fee used for planning is the same category the fee engine resolves.
- ``referral_fee_rate`` records the tier that applies at the TYPICAL individual
  unit price (Health & Personal Care / Beauty / Grocery use Amazon's
  price_switch: 0.08 low tier, 0.15 high tier). The fee engine still applies
  the exact switch schedule at calculation time — this field is the planning
  estimate.
- ``DEFAULT_ROI_FLOOR_PER_UNIT`` is a scanner-level default that profiles may
  override; it is intentionally NOT a master-brain global.
"""

import re

# --------------------------------------------------------------------------
# Brand allowlist: brand_name -> category_slug
# --------------------------------------------------------------------------
# National brands only. Equate / Rite Aid store brands and all other private
# labels are deliberately NOT listed (see BRAND_EXCLUSION_LIST).
BRAND_ALLOWLIST = {
    # --- Nicotine cessation (Nicorette & NicoDerm CQ are GSK national brands)
    "Nicorette": "nicotine_cessation",
    "NicoDerm CQ": "nicotine_cessation",
    "Zonnic": "nicotine_cessation",
    "Habitrol": "nicotine_cessation",
    # --- OTC health
    "Advil": "otc_health",
    "Motrin": "otc_health",
    "Tylenol": "otc_health",
    "Aleve": "otc_health",
    "Zyrtec": "otc_health",
    "Claritin": "otc_health",
    "Allegra": "otc_health",
    "Benadryl": "otc_health",
    "Sudafed": "otc_health",
    "Mucinex": "otc_health",
    "Theraflu": "otc_health",
    "Pepto-Bismol": "otc_health",
    "Tums": "otc_health",
    "Gas-X": "otc_health",
    "Imodium": "otc_health",
    "Dramamine": "otc_health",
    # --- Vitamins & supplements
    "Nature Made": "vitamins_supplements",
    "Nature's Bounty": "vitamins_supplements",
    "Centrum": "vitamins_supplements",
    "Emergen-C": "vitamins_supplements",
    "One A Day": "vitamins_supplements",
    "Olly": "vitamins_supplements",
    "SmartyPants": "vitamins_supplements",
    "Airborne": "vitamins_supplements",
    "Zicam": "vitamins_supplements",
    "Flintstones": "vitamins_supplements",
    # --- Household cleaning
    "Tide": "household_cleaning",
    "Cascade": "household_cleaning",
    "Lysol": "household_cleaning",
    "Clorox": "household_cleaning",
    "Pine-Sol": "household_cleaning",
    "Fabuloso": "household_cleaning",
    "Swiffer": "household_cleaning",
    "Mr. Clean": "household_cleaning",
    "Method": "household_cleaning",
    "Seventh Generation": "household_cleaning",
    # --- Personal care
    "Dove": "personal_care",
    "Old Spice": "personal_care",
    "Colgate": "personal_care",
    "Crest": "personal_care",
    "Oral-B": "personal_care",
    "Burt's Bees": "personal_care",
    "CeraVe": "personal_care",
    "Neutrogena": "personal_care",
    "Aveeno": "personal_care",
    "Dr. Teals": "personal_care",
    "Eucerin": "personal_care",
    "Aquaphor": "personal_care",
    # --- Pet (toys, grooming, collars/harnesses, small accessories — NOT food)
    # User rule: pet = toys, shampoos, collars, harnesses, grooming tools,
    # small accessories. Heavy bags of food / litter are EXCLUDED by the size
    # filter, which is why food brands are not allowlisted here.
    "KONG": "pet",
    "Chuckit": "pet",
    "Furminator": "pet",
    "Hartz": "pet",
    "PetSafe": "pet",
    "Outward Hound": "pet",
    "Nylabone": "pet",
    "ZippyPaws": "pet",
    "Greenies": "pet",
    "Temptations": "pet",
    "Pet Head": "pet",
    "Wahl": "pet",
    # --- Snacks & bars
    "RXBAR": "snacks_bars",
    "KIND": "snacks_bars",
    "Nature Valley": "snacks_bars",
    "Belvita": "snacks_bars",
    "Clif Bar": "snacks_bars",
    "Larabar": "snacks_bars",
    "Quaker Chewy": "snacks_bars",
    "Annie's": "snacks_bars",
    "Pirate's Booty": "snacks_bars",
    # --- Baby & child
    "Huggies": "baby_child",
    "Pampers": "baby_child",
    "Luvs": "baby_child",
    "Enfamil": "baby_child",
    "Similac": "baby_child",
    "Gerber": "baby_child",
    "PediaSure": "baby_child",
}

# --------------------------------------------------------------------------
# Brand exclusion list — any product whose title/brand matches one of these
# substrings (case-insensitive) is rejected as a store/private label.
# --------------------------------------------------------------------------
BRAND_EXCLUSION_LIST = [
    "Kirkland Signature",
    "Member's Mark",
    "Great Value",
    "Equate",
    "store brand",
    "private label",
    # Add more as discovered
]

# --------------------------------------------------------------------------
# Global size filter defaults — small, LIGHT items with low FBA fees.
#
# PREFERRED_MAX_WEIGHT_OZ is the sweet spot (2 lbs): these items land in the
# small-standard FBA fee band and keep fees from eating the margin.
# ABS_MAX_WEIGHT_OZ is the hard ceiling (5 lbs): trash bags / small bulk
# boxes are the largest acceptable items; anything heavier is REJECTED.
# --------------------------------------------------------------------------
PREFERRED_MAX_WEIGHT_OZ = 32.0  # 2 lbs
ABS_MAX_WEIGHT_OZ = 80.0        # 5 lbs — hard ceiling
PREFERRED_MAX_WEIGHT_LBS = PREFERRED_MAX_WEIGHT_OZ / 16.0
ABS_MAX_WEIGHT_LBS = ABS_MAX_WEIGHT_OZ / 16.0

DEFAULT_SIZE_FILTER = {
    "max_weight_oz": PREFERRED_MAX_WEIGHT_OZ,   # 2 lbs preferred
    "abs_max_weight_oz": ABS_MAX_WEIGHT_OZ,     # 5 lbs hard ceiling
    "max_dimensions_in": [12, 8, 4],
    "description": (
        "Small, light items (<= 2 lbs preferred; 5 lbs hard ceiling) so the "
        "item lands in the cheap small-standard FBA band."
    ),
}

# --------------------------------------------------------------------------
# Seller-identity hard blocks (profile-level gate).
# --------------------------------------------------------------------------
BLOCK_BRAND_AS_SELLER = True   # brand owner on the Buy Box -> do not enter
BLOCK_AMAZON_AS_SELLER = True   # Amazon.com as a seller -> do not enter
COMPETITION_MAX_FBA_SELLERS = 2  # 0 = gold; 1-2 OK if we can undercut; 3+ reject
UNDERCUT_DISCOUNT_RATE = 0.02    # we price 2% below the Buy Box to win it

# --------------------------------------------------------------------------
# Demand floor — scanner-level default. Overridable per user profile; this is
# intentionally NOT a master-brain global default.
# --------------------------------------------------------------------------
DEFAULT_MIN_MONTHLY_SALES = 1000  # proven demand: 1K+ units/mo
DEFAULT_ROI_FLOOR_PER_UNIT = 10.00  # Overridable per user profile — NOT a master brain default

# --------------------------------------------------------------------------
# Category configuration
# --------------------------------------------------------------------------
# amazon_category_name matches fee_engine categories; browse nodes are
# realistic Amazon node IDs where high-confidence plus human-readable node
# paths (IDs evolve; names stay stable enough for planning).
CATEGORY_CONFIG = {
    "nicotine_cessation": {
        "display_name": "Nicotine Cessation",
        "amazon_browse_nodes": [
            3760901,  # Health & Personal Care (top node, confirmed in fee engine)
            "Smoking Cessation",
            "Nicotine Gum",
            "Nicotine Patches",
        ],
        "amazon_category_name": "Health & Personal Care",  # fee_engine price_switch
        "referral_fee_rate": 0.15,  # gum/patches typically sell above $10/unit
        "typical_pack_sizes": [10, 20, 30, 40, 60, 80, 100, 120, 160, 200, 240],
        "typical_wholesale_range": [25.0, 90.0],
        "typical_individual_range": [8.0, 25.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 4,
    },
    "otc_health": {
        "display_name": "OTC Health & Remedies",
        "amazon_browse_nodes": [
            3760901,  # Health & Personal Care (top node, confirmed in fee engine)
            "Health & Household",
            "Medications & Treatments",
            "Pain Relievers",
        ],
        "amazon_category_name": "Health & Personal Care",  # fee_engine price_switch
        "referral_fee_rate": 0.08,  # most single OTC units sell under $10 (low tier)
        "typical_pack_sizes": [10, 20, 24, 30, 50, 60, 72, 100, 120, 150, 200, 250, 300, 400, 500, 600, 750, 1000],
        "typical_wholesale_range": [10.0, 60.0],
        "typical_individual_range": [5.0, 20.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 1,
    },
    "vitamins_supplements": {
        "display_name": "Vitamins & Supplements",
        "amazon_browse_nodes": [
            3760901,  # Health & Personal Care (top node, confirmed in fee engine)
            3777871,  # Vitamins & Dietary Supplements
            "Vitamins & Dietary Supplements",
        ],
        "amazon_category_name": "Health & Personal Care",  # fee_engine price_switch
        "referral_fee_rate": 0.15,  # typical bottle sells above $10/unit
        "typical_pack_sizes": [30, 50, 60, 90, 100, 120, 150, 180, 200, 250, 300, 365, 400, 500, 750, 1000],
        "typical_wholesale_range": [12.0, 70.0],
        "typical_individual_range": [8.0, 35.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 2,
    },
    "household_cleaning": {
        "display_name": "Household Cleaning",
        "amazon_browse_nodes": [
            1055398,  # Home & Kitchen (top node, confirmed in fee engine)
            "Home & Kitchen",
            "Household Supplies",
            "Cleaning Supplies",
        ],
        "amazon_category_name": "Home & Kitchen",  # fee_engine flat 15%
        "referral_fee_rate": 0.15,
        "typical_pack_sizes": [2, 3, 4, 6, 8, 9, 10, 12, 16, 18, 20, 24, 32, 48],
        "typical_wholesale_range": [8.0, 45.0],
        "typical_individual_range": [4.0, 15.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 6,
    },
    "personal_care": {
        "display_name": "Personal Care",
        "amazon_browse_nodes": [
            3760901,  # Health & Personal Care (top node, confirmed in fee engine)
            11055981,  # Beauty (top node, confirmed in fee engine)
            "Health & Personal Care",
            "Beauty",
            "Skin Care",
        ],
        "amazon_category_name": "Health & Personal Care",  # fee_engine price_switch
        "referral_fee_rate": 0.15,  # typical unit sells above $10/unit
        "typical_pack_sizes": [2, 3, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 40, 48, 60],
        "typical_wholesale_range": [8.0, 40.0],
        "typical_individual_range": [4.0, 18.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 3,
    },
    "pet": {
        "display_name": "Pet Care",
        "amazon_browse_nodes": [
            2619533011,  # Pet Supplies (top node, confirmed in fee engine)
            "Pet Supplies",
            "Dog Toys",
            "Dog Grooming",
            "Dog Collars, Harnesses & Leashes",
            "Cat Toys",
        ],
        "amazon_category_name": "Pet Supplies",  # fee_engine flat 15%
        "referral_fee_rate": 0.15,
        "typical_pack_sizes": [4, 6, 8, 10, 12, 16, 18, 24, 30, 36, 40, 48, 60, 100, 120, 160],
        "typical_wholesale_range": [15.0, 80.0],
        "typical_individual_range": [8.0, 40.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 8,
    },
    "snacks_bars": {
        "display_name": "Snacks & Bars",
        "amazon_browse_nodes": [
            16310101,  # Grocery & Gourmet Food (top node, confirmed in fee engine)
            "Grocery & Gourmet Food",
            "Snack Foods",
            "Nutrition Bars",
        ],
        "amazon_category_name": "Grocery & Gourmet Food",  # fee_engine price_switch (<$15 -> 0.08)
        "referral_fee_rate": 0.08,  # single bars/boxes sell under $15 (low tier)
        "typical_pack_sizes": [3, 4, 5, 6, 8, 10, 12, 15, 16, 18, 20, 24, 30, 32, 36, 40, 48],
        "typical_wholesale_range": [10.0, 50.0],
        "typical_individual_range": [2.0, 8.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 5,
    },
    "baby_child": {
        "display_name": "Baby & Child",
        "amazon_browse_nodes": [
            165796011,  # Baby Products (top node, confirmed in fee engine)
            "Baby Products",
            "Diapering",
            "Baby Formula",
        ],
        "amazon_category_name": "Baby Products",  # fee_engine price_switch
        "referral_fee_rate": 0.15,  # typical unit sells above $10/unit
        "typical_pack_sizes": [10, 20, 24, 28, 30, 36, 40, 50, 56, 60, 72, 80, 96, 100, 120, 140, 150, 160, 180, 192, 200, 216, 240],
        "typical_wholesale_range": [15.0, 80.0],
        "typical_individual_range": [6.0, 25.0],
        "size_filter_max_weight_oz": 32.0,
        "size_filter_max_dimensions_in": [12, 8, 4],
        "min_monthly_sales": 1000,
        "min_rating": 4.0,
        "priority": 7,
    },
}


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------

def get_category_config(category_slug):
    """Return the full config dict for a category slug.

    Raises KeyError (with valid slugs) for unknown slugs.
    """
    try:
        return CATEGORY_CONFIG[category_slug]
    except KeyError:
        valid = ", ".join(sorted(CATEGORY_CONFIG))
        raise KeyError(
            f"Unknown category slug {category_slug!r}. Valid slugs: {valid}"
        ) from None


def get_all_categories():
    """Return every category slug -> config dict."""
    return CATEGORY_CONFIG


def get_brand_list(category_slug=None):
    """Return brand names for one category, or all brands when slug is None."""
    if category_slug is None:
        return list(BRAND_ALLOWLIST.keys())
    if category_slug not in CATEGORY_CONFIG:
        raise KeyError(
            f"Unknown category slug {category_slug!r}. Valid slugs: "
            + ", ".join(sorted(CATEGORY_CONFIG))
        )
    return [b for b, cat in BRAND_ALLOWLIST.items() if cat == category_slug]


def is_brand_allowed(brand_name):
    """True when the brand is a national allowlisted brand (case-insensitive).

    Rejects any name that is not in BRAND_ALLOWLIST OR that contains an
    exclusion keyword (store brand / private label / known club-store brand).
    """
    if not brand_name or not str(brand_name).strip():
        return False
    name = str(brand_name).strip()
    folded = name.lower()
    # Exclusions always win, even when the text is mixed into a title.
    for excluded in BRAND_EXCLUSION_LIST:
        if excluded.lower() in folded:
            return False
    return folded in {b.lower() for b in BRAND_ALLOWLIST}


def get_amazon_browse_nodes(category_slug):
    """Return the browse-node IDs/names configured for a category."""
    return get_category_config(category_slug)["amazon_browse_nodes"]


# --------------------------------------------------------------------------
# parse_pack_quantity — extract pack/unit counts from product titles
# --------------------------------------------------------------------------

# Units that count discrete sellable items ("primary" counts): the number of
# pills/bars/pieces/etc. in the product. These are preferred over container
# counts because the scanner splits bulk packs into INDIVIDUAL units.
_PRIMARY_COUNT_UNITS = {
    "count", "cnt", "ct",
    "softgels", "softgel", "soft gels", "soft gel",
    "pieces", "piece", "pcs", "pc",
    "tablets", "tablet", "caplets", "caplet",
    "capsules", "capsule", "gummies", "gummie",
    "bars", "bar", "sticks", "stick", "squares", "square",
    "tabs", "tab", "sheets", "sheet", "loads", "load",
    "wipes", "serving", "servings", "sachets", "sachet",
    "vials", "vial", "refills", "refill", "diapers", "diaper",
}

# Container units: the bulk-pack packaging count (e.g. "4 Pack").
_CONTAINER_UNITS = {
    "packs", "pack", "bottles", "bottle", "cans", "can",
    "rolls", "roll", "bags", "bag", "boxes", "box", "jars", "jar",
}

_COUNT_UNIT_WORDS = (
    r"count|cnt|ct|soft\s*gels?|softgels?|pieces?|pcs?|tablets?|caplets?|"
    r"capsules?|gummies?|bars?|sticks?|squares?|tabs?|sheets?|loads?|"
    r"wipes?|servings?|sachets?|vials?|refills?|diapers?|packs?|"
    r"bottles?|cans?|rolls?|bags?|boxes?|jars?"
)
_COUNT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[- ]?\s*(" + _COUNT_UNIT_WORDS + r")\b",
    re.IGNORECASE,
)

# "12 x 2 oz" / "24 x 10.2 oz" multi-pack notation.
_MULTIPACK_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[xX×]\s*\d+")

# Bare-number tokens for the last-resort fallback. Excludes numbers glued to
# letters ("D3", "B12"), dollar prices, and decimal components.
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9$.,])(\d+)(?![.,]?\d)")
_DOSE_UNIT_RE = re.compile(
    r"\s*[-]?\s*(?:iu|mcg|mg|g|grams?|ml|l|fl\.?\s*oz|oz|lb|lbs?|mm|cm|in|inches?|%)\b",
    re.IGNORECASE,
)


def parse_pack_quantity(product_title, category_slug=None):
    """Extract the unit pack count from a product title.

    Resolution order:
    1. number directly before a count unit ("200 Count", "250 Softgels",
       "60 capsules", "30 Tablets") — primary counts beat container counts,
       ties resolve leftmost;
    2. number before a container unit ("30 Pack", "4 bottles");
    3. "N x M" multi-pack notation ("24 x 2 oz" -> 24);
    4. bare number inside parentheses ("(500)");
    5. last-resort: any number > 1 that is not a dose/measure (not "5000 IU",
       "100 mg", "D3", "$12.99").

    ``category_slug`` is reserved for future category-specific heuristics and
    currently does not change the result.

    Returns an int, or None when no plausible quantity is found.
    """
    if not product_title or not str(product_title).strip():
        return None
    title = str(product_title).strip()

    # --- 1 & 2. number + count/container unit ----------------------------
    primary = []   # (position, quantity)
    container = []  # (position, quantity)
    for match in _COUNT_RE.finditer(title):
        number = int(round(float(match.group(1))))
        unit = match.group(2).strip().lower()
        if number < 2:
            continue
        if unit in _PRIMARY_COUNT_UNITS:
            primary.append((match.start(), number))
        elif unit in _CONTAINER_UNITS:
            container.append((match.start(), number))
    if primary:
        return primary[0][1]  # leftmost primary count wins
    if container:
        return container[0][1]

    # --- 3. "N x M" multi-pack -------------------------------------------
    match = _MULTIPACK_RE.search(title)
    if match:
        number = int(round(float(match.group(1))))
        if number > 1:
            return number

    # --- 4. bare number in parentheses ------------------------------------
    match = re.search(r"\((\d+)\)", title)
    if match:
        number = int(match.group(1))
        if number > 1:
            return number

    # --- 5. last-resort "any number > 1 that seems like a quantity" --------
    candidates = []
    for match in _TOKEN_RE.finditer(title):
        number = int(match.group(1))
        if number <= 1 or number > 10000:
            continue
        # Skip numbers immediately followed by a dose/measure unit.
        remainder = title[match.end():]
        if _DOSE_UNIT_RE.match(remainder):
            continue
        candidates.append((match.start(), number))
    if candidates:
        # Titles usually put the quantity last ("... - 200"); pick rightmost.
        return candidates[-1][1]

    return None


# --------------------------------------------------------------------------
# Seller-identity blocking (the "who sells it" gate).
# --------------------------------------------------------------------------


def seller_identity_blocked(
    seller_name: str | None,
    is_brand_seller: bool | None,
    is_amazon_seller: bool | None,
    product_brand: str | None = None,
) -> bool:
    """True when the listing's seller is a hard block for retail arbitrage.

    Hard blocks (profile rule):
      - is_brand_seller is True (the flag was observed), OR
      - is_amazon_seller is True ("Sold by Amazon.com"), OR
      - the seller text itself contains the product brand as a word
        (brand-owner heuristic used when the structured flag is missing).

    None / unknown flags are NOT a block here — whether the scorer treats an
    unknown identity as fail-closed is the caller's decision (it does: an
    unverifiable seller identity fails the hard filter).

    ``is_brand_seller``/``is_amazon_seller`` are observed facts when present;
    the textual checks are fallback heuristics that only fire when the
    corresponding flag is not already True.
    """
    if is_brand_seller:
        return True
    if is_amazon_seller:
        return True
    if not seller_name or not str(seller_name).strip():
        return False
    seller = str(seller_name).strip().lower()
    # "Sold by Amazon.com" detected from the seller text, flag or not.
    if "amazon.com" in seller:
        return True
    if product_brand and str(product_brand).strip():
        brand = str(product_brand).strip().lower()
        if re.search(r"(?<!\w)" + re.escape(brand) + r"(?!\w)", seller):
            # Word-boundary brand match inside the seller name is the
            # strongest un-flagged signal that the OWNER is the seller.
            return True
    return False