"""Tests for wholesale_scanner module."""

from __future__ import annotations

import pytest
from agents.golden_goose_finder.wholesale_scanner import (
    WholesaleProduct,
    extract_brand_from_title,
    extract_pack_count,
    get_mock_wholesale_data,
    parse_wholesale_product,
)


# =========================================================================
# extract_pack_count
# =========================================================================

class TestExtractPackCount:
    """15+ title formats for pack-count extraction."""

    def test_200_count(self):
        assert extract_pack_count("Nicorette Gum 200 Count") == 200

    def test_30_pack(self):
        assert extract_pack_count("Cascade Pods 30 Pack") == 30

    def test_dash_count(self):
        assert extract_pack_count("Zyrtec 12-Count Tablets") == 12

    def test_parenthetical_ct(self):
        assert extract_pack_count("Advil 1.6 oz (60 ct)") == 60

    def test_pack_of_N(self):
        assert extract_pack_count("Colgate Toothpaste Pack of 6") == 6

    def test_rolls(self):
        assert extract_pack_count("Charmin Ultra Soft 24 Rolls") == 24

    def test_sheets(self):
        assert extract_pack_count("Swiffer Refills 52 Sheets") == 52

    def test_bottles(self):
        assert extract_pack_count("Tide Pods 42 Bottles") == 42

    def test_each(self):
        assert extract_pack_count("Dove Bars 8 Each") == 8

    def test_count_with_dash_prefix(self):
        assert extract_pack_count("Emergen-C 100-count") == 100

    def test_large_count(self):
        assert extract_pack_count("Nature Made Vitamin D 1000 Count") == 1000

    def test_single_count(self):
        assert extract_pack_count("Something 1 Count") == 1

    def test_no_pack_count(self):
        assert extract_pack_count("Some Random Product Name") is None

    def test_empty_title(self):
        assert extract_pack_count("") is None

    def test_none_title(self):
        assert extract_pack_count(None) is None

    def test_2x_pattern(self):
        assert extract_pack_count("2x 100 count gum") == 100  # inner count wins

    def test_parenthetical_count(self):
        assert extract_pack_count("Claritin 365 Count (1 Year Supply)") == 365

    def test_pouches(self):
        assert extract_pack_count("Treats 24 Pouches") == 24


# =========================================================================
# extract_brand_from_title
# =========================================================================

class TestExtractBrand:
    """Brand extraction from various title formats."""

    def test_prefix_brand(self):
        assert extract_brand_from_title("Nicorette Nicotine Gum 200 Count") == "Nicorette"

    def test_brand_in_middle(self):
        assert extract_brand_from_title("Extra Strength Advil 500 Tablets") == "Advil"

    def test_brand_not_found(self):
        assert extract_brand_from_title("Generic Store Brand Wipes") is None

    def test_empty_title(self):
        assert extract_brand_from_title("") is None

    def test_none_title(self):
        assert extract_brand_from_title(None) is None

    def test_exact_prefix_match_preferred(self):
        result = extract_brand_from_title("Nature Made Vitamin D 500ct")
        assert result == "Nature Made"

    def test_brand_with_special_chars(self):
        assert extract_brand_from_title("CeraVe Moisturizing Cream 19 oz") == "CeraVe"

    def test_brand_case_insensitive(self):
        assert extract_brand_from_title("ADVIL IBUPROFEN 200mg") == "Advil"

    def test_long_brand_name(self):
        assert extract_brand_from_title("Nature's Bounty Vitamin B12 200ct") == "Nature's Bounty"

    def test_kong_brand(self):
        assert extract_brand_from_title("KONG Classic Dog Toy, Medium (2 Pack)") == "KONG"

    def test_furminator_brand(self):
        assert extract_brand_from_title("Furminator deShedding Tool for Dogs, Large") == "Furminator"

    def test_petsafe_brand(self):
        assert extract_brand_from_title("PetSafe Easy Walk Dog Harness, Large") == "PetSafe"

    def test_dove_brand(self):
        assert extract_brand_from_title("Dove Beauty Bar 14 Count") == "Dove"

    def test_olly_brand(self):
        assert extract_brand_from_title("Olly Restful Sleep Gummies 140ct") == "Olly"

    def test_no_brand_word_at_all(self):
        assert extract_brand_from_title("Vitamins Dietary Supplement Tablets") is None


# =========================================================================
# parse_wholesale_product
# =========================================================================

