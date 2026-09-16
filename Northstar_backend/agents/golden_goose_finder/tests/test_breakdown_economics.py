"""Tests for the Golden Goose Finder breakdown economics engine.

Scenarios use mocked WholesalePack / IndividualListing objects built directly
from the module's dataclasses — no external data sources. Expected fee values
follow the versioned 2026 fee rules in Northstar_backend/amazon_us_fee_rules_2026.py
(Health & Personal Care price_switch: 8% at/below $10, 15% above; Home &
Kitchen flat 15%; FBA standard-size table; $0.30 minimum referral fee).
"""

from typing import Any, Dict

import pytest

from .. import breakdown_economics as bee
from ..breakdown_economics import (
    BreakdownEconomics,
    DEFAULT_INBOUND_COST_PER_UNIT,
    DEFAULT_PREP_COST_PER_UNIT,
    DEFAULT_REPACKAGING_COST_PER_UNIT,
    DEFAULT_RETURN_RESERVE_RATE,
    ECON_ESTIMATED,
    ECON_PROVISIONAL,
    ECON_UNAVAILABLE,
    IndividualListing,
    WholesalePack,
    calculate_breakdown_economics,
    evaluate_batch,
    passes_economics_filter,
)

# --- factory helpers -------------------------------------------------------


def make_wholesale(**overrides: Any) -> WholesalePack:
    data: Dict[str, Any] = dict(
        source_store="Costco",
        product_title="Nicorette Lozenge 200 ct",
        brand="Nicorette",
        category_slug="nicotine_cessation",
        pack_count=10,
        wholesale_price=39.99,
    )
    data.update(overrides)
    return WholesalePack(**data)


def make_individual(**overrides: Any) -> IndividualListing:
    data: Dict[str, Any] = dict(
        asin="B0NICORETTE01",
        title="Nicorette Lozenge 20 ct",
        brand="Nicorette",
        category_slug="nicotine_cessation",
        amazon_price=11.99,
        amazon_category="Health & Personal Care",
        browse_node=3760901,
        weight_oz=4.0,
        dimensions_in=[5, 3, 1],
    )
    data.update(overrides)
    return IndividualListing(**data)


def compute(wholesale: WholesalePack, individual: IndividualListing, **kw) -> BreakdownEconomics:
    return calculate_breakdown_economics(wholesale, individual, **kw)


# --- realistic scenarios ----------------------------------------------------


