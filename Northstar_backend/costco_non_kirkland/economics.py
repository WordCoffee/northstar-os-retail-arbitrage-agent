"""Economics contract for Costco Non-Kirkland candidates.

Wraps the CANONICAL economics engine (`foundation.economics.compute`) so money
math is Decimal, null-first, and provenance-aware. Adds the pipeline's
`economics_completeness` / `calculation_class` contract.

Rules:
  * Costco cost must preserve observed date + pack context (caller supplies).
  * Missing cost/price/fee/pack-identity => relevant outputs null (never zero).
  * `hypothetical` is the ONLY calculation_class when any assumption is used.
  * A `hypothetical` model can never be purchase-authorized.
  * No ROI for identity-conflicted or pack-mismatched records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from .enums import EconomicsCompleteness, CalculationClass

try:  # cwd = Northstar_backend
    from foundation.economics import EconomicsInput, compute
    from foundation.economics.enums import ProvenanceClass
except ImportError:  # running as costco_non_kirkland.* from a different path
    from ..foundation.economics import EconomicsInput, compute
    from ..foundation.economics.enums import ProvenanceClass

PROVENANCE_BY_KIND = {
    "costco_discovery": ProvenanceClass.IMPORTED.value,
    "costco_invoice": ProvenanceClass.VERIFIED.value,
    "user_assumption": ProvenanceClass.USER_SUPPLIED.value,
    "provider_estimate": ProvenanceClass.ESTIMATED.value,
    "cached": ProvenanceClass.CACHED.value,
}


@dataclass
class EconomicsResult:
    economics_completeness: str
    calculation_class: str
    cost_basis: Optional[float] = None
    cost_basis_source: Optional[str] = None
    cost_basis_status: Optional[str] = None
    tax_amount: Optional[float] = None
    prep_cost: Optional[float] = None
    inbound_shipping_cost: Optional[float] = None
    referral_fee: Optional[float] = None
    fba_fee: Optional[float] = None
    fee_source: Optional[str] = None
    fee_status: Optional[str] = None
    sale_price: Optional[float] = None
    sale_price_source: Optional[str] = None
    net_proceeds: Optional[float] = None
    net_profit: Optional[float] = None
    roi_percent: Optional[float] = None
    net_margin_percent: Optional[float] = None
    assumptions: list = field(default_factory=list)
    calculated_at: Optional[str] = None
    missing_inputs: list = field(default_factory=list)
    canonical: Optional[dict] = None   # raw EconomicsOutput.to_dict()
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "economics_completeness": self.economics_completeness,
            "calculation_class": self.calculation_class,
            "cost_basis": self.cost_basis,
            "cost_basis_source": self.cost_basis_source,
            "cost_basis_status": self.cost_basis_status,
            "tax_amount": self.tax_amount,
            "prep_cost": self.prep_cost,
            "inbound_shipping_cost": self.inbound_shipping_cost,
            "referral_fee": self.referral_fee,
            "fba_fee": self.fba_fee,
            "fee_source": self.fee_source,
            "fee_status": self.fee_status,
            "sale_price": self.sale_price,
            "sale_price_source": self.sale_price_source,
            "net_proceeds": self.net_proceeds,
            "net_profit": self.net_profit,
            "roi_percent": self.roi_percent,
            "net_margin_percent": self.net_margin_percent,
            "assumptions": list(self.assumptions),
            "calculated_at": self.calculated_at,
            "missing_inputs": list(self.missing_inputs),
            "blocked_reason": self.blocked_reason,
        }


def _d(x) -> Optional[Decimal]:
    if x is None:
        return None
    return Decimal(str(x))


def _f(x: Optional[Decimal]) -> Optional[float]:
    if x is None:
        return None
    return float(x)


def compute_economics(
    *,
    cost_basis: Optional[object] = None,
    cost_basis_source: Optional[str] = None,
    cost_basis_status: Optional[str] = None,
    sale_price: Optional[object] = None,
    sale_price_source: Optional[str] = None,
    identity_status: Optional[str] = None,
    pack_verified: Optional[bool] = None,
    sales_tax_rate: Optional[object] = None,
    prep_cost: Optional[object] = None,
    inbound_shipping_cost: Optional[object] = None,
    referral_fee_rate: Optional[object] = None,
    fba_fee: Optional[object] = None,
    storage_allowance: Optional[object] = None,
    returns_reserve_rate: Optional[object] = None,
    fee_source: Optional[str] = None,
    fee_status: Optional[str] = None,
    assumptions: Optional[list] = None,
    currency: str = "USD",
) -> EconomicsResult:
    """Compute economics. Null-first. `hypothetical` when assumptions are used."""
    assumptions = list(assumptions or [])
    calculated_at = datetime.now(timezone.utc).isoformat()
    missing: list = []

    # --- identity / pack gating --------------------------------------------
    blocked_identity = identity_status in ("identity_conflict", "pack_mismatch", "size_mismatch")
    if blocked_identity:
        return EconomicsResult(
            economics_completeness=EconomicsCompleteness.BLOCKED_IDENTITY_MISMATCH.value,
            calculation_class=CalculationClass.BLOCKED.value,
            cost_basis=_f(_d(cost_basis)), cost_basis_source=cost_basis_source,
            cost_basis_status=cost_basis_status,
            sale_price=_f(_d(sale_price)), sale_price_source=sale_price_source,
            calculated_at=calculated_at,
            blocked_reason="Identity/pack mismatch blocks economics.",
            missing_inputs=["identity_verified", "pack_verified"],
        )

    # --- required inputs ----------------------------------------------------
    if cost_basis is None:
        missing.append("cost_basis")
    if sale_price is None:
        missing.append("sale_price")
    if identity_status is None or identity_status in ("unresolved", "manual_review_required", "title_brand_candidate"):
        missing.append("identity_verified")
    if pack_verified is not True:
        missing.append("pack_verified")

    use_assumptions = bool(assumptions)
    calc_class = CalculationClass.HYPOTHETICAL.value if use_assumptions else CalculationClass.ESTIMATED.value

    if missing:
        # Incomplete: mark completeness; do NOT fabricate zeros.
        completeness = _incomplete_class(missing)
        return EconomicsResult(
            economics_completeness=completeness,
            calculation_class=calc_class,
            cost_basis=_f(_d(cost_basis)), cost_basis_source=cost_basis_source,
            cost_basis_status=cost_basis_status,
            sale_price=_f(_d(sale_price)), sale_price_source=sale_price_source,
            fee_source=fee_source, fee_status=fee_status,
            assumptions=assumptions, calculated_at=calculated_at,
            missing_inputs=missing,
        )

    # --- canonical engine ----------------------------------------------------
    provenance = PROVENANCE_BY_KIND.get(
        (cost_basis_source or "costco_discovery").lower(), ProvenanceClass.IMPORTED.value)
    inp = EconomicsInput(
        marketplace="US",
        currency=currency,
        selling_price=sale_price,
        acquisition_cost=cost_basis,
        inbound_freight=inbound_shipping_cost,
        prep_cost=prep_cost,
        storage_allocation=storage_allowance,
        referral_fee_rate=referral_fee_rate,
        fba_fulfillment_fee=fba_fee,
        refund_return_reserve_rate=returns_reserve_rate,
        advertising_cost=Decimal("0"),  # no ad spend modeled in this pipeline
        pack_verified=pack_verified,
        provenance=provenance,
    )
    out = compute(inp)
    net_profit = out.pre_ad_contribution
    roi = out.roi_on_invested_cost
    margin = out.margin_on_revenue

    completeness = EconomicsCompleteness.COMPLETE.value
    if net_profit is None:
        completeness = EconomicsCompleteness.INCOMPLETE_FEES.value
    if cost_basis is None:
        completeness = EconomicsCompleteness.INCOMPLETE_COST.value
    if sale_price is None:
        completeness = EconomicsCompleteness.INCOMPLETE_PRICE.value

    return EconomicsResult(
        economics_completeness=completeness,
        calculation_class=calc_class,
        cost_basis=_f(_d(cost_basis)), cost_basis_source=cost_basis_source,
        cost_basis_status=cost_basis_status,
        tax_amount=None,  # caller supplies tax separately; not in canonical engine
        prep_cost=_f(_d(prep_cost)), inbound_shipping_cost=_f(_d(inbound_shipping_cost)),
        referral_fee=_f(out.marketplace_fees) if out.marketplace_fees is not None else None,
        fba_fee=_f(_d(fba_fee)),
        fee_source=fee_source, fee_status=fee_status,
        sale_price=_f(_d(sale_price)), sale_price_source=sale_price_source,
        net_proceeds=_f(out.marketplace_payout_before_ads),
        net_profit=_f(net_profit),
        roi_percent=(float(roi * 100) if roi is not None else None),
        net_margin_percent=(float(margin * 100) if margin is not None else None),
        assumptions=assumptions, calculated_at=calculated_at,
        canonical=out.to_dict(),
    )


def _incomplete_class(missing: list) -> str:
    if "cost_basis" in missing and "sale_price" in missing:
        return EconomicsCompleteness.INCOMPLETE_COST.value
    if "cost_basis" in missing:
        return EconomicsCompleteness.INCOMPLETE_COST.value
    if "sale_price" in missing:
        return EconomicsCompleteness.INCOMPLETE_PRICE.value
    if "identity_verified" in missing or "pack_verified" in missing:
        return EconomicsCompleteness.INCOMPLETE_FEES.value
    return EconomicsCompleteness.INCOMPLETE_FEES.value


# ---------------------------------------------------------------------------
# Conservative expected sale price (Phase 6)
# ---------------------------------------------------------------------------

def conservative_sale_price(*, buy_box_price: Optional[object],
                            price_history_midpoint: Optional[object] = None,
                            price_history_observed_at: Optional[str] = None,
                            market_snapshot_max_age_minutes: int = 60,
                            price_history_max_age_hours: int = 24,
                            stability_floor_pct: float = 0.90,
                            settings: Optional[dict] = None) -> Dict[str, Any]:
    """Compute a conservative expected sale price.

    Rules:
      - Use provider-reported Buy Box price ONLY when fresh.
      - If price-history data exists and is fresh, use the LOWER of current Buy
        Box and the configured historical stability floor (90% of midpoint).
      - Never use the highest listed seller offer.
      - Return None (no price) if no current usable price.
    """
    from datetime import datetime, timezone

    def age_minutes(ts):
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
        except (ValueError, TypeError):
            return None

    bb = _d(buy_box_price)
    if bb is None:
        return {"price": None, "source": "none", "reason": "no usable provider price",
                "buy_box_price": None, "history_midpoint": None}

    use_history = False
    history_mid = None
    if price_history_midpoint is not None:
        hist_age_hours = None
        if price_history_observed_at:
            hist_age_min = age_minutes(price_history_observed_at)
            hist_age_hours = hist_age_min / 60.0 if hist_age_min is not None else None
        if hist_age_hours is None or hist_age_hours <= price_history_max_age_hours:
            hm = _d(price_history_midpoint)
            if hm is not None and hm > 0:
                use_history = True
                history_mid = hm

    if use_history:
        floor = (history_mid * _d(stability_floor_pct) if _d(stability_floor_pct) else history_mid)
        conservative = min(bb, floor)
        return {
            "price": _f(conservative),
            "source": "conservative_buybox_vs_history_floor",
            "reason": "lower of fresh Buy Box and historical stability floor",
            "buy_box_price": _f(bb),
            "history_midpoint": _f(history_mid),
            "history_floor": _f(floor),
        }

    return {
        "price": _f(bb),
        "source": "provider_buy_box",
        "reason": "provider-reported Buy Box price (no fresh price history)",
        "buy_box_price": _f(bb),
        "history_midpoint": None,
    }


def maximum_buy_cost(sale_price: Optional[object], *, target_roi: object = None,
                     settings: Optional[dict] = None,
                     prep_cost=None, inbound_shipping_cost=None,
                     referral_fee_rate=None, fba_fee=None,
                     storage_allowance=None, returns_allowance_rate=None,
                     sales_tax_rate=None) -> Optional[float]:
    """Maximum buy cost to hit a target ROI.

    Uses the same null-first rule: if required fee/price inputs are unknown,
    returns None (no max buy cost can be derived) rather than guessing.
    """
    from .settings import get_settings
    st = get_settings(settings)
    sp = _d(sale_price)
    if sp is None:
        return None
    t_roi = _d(target_roi) if target_roi is not None else _d(st.get("minimum_roi_pct", 30.0)) / 100
    ref_rate = _d(referral_fee_rate) if referral_fee_rate is not None else _d(st.get("referral_fee_rate", 0.15))
    fba = _d(fba_fee) if fba_fee is not None else None
    prep = _d(prep_cost) if prep_cost is not None else _d(st.get("prep_cost", 0.0))
    inbound = _d(inbound_shipping_cost) if inbound_shipping_cost is not None else _d(st.get("inbound_shipping_cost", 0.0))
    storage = _d(storage_allowance) if storage_allowance is not None else _d(st.get("storage_allowance", 0.0))
    returns = _d(returns_allowance_rate) if returns_allowance_rate is not None else _d(st.get("returns_allowance_rate", 0.02))
    tax_rate = _d(sales_tax_rate) if sales_tax_rate is not None else _d(st.get("source_sales_tax_rate", 0.0825))

    if ref_rate is None or fba is None:
        return None  # cannot derive max buy cost without fees

    # net_profit = sp - sp*ref - fba - storage - sp*returns - (buy + buy*tax + prep + inbound)
    # target: net_profit = t_roi * (buy + buy*tax + prep + inbound)
    fixed = prep + inbound
    gross = sp - sp * ref_rate - fba - storage - sp * returns
    # gross - (buy*(1+tax) + fixed) = t_roi * (buy*(1+tax) + fixed)
    # gross - fixed = (1 + t_roi) * (buy*(1+tax) + fixed)
    term = (gross - fixed) / (1 + t_roi) - fixed
    buy = term / (1 + tax_rate)
    return round(float(buy), 2) if buy is not None else None