"""Phase H / H7 — Word Coffee ad analysis tests (offline fixture)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import word_coffee as wc  # noqa: E402


def test_fixture_loads():
    d = wc.load()
    assert d["brand"] == "Word Coffee"
    assert len(d["campaigns"]) == 6 and len(d["targets"]) == 6


def test_account_summary_is_unprofitable():
    s = wc.account_summary()
    assert s["acos_pct"] == 166.0 and s["profitable"] is False
    assert s["spend"] == 2370.40


def test_every_campaign_above_100_acos():
    d = wc.load()
    assert all(c["acos_pct"] >= 100 for c in d["campaigns"])


def test_breakeven_from_cogs():
    b = wc.breakeven_acos(cogs_per_unit=5.0)
    # 15.87 - 5.00 - 2.3805 = 8.4895 -> 53.5%
    assert b["breakeven_acos_pct"] == 53.5
    assert b["contribution_per_unit"] == 8.49


def test_classify_bands():
    assert wc.classify(459.3) == "pause_or_cut"
    assert wc.classify(68.7) == "cut_bid"          # > 30 target
    assert wc.classify(20.0) == "increase_bid"     # <= 21
    assert wc.classify(30.0) == "hold"


def test_guardrail_clamps():
    assert wc.clamp_delta("increase_bid") == 10.0
    assert wc.clamp_delta("cut_bid") == -20.0
    assert wc.clamp_delta("pause_or_cut") == -20.0
    assert wc.clamp_delta("hold") == 0.0


def test_capital_leaks_are_all_bleeders_worst_first():
    leaks = wc.capital_leaks()
    # five targets sit at/above 100% ACoS; worst two are the operator's named leaks
    assert len(leaks) == 5
    assert leaks[0]["target"] == "gifts for women" and leaks[0]["acos_pct"] == 459.3
    assert leaks[1]["target"] == "substitutes (PT)" and leaks[1]["acos_pct"] == 412.1


def test_plan_sorted_and_healthy_target_flagged():
    plan = wc.change_plan()
    assert plan[0]["acos_pct"] == 459.3
    healthy = [r for r in plan if r["target"] == "birthday gift for women"][0]
    assert healthy["action"] == "cut_bid"   # 68.7 > 30 target, still above target
    assert healthy["bid_delta_pct"] == -20.0


def test_summary_without_cogs_is_honest():
    s = wc.summary()
    assert s["breakeven"] is None and s["cogs_supplied"] is False
    assert "COGS/unit not supplied" in s["note"]


def test_summary_with_cogs():
    s = wc.summary(cogs_per_unit=5.0)
    assert s["breakeven"]["breakeven_acos_pct"] == 53.5