def test_nicorette_lozenge_scenario():
    """200ct Costco pack $39.99 -> 10 x 20ct Amazon units at $11.99.

    Cogs $4.00/unit; Health & Personal Care 15% referral ($1.80); 4oz unit ->
    $4.75 FBA band. The economics are negative (fees outweigh the margin),
    which is the honest 'don't buy' signal this module must produce.
    """
    eco = compute(make_wholesale(), make_individual())

    assert eco.unit_cogs == pytest.approx(4.00, abs=0.01)
    assert eco.repackaging_cost_per_unit == pytest.approx(0.75)
    assert eco.packaging_cost == pytest.approx(0.25)
    assert eco.inbound_cost == pytest.approx(DEFAULT_INBOUND_COST_PER_UNIT)
    assert eco.prep_cost == pytest.approx(DEFAULT_PREP_COST_PER_UNIT)
    assert eco.referral_fee == pytest.approx(1.80, abs=0.01)
    assert eco.fulfillment_fee == pytest.approx(4.75)
    assert eco.return_reserve == pytest.approx(0.24, abs=0.01)
    assert eco.total_amazon_fees == pytest.approx(6.79, abs=0.01)
    assert eco.total_costs_per_unit == pytest.approx(12.14, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-0.15, abs=0.01)
    assert eco.net_profit_per_costco_pack == pytest.approx(-1.49, abs=0.01)
    assert eco.roi_per_unit == pytest.approx(-3.72, abs=0.01)
    assert eco.roi_per_costco_pack == pytest.approx(-3.72, abs=0.01)
    assert eco.profit_margin_pct == pytest.approx(-1.24, abs=0.01)
    assert eco.breakeven_amazon_price == pytest.approx(12.14, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_advil_scenario():
    """500ct Costco $24.99 -> 5 x 100ct Amazon at $8.99 (OTA low-tier 8% referral)."""
    wholesale = make_wholesale(
        source_store="Costco",
        product_title="Advil Coated Tablets 500 ct",
        brand="Advil",
        category_slug="otc_health",
        pack_count=5,
        wholesale_price=24.99,
    )
    individual = make_individual(
        asin="B0ADVIL0001",
        title="Advil Coated Tablets 100 ct",
        brand="Advil",
        category_slug="otc_health",
        amazon_price=8.99,
        weight_oz=6.0,
        dimensions_in=[3.5, 1.9, 5.7],
    )
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(5.00, abs=0.01)
    assert eco.referral_fee == pytest.approx(0.72, abs=0.01)  # 8% of 8.99
    assert eco.fulfillment_fee == pytest.approx(4.75)
    assert eco.total_costs_per_unit == pytest.approx(12.00, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-3.01, abs=0.01)
    assert eco.net_profit_per_costco_pack == pytest.approx(-15.04, abs=0.01)
    assert eco.breakeven_amazon_price == pytest.approx(12.00, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_tide_pods_scenario():
    """152ct Costco $29.99 -> 3 x 42ct Amazon at $14.99 (Home & Kitchen flat 15%)."""
    wholesale = make_wholesale(
        source_store="Costco",
        product_title="Tide PODS Laundry Detergent 152 ct",
        brand="Tide",
        category_slug="household_cleaning",
        pack_count=3,
        wholesale_price=29.99,
    )
    individual = make_individual(
        asin="B0TIDEPODS01",
        title="Tide PODS Laundry Detergent 42 ct",
        brand="Tide",
        category_slug="household_cleaning",
        amazon_price=14.99,
        amazon_category="Home & Kitchen",
        browse_node=1055398,
        weight_oz=40.0,
        dimensions_in=[7, 5, 6],
    )
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(10.00, abs=0.01)
    assert eco.referral_fee == pytest.approx(2.25, abs=0.01)  # 15% of 14.99
    assert eco.fulfillment_fee == pytest.approx(7.10)  # 2.5 lb band
    assert eco.total_costs_per_unit == pytest.approx(21.00, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-6.01, abs=0.01)
    assert eco.net_profit_per_costco_pack == pytest.approx(-18.02, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_nature_made_vitamin_d_scenario():
    """250ct Costco $12.99 -> 4 x 60ct Amazon at $7.99 (low-tier referral)."""
    wholesale = make_wholesale(
        source_store="Costco",
        product_title="Nature Made Vitamin D3 250 ct",
        brand="Nature Made",
        category_slug="vitamins_supplements",
        pack_count=4,
        wholesale_price=12.99,
    )
    individual = make_individual(
        asin="B0VITD00001",
        title="Nature Made Vitamin D3 60 ct",
        brand="Nature Made",
        category_slug="vitamins_supplements",
        amazon_price=7.99,
        weight_oz=5.0,
        dimensions_in=[2.5, 2.5, 4.5],
    )
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(3.25, abs=0.01)
    assert eco.referral_fee == pytest.approx(0.64, abs=0.01)  # 8% of 7.99
    assert eco.fulfillment_fee == pytest.approx(4.75)
    assert eco.total_costs_per_unit == pytest.approx(10.15, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-2.16, abs=0.01)
    assert eco.net_profit_per_costco_pack == pytest.approx(-8.63, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_dove_body_wash_scenario():
    """6-pack Costco $19.99 -> single Amazon bottle at $5.99 (1.4 lb -> $6.10 FBA)."""
    wholesale = make_wholesale(
        source_store="Costco",
        product_title="Dove Body Wash 6 Pack",
        brand="Dove",
        category_slug="personal_care",
        pack_count=6,
        wholesale_price=19.99,
    )
    individual = make_individual(
        asin="B0DOVEBODY01",
        title="Dove Body Wash 20 oz",
        brand="Dove",
        category_slug="personal_care",
        amazon_price=5.99,
        weight_oz=22.4,
        dimensions_in=[3.5, 2.2, 10.0],
    )
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(3.33, abs=0.01)
    assert eco.referral_fee == pytest.approx(0.48, abs=0.01)
    assert eco.fulfillment_fee == pytest.approx(6.10)
    assert eco.total_costs_per_unit == pytest.approx(11.38, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-5.39, abs=0.01)
    assert eco.net_profit_per_costco_pack == pytest.approx(-32.35, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


# --- profitable scenario (for the filter tests) -----------------------------


@pytest.fixture
def profitable() -> BreakdownEconomics:
    """Nicorette gum 100ct at $39.99, 5 units from a $49.99 club pack.

    The high unit price clears fees: net ~$16.59/unit, ROI ~166%. Used to test
    that the filter admits genuinely good opportunities.
    """
    wholesale = make_wholesale(
        product_title="Nicorette Gum 5 x 100 ct",
        pack_count=5,
        wholesale_price=49.99,
    )
    individual = make_individual(
        asin="B0GUM100CT01",
        title="Nicorette Gum 100 ct",
        amazon_price=39.99,
        weight_oz=10.0,
        dimensions_in=[6, 4, 3],
    )
    return compute(wholesale, individual)


def test_profitable_scenario(profitable: BreakdownEconomics):
    assert profitable.net_profit_per_unit == pytest.approx(16.59, abs=0.01)
    assert profitable.roi_per_unit == pytest.approx(165.96, abs=0.01)
    assert profitable.profit_margin_pct == pytest.approx(41.49, abs=0.01)
    assert profitable.total_costs_per_unit == pytest.approx(23.40, abs=0.01)
    assert profitable.breakeven_amazon_price == pytest.approx(23.40, abs=0.01)
    assert profitable.referral_fee == pytest.approx(6.00, abs=0.01)
    assert profitable.fulfillment_fee == pytest.approx(5.25)  # 0.625 lb band
    assert profitable.economics_confidence == ECON_ESTIMATED


# --- edge cases -------------------------------------------------------------


def test_pack_count_of_one():
    """pack_count=1: unit_cogs == wholesale price and a warning note fires."""
    wholesale = make_wholesale(pack_count=1, wholesale_price=12.99)
    individual = make_individual(amazon_price=9.99, weight_oz=4.0)
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(12.99)
    # $9.99 hits the Health & Personal Care LOW tier (8% -> $0.80 referral).
    assert eco.referral_fee == pytest.approx(0.80, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-10.10, abs=0.01)
    assert any("pack_count is 1" in n for n in eco.economics_notes)


def test_very_expensive_item():
    """Expensive units scale the referral fee and take the 12.50 FBA band."""
    wholesale = make_wholesale(
        product_title="Luxury Home Appliance Units 2 pk",
        brand="Cascade",
        category_slug="household_cleaning",
        pack_count=2,
        wholesale_price=800.00,
    )
    individual = make_individual(
        asin="B0EXPENSIVE01",
        title="Luxury Appliance Unit",
        amazon_price=499.99,
        amazon_category="Home & Kitchen",
        weight_oz=240.0,
        dimensions_in=[16, 12, 7],
    )
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(400.00)
    assert eco.referral_fee == pytest.approx(75.00, abs=0.01)  # 15% flat
    assert eco.fulfillment_fee == pytest.approx(12.50)  # 15 lb band
    assert eco.return_reserve == pytest.approx(10.00, abs=0.01)
    assert eco.total_costs_per_unit == pytest.approx(498.85, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(1.14, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_very_cheap_item_min_referral_fee():
    """Cheap items hit the $0.30 minimum referral fee floor (8% of $1.29 < $0.30)."""
    wholesale = make_wholesale(
        product_title="Generic Vitamins 20 pk",
        brand="Nature's Bounty",
        category_slug="vitamins_supplements",
        pack_count=20,
        wholesale_price=3.99,
    )
    individual = make_individual(
        asin="B0CHEAP0001",
        title="Vitamin Tablet 1 ct",
        amazon_price=1.29,
        weight_oz=1.0,
    )
    eco = compute(wholesale, individual)

    assert eco.unit_cogs == pytest.approx(0.20, abs=0.01)
    assert eco.referral_fee == pytest.approx(0.30, abs=0.01)  # min fee floor
    assert eco.fulfillment_fee == pytest.approx(4.75)
    assert eco.total_costs_per_unit == pytest.approx(6.63, abs=0.01)
    assert eco.net_profit_per_unit == pytest.approx(-5.34, abs=0.01)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_custom_repackaging_cost():
    """A heftier repackaging budget ($1.00) splits into $0.50 labor + $0.50 packaging."""
    eco = compute(make_wholesale(), make_individual(), repackaging_cost_per_unit=1.00)

    assert eco.repackaging_cost_per_unit == pytest.approx(1.00)
    assert eco.packaging_cost == pytest.approx(0.50)
    assert eco.net_profit_per_unit == pytest.approx(
        -0.15 - 0.25, abs=0.01  # 0.25c more cost vs the 0.75 baseline
    )
    assert any("exceeds the default" in n for n in eco.economics_notes)


def test_zero_repackaging_cost_clamps_packaging():
    """An explicit $0.00 repackaging budget is honored (no labor/packaging)."""
    eco = compute(make_wholesale(), make_individual(), repackaging_cost_per_unit=0.0)

    assert eco.repackaging_cost_per_unit == pytest.approx(0.00)
    assert eco.packaging_cost == pytest.approx(0.00)
    assert eco.net_profit_per_unit == pytest.approx(-0.15 + 0.75, abs=0.01)


# --- breakeven --------------------------------------------------------------


@pytest.mark.parametrize(
    "wholesale_kw, individual_kw",
    [
        (dict(), dict()),
        (
            dict(pack_count=5, wholesale_price=49.99),
            dict(amazon_price=39.99, weight_oz=10.0),
        ),
        (dict(pack_count=1, wholesale_price=12.99), dict(amazon_price=9.99)),
    ],
)
def test_breakeven_equals_total_costs(wholesale_kw, individual_kw):
    eco = compute(make_wholesale(**wholesale_kw), make_individual(**individual_kw))
    assert eco.breakeven_amazon_price is not None
    assert eco.breakeven_amazon_price == pytest.approx(eco.total_costs_per_unit, abs=0.001)


def test_breakeven_matches_manual_stack():
    eco = compute(make_wholesale(), make_individual())
    manual = (
        39.99 / 10
        + 0.75
        + 1.80
        + 4.75
        + DEFAULT_INBOUND_COST_PER_UNIT
        + DEFAULT_PREP_COST_PER_UNIT
        + 0.02 * 11.99
    )
    assert eco.breakeven_amazon_price == pytest.approx(manual, abs=0.01)


# --- warnings in economics_notes --------------------------------------------


def test_notes_flag_roi_below_floor():
    eco = compute(make_wholesale(), make_individual(), roi_floor=10.00)
    assert any("roi floor" in n for n in eco.economics_notes)


def test_notes_flag_default_category_when_no_category():
    individual = make_individual(amazon_category=None, browse_node=None)
    eco = compute(make_wholesale(), individual)

    assert eco.referral_fee == pytest.approx(1.80, abs=0.01)  # 15% default
    assert any("default" in n.lower() for n in eco.economics_notes)


def test_notes_flag_missing_weight():
    individual = make_individual(weight_oz=None)
    wholesale = make_wholesale()  # no per-unit weight either
    eco = compute(wholesale, individual)

    assert eco.fulfillment_fee is None
    assert any("EXCLUDED" in n for n in eco.economics_notes)
    assert eco.economics_confidence == ECON_PROVISIONAL


def test_notes_present_for_estimated():
    eco = compute(make_wholesale(), make_individual())
    assert eco.economics_notes
    assert any("All costs included" in n for n in eco.economics_notes)


# --- confidence levels ------------------------------------------------------


def test_confidence_estimated_with_full_data():
    eco = compute(make_wholesale(), make_individual())
    assert eco.economics_confidence == ECON_ESTIMATED


def test_confidence_provisional_without_weight():
    individual = make_individual(weight_oz=None)
    wholesale = make_wholesale(individual_unit_weight_oz=None)
    eco = compute(wholesale, individual)
    assert eco.economics_confidence == ECON_PROVISIONAL


def test_confidence_provisional_with_listing_fee_but_no_weight():
    """A listing-reported FBA fee is used even without weight data."""
    individual = make_individual(weight_oz=None, listing_fba_fee=4.50)
    eco = compute(make_wholesale(), individual)

    assert eco.fulfillment_fee == pytest.approx(4.50)
    assert eco.economics_confidence == ECON_ESTIMATED
    assert any("reported by the listing" in n for n in eco.economics_notes)


def test_confidence_unavailable_without_price():
    individual = make_individual(amazon_price=None)
    eco = compute(make_wholesale(), individual)

    assert eco.economics_confidence == ECON_UNAVAILABLE
    assert eco.net_profit_per_unit is None
    assert eco.roi_per_unit is None
    assert eco.breakeven_amazon_price is None
    assert any("No Amazon sale price" in n for n in eco.economics_notes)


def test_confidence_unavailable_without_wholesale_price():
    wholesale = make_wholesale(wholesale_price=None)
    eco = compute(wholesale, make_individual())

    assert eco.economics_confidence == ECON_UNAVAILABLE
    assert eco.net_profit_per_unit is None
    assert any("No wholesale" in n for n in eco.economics_notes)


def test_confidence_unavailable_without_pack_count():
    wholesale = make_wholesale(pack_count=None)
    eco = compute(wholesale, make_individual())

    assert eco.economics_confidence == ECON_UNAVAILABLE
    assert eco.net_profit_per_unit is None


# --- missing data (None fields) --------------------------------------------


def test_missing_weight_falls_back_to_wholesale_unit_weight():
    """Listing weight unknown but the wholesale pack records per-unit weight."""
    wholesale = make_wholesale(individual_unit_weight_oz=4.0)
    individual = make_individual(weight_oz=None)
    eco = compute(wholesale, individual)

    assert eco.fulfillment_fee == pytest.approx(4.75)
    assert eco.economics_confidence == ECON_ESTIMATED


def test_missing_optional_listing_fields_do_not_break():
    individual = make_individual(
        asin=None,
        bsr=None,
        review_rating=None,
        review_count=None,
        fba_sellers=None,
        is_prime=False,
    )
    eco = compute(make_wholesale(), individual)
    assert eco.net_profit_per_unit is not None
    assert eco.economics_confidence == ECON_ESTIMATED


def test_zero_weights_treated_as_missing():
    individual = make_individual(weight_oz=0)
    wholesale = make_wholesale(individual_unit_weight_oz=0)
    eco = compute(wholesale, individual)
    assert eco.fulfillment_fee is None
    assert eco.economics_confidence == ECON_PROVISIONAL


# --- fee_engine fallback paths ----------------------------------------------


def test_fallback_when_fee_engine_import_missing(monkeypatch):
    """fee_engine unavailable -> 15% flat referral + pricing FBA table, provisional."""
    monkeypatch.setattr(bee, "_fee_engine", None)
    eco = compute(make_wholesale(), make_individual())

    assert eco.referral_fee == pytest.approx(1.80, abs=0.01)  # 15% of 11.99
    assert eco.fulfillment_fee == pytest.approx(4.75)  # pricing.estimate_fba_fee(0.25)
    assert eco.economics_confidence == ECON_PROVISIONAL
    assert any("fee_engine unavailable" in n for n in eco.economics_notes)


def test_fallback_when_fee_engine_raises(monkeypatch):
    """fee_engine importable but its FBA call raises -> pricing fallback."""

    class _Boom:
        @staticmethod
        def calculate_fba_fulfillment_fee(*args, **kwargs):
            raise RuntimeError("engine exploded")

        @staticmethod
        def calculate_referral_fee(*args, **kwargs):
            from fee_engine import calculate_referral_fee
            return calculate_referral_fee(*args, **kwargs)

        @staticmethod
        def calculate_unit_costs():
            from fee_engine import calculate_unit_costs
            return calculate_unit_costs()

    monkeypatch.setattr(bee, "_fee_engine", _Boom())
    eco = compute(make_wholesale(), make_individual())

    assert eco.referral_fee == pytest.approx(1.80, abs=0.01)  # engine rule (verified)
    assert eco.fulfillment_fee == pytest.approx(4.75)  # pricing fallback
    assert any("pricing.estimate_fba_fee" in n for n in eco.economics_notes)
    assert eco.economics_confidence == ECON_PROVISIONAL


def test_fallback_when_pricing_import_missing(monkeypatch):
    """fee_engine AND pricing both unavailable with a known weight -> fee excluded."""
    monkeypatch.setattr(bee, "_fee_engine", None)
    monkeypatch.setattr(bee, "_pricing", None)
    eco = compute(make_wholesale(), make_individual())

    assert eco.fulfillment_fee is None
    assert eco.economics_confidence == ECON_PROVISIONAL
    assert any("EXCLUDED" in n for n in eco.economics_notes)


# --- ROI floor / margin filters ---------------------------------------------


def test_filter_passes_good_opportunity(profitable: BreakdownEconomics):
    assert passes_economics_filter(profitable, roi_floor=10.00, min_margin_pct=0.0) is True


def test_filter_rejects_below_roi_floor():
    eco = compute(make_wholesale(), make_individual())  # ROI ~ -3.7%
    assert passes_economics_filter(eco, roi_floor=10.00) is False
    # Negative-margin item can only clear an eased margin gate too:
    assert passes_economics_filter(eco, roi_floor=-100.00, min_margin_pct=-100.0) is True


def test_filter_min_margin_gate(profitable: BreakdownEconomics):
    assert passes_economics_filter(profitable, roi_floor=10.00, min_margin_pct=40.0) is True
    assert passes_economics_filter(profitable, roi_floor=10.00, min_margin_pct=50.0) is False


def test_filter_boundary_roi_exact():
    """An opportunity with exactly the roi_floor passes (>= semantics)."""
    eco = BreakdownEconomics(
        wholesale=make_wholesale(),
        individual=make_individual(),
        unit_cogs=1.0,
        repackaging_cost_per_unit=0.75,
        referral_fee=1.0,
        fulfillment_fee=4.0,
        inbound_cost=0.35,
        prep_cost=0.25,
        packaging_cost=0.25,
        return_reserve=0.2,
        total_amazon_fees=5.2,
        total_costs_per_unit=1.0,
        net_profit_per_unit=0.10,
        net_profit_per_costco_pack=1.0,
        roi_per_unit=10.00,
        roi_per_costco_pack=10.0,
        profit_margin_pct=1.0,
        breakeven_amazon_price=1.0,
        economics_confidence=ECON_ESTIMATED,
    )
    assert passes_economics_filter(eco, roi_floor=10.00, min_margin_pct=1.0) is True
    assert passes_economics_filter(eco, roi_floor=10.01, min_margin_pct=1.0) is False


def test_filter_fails_closed_on_unavailable():
    individual = make_individual(amazon_price=None)
    eco = compute(make_wholesale(), individual)
    assert eco.economics_confidence == ECON_UNAVAILABLE
    assert passes_economics_filter(eco, roi_floor=-1000.0, min_margin_pct=-100.0) is False


def test_filter_fails_closed_on_missing_values():
    eco = BreakdownEconomics(
        wholesale=make_wholesale(),
        individual=make_individual(),
        unit_cogs=None,
        repackaging_cost_per_unit=None,
        referral_fee=None,
        fulfillment_fee=None,
        inbound_cost=None,
        prep_cost=None,
        packaging_cost=None,
        return_reserve=None,
        total_amazon_fees=None,
        total_costs_per_unit=None,
        net_profit_per_unit=None,
        net_profit_per_costco_pack=None,
        roi_per_unit=None,
        roi_per_costco_pack=None,
        profit_margin_pct=None,
        breakeven_amazon_price=None,
        economics_confidence=ECON_PROVISIONAL,
    )
    assert passes_economics_filter(eco) is False


# --- batch evaluation -------------------------------------------------------


def test_evaluate_batch_returns_one_result_per_pair():
    pairs = [
        (make_wholesale(), make_individual()),
        (
            make_wholesale(
                source_store="Sam's Club",
                product_title="Dove Body Wash 6 Pack",
                brand="Dove",
                category_slug="personal_care",
                pack_count=6,
                wholesale_price=19.99,
            ),
            make_individual(
                asin="B0DOVEBODY01",
                title="Dove Body Wash 20 oz",
                brand="Dove",
                category_slug="personal_care",
                amazon_price=5.99,
                weight_oz=22.4,
                dimensions_in=[3.5, 2.2, 10.0],
            ),
        ),
    ]
    results = evaluate_batch(pairs)

    assert len(results) == 2
    assert results[0].wholesale.brand == "Nicorette"
    assert results[0].net_profit_per_unit == pytest.approx(-0.15, abs=0.01)
    assert results[1].wholesale.source_store == "Sam's Club"
    assert results[1].net_profit_per_unit == pytest.approx(-5.39, abs=0.01)


def test_evaluate_batch_empty():
    assert evaluate_batch([]) == []


def test_evaluate_batch_with_roi_floor_note():
    pair = [(make_wholesale(), make_individual())]
    results = evaluate_batch(pair, roi_floor=10.00)
    assert any("roi floor" in n for n in results[0].economics_notes)


def test_calculate_breakdown_economics_returns_correct_roi_formula():
    """ROI per unit is net profit / cogs as a percentage; pack ROI mirrors it."""
    eco = compute(
        make_wholesale(pack_count=2, wholesale_price=10.00),
        make_individual(amazon_price=20.00, weight_oz=4.0),
    )
    # cogs=5.00; referral 15% of 20 = 3.00; fba 4.75; reserve 0.40
    total = 5.00 + 0.75 + 3.00 + 4.75 + 0.35 + 0.25 + 0.40
    net = 20.00 - total
    assert eco.net_profit_per_unit == pytest.approx(net, abs=0.01)
    assert eco.roi_per_unit == pytest.approx(net / 5.00 * 100.0, abs=0.01)
    assert eco.net_profit_per_costco_pack == pytest.approx(net * 2, abs=0.01)