"""Canonical economics output contract (Phase 1C-03)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Optional

from .money import money_str, percent_str, ratio_str
from .versions import FORMULA_VERSION


@dataclass
class EconomicsOutput:
    formula_version: str = FORMULA_VERSION
    currency: Optional[str] = None
    marketplace: Optional[str] = None
    readiness: str = "SOURCE_UNVERIFIED"
    missing_inputs: list[str] = field(default_factory=list)
    purchase_ready: bool = False
    explanation: list[str] = field(default_factory=list)

    # money (Decimal)
    gross_revenue: Optional[Decimal] = None
    marketplace_fees: Optional[Decimal] = None
    marketplace_payout_before_ads: Optional[Decimal] = None
    landed_inventory_cost: Optional[Decimal] = None
    pre_ad_contribution: Optional[Decimal] = None
    advertising_cost: Optional[Decimal] = None
    contribution_profit_after_ads: Optional[Decimal] = None
    cash_available_for_reinvestment: Optional[Decimal] = None

    # ratios / percentages (Decimal)
    roi_on_invested_cost: Optional[Decimal] = None
    roi_denominator_label: str = "landed_inventory_cost"
    margin_on_revenue: Optional[Decimal] = None
    markup_on_cost: Optional[Decimal] = None
    break_even_acos: Optional[Decimal] = None
    target_acos: Optional[Decimal] = None
    tacos: Optional[Decimal] = None
    cvr: Optional[Decimal] = None
    ctr: Optional[Decimal] = None
    cpc: Optional[Decimal] = None
    roas: Optional[Decimal] = None
    maximum_cpc: Optional[Decimal] = None

    def to_dict(self) -> dict:
        """Serialize for API/frontend: money/rates as decimal strings, None stays None."""
        out = asdict(self)
        for k, v in list(out.items()):
            if isinstance(v, Decimal):
                if k in ("gross_revenue", "marketplace_fees", "marketplace_payout_before_ads",
                         "landed_inventory_cost", "pre_ad_contribution", "advertising_cost",
                         "contribution_profit_after_ads", "cash_available_for_reinvestment",
                         "cpc", "maximum_cpc"):
                    out[k] = money_str(v)
                elif k in ("cvr", "ctr", "roas"):
                    out[k] = ratio_str(v)
                else:
                    out[k] = percent_str(v)
        return out