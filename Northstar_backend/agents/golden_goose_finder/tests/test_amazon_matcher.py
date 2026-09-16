"""Tests for amazon_matcher module."""

from __future__ import annotations

import pytest
from agents.golden_goose_finder.amazon_matcher import (
    AmazonMatch,
    build_search_query,
    find_individual_listing,
    get_mock_amazon_matches,
    is_individual_listing,
    rank_candidates,
)
from agents.golden_goose_finder.wholesale_scanner import WholesaleProduct


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wholesale(**overrides) -> WholesaleProduct:
    defaults = dict(
        source_store="Costco",
        product_title="Nicorette Nicotine Gum 2mg, 200 Count",
        brand="Nicorette",
        category_slug="nicotine-cessation",
        pack_count=200,
        wholesale_price=89.99,
    )
    defaults.update(overrides)
    return WholesaleProduct(**defaults)


def _make_amazon(**overrides) -> AmazonMatch:
    defaults = dict(
        asin="B0EXAMPLE01",
        title="Nicorette Nicotine Gum 2mg",
        brand="Nicorette",
        amazon_price=19.99,
    )
    defaults.update(overrides)
    return AmazonMatch(**defaults)


# =========================================================================
# build_search_query
# =========================================================================

class TestBuildSearchQuery:

    def test_strips_pack_count(self):
        wp = _make_wholesale(product_title="Nicorette Nicotine Gum 2mg, 200 Count")
        q = build_search_query(wp)
        assert "200" not in q
        assert "Count" not in q
        assert "Nicorette" in q

    def test_preserves_brand_and_type(self):
        wp = _make_wholesale(product_title="Advil Ibuprofen Pain Reliever 200mg, 500 Tablets")
        q = build_search_query(wp)
        assert "Advil" in q
        assert "Ibuprofen" in q

    def test_empty_title_uses_brand(self):
        wp = _make_wholesale(product_title="", brand="Zyrtec")
        q = build_search_query(wp)
        assert q == "Zyrtec"

    def test_strips_parenthetical_count(self):
        wp = _make_wholesale(product_title="Item For Sale (60 ct)")
        q = build_search_query(wp)
        assert "60" not in q
        assert "ct" not in q

    def test_strips_pack_of(self):
        wp = _make_wholesale(product_title="Colgate Toothpaste Pack of 6")
        q = build_search_query(wp)
        assert "Pack of 6" not in q
        assert "Colgate" in q

    def test_strips_rolls(self):
        wp = _make_wholesale(product_title="Charmin Ultra Soft 24 Rolls")
        q = build_search_query(wp)
        assert "24" not in q
        assert "Rolls" not in q


# =========================================================================
# is_individual_listing
# =========================================================================

class TestIsIndividualListing:

    def test_individual_passes(self):
        m = _make_amazon(title="Nicorette Nicotine Gum 2mg, 1 Count")
        assert is_individual_listing(m, 200) is True

    def test_multi_pack_filtered(self):
        m = _make_amazon(title="Nicorette Nicotine Gum 2mg, 200 Count")
        assert is_individual_listing(m, 200) is False

    def test_large_count_filtered(self):
        m = _make_amazon(title="Nicorette Gum 2mg, 160 Count")
        assert is_individual_listing(m, 200) is False

    def test_no_pack_indicators_passes(self):
        m = _make_amazon(title="Nicorette Nicotine Gum 2mg Lozenge")
        assert is_individual_listing(m, 200) is True

    def test_empty_title_passes(self):
        m = _make_amazon(title="")
        assert is_individual_listing(m, 200) is True

    def test_parenthetical_count_validated(self):
        # A 50-count listing with a 100-count wholesale pack is an
        # individual/smaller pack — passes the relative filter.
        m = _make_amazon(title="Product (50 ct)")
        assert is_individual_listing(m, 100) is True

    def test_parenthetical_count_near_wholesale_rejected(self):
        # A 60-count listing against a 100-count wholesale pack is NOT a
        # meaningfully smaller pack — reject.
        m = _make_amazon(title="Product (60 ct)")
        assert is_individual_listing(m, 100) is False

    def test_no_wholesale_count_falls_through(self):
        m = _make_amazon(title="Nicorette Gum 2mg, 200 Count")
        assert is_individual_listing(m, None) is False  # still filtered by multi-pack signal

    def test_small_count_passes(self):
        m = _make_amazon(title="Nicorette Gum 2mg, 10 Count")
        assert is_individual_listing(m, 200) is True


# =========================================================================
# rank_candidates
# =========================================================================

