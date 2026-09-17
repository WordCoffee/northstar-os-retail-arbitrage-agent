"""Tests for the Golden Goose Finder category/brand registry."""

import pytest

from agents.golden_goose_finder.category_config import (
    BRAND_ALLOWLIST,
    BRAND_EXCLUSION_LIST,
    CATEGORY_CONFIG,
    DEFAULT_ROI_FLOOR_PER_UNIT,
    DEFAULT_SIZE_FILTER,
    get_all_categories,
    get_amazon_browse_nodes,
    get_brand_list,
    get_category_config,
    is_brand_allowed,
    parse_pack_quantity,
)

EXPECTED_CATEGORY_SLUGS = {
    "nicotine_cessation",
    "otc_health",
    "vitamins_supplements",
    "household_cleaning",
    "personal_care",
    "pet",
    "snacks_bars",
    "baby_child",
}

REQUIRED_CONFIG_KEYS = {
    "display_name",
    "amazon_browse_nodes",
    "amazon_category_name",
    "referral_fee_rate",
    "typical_pack_sizes",
    "typical_wholesale_range",
    "typical_individual_range",
    "size_filter_max_weight_oz",
    "size_filter_max_dimensions_in",
    "min_monthly_sales",
    "min_rating",
    "priority",
}

EXPECTED_FEE_ENGINE_CATEGORIES = {
    "nicotine_cessation": "Health & Personal Care",
    "otc_health": "Health & Personal Care",
    "vitamins_supplements": "Health & Personal Care",
    "household_cleaning": "Home & Kitchen",
    "personal_care": "Health & Personal Care",
    "pet": "Pet Supplies",
    "snacks_bars": "Grocery & Gourmet Food",
    "baby_child": "Baby Products",
}


# --------------------------------------------------------------------------
# Category registry completeness
# --------------------------------------------------------------------------

def test_all_category_slugs_exist():
    assert set(CATEGORY_CONFIG) == EXPECTED_CATEGORY_SLUGS


def test_all_brand_categories_resolve():
    for brand, slug in BRAND_ALLOWLIST.items():
        assert slug in CATEGORY_CONFIG, f"{brand} maps to unknown slug {slug!r}"


def test_every_category_has_brands():
    for slug in CATEGORY_CONFIG:
        assert slug in BRAND_ALLOWLIST.values(), f"category {slug} has no brands"


def test_category_config_completeness():
    for slug, cfg in CATEGORY_CONFIG.items():
        assert set(cfg) == REQUIRED_CONFIG_KEYS, f"{slug} missing/extra keys"
        assert isinstance(cfg["display_name"], str) and cfg["display_name"]
        assert isinstance(cfg["amazon_browse_nodes"], list) and cfg["amazon_browse_nodes"]
        assert isinstance(cfg["amazon_category_name"], str) and cfg["amazon_category_name"]
        assert isinstance(cfg["referral_fee_rate"], float)
        assert isinstance(cfg["typical_pack_sizes"], list) and cfg["typical_pack_sizes"]
        assert all(isinstance(n, int) and n > 1 for n in cfg["typical_pack_sizes"])
        minimum, maximum = cfg["typical_wholesale_range"]
        assert isinstance(minimum, float) and isinstance(maximum, float)
        assert 0 < minimum <= maximum
        minimum_i, maximum_i = cfg["typical_individual_range"]
        assert isinstance(minimum_i, float) and isinstance(maximum_i, float)
        assert 0 < minimum_i <= maximum_i
        assert isinstance(cfg["size_filter_max_weight_oz"], float)
        assert cfg["size_filter_max_dimensions_in"] == [12, 8, 4]
        assert isinstance(cfg["min_monthly_sales"], int) and cfg["min_monthly_sales"] > 0
        assert isinstance(cfg["min_rating"], float) and 0 < cfg["min_rating"] <= 5
        assert isinstance(cfg["priority"], int) and cfg["priority"] >= 1


def test_size_filter_defaults():
    assert DEFAULT_SIZE_FILTER == {
        "max_weight_oz": 32.0,
        "abs_max_weight_oz": 80.0,
        "max_dimensions_in": [12, 8, 4],
        "description": "Small, light items (<= 2 lbs preferred; 5 lbs hard ceiling) so the item lands in the cheap small-standard FBA band.",
    }


