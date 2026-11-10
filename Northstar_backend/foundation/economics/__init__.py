"""Canonical economics engine (Phase 1C-03).

One authoritative, deterministic, Decimal-based economics engine. Pure functions;
no provider calls, no DB side effects, no frontend assumptions.

The module is intentionally self-contained under ``foundation.economics``.
"""
from .engine import EconomicsEngine, compute
from .inputs import EconomicsInput
from .outputs import EconomicsOutput
from .enums import Readiness, MetricName, RoundingMode
from .versions import FORMULA_VERSION

__all__ = [
    "EconomicsEngine", "compute", "EconomicsInput", "EconomicsOutput",
    "Readiness", "MetricName", "RoundingMode", "FORMULA_VERSION",
]