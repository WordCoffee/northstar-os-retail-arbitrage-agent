"""Canonical economics input contract (Phase 1C-03).

Every field is Optional; None means UNKNOWN (never silently zero). Monetary
values are Decimal-coerced. Per-field provenance/confidence is preserved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .enums import CashBasis, ProvenanceClass, RoundingMode
from .money import to_decimal


@dataclass
class EconomicsInput:
    # identity / scope
    marketplace: Optional[str] = None
    currency: Optional[str] = None
    cost_currency: Optional[str] = None

    # sell-side (per sellable unit unless quantity set)
    selling_price: Optional[object] = None

    # buy-side / landed cost
    acquisition_cost: Optional[object] = None
    inbound_freight: Optional[object] = None
    prep_cost: Optional[object] = None
    label_cost: Optional[object] = None
    duties: Optional[object] = None
    storage_allocation: Optional[object] = None

    # marketplace fees (amount OR rate)
    referral_fee_rate: Optional[object] = None
    referral_fee_amount: Optional[object] = None
    fba_fulfillment_fee: Optional[object] = None
    closing_fee: Optional[object] = None
    variable_closing_fee: Optional[object] = None
    other_marketplace_fees: Optional[object] = None

    # reserves / advertising
    refund_return_reserve: Optional[object] = None   # amount or rate hint
    refund_return_reserve_rate: Optional[object] = None
    damage_reserve: Optional[object] = None
    advertising_cost: Optional[object] = None

    # advertising context
    ad_attributed_revenue: Optional[object] = None
    total_revenue: Optional[object] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    orders: Optional[int] = None

    # policy
    required_post_ad_profit: Optional[object] = None
    target_acos: Optional[object] = None
    cash_basis: Optional[str] = CashBasis.MARKETPLACE_PAYOUT.value
    reinvestment_policy_amount: Optional[object] = None

    # packing / normalization
    quantity: Optional[int] = 1
    pack_count: Optional[int] = None
    pack_verified: Optional[bool] = None

    # qualification gates (not economics, but required for purchase-readiness)
    sourcing_verified: Optional[bool] = None
    documentation_verified: Optional[bool] = None
    eligibility_confirmed: Optional[bool] = None

    # provenance / quality
    provenance: str = ProvenanceClass.UNKNOWN.value
    confidence: Optional[float] = None
    stale: bool = False
    rounding: str = RoundingMode.HALF_UP.value

    def d(self, name: str) -> Optional[Decimal]:
        return to_decimal(getattr(self, name, None))