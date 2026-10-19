"""Creative pricing — job-scaled credits that can never break the tier margin.

The important tests here are the two invariants:
  1. every job/quality price sits inside the repository's 60-80% margin band;
  2. a member who spends their ENTIRE monthly allowance on one job class still
     leaves the tier at >= 60% margin (worst-case cost <= 40% of the fee).

If either breaks, the operator would be selling creative work below cost.
"""
from __future__ import annotations

import json
import os

import pytest

import creative_pricing as cp

PLAN_PRICE = {"foundation": 39.0, "scout": 79.0, "mover": 129.0, "autothink": 179.0}


# ── the pinned fallbacks must agree with the canonical file ─────────────────

def test_fallbacks_match_the_canonical_usage_caps():
    caps_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "shared", "usage-caps.json")
    d = json.load(open(caps_path, encoding="utf-8-sig"))
    assert d["refund_policy"]["credit_rate_usd"] == cp.DEFAULT_CREDIT_RATE_USD
    for key, value in cp.DEFAULT_UNIT_COSTS.items():
        assert d["unit_costs_usd"][key] == value, key


def test_pricing_reads_the_canonical_source():
    p = cp._pricing()
    assert p["credit_rate_usd"] == cp.DEFAULT_CREDIT_RATE_USD
    assert p["unit_costs"]["image_v3"] == 0.08
    assert p["unit_costs"]["video_wan_15s"] == 0.75
    assert p["source"].endswith("usage-caps.json")


# ── invariant 1: every quote is inside the margin band ─────────────────────

@pytest.mark.parametrize("job", sorted(cp.JOBS))
@pytest.mark.parametrize("quality", cp.QUALITIES)
def test_every_quote_sits_inside_the_margin_band(job, quality):
    q = cp.quote(job, quality)
    assert cp.MARGIN_FLOOR <= q["margin"] <= cp.MARGIN_CEILING, q
    assert q["credits"] >= 1
    assert q["credit_value_usd"] >= q["real_cost_usd"]


# ── invariant 2: a drained tier still keeps >= 60% margin ──────────────────

@pytest.mark.parametrize("plan", sorted(PLAN_PRICE))
@pytest.mark.parametrize("job", sorted(cp.JOBS))
@pytest.mark.parametrize("quality", cp.QUALITIES)
def test_a_tier_drained_on_one_job_class_still_keeps_its_margin(plan, job, quality):
    cap = cp.monthly_capacity(plan, job, quality)
    if not cap["allowed"] or cap["jobs_per_month"] == 0:
        pytest.skip("not available on this tier")
    fraction = cap["cost_to_tier_usd"] / PLAN_PRICE[plan]
    assert fraction <= 0.40 + 1e-6, (
        f"{plan} drained on {job}/{quality}: cost {cap['cost_to_tier_usd']} is "
        f"{fraction:.1%} of ${PLAN_PRICE[plan]} (margin floor 60%)")
    assert fraction >= 0.20 - 1e-6, (
        f"{plan}/{job}/{quality} is over-margin at {fraction:.1%}; the band caps at 80%")


# ── the operator's core requirement: price scales with the work ────────────

def test_a_portrait_costs_far_less_than_a_package_design():
    portrait = cp.quote("portrait_photo", "final")
    package = cp.quote("package_design", "final")
    assert portrait["credits"] < package["credits"] / 3
    assert portrait["real_cost_usd"] < package["real_cost_usd"] / 3


def test_draft_is_always_cheaper_than_final():
    for job in cp.JOBS:
        d = cp.quote(job, "draft")
        f = cp.quote(job, "final")
        assert d["credits"] < f["credits"], job
        assert d["real_cost_usd"] < f["real_cost_usd"], job


def test_cost_ordering_across_the_image_classes():
    """The operator's requirement: work-scaled pricing, cheapest to most expensive."""
    portrait = cp.quote("portrait_photo", "final")["credits"]
    listing = cp.quote("listing_image", "final")["credits"]
    ad = cp.quote("ad_creative", "final")["credits"]
    label = cp.quote("label_design", "final")["credits"]
    package = cp.quote("package_design", "final")["credits"]

    assert portrait <= listing < ad < package
    assert listing < label < package          # prepress makes a label costlier than a still
    assert package > portrait * 3             # the operator's headline comparison


def test_video_is_priced_above_stills():
    short = cp.quote("video_short", "final")
    still = cp.quote("package_design", "final")
    assert short["credits"] > still["credits"]


# ── tier access is explicit and economical for the entry tier ──────────────

def test_entry_tier_gets_a_working_creative_experience():
    allowed = [j for j in cp.JOBS if cp.quote_for_plan("foundation", j, "draft")["allowed"]]
    assert len(allowed) >= 4, allowed                       # every image class
    for job in allowed:
        cap = cp.monthly_capacity("foundation", job, "draft")
        assert cap["jobs_per_month"] >= 20, (job, cap)      # a real month of work


def test_entry_tier_cannot_reach_final_package_design_or_video():
    denied = cp.quote_for_plan("foundation", "package_design", "final")
    assert denied["allowed"] is False
    assert "tier or above" in denied["reason"]
    assert cp.quote_for_plan("foundation", "video_short", "draft")["allowed"] is False


def test_top_tier_reaches_everything():
    for job in cp.JOBS:
        for quality in cp.QUALITIES:
            assert cp.quote_for_plan("autothink", job, quality)["allowed"] is True


def test_denial_names_the_minimum_tier():
    denied = cp.quote_for_plan("foundation", "ad_creative", "final")
    assert denied["allowed"] is False
    assert "scout" in denied["reason"]


# ── fail closed ────────────────────────────────────────────────────────────

def test_unknown_job_and_quality_fail_closed():
    with pytest.raises(ValueError):
        cp.quote("hologram", "final")
    with pytest.raises(ValueError):
        cp.quote("portrait_photo", "ultra")
    with pytest.raises(ValueError):
        cp.quote_for_plan("platinum", "portrait_photo")
    with pytest.raises(ValueError):
        cp.real_cost("portrait_photo", "final", 0)


# ── reporting ──────────────────────────────────────────────────────────────

def test_price_table_is_complete_and_consistent():
    t = cp.price_table()
    assert len(t["rows"]) == len(cp.JOBS) * len(cp.QUALITIES)
    assert t["plans"]["foundation"]["credit_value_usd"] == 39.0
    assert t["plans"]["autothink"]["credit_value_usd"] == pytest.approx(202.8, abs=0.2)
    for row in t["rows"]:
        assert cp.MARGIN_FLOOR <= row["margin"] <= cp.MARGIN_CEILING
