"""Tests for amazon_adapters ASIN validation (FIXES_50 #12).

Covers the two external boundaries where ASINs enter the provider layer:
  1. parse_chocodata_results — provider RESULTS entering matching must be
     dropped when they carry an invalid / mock-pattern ASIN.
  2. The three seller caller factories — ASINs bound FOR a provider call
     must be rejected (ValueError) before any request can be constructed.
"""

from __future__ import annotations

import pytest

from agents.golden_goose_finder.amazon_adapters import (
    make_bright_data_offers_caller,
    make_easy_parser_seller_caller,
    make_generic_seller_caller,
    parse_chocodata_results,
)

# ^B0[a-f0-9]{8}$ — the mock-pattern shape (case-insensitive).
MOCK_PATTERN_ASIN = "b0a1b2c3d4"
# Well-formed, non-mock ASIN (10 chars, letters outside a-f → not the mock shape).
REAL_SHAPE_ASIN = "B0TEST0001"


def _raw_product(asin: str) -> dict:
    return {
        "asin": asin,
        "title": "Nicorette Nicotine Gum 2mg",
        "brand": "Nicorette",
        "price": 19.99,
    }


# =========================================================================
# parse_chocodata_results — provider-result boundary
# =========================================================================

class TestParseChocodataResultsAsinGate:

    def test_mock_pattern_asins_dropped(self):
        assert parse_chocodata_results([_raw_product(MOCK_PATTERN_ASIN)]) == []

    def test_malformed_asins_dropped(self):
        raw = [
            _raw_product("SHORT"),          # too short
            _raw_product("B0ABCDEF012"),    # too long
            _raw_product("B0ABCD-EF1"),     # non-alphanumeric
            _raw_product(""),               # empty
        ]
        assert parse_chocodata_results(raw) == []

    def test_missing_asin_dropped(self):
        raw = [{"title": "No ASIN here", "price": 1.0}]
        assert parse_chocodata_results(raw) == []

    def test_real_shaped_asins_kept(self):
        raw = [_raw_product(REAL_SHAPE_ASIN), _raw_product("B08R68VXFR")]
        out = parse_chocodata_results(raw)
        assert [c["asin"] for c in out] == [REAL_SHAPE_ASIN, "B08R68VXFR"]

    def test_mixed_batch_keeps_only_valid(self):
        raw = [_raw_product(MOCK_PATTERN_ASIN), _raw_product(REAL_SHAPE_ASIN)]
        out = parse_chocodata_results(raw)
        assert [c["asin"] for c in out] == [REAL_SHAPE_ASIN]


# =========================================================================
# Seller caller factories — provider-boundary
# =========================================================================

_CALLER_FACTORIES = [
    make_easy_parser_seller_caller,
    make_bright_data_offers_caller,
    make_generic_seller_caller,
]


class TestSellerCallerFactoriesAsinGate:

    @pytest.mark.parametrize("factory", _CALLER_FACTORIES)
    def test_rejects_mock_pattern(self, factory):
        with pytest.raises(ValueError, match="mock-pattern"):
            factory(MOCK_PATTERN_ASIN)

    @pytest.mark.parametrize("factory", _CALLER_FACTORIES)
    def test_rejects_malformed(self, factory):
        with pytest.raises(ValueError, match="Invalid or mock-pattern"):
            factory("B0-short")

    @pytest.mark.parametrize("factory", _CALLER_FACTORIES)
    def test_rejects_empty(self, factory):
        with pytest.raises(ValueError):
            factory("")

    @pytest.mark.parametrize("factory", _CALLER_FACTORIES)
    def test_accepts_real_shaped(self, factory):
        caller = factory(REAL_SHAPE_ASIN)
        assert callable(caller)