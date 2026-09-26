"""Readiness classification facade (Phase 1C-03)."""
from __future__ import annotations

from .engine import _classify as _engine_classify
from .enums import Readiness
from .inputs import EconomicsInput
from .money import to_decimal

__all__ = ["Readiness", "classify"]


def classify(inp: EconomicsInput) -> str:
    qty = 1
    price = to_decimal(inp.selling_price)
    acq = to_decimal(inp.acquisition_cost)
    ref_amt = to_decimal(inp.referral_fee_amount)
    ref_rate = to_decimal(inp.referral_fee_rate)
    referral = ref_amt if ref_amt is not None else (ref_rate if (ref_rate is not None and price is not None) else None)
    fba = to_decimal(inp.fba_fulfillment_fee)
    return _engine_classify(inp, price, acq, referral, fba)