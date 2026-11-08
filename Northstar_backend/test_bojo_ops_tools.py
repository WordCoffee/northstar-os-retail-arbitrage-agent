"""Bojo tools for OfferChisel and Operations Hub.

Two contracts worth protecting:

* the pricing maths is checkable by hand — every component is in the payload,
  including the branch the solve took and the fee minimum when it binds;
* the status tool never fabricates. A source it cannot read is ``unknown`` with
  a reason, and it only refuses outright when *nothing* could be read.
"""
from __future__ import annotations

import json

import pytest

import bojo_tools_ops as tools

# ── helpers ──────────────────────────────────────────────────────────────────

DEMO_FEES = {"referral_pct": 15.0, "referral_min": 0.30, "fulfilment": 4.25}


def _up(**extra):
    payload = {"available": True, "verdict": "ok", "reason": None}
    payload.update(extra)
    return payload


# ── offer_recommendation: arithmetic ────────────────────────────────────────

def test_offer_matches_hand_arithmetic():
    """$8.50 cost, $4.25 fulfilment, 15%/min $0.30 referral, 25% target."""
    out = tools.offer_recommendation(
        8.50, 25, [34.99, 32.50, 36.00], fees=DEMO_FEES)

    assert out["ok"] is True
    assert out["tool"] == "offer_recommendation"
    data = out["data"]

    # (8.50 + 4.25) / (1 - 0.15 - 0.25) = 21.25 exactly; rounded up to the cent
    # and repaired by one cent so the rounded referral fee still clears 25%.
    assert data["recommended_price"] == 21.26
    assert data["target_price_before_ceiling"] == 21.26
    assert data["fees"]["referral_fee"] == 3.19
    assert data["fees"]["referral_min_applied"] is False
    assert data["achieved"]["profit_per_unit"] == 5.32
    assert data["achieved"]["margin_pct"] == 25.02
    assert data["achieved"]["total_fees"] == 7.44
    assert data["achieved"]["total_cost"] == 15.94
    assert data["target_met"] is True
    assert data["verdict"] == "sell"
    assert data["warnings"] == []

    # The seller can re-add the trail and land on the same figures.
    trail = " | ".join(data["arithmetic"])
    for fragment in ("$12.75", "$21.26", "$3.19", "$5.32", "25.02%"):
        assert fragment in trail
    assert data["competitor"]["ceiling"] == 32.50
    assert data["competitor"]["clamped"] is False
    assert "rounded UP" in data["rounding"]


def test_offer_result_is_json_serialisable():
    out = tools.offer_recommendation(8.50, 25, [30.00], fees=DEMO_FEES)
    assert json.loads(json.dumps(out)) == out


def test_referral_minimum_binds_on_a_cheap_item():
    """At $1 cost the 15% fee is $0.24, below the $0.30 minimum."""
    out = tools.offer_recommendation(
        1.00, 20, fees={"referral_pct": 15.0, "referral_min": 0.30, "fulfilment": 0.0})

    data = out["data"]
    # (1.00 + 0.30) / (1 - 0.20) = 1.625 -> 1.63
    assert data["recommended_price"] == 1.63
    assert data["fees"]["referral_fee"] == 0.30
    assert data["fees"]["referral_min_applied"] is True
    assert data["achieved"]["profit_per_unit"] == 0.33
    assert data["achieved"]["margin_pct"] == 20.25
    assert data["target_met"] is True
    assert any("minimum-fee branch" in line for line in data["arithmetic"])
    assert any("referral minimum applies" in w for w in data["warnings"])


def test_competitor_ceiling_clamps_the_ask():
    out = tools.offer_recommendation(
        8.50, 25, [19.50, 18.99], fees=DEMO_FEES)

    data = out["data"]
    assert data["target_price_before_ceiling"] == 21.26
    assert data["competitor"]["ceiling"] == 18.99
    assert data["recommended_price"] == 18.99
    assert data["competitor"]["clamped"] is True
    assert data["target_met"] is False
    assert data["achieved"]["margin_pct"] == 17.85      # (18.99 - 2.85 - 4.25 - 8.50)
    assert data["achieved"]["profit_per_unit"] == 3.39
    assert data["verdict"] == "sell"                     # still profitable, just short
    assert any("ceiling" in w and "target" in w for w in data["warnings"])


def test_negative_margin_at_the_ceiling_says_do_not_sell():
    """The ceiling is below break-even: report the loss, do not hide it."""
    out = tools.offer_recommendation(8.50, 25, [10.00], fees=DEMO_FEES)

    assert out["ok"] is True
    data = out["data"]
    assert data["recommended_price"] == 10.00
    assert data["achieved"]["profit_per_unit"] == -4.25
    assert data["achieved"]["margin_pct"] == -42.50
    assert data["target_met"] is False
    assert data["verdict"] == "do_not_sell"
    assert any("loses $4.25" in w for w in data["warnings"])


def test_negative_target_margin_is_allowed_for_clearance():
    out = tools.offer_recommendation(10.00, -10, fees={"fulfilment": 1.00})

    data = out["data"]
    assert data["recommended_price"] == 11.59          # 11.00 / 0.95, repaired 1c
    assert data["achieved"]["margin_pct"] == -9.92
    assert data["target_met"] is True                  # the -10% target is met
    assert data["verdict"] == "do_not_sell"
    assert any("clearance" in w for w in data["warnings"])


