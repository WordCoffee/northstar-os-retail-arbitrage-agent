"""Decimal money handling and rounding policy (Phase 1C-03).

Money is NEVER computed with binary floats. Internal precision is high; outputs
are quantized with explicit rounding modes; negative zero is normalized.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN, ROUND_UP
from decimal import getcontext, localcontext
from typing import Optional

from .enums import RoundingMode

# Internal working precision (more than enough for product economics).
INTERNAL_PRECISION = 34

CURRENCY_QUANTUM = Decimal("0.01")     # money -> 2 dp
RATE_QUANTUM = Decimal("0.0001")       # rates/ratios -> 4 dp
PERCENT_QUANTUM = Decimal("0.01")      # percentages -> 2 dp

_ROUNDING = {
    RoundingMode.HALF_UP: ROUND_HALF_UP,
    RoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
    RoundingMode.DOWN: ROUND_DOWN,
    RoundingMode.UP: ROUND_UP,
}


def _init_ctx() -> None:
    getcontext().prec = INTERNAL_PRECISION


_init_ctx()


def to_decimal(value) -> Optional[Decimal]:
    """Coerce to Decimal WITHOUT introducing float error. None -> None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # guard: bool is int subclass; not a money value
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # never authoritative; convert via str to avoid binary artifacts
        return Decimal(str(value))
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


def _normalize_zero(d: Decimal) -> Decimal:
    return Decimal("0") if d == 0 else d


def quantize_money(value: Optional[Decimal], mode: RoundingMode = RoundingMode.HALF_UP) -> Optional[Decimal]:
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = INTERNAL_PRECISION
        return _normalize_zero(value.quantize(CURRENCY_QUANTUM, rounding=_ROUNDING[mode]))


def quantize_rate(value: Optional[Decimal], mode: RoundingMode = RoundingMode.HALF_UP) -> Optional[Decimal]:
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = INTERNAL_PRECISION
        return _normalize_zero(value.quantize(RATE_QUANTUM, rounding=_ROUNDING[mode]))


def quantize_percent(value: Optional[Decimal], mode: RoundingMode = RoundingMode.HALF_UP) -> Optional[Decimal]:
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = INTERNAL_PRECISION
        return _normalize_zero(value.quantize(PERCENT_QUANTUM, rounding=_ROUNDING[mode]))


def safe_div(numerator: Optional[Decimal], denominator: Optional[Decimal]) -> Optional[Decimal]:
    """Division that returns None (never raises) for unknown/zero denominators."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = INTERNAL_PRECISION
        return numerator / denominator


def money_str(value: Optional[Decimal]) -> Optional[str]:
    """Serialize money as a decimal string (for the frontend). None stays None."""
    q = quantize_money(value)
    return None if q is None else format(q, "f")


def ratio_str(value: Optional[Decimal]) -> Optional[str]:
    q = quantize_rate(value)
    return None if q is None else format(q, "f")


def percent_str(value: Optional[Decimal]) -> Optional[str]:
    q = quantize_percent(value)
    return None if q is None else format(q, "f")