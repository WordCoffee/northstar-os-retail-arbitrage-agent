"""Tests for the Bojo economics tool (`margin_report`).

Offline: no network, no database, no model. The canonical engine is pure, so
the pass path runs it for real and the assertions pin real Decimal output; an
injected ``compute`` proves the seam.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bojo_tools import economics as econ  # noqa: E402
from bojo_tools.economics import TOOLS, margin_report  # noqa: E402

GOOD_INPUTS = {
    "selling_price": 34.99,
    "acquisition_cost": 12.00,
    "referral_fee_rate": 0.15,
    "fba_fulfillment_fee": 5.50,
    "advertising_cost": 1.00,
    "total_revenue": 34.99,
    "provenance": "user_supplied",
}


class FakeOutput:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


def test_tools_registry_exports_margin_report():
    assert set(TOOLS) == {"margin_report"}
    assert TOOLS["margin_report"] is margin_report


def test_margin_report_runs_the_canonical_engine():
    result = margin_report(GOOD_INPUTS)

    assert result["ok"] is True
    assert result["tool"] == "margin_report"
    data = result["data"]
    payload = data["economics"]

    # Real fee stack from foundation.economics: referral 15% + a $5.50 FBA fee.
    assert payload["gross_revenue"] == "34.99"
    assert payload["marketplace_fees"] == "10.75"
    assert payload["pre_ad_contribution"] == "12.24"
    assert payload["contribution_profit_after_ads"] == "11.24"
    assert payload["roi_on_invested_cost"] == "0.94"
    assert payload["margin_on_revenue"] == "0.32"
    assert payload["formula_version"]

    assert data["readiness"] == "COMPLETE_ESTIMATED"
    assert data["missing_inputs"] == []
    assert data["ignored_inputs"] == []
    assert payload["purchase_ready"] is False  # never granted by an estimate
    json.dumps(result)


def test_margin_report_injected_compute_is_used():
    seen = {}

    class FakeEngine:
        @staticmethod
        def engine(inp):
            seen["selling_price"] = inp.selling_price
            seen["acquisition_cost"] = inp.acquisition_cost
            return FakeOutput({"contribution_profit_after_ads": "9.99",
                               "readiness": "COMPLETE_VERIFIED",
                               "missing_inputs": []})

    result = margin_report(GOOD_INPUTS, compute=FakeEngine.engine)

    assert result["ok"] is True
    assert result["data"]["economics"]["contribution_profit_after_ads"] == "9.99"
    assert seen == {"selling_price": 34.99, "acquisition_cost": 12.0}


def test_margin_report_resolves_operator_shorthand():
    """Measured 2026-11-14: `{cost, price}` refused, and a bare `referral_fee` was dropped."""
    seen = {}

    class FakeEngine:
        @staticmethod
        def engine(inp):
            seen["selling_price"] = inp.selling_price
            seen["acquisition_cost"] = inp.acquisition_cost
            seen["referral_fee_amount"] = inp.referral_fee_amount
            return FakeOutput({"contribution_profit_after_ads": "9.99",
                               "readiness": "COMPLETE_ESTIMATED",
                               "missing_inputs": []})

    result = margin_report({"price": 24.0, "cost": 8.5, "referral_fee": 3.6},
                           compute=FakeEngine.engine)

    assert result["ok"] is True
    assert result["data"]["aliased_inputs"] == [
        {"from": "price", "to": "selling_price"},
        {"from": "cost", "to": "acquisition_cost"},
        {"from": "referral_fee", "to": "referral_fee_amount"},
    ]
    assert seen == {"selling_price": 24.0, "acquisition_cost": 8.5,
                    "referral_fee_amount": 3.6}
    assert result["data"]["ignored_inputs"] == []
    assert result["data"]["aliased_inputs"]


def test_a_canonical_input_wins_over_its_alias():
    seen = {}

    class FakeEngine:
        @staticmethod
        def engine(inp):
            seen["selling_price"] = inp.selling_price
            seen["acquisition_cost"] = inp.acquisition_cost
            return FakeOutput({"contribution_profit_after_ads": "9.99",
                               "readiness": "COMPLETE_ESTIMATED",
                               "missing_inputs": []})

    result = margin_report({"selling_price": 24.0, "price": 20.0, "cost": 8.5},
                           compute=FakeEngine.engine)

    assert result["ok"] is True
    assert seen["selling_price"] == 24.0
    assert result["data"]["ignored_inputs"] == ["price"]
    assert result["data"]["aliased_inputs"] == [{"from": "cost", "to": "acquisition_cost"}]


def test_shorthand_computes_a_real_margin_without_refusal():
    """The whole point: `{price, cost, referral_fee, fba_fee, ads}` must compute, not refuse."""
    result = margin_report({"price": 34.99, "cost": 12.0, "referral_fee": 5.25,
                            "fba_fee": 5.50, "ads": 1.0,
                            "provenance": "user_supplied"})
    assert result["ok"] is True, result
    payload = result["data"]["economics"]
    assert payload["contribution_profit_after_ads"] == "11.24"
    assert result["data"]["readiness"] == "COMPLETE_ESTIMATED"
    assert {row["from"] for row in result["data"]["aliased_inputs"]} == {
        "price", "cost", "referral_fee", "fba_fee", "ads"}


def test_registry_alias_hints_match_the_handler():
    """The registry's hints are not decoration: they must be the handler's own table."""
    from pathlib import Path

    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "ty" / "service_registry.json")
        .read_text(encoding="utf-8")
    )
    row = next(s for s in registry["services"] if s["id"] == "profitability")
    assert row["input_aliases"] == econ.INPUT_ALIASES
    assert "aliased_inputs" in row["input_aliases_note"]


def test_margin_report_drops_and_names_unknown_fields():
    result = margin_report({**GOOD_INPUTS, "listing_optimizer_thing": "ignored"})

    assert result["ok"] is True
    assert result["data"]["ignored_inputs"] == ["listing_optimizer_thing"]
    assert "listing_optimizer_thing" not in result["data"]["inputs_used"]


def test_margin_report_missing_required_number_is_a_business_failure():
    inputs = dict(GOOD_INPUTS)
    inputs.pop("acquisition_cost")

    result = margin_report(inputs)

    assert result == {
        "ok": False,
        "tool": "margin_report",
        "reason": "acquisition_cost is required to report a margin",
    }


def test_margin_report_incomplete_economics_is_a_business_failure():
    result = margin_report({"selling_price": 20.0, "acquisition_cost": 8.0})

    assert result["ok"] is False
    assert result["tool"] == "margin_report"
    assert result["reason"].startswith("the margin is not computable")
    assert "referral_fee" in result["reason"]
    assert "fba_fulfillment_fee" in result["reason"]


def test_margin_report_engine_error_is_reported_not_raised():
    def broken(inp):
        raise RuntimeError("engine exploded")

    result = margin_report(GOOD_INPUTS, compute=broken)

    assert result["ok"] is False
    assert result["reason"].startswith("economics engine failed: RuntimeError")


def test_margin_report_programmer_errors_raise():
    with pytest.raises(TypeError):
        margin_report("selling_price=20")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        margin_report({"selling_price": {"amount": 20}, "acquisition_cost": 8})
    with pytest.raises(TypeError):
        margin_report({**GOOD_INPUTS, "quantity": "one"})


def test_default_engine_is_the_real_canonical_economics_module():
    from foundation import economics as real

    assert econ._default_economics() is real
    assert econ._default_economics().compute is real.compute
    assert margin_report.__defaults__[-1] is None
