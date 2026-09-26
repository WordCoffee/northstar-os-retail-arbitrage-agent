"""Canonical economics engine tests (Phase 1C-03)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from Northstar_backend.foundation.economics import (
    EconomicsInput, compute, Readiness,
)
from Northstar_backend.foundation.economics.enums import ProvenanceClass
from Northstar_backend.foundation.economics import compatibility
from Northstar_backend.foundation.economics.benchmarks import (
    MINOXIDIL_LEGACY, MINOXIDIL_NEWER, benchmark_input,
)


def _verified(**kw):
    base = dict(marketplace="amazon.com", currency="USD",
                selling_price="42.00", acquisition_cost="17.99",
                referral_fee_amount="6.30", fba_fulfillment_fee="5.55",
                advertising_cost="0", provenance=ProvenanceClass.VERIFIED.value)
    base.update(kw)
    return EconomicsInput(**base)


# --- complete / verified -----------------------------------------------------

def test_complete_verified():
    out = compute(_verified())
    assert out.readiness == Readiness.COMPLETE_VERIFIED.value
    assert out.gross_revenue == Decimal("42.00")
    assert out.marketplace_fees == Decimal("11.85")
    assert out.marketplace_payout_before_ads == Decimal("30.15")
    assert out.landed_inventory_cost == Decimal("17.99")
    assert out.pre_ad_contribution == Decimal("12.16")
    assert out.contribution_profit_after_ads == Decimal("12.16")
    assert out.purchase_ready is False  # gates not supplied
    assert out.formula_version


def test_complete_estimated():
    out = compute(_verified(provenance=ProvenanceClass.ESTIMATED.value))
    assert out.readiness == Readiness.COMPLETE_ESTIMATED.value


def test_purchase_ready_requires_all_gates():
    out = compute(_verified(sourcing_verified=True, documentation_verified=True,
                            eligibility_confirmed=True))
    assert out.purchase_ready is True
    out2 = compute(_verified(sourcing_verified=True, documentation_verified=True,
                             eligibility_confirmed=False))
    assert out2.purchase_ready is False


# --- null-first --------------------------------------------------------------

def test_missing_selling_price():
    out = compute(_verified(selling_price=None))
    assert out.readiness == Readiness.SELLING_PRICE_MISSING.value
    assert out.gross_revenue is None
    assert "selling_price" in out.missing_inputs


def test_missing_acquisition_cost():
    out = compute(_verified(acquisition_cost=None))
    assert out.readiness == Readiness.ACQUISITION_COST_MISSING.value
    assert out.landed_inventory_cost is None
    assert out.contribution_profit_after_ads is None


def test_missing_referral_and_fba():
    assert compute(_verified(referral_fee_amount=None)).readiness == Readiness.REFERRAL_FEE_UNKNOWN.value
    assert compute(_verified(fba_fulfillment_fee=None)).readiness == Readiness.FULFILLMENT_FEE_UNKNOWN.value


def test_unknown_never_becomes_zero():
    out = compute(_verified(acquisition_cost=None))
    assert out.contribution_profit_after_ads is None  # not 0


def test_referral_from_rate():
    out = compute(_verified(referral_fee_amount=None, referral_fee_rate="0.15"))
    assert out.marketplace_fees == Decimal("11.85")  # 42*0.15 + 5.55


# --- edge values -------------------------------------------------------------

def test_zero_price_safe():
    out = compute(_verified(selling_price="0"))
    assert out.gross_revenue == Decimal("0.00")
    assert out.margin_on_revenue is None  # div-by-zero->None


def test_zero_cost_roi_unknown():
    out = compute(_verified(acquisition_cost="0"))
    assert out.landed_inventory_cost == Decimal("0.00")
    assert out.roi_on_invested_cost is None


def test_negative_inputs_produce_loss():
    out = compute(_verified(selling_price="10.00", acquisition_cost="25.00",
                            referral_fee_amount="1.50", fba_fulfillment_fee="5.00"))
    assert out.contribution_profit_after_ads < 0


def test_invalid_currency():
    out = compute(_verified(currency="US"))
    assert out.readiness == Readiness.CURRENCY_MISMATCH.value


def test_currency_mismatch():
    out = compute(_verified(currency="USD", cost_currency="CAD"))
    assert out.readiness == Readiness.CURRENCY_MISMATCH.value


def test_decimal_precision_exact():
    out = compute(_verified(selling_price="0.10", acquisition_cost="0.03",
                            referral_fee_amount="0.01", fba_fulfillment_fee="0.01",
                            advertising_cost="0"))
    assert out.contribution_profit_after_ads == Decimal("0.05")


def test_large_values():
    out = compute(_verified(selling_price="999999.99", acquisition_cost="1.00",
                            referral_fee_amount="500000.00", fba_fulfillment_fee="1.00"))
    assert out.contribution_profit_after_ads == Decimal("499997.99")


# --- metric distinctness -----------------------------------------------------

def test_roi_margin_markup_distinct_and_named():
    out = compute(_verified())
    assert out.roi_on_invested_cost is not None
    assert out.margin_on_revenue is not None
    assert out.markup_on_cost is not None
    assert out.roi_denominator_label == "landed_inventory_cost"
    # markup/(1-markup) relationship sanity: margin != roi here
    assert out.margin_on_revenue != out.roi_on_invested_cost


# --- reserves / advertising --------------------------------------------------

def test_reserves_and_ads_reduce_contribution():
    base = compute(_verified())
    with_r = compute(_verified(refund_return_reserve="1.00", advertising_cost="2.00"))
    assert with_r.pre_ad_contribution == base.pre_ad_contribution - Decimal("1.00")
    assert with_r.contribution_profit_after_ads == base.contribution_profit_after_ads - Decimal("3.00")


def test_multipack_quantity_scaling():
    one = compute(_verified(quantity=1))
    two = compute(_verified(quantity=2))
    assert two.gross_revenue == one.gross_revenue * 2
    assert two.landed_inventory_cost == one.landed_inventory_cost * 2


# --- advertising metrics -----------------------------------------------------

def test_advertising_metrics():
    out = compute(_verified(
        advertising_cost="5.00", ad_attributed_revenue="42.00", total_revenue="100.00",
        impressions=1000, clicks=50, orders=5, required_post_ad_profit="3.00"))
    assert out.ctr == Decimal("0.0500")
    assert out.cvr == Decimal("0.1000")
    assert out.cpc == Decimal("0.1000")
    assert out.roas == Decimal("8.4000")
    assert out.tacos == Decimal("0.0500")
    assert out.break_even_acos is not None
    assert out.target_acos is not None
    assert out.maximum_cpc is not None


def test_tacos_none_without_total_revenue():
    out = compute(_verified(advertising_cost="5.00"))
    assert out.tacos is None
    assert "total_revenue" in out.missing_inputs


def test_target_acos_not_hardcoded_constant():
    # no policy supplied -> target unknown (not 0.7 * break-even)
    out = compute(_verified(advertising_cost="1.00"))
    assert out.target_acos is None


# --- cash --------------------------------------------------------------------

def test_cash_available_basis():
    payout = compute(_verified(cash_basis="marketplace_payout"))
    assert payout.cash_available_for_reinvestment == payout.marketplace_payout_before_ads
    settlement = compute(_verified(cash_basis="settlement"))
    assert settlement.cash_available_for_reinvestment is None  # unknown, not fabricated


# --- serialization -----------------------------------------------------------

def test_to_dict_serializes_decimal_strings():
    d = compute(_verified(advertising_cost="1.00", total_revenue="50.00")).to_dict()
    assert d["gross_revenue"] == "42.00"
    assert isinstance(d["roi_on_invested_cost"], str)
    assert d["contribution_profit_after_ads"] is not None


# --- compatibility adapter ---------------------------------------------------

def test_legacy_adapter_no_hidden_defaults():
    out = compatibility.economics_from_legacy(selling_price="42.00", acquisition_cost="17.99")
    # no referral supplied -> unknown -> not resolved as a fee-bearing result
    assert out.readiness == Readiness.REFERRAL_FEE_UNKNOWN.value
    legacy = compatibility.to_legacy_fields(out)
    assert legacy["net_profit"] is None


def test_legacy_adapter_with_fees():
    out = compatibility.economics_from_legacy(
        selling_price="42.00", acquisition_cost="17.99",
        referral_fee="6.30", fba_fee="5.55", advertising_cost="0")
    assert out.contribution_profit_after_ads == Decimal("12.16")


def test_target_acos_from_floor():
    t = compatibility.target_acos_from_floor(
        pre_ad_contribution=Decimal("12.16"), ad_revenue=Decimal("42.00"),
        required_post_ad_profit=Decimal("3.00"))
    assert t == (Decimal("12.16") - Decimal("3.00")) / Decimal("42.00")


# --- Minoxidil benchmark vectors ---------------------------------------------

def test_minoxidil_vectors_separate():
    assert MINOXIDIL_LEGACY.implied_marketplace_fee == Decimal("12.48")
    assert MINOXIDIL_NEWER.implied_marketplace_fee == Decimal("12.48")
    assert MINOXIDIL_LEGACY.profit_assumption == Decimal("7.52")
    assert MINOXIDIL_NEWER.profit_assumption == Decimal("11.53")
    assert MINOXIDIL_LEGACY.selling_price != MINOXIDIL_NEWER.selling_price


def test_minoxidil_engine_reproduces_via_implied_fee():
    for vec, payout, profit in ((MINOXIDIL_LEGACY, "25.51", "7.52"),
                                (MINOXIDIL_NEWER, "29.52", "11.53")):
        out = compute(benchmark_input(vec, use_implied_fee=True))
        assert out.marketplace_payout_before_ads == Decimal(payout)
        assert out.contribution_profit_after_ads == Decimal(profit)


# --- Faire adapter fail-closed ----------------------------------------------

def test_faire_fee_unknown_fails_closed():
    from Northstar_backend.faire_research.economics import (
        FeeInputs, contribution_profit,
    )
    from Northstar_backend.faire_research.enums import FeeConfidence
    r = contribution_profit("42.00", Decimal("17.99"), FeeInputs(confidence=FeeConfidence.FEE_UNKNOWN))
    assert r.resolved is False


def test_faire_adapter_resolved_delegates_canonical():
    from Northstar_backend.faire_research.economics import (
        FeeInputs, contribution_profit,
    )
    from Northstar_backend.faire_research.enums import FeeConfidence
    fees = FeeInputs(referral_fee=Decimal("6.30"), fba_fulfillment_fee=Decimal("5.55"),
                     inbound_fba_per_unit=Decimal("0"), prep_label_per_unit=Decimal("0"),
                     storage_alloc_per_unit=Decimal("0"), advertising_reserve_per_unit=Decimal("0"),
                     return_reserve_per_unit=Decimal("0"), other_per_unit=Decimal("0"),
                     confidence=FeeConfidence.AMAZON_API_VERIFIED)
    r = contribution_profit("42.00", Decimal("17.99"), fees)
    assert r.resolved is True
    assert r.contribution_profit == Decimal("12.16")