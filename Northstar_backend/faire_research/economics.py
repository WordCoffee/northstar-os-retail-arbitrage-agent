"""Faire research economics ADAPTER (Phase 1C-03).

*** STATUS: COMPATIBILITY ADAPTER (non-canonical formulas removed) ***

Authoritative money math now delegates to the canonical engine
(``foundation.economics``). This module preserves the Faire qualification
contract and its fail-closed gates, but no longer contains independent
authoritative formulas.

Rules preserved:
  * Decimal for all authoritative money math (delegated to canonical engine).
  * Unknown fee/cost is NEVER treated as zero; a required unknown yields an
    unresolved result the caller cannot pass.
  * Fee-confidence gate: FEE_UNKNOWN cannot pass.
  * Contribution profit != ROI != margin != markup (distinct canonical outputs).

Invoice-path / eligibility / exact-pack gates live in ``qualification.py`` and
are unchanged; Faire discovery never establishes Amazon eligibility, invoice
acceptance, brand authorization, or purchase readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from .enums import FeeConfidence

try:  # run as `foundation.*` (cwd = Northstar_backend)
    from foundation.economics import EconomicsInput, compute
    from foundation.economics.enums import ProvenanceClass
except ImportError:  # run as `Northstar_backend.faire_research.*`
    from ..foundation.economics import EconomicsInput, compute
    from ..foundation.economics.enums import ProvenanceClass

CENT = Decimal("0.01")


def _d(x) -> Optional[Decimal]:
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeeInputs:
    referral_fee: Optional[Decimal] = None
    fba_fulfillment_fee: Optional[Decimal] = None
    inbound_fba_per_unit: Optional[Decimal] = None
    prep_label_per_unit: Optional[Decimal] = None
    storage_alloc_per_unit: Optional[Decimal] = None
    advertising_reserve_per_unit: Optional[Decimal] = None
    return_reserve_per_unit: Optional[Decimal] = None
    other_per_unit: Optional[Decimal] = None
    confidence: FeeConfidence = FeeConfidence.FEE_UNKNOWN
    notes: str = ""


@dataclass(frozen=True)
class LandedCostInputs:
    wholesale_case_cost: Optional[Decimal] = None
    supplier_shipping: Optional[Decimal] = None
    nonrecoverable_tax: Optional[Decimal] = None
    duties: Optional[Decimal] = None
    receiving_cost: Optional[Decimal] = None
    case_level_prep_cost: Optional[Decimal] = None
    verified_sellable_units: Optional[int] = None
    notes: str = ""


@dataclass
class EconomicsResult:
    resolved: bool
    reasons: List[str] = field(default_factory=list)
    landed_unit_cost: Optional[Decimal] = None
    contribution_profit: Optional[Decimal] = None
    roi_pct: Optional[Decimal] = None
    margin_pct: Optional[Decimal] = None
    invested_cost_per_unit: Optional[Decimal] = None
    fee_confidence: FeeConfidence = FeeConfidence.FEE_UNKNOWN
    breakdown: Dict[str, Optional[Decimal]] = field(default_factory=dict)


DEFAULT_MIN_CONTRIBUTION_PROFIT = Decimal("5.00")
DEFAULT_MIN_ROI_PCT = Decimal("30")
DEFAULT_SECONDARY_ROI_FLOOR_PCT = Decimal("20")
DEFAULT_MIN_MARGIN_PCT = Decimal("15")


def landed_unit_cost(inputs: LandedCostInputs) -> Optional[Decimal]:
    """(case cost + shipping + tax + duties + receiving + case prep) / verified
    sellable units. Returns None when any required component is unknown or units
    is missing/zero. This is cost normalization, not a fee formula."""
    units = inputs.verified_sellable_units
    if not units or units <= 0:
        return None
    parts = [inputs.wholesale_case_cost, inputs.supplier_shipping,
             inputs.nonrecoverable_tax, inputs.duties,
             inputs.receiving_cost, inputs.case_level_prep_cost]
    values: List[Decimal] = []
    for p in parts:
        d = _d(p)
        if d is None:
            return None
        values.append(d)
    return sum(values, Decimal("0")) / Decimal(units)


def contribution_profit(
    amazon_sale_price,
    landed_unit_cost_value,
    fees: FeeInputs,
    *,
    min_profit: Decimal = DEFAULT_MIN_CONTRIBUTION_PROFIT,
    min_roi_pct: Decimal = DEFAULT_MIN_ROI_PCT,
    min_margin_pct: Decimal = DEFAULT_MIN_MARGIN_PCT,
) -> EconomicsResult:
    """Contribution profit/ROI/margin via the canonical engine.

    Fail-closed gates are preserved: any unknown required input, or FEE_UNKNOWN,
    yields resolved=False and the caller cannot pass."""
    price = _d(amazon_sale_price)
    landed = _d(landed_unit_cost_value)
    reasons: List[str] = []

    fee_parts = {
        "referral_fee": _d(fees.referral_fee),
        "fba_fulfillment_fee": _d(fees.fba_fulfillment_fee),
        "inbound_fba_per_unit": _d(fees.inbound_fba_per_unit),
        "prep_label_per_unit": _d(fees.prep_label_per_unit),
        "storage_alloc_per_unit": _d(fees.storage_alloc_per_unit),
        "advertising_reserve_per_unit": _d(fees.advertising_reserve_per_unit),
        "return_reserve_per_unit": _d(fees.return_reserve_per_unit),
        "other_per_unit": _d(fees.other_per_unit),
    }

    if price is None:
        reasons.append("amazon_sale_price unknown")
    if landed is None:
        reasons.append("landed_unit_cost unresolved (unknown case component or units)")
    if fees.confidence == FeeConfidence.FEE_UNKNOWN:
        reasons.append("fee_confidence FEE_UNKNOWN (cannot pass)")
    for name, v in fee_parts.items():
        if v is None:
            reasons.append("%s unknown (not treated as zero)" % name)

    if reasons:
        return EconomicsResult(resolved=False, reasons=reasons,
                               fee_confidence=fees.confidence, breakdown=fee_parts)

    # Delegate authoritative math to the canonical engine.
    out = compute(EconomicsInput(
        marketplace="amazon.com", currency="USD",
        selling_price=price, acquisition_cost=landed,
        referral_fee_amount=fee_parts["referral_fee"],
        fba_fulfillment_fee=fee_parts["fba_fulfillment_fee"],
        inbound_freight=fee_parts["inbound_fba_per_unit"],
        prep_cost=fee_parts["prep_label_per_unit"],
        storage_allocation=fee_parts["storage_alloc_per_unit"],
        refund_return_reserve=fee_parts["return_reserve_per_unit"],
        other_marketplace_fees=fee_parts["other_per_unit"],
        advertising_cost=fee_parts["advertising_reserve_per_unit"],
        provenance=ProvenanceClass.ESTIMATED.value,
    ))

    profit = out.contribution_profit_after_ads
    roi = out.roi_on_invested_cost
    margin = out.margin_on_revenue
    invested = out.landed_inventory_cost
    roi_pct = (roi * Decimal("100")) if roi is not None else None
    margin_pct = (margin * Decimal("100")) if margin is not None else None

    result = EconomicsResult(
        resolved=profit is not None,
        landed_unit_cost=_q(landed),
        contribution_profit=(_q(profit) if profit is not None else None),
        roi_pct=(roi_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if roi_pct is not None else None),
        margin_pct=(margin_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if margin_pct is not None else None),
        invested_cost_per_unit=(_q(invested) if invested is not None else None),
        fee_confidence=fees.confidence,
        breakdown=fee_parts,
    )
    if profit is not None and profit < min_profit:
        result.reasons.append("contribution_profit %.2f < %.2f" % (profit, min_profit))
    if roi_pct is not None and roi_pct < min_roi_pct:
        result.reasons.append("roi %.2f%% < %.2f%%" % (roi_pct, min_roi_pct))
    if margin_pct is not None and margin_pct < min_margin_pct:
        result.reasons.append("margin %.2f%% < %.2f%%" % (margin_pct, min_margin_pct))
    return result


def downside_scenarios(
    amazon_sale_price,
    landed_unit_cost_value,
    fees: FeeInputs,
    declines_pct=(Decimal("0"), Decimal("5"), Decimal("10"), Decimal("15")),
) -> List[Dict[str, Optional[Decimal]]]:
    """Contribution profit / ROI at price declines, via the adapter."""
    price = _d(amazon_sale_price)
    out: List[Dict[str, Optional[Decimal]]] = []
    if price is None:
        return out
    for pct in declines_pct:
        factor = (Decimal("100") - Decimal(str(pct))) / Decimal("100")
        scenario_price = price * factor
        scenario_fees = FeeInputs(
            referral_fee=(_d(fees.referral_fee) * factor) if fees.referral_fee is not None else None,
            fba_fulfillment_fee=fees.fba_fulfillment_fee,
            inbound_fba_per_unit=fees.inbound_fba_per_unit,
            prep_label_per_unit=fees.prep_label_per_unit,
            storage_alloc_per_unit=fees.storage_alloc_per_unit,
            advertising_reserve_per_unit=fees.advertising_reserve_per_unit,
            return_reserve_per_unit=fees.return_reserve_per_unit,
            other_per_unit=fees.other_per_unit,
            confidence=fees.confidence,
        )
        r = contribution_profit(scenario_price, landed_unit_cost_value, scenario_fees)
        out.append({"decline_pct": Decimal(str(pct)), "sale_price": _q(scenario_price),
                    "contribution_profit": r.contribution_profit, "roi_pct": r.roi_pct,
                    "resolved": r.resolved})
    return out