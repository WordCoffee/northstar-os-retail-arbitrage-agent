"""Compatibility adapters from legacy formula sites to the canonical engine.

These adapters let existing consumers delegate to the canonical engine WITHOUT
retaining independent authoritative math. Unknown inputs stay unknown (no hidden
0.15 referral default, no fixed FBA fee).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .engine import compute
from .enums import ProvenanceClass
from .inputs import EconomicsInput
from .outputs import EconomicsOutput


def economics_from_legacy(*, selling_price, acquisition_cost,
                          referral_fee=None, referral_rate=None,
                          fba_fee=None, closing_fee=None,
                          inbound_freight=None, prep_cost=None,
                          advertising_cost=None, quantity=1,
                          currency="USD", marketplace="amazon.com",
                          provenance=ProvenanceClass.IMPORTED.value) -> EconomicsOutput:
    """Adapter for legacy per-unit economics. NO hidden referral/FBA defaults."""
    return compute(EconomicsInput(
        marketplace=marketplace, currency=currency,
        selling_price=selling_price, acquisition_cost=acquisition_cost,
        referral_fee_amount=referral_fee, referral_fee_rate=referral_rate,
        fba_fulfillment_fee=fba_fee, closing_fee=closing_fee,
        inbound_freight=inbound_freight, prep_cost=prep_cost,
        advertising_cost=advertising_cost, quantity=quantity,
        provenance=provenance,
    ))


def to_legacy_fields(out: EconomicsOutput) -> dict:
    """Map canonical output back to the legacy field names some consumers expect.
    Values are Decimal or None (never float, never fabricated)."""
    return {
        "net_profit": out.contribution_profit_after_ads,
        "roi_pct": out.roi_on_invested_cost,
        "margin_pct": out.margin_on_revenue,
        "marketplace_fees": out.marketplace_fees,
        "payout": out.marketplace_payout_before_ads,
        "break_even_acos": out.break_even_acos,
    }


def target_acos_from_floor(*, pre_ad_contribution, ad_revenue,
                           required_post_ad_profit) -> Optional[Decimal]:
    """Policy-derived target ACoS (NOT a universal 70% constant)."""
    if ad_revenue in (None, Decimal("0")) or pre_ad_contribution is None:
        return None
    return (pre_ad_contribution - (required_post_ad_profit or Decimal("0"))) / ad_revenue