def test_median_policy_with_an_undercut():
    out = tools.offer_recommendation(
        10.00, 30, [19.99, 20.00, 25.00],
        fees={"fulfilment": 2.00}, competitor_policy="median", undercut_pct=5)

    data = out["data"]
    assert data["competitor"]["ceiling"] == 20.00      # median, not the lowest
    assert data["competitor"]["effective_ceiling"] == 19.00   # 5% under, floored to the cent
    assert data["recommended_price"] == 19.00
    assert data["competitor"]["clamped"] is True
    assert data["achieved"]["margin_pct"] == 21.84


# ── offer_recommendation: error paths ───────────────────────────────────────

def test_rejects_missing_cost():
    out = tools.offer_recommendation(None, 25)
    assert out["ok"] is False
    assert out["tool"] == "offer_recommendation"
    assert "cost" in out["reason"]


def test_rejects_target_margin_the_fee_model_makes_impossible():
    out = tools.offer_recommendation(5.00, 90, fees={"referral_pct": 15.0})
    assert out["ok"] is False
    assert "reachable range" in out["reason"]


def test_rejects_a_non_numeric_competitor_price():
    out = tools.offer_recommendation(5.00, 20, ["19.99"])
    assert out["ok"] is False
    assert "competitor_prices[0]" in out["reason"]


def test_rejects_an_unknown_fee_key():
    out = tools.offer_recommendation(5.00, 20, fees={"referal_pct": 15.0})
    assert out["ok"] is False
    assert "unknown fee key" in out["reason"]


# ── hub_status: aggregation ─────────────────────────────────────────────────

def test_hub_status_all_up():
    out = tools.hub_status({
        "alpha": lambda: _up(measured=1),
        "beta": lambda: _up(measured=2),
        "gamma": lambda: _up(measured=3),
    })

    assert out["ok"] is True
    data = out["data"]
    assert data["status"] == "ok"
    assert data["summary"] == {"total": 3, "ok": 3, "degraded": 0, "critical": 0,
                               "unknown": 0, "readable": 3, "unreadable": 0}
    assert data["unhealthy"] == []
    assert data["services"]["alpha"]["evidence"]["measured"] == 1
    assert data["services"]["alpha"]["status"] == "ok"


def test_hub_status_one_down_is_reported_not_hidden():
    def boom():
        raise RuntimeError("probe exploded")

    out = tools.hub_status({
        "alpha": lambda: _up(),
        "beta": boom,
        "gamma": lambda: {"available": False, "reason": "device absent"},
    })

    assert out["ok"] is True                     # something WAS readable
    data = out["data"]
    assert data["status"] == "degraded"
    assert data["services"]["alpha"]["status"] == "ok"
    assert data["services"]["beta"]["status"] == "unknown"
    assert "probe exploded" in data["services"]["beta"]["reason"]
    assert data["services"]["beta"]["evidence"] is None
    assert data["services"]["gamma"]["status"] == "unknown"
    assert data["services"]["gamma"]["reason"] == "device absent"
    assert data["summary"]["readable"] == 1
    assert data["summary"]["unreadable"] == 2
    assert data["unhealthy"] == ["beta", "gamma"]


def test_hub_status_all_unreadable_returns_not_ok():
    def boom():
        raise OSError("no such device")

    out = tools.hub_status({"alpha": boom, "beta": boom})

    assert out["ok"] is False
    assert out["tool"] == "hub_status"
    assert "no status source could be read" in out["reason"]
    assert out["data"]["summary"]["readable"] == 0
    assert {e["status"] for e in out["data"]["services"].values()} == {"unknown"}


def test_hub_status_does_not_call_a_network_probe_for_injected_services(monkeypatch):
    def forbidden(*_a, **_k):
        raise AssertionError("default status probe was called")

    monkeypatch.setattr(tools.ops_status, "model_status", forbidden)
    monkeypatch.setattr(tools.ops_status, "disk_status", forbidden)

    out = tools.hub_status({"alpha": lambda: _up()})
    assert out["ok"] is True
    assert out["data"]["services"]["alpha"]["source"] == "injected"


def test_hub_status_survives_a_probe_returning_a_non_mapping():
    out = tools.hub_status({"alpha": lambda: _up(), "beta": lambda: 42})

    assert out["ok"] is True
    assert out["data"]["services"]["beta"]["status"] == "unknown"
    assert "not a mapping" in out["data"]["services"]["beta"]["reason"]


def test_hub_status_rejects_a_bad_services_argument():
    out = tools.hub_status([])
    assert out["ok"] is False
    assert "mapping" in out["reason"]


def test_hub_status_annotates_empty_lane_telemetry_as_unknown():
    """An empty telemetry table is absence of evidence, not health."""
    out = tools.hub_status({"lanes": lambda: {"available": True, "lanes": {}}})

    assert out["ok"] is False                    # the only source measured nothing
    assert out["data"]["services"]["lanes"]["status"] == "unknown"
    assert "no lane runs" in out["data"]["services"]["lanes"]["reason"]


# ── wiring ──────────────────────────────────────────────────────────────────

def test_tools_export_and_default_sources_are_the_existing_status_module():
    assert set(tools.TOOLS) == {"offer_recommendation", "hub_status"}
    assert all(callable(fn) for fn in tools.TOOLS.values())
    for source in tools.DEFAULT_SERVICE_SOURCES.values():
        assert source.startswith("ops_status.")