class TestRankCandidates:

    def test_brand_match_ranked_higher(self):
        wp = _make_wholesale()
        brand_match = _make_amazon(asin="B0BRAND001", brand="Nicorette", amazon_price=19.99)
        no_match = _make_amazon(asin="B0NOBRAND1", brand="Generic", amazon_price=19.99)
        ranked = rank_candidates([no_match, brand_match], wp)
        assert ranked[0].asin == "B0BRAND001"

    def test_prime_gets_bonus(self):
        wp = _make_wholesale()
        prime = _make_amazon(asin="B0PRIME001", brand="Nicorette", amazon_price=19.99, is_prime=True)
        non_prime = _make_amazon(asin="B0NOPRIME1", brand="Nicorette", amazon_price=19.99, is_prime=False)
        ranked = rank_candidates([non_prime, prime], wp)
        assert ranked[0].asin == "B0PRIME001"

    def test_low_bsr_ranked_higher(self):
        wp = _make_wholesale()
        good_bsr = _make_amazon(asin="B0BSRGOOD1", brand="Nicorette", amazon_price=19.99, bsr=500)
        bad_bsr = _make_amazon(asin="B0BSRBAD01", brand="Nicorette", amazon_price=19.99, bsr=50000)
        ranked = rank_candidates([bad_bsr, good_bsr], wp)
        assert ranked[0].asin == "B0BSRGOOD1"

    def test_empty_candidates(self):
        assert rank_candidates([], _make_wholesale()) == []

    def test_reasonable_price_ranks_higher(self):
        wp = _make_wholesale(wholesale_price=89.99, pack_count=200)
        # Expected unit = 0.45; 2.5x = 1.12 — good
        sweet_spot = _make_amazon(asin="B0SWEET001", brand="Nicorette", amazon_price=1.12, bsr=5000, is_prime=True)
        # Way too expensive
        overpriced = _make_amazon(asin="B0OVER0001", brand="Nicorette", amazon_price=50.00, bsr=5000, is_prime=True)
        ranked = rank_candidates([overpriced, sweet_spot], wp)
        assert ranked[0].asin == "B0SWEET001"


# =========================================================================
# Mock data
# =========================================================================

class TestMockData:

    def test_returns_matches(self):
        wp = _make_wholesale()
        matches = get_mock_amazon_matches(wp)
        assert len(matches) >= 4

    def test_all_valid(self):
        wp = _make_wholesale()
        for m in get_mock_amazon_matches(wp):
            assert isinstance(m, AmazonMatch)
            assert m.asin
            assert m.title
            assert m.amazon_price > 0
            assert len(m.asin) == 10

    def test_has_brand_match(self):
        wp = _make_wholesale()
        matches = get_mock_amazon_matches(wp)
        brands = {m.brand for m in matches}
        assert "Nicorette" in brands

    def test_includes_multipack_for_filter_test(self):
        """Mock data intentionally includes a multi-pack to test filtering."""
        wp = _make_wholesale(pack_count=200)
        matches = get_mock_amazon_matches(wp)
        has_mp = any("200 Count" in m.title for m in matches)
        assert has_mp, "Mock should include a multi-pack listing for filtering tests"


# =========================================================================
# find_individual_listing (async)
# =========================================================================

class TestFindIndividualListing:

    def test_returns_filtered_and_ranked(self):
        import asyncio
        wp = _make_wholesale()
        results = asyncio.run(find_individual_listing(wp, max_candidates=5))
        assert len(results) > 0
        assert len(results) <= 5
        # All results should be individual listings (no wholesale-size multi-pack)
        for m in results:
            assert "200 Count" not in m.title

    def test_max_candidates_respected(self):
        import asyncio
        wp = _make_wholesale()
        results = asyncio.run(find_individual_listing(wp, max_candidates=2))
        assert len(results) <= 2

    def test_brand_match_present(self):
        import asyncio
        wp = _make_wholesale()
        results = asyncio.run(find_individual_listing(wp))
        brands = {m.brand for m in results}
        assert "Nicorette" in brands

    def test_different_wholesale_product(self):
        import asyncio
        wp = _make_wholesale(
            product_title="Advil Ibuprofen 200mg, 500 Tablets",
            brand="Advil",
            pack_count=500,
            wholesale_price=29.99,
        )
        results = asyncio.run(find_individual_listing(wp))
        assert len(results) > 0
        for m in results:
            assert "500" not in m.title  # filtered out


# =========================================================================
# AmazonMatch dataclass
# =========================================================================

class TestAmazonMatch:

    def test_defaults(self):
        m = AmazonMatch(asin="B0TEST0001", title="Test", brand="Brand", amazon_price=9.99)
        assert m.amazon_category is None
        assert m.bsr is None
        assert m.review_rating is None
        assert m.is_prime is False
        assert m.monthly_sales_estimate is None

    def test_full_init(self):
        m = AmazonMatch(
            asin="B0FULL0001",
            title="Full Product",
            brand="Brand",
            amazon_price=29.99,
            amazon_category="Health",
            bsr=1234,
            review_rating=4.5,
            review_count=1500,
            fba_sellers=2,
            is_prime=True,
            monthly_sales_estimate=500,
        )
        assert m.bsr == 1234
        assert m.is_prime is True
        assert m.monthly_sales_estimate == 500
