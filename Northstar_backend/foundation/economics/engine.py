"""Canonical economics engine (Phase 1C-03). Pure, deterministic, Decimal-based."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from .enums import Readiness, ProvenanceClass, CashBasis
from .inputs import EconomicsInput
from .outputs import EconomicsOutput
from .money import to_decimal, safe_div, quantize_money, quantize_rate

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_VERIFIED = {ProvenanceClass.VERIFIED.value}
_KNOWN_Q = {ProvenanceClass.IMPORTED.value, ProvenanceClass.CACHED.value,
            ProvenanceClass.ESTIMATED.value, ProvenanceClass.USER_SUPPLIED.value,
            ProvenanceClass.DERIVED.value}


def compute(inp: EconomicsInput) -> EconomicsOutput:
    out = EconomicsOutput(currency=inp.currency, marketplace=inp.marketplace)
    missing: list[str] = []
    expl: list[str] = []
    rounding = inp.rounding

    qty = Decimal(inp.quantity or 1)
    price = inp.d("selling_price")
    acq = inp.d("acquisition_cost")

    # ---- gross revenue ------------------------------------------------------
    gross = price * qty if price is not None else None
    if gross is not None:
        expl.append(f"gross_revenue = selling_price({price}) x qty({qty})")

    # ---- marketplace fees ---------------------------------------------------
    ref_amt = inp.d("referral_fee_amount")
    ref_rate = inp.d("referral_fee_rate")
    referral: Optional[Decimal] = None
    if ref_amt is not None:
        referral = ref_amt * qty
    elif ref_rate is not None and price is not None:
        referral = price * qty * ref_rate
    fba = inp.d("fba_fulfillment_fee")
    fba_total = fba * qty if fba is not None else None
    closing = inp.d("closing_fee") or Decimal("0")
    var_closing = inp.d("variable_closing_fee") or Decimal("0")
    other = inp.d("other_marketplace_fees") or Decimal("0")

    fees: Optional[Decimal] = None
    if referral is not None and fba_total is not None:
        fees = referral + fba_total + closing + var_closing + other

    payout = (gross - fees) if (gross is not None and fees is not None) else None

    # ---- landed inventory cost (per-unit inputs -> total for qty) -----------
    landed: Optional[Decimal] = None
    if acq is not None:
        per_unit = (acq + (inp.d("inbound_freight") or Decimal("0"))
                    + (inp.d("prep_cost") or Decimal("0"))
                    + (inp.d("label_cost") or Decimal("0"))
                    + (inp.d("duties") or Decimal("0"))
                    + (inp.d("storage_allocation") or Decimal("0")))
        landed = per_unit * qty

    # ---- reserves -----------------------------------------------------------
    reserve = Decimal("0")
    rr = inp.d("refund_return_reserve")
    rr_rate = inp.d("refund_return_reserve_rate")
    if rr is not None:
        reserve += rr * qty
    elif rr_rate is not None and gross is not None:
        reserve += gross * rr_rate
    if inp.d("damage_reserve") is not None:
        reserve += inp.d("damage_reserve")

    # ---- pre-ad contribution ------------------------------------------------
    pre_ad = None
    if gross is not None and fees is not None and landed is not None:
        pre_ad = gross - fees - landed - reserve

    # ---- advertising --------------------------------------------------------
    ad_cost = inp.d("advertising_cost")
    ad_rev = inp.d("ad_attributed_revenue")
    if ad_rev is None and gross is not None:
        ad_rev = gross  # per-unit ad-attributed revenue default (documented)
    after_ads = (pre_ad - ad_cost) if (pre_ad is not None and ad_cost is not None) else None

    # ---- ratios -------------------------------------------------------------
    roi = safe_div(after_ads, landed)
    margin = safe_div(after_ads, gross)
    markup = safe_div(after_ads, landed)
    be_acos = safe_div(pre_ad, ad_rev) if (ad_rev is not None and ad_rev > 0) else None

    req_profit = inp.d("required_post_ad_profit")
    target_acos = inp.d("target_acos")
    if target_acos is None and req_profit is not None and ad_rev not in (None, Decimal("0")):
        target_acos = safe_div(pre_ad - req_profit, ad_rev)
    tacos = safe_div(ad_cost, inp.d("total_revenue"))
    ctr = safe_div(Decimal(inp.clicks) if inp.clicks is not None else None,
                   Decimal(inp.impressions) if inp.impressions is not None else None)
    cvr = safe_div(Decimal(inp.orders) if inp.orders is not None else None,
                   Decimal(inp.clicks) if inp.clicks is not None else None)
    cpc = safe_div(ad_cost, Decimal(inp.clicks) if inp.clicks is not None else None)
    roas = safe_div(ad_rev, ad_cost)
    max_cpc = None
    if cvr is not None and pre_ad is not None:
        per_order = pre_ad - (req_profit or Decimal("0"))
        max_cpc = per_order * cvr

    # ---- cash available for reinvestment (separate metric) ------------------
    cash = None
    basis = inp.cash_basis or CashBasis.MARKETPLACE_PAYOUT.value
    if basis == CashBasis.MARKETPLACE_PAYOUT.value:
        cash = payout
    elif basis == CashBasis.USER_DEFINED.value:
        cash = inp.d("reinvestment_policy_amount")
    elif basis == CashBasis.CONTRIBUTION_AFTER_REPLACEMENT.value:
        cash = (after_ads - landed) if (after_ads is not None and landed is not None) else None
    # SETTLEMENT basis is only knowable from settlement data -> None (unknown)

    # ---- missing inputs -----------------------------------------------------
    if price is None:
        missing.append("selling_price")
    if acq is None:
        missing.append("acquisition_cost")
    if referral is None:
        missing.append("referral_fee")
    if fba_total is None:
        missing.append("fba_fulfillment_fee")
    if ad_cost is None:
        missing.append("advertising_cost")
    if inp.d("total_revenue") is None:
        missing.append("total_revenue")

    # ---- readiness ----------------------------------------------------------
    out.readiness = _classify(inp, price, acq, referral, fba_total)
    out.missing_inputs = missing
    out.purchase_ready = (
        out.readiness == Readiness.COMPLETE_VERIFIED.value
        and bool(inp.sourcing_verified) and bool(inp.documentation_verified)
        and bool(inp.eligibility_confirmed))

    # ---- assign outputs (quantized) ----------------------------------------
    out.gross_revenue = quantize_money(gross, rounding)
    out.marketplace_fees = quantize_money(fees, rounding)
    out.marketplace_payout_before_ads = quantize_money(payout, rounding)
    out.landed_inventory_cost = quantize_money(landed, rounding)
    out.pre_ad_contribution = quantize_money(pre_ad, rounding)
    out.advertising_cost = quantize_money(ad_cost, rounding)
    out.contribution_profit_after_ads = quantize_money(after_ads, rounding)
    out.roi_on_invested_cost = quantize_rate(roi, rounding)
    out.margin_on_revenue = quantize_rate(margin, rounding)
    out.markup_on_cost = quantize_rate(markup, rounding)
    out.break_even_acos = quantize_rate(be_acos, rounding)
    out.target_acos = quantize_rate(target_acos, rounding)
    out.tacos = quantize_rate(tacos, rounding)
    out.ctr = quantize_rate(ctr, rounding)
    out.cvr = quantize_rate(cvr, rounding)
    out.cpc = quantize_money(cpc, rounding)
    out.roas = quantize_rate(roas, rounding)
    out.maximum_cpc = quantize_money(max_cpc, rounding)
    out.cash_available_for_reinvestment = quantize_money(cash, rounding)

    expl.append(f"marketplace_fees = referral({referral}) + fba({fba_total}) + closing({closing}) + variable({var_closing}) + other({other})")
    expl.append(f"pre_ad_contribution = gross - fees - landed - reserves({reserve})")
    expl.append(f"roi denominator = landed_inventory_cost({landed}); cash basis = {basis}")
    out.explanation = expl
    return out


def _classify(inp: EconomicsInput, price, acq, referral, fba_total) -> str:
    if inp.currency and inp.cost_currency and inp.currency != inp.cost_currency:
        return Readiness.CURRENCY_MISMATCH.value
    if inp.currency and not _CURRENCY_RE.match(inp.currency or ""):
        return Readiness.CURRENCY_MISMATCH.value
    if inp.pack_count is not None and inp.pack_verified is False:
        return Readiness.PACK_CONFIGURATION_UNRESOLVED.value
    if inp.stale:
        return Readiness.PROVENANCE_STALE.value
    if price is None:
        return Readiness.SELLING_PRICE_MISSING.value
    if acq is None:
        return Readiness.ACQUISITION_COST_MISSING.value
    if referral is None:
        return Readiness.REFERRAL_FEE_UNKNOWN.value
    if fba_total is None:
        return Readiness.FULFILLMENT_FEE_UNKNOWN.value
    if inp.provenance in _VERIFIED:
        return Readiness.COMPLETE_VERIFIED.value
    if inp.provenance in _KNOWN_Q:
        return Readiness.COMPLETE_ESTIMATED.value
    return Readiness.SOURCE_UNVERIFIED.value


class EconomicsEngine:
    """Stateless facade over the canonical compute()."""

    version = None  # set below

    def compute(self, inp: EconomicsInput) -> EconomicsOutput:
        return compute(inp)


from .versions import FORMULA_VERSION as _FV  # noqa: E402
EconomicsEngine.version = _FV