def test_roi_floor_default():
    assert DEFAULT_ROI_FLOOR_PER_UNIT == 10.00


def test_priorities_unique_and_dense():
    priorities = sorted(cfg["priority"] for cfg in CATEGORY_CONFIG.values())
    assert priorities == list(range(1, len(CATEGORY_CONFIG) + 1))


def test_referral_fee_rates_valid():
    for slug, cfg in CATEGORY_CONFIG.items():
        assert cfg["referral_fee_rate"] in (0.08, 0.15), slug


def test_amazon_category_names_match_fee_engine():
    for slug, cfg in CATEGORY_CONFIG.items():
        assert cfg["amazon_category_name"] == EXPECTED_FEE_ENGINE_CATEGORIES[slug]


def test_health_categories_use_health_and_personal_care():
    for slug in ("nicotine_cessation", "otc_health", "vitamins_supplements", "personal_care"):
        assert CATEGORY_CONFIG[slug]["amazon_category_name"] == "Health & Personal Care"


# --------------------------------------------------------------------------
# Brand allowlist
# --------------------------------------------------------------------------

def test_brand_allowlist_spot_checks():
    expected_samples = {
        "nicotine_cessation": ["Nicorette", "NicoDerm CQ", "Zonnic", "Habitrol"],
        "otc_health": ["Advil", "Motrin", "Tylenol", "Zyrtec", "Mucinex", "Pepto-Bismol"],
        "vitamins_supplements": ["Nature Made", "Centrum", "Olly", "Airborne"],
        "household_cleaning": ["Tide", "Cascade", "Lysol", "Clorox", "Swiffer"],
        "personal_care": ["Dove", "Old Spice", "Colgate", "CeraVe", "Aquaphor"],
        "pet": ["KONG", "Chuckit", "Furminator", "Hartz", "Greenies"],
        "snacks_bars": ["RXBAR", "KIND", "Nature Valley", "Clif Bar", "Pirate's Booty"],
        "baby_child": ["Huggies", "Pampers", "Enfamil", "PediaSure"],
    }
    for slug, brands in expected_samples.items():
        for brand in brands:
            assert BRAND_ALLOWLIST[brand] == slug, brand


def test_brand_allowlist_has_no_store_brands():
    for brand in BRAND_ALLOWLIST:
        folded = brand.lower()
        for excluded in BRAND_EXCLUSION_LIST:
            assert excluded.lower() not in folded, f"{brand!r} looks like {excluded!r}"


def test_known_store_brands_absent_from_allowlist():
    for store_brand in ("Kirkland Signature", "Member's Mark", "Great Value", "Equate"):
        assert store_brand not in BRAND_ALLOWLIST


def test_equate_not_allowlisted_even_case_insensitive():
    assert is_brand_allowed("Equate") is False
    assert is_brand_allowed("equate") is False


# --------------------------------------------------------------------------
# Exclusion list
# --------------------------------------------------------------------------

def test_exclusion_list_contents():
    for required in ("Kirkland Signature", "Member's Mark", "Great Value", "store brand", "private label"):
        assert required in BRAND_EXCLUSION_LIST


def test_exclusion_list_catches_kirkland_and_members_mark():
    for brand in ("Kirkland Signature", "Kirkland", "Member's Mark", "members mark"):
        assert is_brand_allowed(brand) is False


# --------------------------------------------------------------------------
# is_brand_allowed
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "brand,expected",
    [
        ("Advil", True),
        ("advil", True),
        ("ADVIL", True),
        ("Tide", True),
        ("Dove", True),
        ("Nature Made", True),
        ("KONG", True),
        ("Furminator", True),
        ("RXBAR", True),
        ("Kirkland Signature", False),
        ("Kirkland", False),
        ("Member's Mark", False),
        ("Great Value", False),
        ("Equate", False),
        ("store brand", False),
        ("Private Label", False),
        ("Sam's Choice", False),
        ("UnknownBrandXYZ", False),
        ("", False),
        (None, False),
    ],
)
def test_is_brand_allowed(brand, expected):
    assert is_brand_allowed(brand) is expected


def test_is_brand_allowed_rejects_title_with_exclusion_keyword():
    assert is_brand_allowed("Kirkland Signature Vitamins") is False
    assert is_brand_allowed("Member's Mark Paper Towels") is False


