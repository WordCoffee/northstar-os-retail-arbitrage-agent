"""Scanner end-to-end canonical economics (Phase 1C-03R).

Proves the active scanner economics path returns canonical economics: formula
version, readiness, canonical net, and canonical ROI-on-invested-cost, while
preserving legacy response field names. No provider/network access.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # Northstar_backend

from Northstar_backend.foundation.economics.versions import FORMULA_VERSION  # noqa: E402


def _fee_engine():
    import fee_engine  # top-level module under Northstar_backend
    return fee_engine


def test_complete_scanner_economics_is_canonical():
    fe = _fee_engine()
    out = fe.calculate_unit_economics(
        {"amazon_price": 42.00, "listing_fba_fee": 5.55},
        {"costco_cost": 17.99, "costco_cost_basis": "verified"})
    assert out["formula_version"] == FORMULA_VERSION
    assert out["readiness"] == "COMPLETE_ESTIMATED"
    assert out["net_profit"] is not None
    assert out["roi_on_invested_cost"] is not None
    assert out["roi_denominator_label"] == "landed_inventory_cost"


def test_missing_price_remains_incomplete_not_zero():
    fe = _fee_engine()
    out = fe.calculate_unit_economics({"amazon_price": None}, {"costco_cost": 17.99})
    assert out["net_profit"] is None
    assert out["formula_version"] == FORMULA_VERSION


def test_missing_cogs_remains_incomplete_not_zero():
    fe = _fee_engine()
    out = fe.calculate_unit_economics({"amazon_price": 42.00}, {"costco_cost": None})
    assert out["net_profit"] is None
    assert out["roi_pct"] is None


def test_no_formula_version_missing_on_any_branch():
    fe = _fee_engine()
    for prod, costco in (
        ({"amazon_price": 42.0, "listing_fba_fee": 5.55}, {"costco_cost": 17.99}),
        ({"amazon_price": 42.0}, {"costco_cost": 17.99}),          # provisional (no fba)
        ({"amazon_price": None}, {"costco_cost": 17.99}),          # missing price
        ({"amazon_price": 42.0}, {"costco_cost": None}),           # missing cogs
    ):
        out = fe.calculate_unit_economics(prod, costco)
        assert out.get("formula_version") == FORMULA_VERSION