class TestParseWholesaleProduct:

    def test_basic_parse(self):
        raw = {
            "product_title": "Nicorette Gum 200 Count",
            "brand": "Nicorette",
            "wholesale_price": 89.99,
            "item_number": "12345",
            "item_url": "https://costco.com/gum.html",
        }
        result = parse_wholesale_product(raw, "Costco", "nicotine-cessation")
        assert result is not None
        assert result.source_store == "Costco"
        assert result.product_title == "Nicorette Gum 200 Count"
        assert result.brand == "Nicorette"
        assert result.pack_count == 200
        assert result.wholesale_price == 89.99
        assert result.item_number == "12345"
        assert result.in_stock is True

    def test_missing_title_returns_none(self):
        raw = {"wholesale_price": 10.0}
        assert parse_wholesale_product(raw, "Costco", "test") is None

    def test_missing_price_returns_none(self):
        raw = {"product_title": "Something"}
        assert parse_wholesale_product(raw, "Costco", "test") is None

    def test_zero_price_returns_none(self):
        raw = {"product_title": "Something", "wholesale_price": 0}
        assert parse_wholesale_product(raw, "Costco", "test") is None

    def test_negative_price_returns_none(self):
        raw = {"product_title": "Something", "wholesale_price": -5}
        assert parse_wholesale_product(raw, "Costco", "test") is None

    def test_brand_inferred_from_title(self):
        raw = {
            "product_title": "Advil Pain Reliever 500 Tablets",
            "wholesale_price": 29.99,
        }
        result = parse_wholesale_product(raw, "Costco", "otc-health")
        assert result is not None
        assert result.brand == "Advil"

    def test_price_from_current_price_key(self):
        raw = {
            "product_title": "Test Product",
            "current_price": 19.99,
        }
        result = parse_wholesale_product(raw, "Sam's Club", "test")
        assert result is not None
        assert result.wholesale_price == 19.99

    def test_in_stock_string_false(self):
        raw = {
            "product_title": "Test Product",
            "wholesale_price": 10.0,
            "in_stock": "out_of_stock",
        }
        result = parse_wholesale_product(raw, "Costco", "test")
        assert result is not None
        assert result.in_stock is False

    def test_weight_parsed(self):
        raw = {
            "product_title": "Heavy Item",
            "wholesale_price": 50.0,
            "weight_lbs": "12.5",
        }
        result = parse_wholesale_product(raw, "Costco", "test")
        assert result is not None
        assert result.weight_lbs == 12.5


# =========================================================================
# Scanner live-call gate (§3)
# =========================================================================

class TestLiveCallGate:
    """Without explicit operator approval, scans MUST return mock data only
    and MUST NOT hit the live OpenWebNinja/Costco path (per §3)."""

    def test_scan_costco_default_returns_mock(self):
        import asyncio
        from agents.golden_goose_finder.wholesale_scanner import (
            _MOCK_PRODUCTS,
            scan_costco_categories,
        )
        results = asyncio.run(scan_costco_categories())
        assert len(results) == len(_MOCK_PRODUCTS)
        # Every row must be one of the known mock products
        mock_keys = {(p.brand, p.product_title) for p in _MOCK_PRODUCTS}
        for p in results:
            assert (p.brand, p.product_title) in mock_keys, \
                f"{p.product_title!r} leaked from a live path"

    def test_scan_costco_live_flag_without_approval_stays_mock(self):
        import asyncio
        from agents.golden_goose_finder.wholesale_scanner import (
            _MOCK_PRODUCTS,
            scan_costco_categories,
        )
        results = asyncio.run(scan_costco_categories(live=True))
        assert len(results) == len(_MOCK_PRODUCTS)
        mock_keys = {(p.brand, p.product_title) for p in _MOCK_PRODUCTS}
        for p in results:
            assert (p.brand, p.product_title) in mock_keys

    def test_scan_sams_returns_mock(self):
        import asyncio
        from agents.golden_goose_finder.wholesale_scanner import scan_sams_club
        results = asyncio.run(scan_sams_club())
        assert results
        assert all(p.source_store == "Sam's Club" for p in results)


# =========================================================================
# Mock data
# =========================================================================

class TestMockData:

    def test_returns_list(self):
        data = get_mock_wholesale_data()
        assert isinstance(data, list)
        assert len(data) >= 30

    def test_all_valid_products(self):
        data = get_mock_wholesale_data()
        for p in data:
            assert isinstance(p, WholesaleProduct)
            assert p.source_store in ("Costco", "Sam's Club")
            assert p.product_title
            assert p.brand
            assert p.category_slug
            assert p.wholesale_price > 0

    def test_category_filter(self):
        data = get_mock_wholesale_data("nicotine-cessation")
        assert len(data) == 5
        assert all(p.category_slug == "nicotine-cessation" for p in data)

    def test_otc_health_category(self):
        data = get_mock_wholesale_data("otc-health")
        assert len(data) == 5

    def test_vitamins_category(self):
        data = get_mock_wholesale_data("vitamins")
        assert len(data) == 5

    def test_household_category(self):
        data = get_mock_wholesale_data("household")
        assert len(data) == 5

    def test_personal_care_category(self):
        data = get_mock_wholesale_data("personal-care")
        assert len(data) == 5

    def test_pet_category(self):
        data = get_mock_wholesale_data("pet")
        assert len(data) == 5

    def test_all_have_pack_counts(self):
        data = get_mock_wholesale_data()
        for p in data:
            assert p.pack_count is not None, f"{p.product_title} missing pack_count"

    def test_nonexistent_category(self):
        data = get_mock_wholesale_data("nonexistent")
        assert data == []


# =========================================================================
# WholesaleProduct dataclass
# =========================================================================

class TestWholesaleProduct:

    def test_defaults(self):
        p = WholesaleProduct(
            source_store="Costco",
            product_title="Test",
            brand="Brand",
            category_slug="cat",
            pack_count=10,
            wholesale_price=9.99,
        )
        assert p.item_url is None
        assert p.item_number is None
        assert p.weight_lbs is None
        assert p.dimensions_in is None
        assert p.image_url is None
        assert p.in_stock is True

    def test_full_init(self):
        p = WholesaleProduct(
            source_store="Costco",
            product_title="Full",
            brand="Brand",
            category_slug="cat",
            pack_count=5,
            wholesale_price=19.99,
            item_url="https://example.com",
            item_number="12345",
            weight_lbs=2.5,
            dimensions_in=[10.0, 5.0, 3.0],
            image_url="https://img.example.com",
            in_stock=False,
        )
        assert p.item_url == "https://example.com"
        assert p.in_stock is False
        assert p.weight_lbs == 2.5
