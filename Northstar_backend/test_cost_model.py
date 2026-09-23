"""Phase H / H5 — usage meter + cost model tests (offline)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cost_model as cm  # noqa: E402
import usage_meter as um  # noqa: E402


# --- usage meter ---

def _meter():
    m = um.UsageMeter()
    m.set_plan_limits("whetstone", {"chat_t1": 3, "gg_scan": 1})
    return m


def test_check_allows_under_cap():
    m = _meter()
    d = m.check("acct", "whetstone", "chat_t1")
    assert d["allowed"] is True and d["limit"] == 3 and d["remaining"] == 3


def test_consume_then_cap():
    m = _meter()
    for i in range(3):
        assert m.consume("acct", "whetstone", "chat_t1")["allowed"] is True
    d = m.consume("acct", "whetstone", "chat_t1")
    assert d["allowed"] is False and d["reason"] == "cap_reached"
    assert "Upgrade" in d["upgrade_prompt"]
    assert m.used("acct", "chat_t1") == 3


def test_unknown_action_fails_closed():
    m = _meter()
    d = m.check("acct", "whetstone", "teleport")
    assert d["allowed"] is False and d["reason"] == "unknown_action"


def test_action_not_in_plan_fails_closed():
    m = _meter()
    d = m.check("acct", "whetstone", "autothink_t3")
    assert d["allowed"] is False and d["reason"] == "action_not_in_plan"


def test_month_rollover_resets():
    m = _meter()
    assert m.consume("acct", "whetstone", "chat_t1", month="2026-09")["allowed"] is True
    assert m.used("acct", "chat_t1", "2026-09") == 1
    assert m.used("acct", "chat_t1", "2026-10") == 0


def test_bulk_consume_refuses_without_partial_charge():
    m = _meter()
    d = m.consume("acct", "whetstone", "chat_t1", n=5)
    assert d["allowed"] is False and m.used("acct", "chat_t1") == 0


def test_meter_from_caps_loads_all_tiers():
    m = um.meter_from_caps()
    assert m.limit_for("whetstone", "gg_scan") == 3
    assert m.limit_for("mainstay", "rank_snapshot") == 2128
    assert m.limit_for("keystone", "alert") == 748
    assert m.limit_for("autothink", "autothink_t3") == 1645


# --- cost model ---

def test_all_tiers_keep_margin_floor():
    for tier in cm.all_tiers():
        assert tier.margin >= cm.MARGIN_FLOOR, (
            "%s margin %.3f below floor" % (tier.plan, tier.margin)
        )
        assert tier.worst_case_cost <= cm.MAX_COST_FRACTION * tier.price


def test_all_tiers_within_target_band():
    """Phase A/A1 — worst-case margin sits inside the 60-80% band."""
    for tier in cm.all_tiers():
        assert cm.MARGIN_FLOOR <= tier.margin <= cm.MARGIN_CEILING, (
            "%s margin %.3f outside band" % (tier.plan, tier.margin)
        )
        assert cm.within_band(tier.plan) is True


def test_video_cap_priced_into_worst_case():
    d = cm.load_caps()
    c = cm.worst_case("autothink")
    wan = d["tiers"]["autothink"]["video"]["Wan15s"]
    assert wan > 0
    assert c.breakdown["video_wan_15s"] == round(wan * d["unit_costs_usd"]["video_wan_15s"], 6)


def test_autothink_is_priciest_and_covers_t3():
    d = cm.load_caps()
    assert d["tiers"]["autothink"]["price_usd_month"] == 179
    assert d["tiers"]["autothink"]["caps"]["autothink_t3"] == 1645
    assert cm.worst_case("autothink").worst_case_cost > cm.worst_case("whetstone").worst_case_cost


def test_images_increase_per_tier():
    d = cm.load_caps()
    totals = [sum(t["images"].values()) for t in d["tiers"].values()]
    assert totals == sorted(totals) and totals[0] > 0, totals


def test_gg_scan_cost_includes_items():
    d = cm.load_caps()
    caps = d["tiers"]["autothink"]["caps"]
    c = cm.worst_case("autothink")
    expected_gg = caps["gg_scan"] * (d["unit_costs_usd"]["gg_scan"]
                                     + caps["gg_items_per_scan"] * d["unit_costs_usd"]["gg_item"])
    assert abs(c.breakdown["gg_scan"] - round(expected_gg, 6)) < 1e-6


def test_margin_ok_helper():
    assert cm.margin_ok("whetstone") is True
    assert cm.margin_ok("autothink") is True


# --- ppc fee bands ---

def test_ppc_fee_first_10k_free():
    assert cm.ppc_fee(5000)["fee_usd"] == 0.0
    assert cm.ppc_fee(10000)["fee_usd"] == 0.0


def test_ppc_fee_scales_with_spend():
    f30k = cm.ppc_fee(30000)["fee_usd"]      # 20k x 2.5%
    f1m = cm.ppc_fee(1_000_000)["fee_usd"]   # 40k*2.5 + 200k*3 + 750k*3.5
    assert f30k == 500.0
    assert f1m == pytest.approx(40000 * 0.025 + 200000 * 0.03 + 750000 * 0.035, abs=0.5)
    assert f1m > f30k


# --- refund policy ---

def test_refund_partial_minus_credits():
    r = cm.refund(39.0, credits_consumed=1000)
    assert r["refund_usd"] == pytest.approx(39.0 - 1000 * 0.0078, abs=0.01)
    assert r["window_days"] == 7


def test_refund_full_when_zero_cost_only():
    r = cm.refund(39.0, credits_consumed=5000, zero_cost_only=True)
    assert r["refund_usd"] == 39.0 and r["reason"] == "zero_cost_data_only"


def test_refund_never_negative():
    assert cm.refund(39.0, credits_consumed=100000)["refund_usd"] == 0.0
