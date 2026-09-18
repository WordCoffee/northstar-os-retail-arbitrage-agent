"""Tests for the universal product filter (Golden Goose rules, any category)."""

import pytest

from filters.universal_filter import (
    DEFAULT_ABS_MAX_WEIGHT_OZ,
    DEFAULT_MAX_FBA_SELLERS,
    DEFAULT_MIN_MONTHLY_SALES,
    DEFAULT_MIN_ROI_PER_UNIT,
    DEFAULT_PREFERRED_MAX_WEIGHT_OZ,
    UniversalProductFilter,
    apply_universal_filter,
    default_filter,
)


def good_product(**overrides):
    """A product that passes every gate; override individual fields."""
    p = {
        "name": "Some National Brand 200 ct",
        "brand": "Advil",
        "net_profit_per_unit": 12.50,
        "monthly_sales_estimate": 2500,
        "weight_lbs": 1.0,
        "fba_sellers": 1,
    }
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_defaults_match_golden_goose_thresholds():
    assert DEFAULT_MIN_ROI_PER_UNIT == 10.00
    assert DEFAULT_MIN_MONTHLY_SALES == 1000
    assert DEFAULT_PREFERRED_MAX_WEIGHT_OZ == 32.0
    assert DEFAULT_ABS_MAX_WEIGHT_OZ == 80.0
    assert DEFAULT_MAX_FBA_SELLERS == 2
    f = default_filter()
    assert f.min_roi_per_unit == 10.00
    assert f.min_monthly_sales == 1000
    assert f.max_fba_sellers == 2


# ---------------------------------------------------------------------------
# Pass / fail
# ---------------------------------------------------------------------------

def test_good_product_passes_all_gates():
    result = default_filter().apply(good_product())
    assert result.passed is True
    assert result.reasons == []
    assert set(result.passed_gates) == {"ROI", "Demand", "Weight", "Competition"}


def test_low_profit_rejected():
    result = default_filter().apply(good_product(net_profit_per_unit=4.99))
    assert result.passed is False
    assert any("below $10.00 floor" in r for r in result.reasons)


def test_low_sales_rejected():
    result = default_filter().apply(good_product(monthly_sales_estimate=999))
    assert result.passed is False
    assert any("demand floor" in r for r in result.reasons)


def test_overweight_rejected_at_hard_ceiling():
    result = default_filter().apply(good_product(weight_lbs=6.0))  # 96 oz
    assert result.passed is False
    assert any("hard ceiling" in r for r in result.reasons)


def test_above_preferred_weight_rejected():
    result = default_filter().apply(good_product(weight_lbs=3.0))  # 48 oz
    assert result.passed is False
    assert any("preferred" in r for r in result.reasons)


def test_too_many_fba_sellers_rejected():
    result = default_filter().apply(good_product(fba_sellers=3))
    assert result.passed is False
    assert any("exceed 2 seller limit" in r for r in result.reasons)


def test_zero_fba_sellers_is_gold_and_passes():
    result = default_filter().apply(good_product(fba_sellers=0))
    assert result.passed is True


def test_two_fba_sellers_passes():
    result = default_filter().apply(good_product(fba_sellers=2))
    assert result.passed is True


def test_missing_fields_fail_closed():
    result = default_filter().apply({"name": "Mystery", "brand": "Acme"})
    assert result.passed is False
    # ROI, Demand, Weight, Competition all unknown -> 4 reasons.
    assert len(result.reasons) == 4


def test_multiple_failures_reported_together():
    result = default_filter().apply(
        good_product(net_profit_per_unit=1.0, monthly_sales_estimate=10, fba_sellers=9)
    )
    assert result.passed is False
    assert len(result.reasons) >= 3


# ---------------------------------------------------------------------------
# Weight units
# ---------------------------------------------------------------------------

def test_weight_oz_key_takes_precedence():
    # 16 oz passing as oz even without lbs.
    result = default_filter().apply(good_product(weight_lbs=None, weight_oz=16))
    assert result.passed is True