# --------------------------------------------------------------------------
# getters
# --------------------------------------------------------------------------

def test_get_brand_list_all_and_per_category():
    assert set(get_brand_list()) == set(BRAND_ALLOWLIST)
    for slug in CATEGORY_CONFIG:
        assert set(get_brand_list(slug)) == {
            b for b, cat in BRAND_ALLOWLIST.items() if cat == slug
        }


def test_get_brand_list_unknown_slug_raises():
    with pytest.raises(KeyError):
        get_brand_list("does_not_exist")


def test_get_category_config_returns_complete_data():
    cfg = get_category_config("otc_health")
    assert cfg == CATEGORY_CONFIG["otc_health"]
    assert cfg["display_name"] == "OTC Health & Remedies"
    assert cfg["referral_fee_rate"] in (0.08, 0.15)
    assert cfg["size_filter_max_weight_oz"] == 32.0
    assert cfg["min_monthly_sales"] == 1000
    assert cfg["min_rating"] == 4.0
    assert cfg["priority"] == 1  # OTC health is a top-priority category


def test_get_category_config_unknown_slug_raises():
    with pytest.raises(KeyError):
        get_category_config("nope")


def test_get_all_categories_matches_registry():
    assert get_all_categories() == CATEGORY_CONFIG


def test_get_amazon_browse_nodes():
    for slug in CATEGORY_CONFIG:
        nodes = get_amazon_browse_nodes(slug)
        assert isinstance(nodes, list) and nodes
        assert nodes == CATEGORY_CONFIG[slug]["amazon_browse_nodes"]


def test_get_amazon_browse_nodes_unknown_slug_raises():
    with pytest.raises(KeyError):
        get_amazon_browse_nodes("nope")


# --------------------------------------------------------------------------
# parse_pack_quantity
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "title,expected",
    [
        ("200 Count", 200),
        ("30 Pack", 30),
        ("12-Count", 12),
        ("1.6 oz (60 ct)", 60),
        ("24 Pack of 2 oz tubes", 24),
        ("Nature Made Vitamin D3 5000 IU (250 Softgels)", 250),
        ("Advil 200 Count Liquid Gels", 200),
        ("Nicorette Gum 100 Count, 2 Pack", 100),
        ("Zyrtec 24 Hour Allergy - 30 Tablets", 30),
        ("KIND Bars, 12 Count (Pack of 12)", 12),
        ("Tide PODS 81 Count (4 Pack)", 81),
        ("Centrum Adults 250 Count (2 Pack)", 250),
        ("Claritin 300 Count, 2 Pack", 300),
        ("Dove Beauty Bar 4 Count", 4),
        ("Emergen-C 1000mg Vitamin C 30 Count", 30),
        ("60 capsules", 60),
        ("3 Bars", 3),
        ("Pack of 6", 6),
        ("12 x 2 oz bottles", 12),
        ("24 x 10.2 oz cans", 24),
        ("Rubber Gloves - 200", 200),
        ("500 Soft Gels", 500),
    ],
)
def test_parse_pack_quantity_known_formats(title, expected):
    assert parse_pack_quantity(title) == expected


@pytest.mark.parametrize(
    "title",
    [
        ("No quantity listed here"),
        ("Vitamin B12 5000 mcg",),
        ("Vitamin D3 5000 IU",),
        ("Ultra Moisture 12 fl oz (355 mL) Lotion",),
        ("Pure Cane Sugar 4 lb Bag",),
        ("",),
        (None,),
    ],
)
def test_parse_pack_quantity_no_quantity(title):
    assert parse_pack_quantity(title) is None


def test_parse_pack_quantity_accepts_category_slug():
    assert parse_pack_quantity("Zyrtec 30 Tablets", category_slug="otc_health") == 30
    assert parse_pack_quantity("Whatever 200 Count", category_slug="nope") == 200


def test_parse_pack_quantity_never_returns_one():
    assert parse_pack_quantity("1 Count") is None
    assert parse_pack_quantity("Pack of 1") is None


def test_parse_pack_quantity_prefers_primary_count_over_container():
    # "250 Count (2 Pack)": total units (250) beat the container count (2).
    assert parse_pack_quantity("Centrum 250 Count (2 Pack)") == 250