"""Historical Minoxidil benchmark/assumption vectors (Phase 1C-03).

These are EXPLICIT benchmark/test vectors — NOT current live market data, and the
two sets must never be combined or presented as live.

The original records supply only aggregated payout/profit assumptions, not a fee
component breakdown. The engine therefore reports the IMPLIED total marketplace
fee (= selling_price - payout_assumption) and does not invent component splits.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .versions import (MINOXIDIL_LEGACY_CONTEXT_ASSUMPTION,
                       MINOXIDIL_NEWER_CHAT_ASSUMPTION)
from .inputs import EconomicsInput
from .enums import ProvenanceClass


@dataclass(frozen=True)
class BenchmarkVector:
    label: str
    cost: Decimal
    selling_price: Decimal
    payout_assumption: Decimal
    profit_assumption: Decimal

    @property
    def implied_marketplace_fee(self) -> Decimal:
        return self.selling_price - self.payout_assumption


MINOXIDIL_LEGACY = BenchmarkVector(
    label=MINOXIDIL_LEGACY_CONTEXT_ASSUMPTION,
    cost=Decimal("17.99"), selling_price=Decimal("37.99"),
    payout_assumption=Decimal("25.51"), profit_assumption=Decimal("7.52"))

MINOXIDIL_NEWER = BenchmarkVector(
    label=MINOXIDIL_NEWER_CHAT_ASSUMPTION,
    cost=Decimal("17.99"), selling_price=Decimal("42.00"),
    payout_assumption=Decimal("29.52"), profit_assumption=Decimal("11.53"))


def benchmark_input(vector: BenchmarkVector, *, use_implied_fee: bool = False) -> EconomicsInput:
    """Build an engine input from a benchmark vector.

    The implied total fee is supplied ONLY when explicitly requested, as a single
    aggregate amount (referral_fee_amount), with no fabricated component split.
    """
    referral = vector.implied_marketplace_fee if use_implied_fee else None
    return EconomicsInput(
        marketplace="amazon.com", currency="USD",
        selling_price=vector.selling_price, acquisition_cost=vector.cost,
        referral_fee_amount=referral, fba_fulfillment_fee=(Decimal("0") if use_implied_fee else None),
        advertising_cost=Decimal("0") if use_implied_fee else None,
        provenance=ProvenanceClass.USER_SUPPLIED.value,
    )