def test_weight_conversion_2lbs_is_at_preferred_ceiling():
    result = default_filter().apply(good_product(weight_lbs=2.0))
    assert result.passed is True
    result = default_filter().apply(good_product(weight_lbs=2.01))
    assert result.passed is False


# ---------------------------------------------------------------------------
# Brand exclusions / blacklist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("brand", ["Kirkland Signature", "Member's Mark", "Great Value", "Equate"])
def test_store_brands_excluded(brand):
    result = default_filter().apply(good_product(brand=brand))
    assert result.passed is False
    assert any("store/private label" in r for r in result.reasons)


def test_store_brand_token_in_title_excluded():
    result = default_filter().apply(
        good_product(name="Kirkland Signature Organic Coffee 2 lb", brand="Generic")
    )
    assert result.passed is False


def test_dynamic_blacklist_blocks_brand():
    f = UniversalProductFilter(brand_blacklist=["Acme Corp"])
    result = f.apply(good_product(brand="Acme Corp"))
    assert result.passed is False
    assert any("blacklisted" in r for r in result.reasons)


def test_dynamic_blacklist_is_case_insensitive_substring():
    f = UniversalProductFilter(brand_blacklist=["acme"])
    result = f.apply(good_product(name="Acme Corp Pain Relief"))
    assert result.passed is False


def test_blacklist_does_not_block_unrelated_brand():
    f = UniversalProductFilter(brand_blacklist=["Acme"])
    result = f.apply(good_product(brand="Advil"))
    assert result.passed is True


def test_brand_gate_short_circuits_before_other_gates():
    # Even a great product is rejected on brand alone, with one reason.
    result = default_filter().apply(good_product(brand="Kirkland Signature"))
    assert len(result.reasons) == 1


# ---------------------------------------------------------------------------
# Overrides / disabled gates
# ---------------------------------------------------------------------------

def test_override_roi_floor():
    f = UniversalProductFilter(min_roi_per_unit=5.0)
    assert f.apply(good_product(net_profit_per_unit=6.0)).passed is True


def test_disabled_weight_gate_ignores_weight():
    f = UniversalProductFilter(enforce_weight=False)
    assert f.apply(good_product(weight_lbs=50.0)).passed is True


def test_disabled_gates_listed_as_blocked():
    f = UniversalProductFilter(enforce_sales=False, enforce_competition=False)
    assert set(f.gates_blocked()) == {"Demand", "Competition"}


# ---------------------------------------------------------------------------
# Batch + convenience
# ---------------------------------------------------------------------------

def test_filter_all_keeps_only_passers_and_annotates():
    products = [good_product(), good_product(brand="Kirkland Signature")]
    out = default_filter().filter_all(products)
    assert len(out) == 1
    assert out[0]["universal_filter_passed"] is True
    assert "universal_filter_gates" in out[0]


def test_filter_all_keep_rejected_annotates_reasons():
    products = [good_product(net_profit_per_unit=1.0)]
    out = default_filter().filter_all(products, keep_rejected=True)
    assert len(out) == 1
    assert out[0]["universal_filter_passed"] is False
    assert out[0]["universal_filter_reasons"]


def test_explain_rejection_returns_reasons():
    reasons = default_filter().explain_rejection(good_product(fba_sellers=8))
    assert len(reasons) == 1


def test_apply_universal_filter_convenience():
    result = apply_universal_filter(good_product(), min_roi_per_unit=1.0)
    assert result.passed is True


def test_non_dict_product_does_not_raise():
    result = default_filter().apply("not a dict")
    assert result.passed is False


def test_alternate_key_names_are_read():
    p = {
        "title": "Brand X 100 ct",
        "brand": "Brand X",
        "net_profit": 15.0,
        "monthly_sales": 2000,
        "weight_lbs": 1.0,
        "competition_fba_sellers": 1,
    }
    assert default_filter().apply(p).passed is True
