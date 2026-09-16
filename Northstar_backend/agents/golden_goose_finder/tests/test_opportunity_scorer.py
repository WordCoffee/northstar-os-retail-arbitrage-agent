"""Comprehensive tests for the Golden Goose opportunity scorer.

Covers: tier classification (HIGH/MEDIUM/LOW/REJECT), each component
score function and its anchors, tier boundaries, hard filters (including
the near-baseline rating escape and the undercut competition escape),
tag application, batch ordering/filtering, summary statistics, and the
unknown-data / empty edge cases.
"""

import pytest

from agents.golden_goose_finder.opportunity_scorer import (
    WEIGHT_COMPETITION,
    WEIGHT_DEMAND,
    WEIGHT_LISTING_HEALTH,
    WEIGHT_PROFIT,
    TIER_HIGH,
    TIER_LOW,
    TIER_MEDIUM,
    TIER_REJECT,
    _apply_tags,
    _as_pct,
    _assign_tier,
    _competition_score,
    _demand_score,
    _listing_health_score,
    _profit_score,
    get_scoring_summary,
    score_batch,
    score_opportunity,
)


# ---------------------------------------------------------------------------
# Tier classification.
# ---------------------------------------------------------------------------


def test_high_tier_opportunity(high):
    s = score_opportunity(high)
    assert s.tier == TIER_HIGH
    assert s.composite_score >= 0.7
    assert s.passes_all_filters is True
    assert s.passes_profit_floor and s.passes_demand_floor
    assert s.passes_competition_ceiling and s.passes_listing_health
    assert s.profit_score > 0.5          # above the $10 floor anchor
    assert s.demand_score > 0.75         # high velocity
    assert s.competition_score == 0.75   # 1 FBA seller
    assert s.listing_health_score == 1.0  # rating 4.7 + 1200 reviews, clamped
    assert 0.0 <= s.composite_score <= 1.0
    assert s.asin == "B09GOLDDEMO1"


def test_medium_tier_opportunity(medium):
    s = score_opportunity(medium)
    assert s.tier == TIER_MEDIUM
    assert 0.45 <= s.composite_score < 0.7
    assert s.passes_profit_floor is True
    assert s.passes_all_filters is True  # 3 FBA sellers / 700 sales still clear


def test_low_tier_opportunity(low):
    s = score_opportunity(low)
    assert s.tier == TIER_LOW
    assert 0.25 <= s.composite_score < 0.45
    assert s.passes_profit_floor is True
    assert s.passes_demand_floor is False        # 300/mo < 500
    assert s.passes_competition_ceiling is False  # 6 FBA sellers, undercut fails
    assert s.passes_listing_health is True        # rating 4.0 >= 3.5
    assert s.passes_all_filters is False


def test_reject_tier_below_profit_floor(reject):
    s = score_opportunity(reject)
    assert s.tier == TIER_REJECT
    assert s.composite_score < 0.25
    assert s.passes_profit_floor is False          # -$0.61/unit
    assert s.passes_demand_floor is False
    assert s.passes_competition_ceiling is False
    assert s.passes_all_filters is False


def test_unknown_data_scores_fallback_and_rejects(unknown_data):
    s = score_opportunity(unknown_data)
    assert s.profit_score == 0.0            # None -> 0.0 for profit
    assert s.demand_score == 0.3            # no BSR/sales -> 0.3
    assert s.competition_score == 0.3       # no seller data -> 0.3
    assert s.listing_health_score == 0.4    # no rating -> 0.4
    assert s.tier == TIER_REJECT
    assert s.passes_all_filters is False
    joined = " ".join(s.scoring_notes).lower()
    assert "no bsr/sales data" in joined
    assert "unknown seller data" in joined
    assert "no rating data" in joined


# ---------------------------------------------------------------------------
# Component scores.
# ---------------------------------------------------------------------------


def test_profit_score_anchors():
    assert _profit_score(None) == 0.0
    assert _profit_score(-5.0) == 0.0
    assert _profit_score(0.0) == 0.0
    assert _profit_score(10.0) == pytest.approx(0.5, abs=0.001)
    assert _profit_score(20.0) == pytest.approx(0.75, abs=0.001)
    assert _profit_score(30.0) == 1.0
    assert _profit_score(40.0) == 1.0
    # Monotonic and smooth between anchors (log curve).
    assert _profit_score(5.0) < 0.5 < _profit_score(15.0) < 0.75 < _profit_score(25.0)


def test_demand_score_anchors():
    assert _demand_score(None) == 0.3
    assert _demand_score(0.0) == 0.0
    assert _demand_score(500.0) == pytest.approx(0.5, abs=0.001)
    assert _demand_score(2000.0) == pytest.approx(0.75, abs=0.001)
    assert _demand_score(5000.0) == 1.0
    assert _demand_score(100000.0) == 1.0
    assert _demand_score(100.0) < 0.5 < _demand_score(1000.0) < 0.75 < _demand_score(3000.0)


def test_competition_score_anchors():
    assert _competition_score(None) == 0.3
    assert _competition_score(0) == 1.0
    assert _competition_score(1) == 0.75
    assert _competition_score(2) == 0.5
    assert _competition_score(3) == 0.25
    assert _competition_score(4) == 0.25
    assert _competition_score(5) == 0.25
    assert _competition_score(6) == 0.1
    assert _competition_score(12) == 0.1


def test_listing_health_score_rating_anchors():
    assert _listing_health_score(None, None) == 0.4
    assert _listing_health_score(5.0, None) == 1.0
    assert _listing_health_score(4.8, None) == pytest.approx(1.0)
    assert _listing_health_score(4.5, None) == pytest.approx(0.8)
    assert _listing_health_score(4.0, None) == pytest.approx(0.5)
    assert _listing_health_score(3.9, None) == pytest.approx(0.2)
    assert _listing_health_score(2.0, None) == pytest.approx(0.2)
    # Monotonic between anchors.
    assert _listing_health_score(4.3, None) > _listing_health_score(4.0, None)
    assert _listing_health_score(4.6, None) > _listing_health_score(4.5, None)


def test_listing_health_score_review_bonus():
    assert _listing_health_score(4.5, 1000) >= 1.0  # 0.8 + 0.2 clamped
    assert _listing_health_score(4.5, 600) == pytest.approx(0.9)
    assert _listing_health_score(4.5, 30) == pytest.approx(0.6)   # 0.8 - 0.2
    assert _listing_health_score(3.9, 30) == pytest.approx(0.0)   # 0.2 - 0.2 clamped to 0
    assert _listing_health_score(4.6, 1000) == 1.0                # clamped
    assert _listing_health_score(4.7, 200) == pytest.approx(0.9333, abs=0.001)  # no bonus band


# ---------------------------------------------------------------------------
# Tier boundaries.
# ---------------------------------------------------------------------------


def test_tier_boundaries():
    assert _assign_tier(0.7, True, True) == TIER_HIGH
    assert _assign_tier(0.7, True, False) == TIER_MEDIUM     # filtered out of HIGH
    assert _assign_tier(0.7, False, False) == TIER_LOW       # no profit floor -> not HIGH/MEDIUM
    assert _assign_tier(0.45, True, False) == TIER_MEDIUM
    assert _assign_tier(0.4499, True, False) == TIER_LOW
    assert _assign_tier(0.25, False, False) == TIER_LOW
    assert _assign_tier(0.2499, False, False) == TIER_REJECT
    assert _assign_tier(1.0, True, True) == TIER_HIGH


def test_weights_sum_to_one():
    total = WEIGHT_PROFIT + WEIGHT_DEMAND + WEIGHT_COMPETITION + WEIGHT_LISTING_HEALTH
    assert total == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tags.
# ---------------------------------------------------------------------------


def test_tags_applied_for_high_opportunity(high):
    s = score_opportunity(high)
    assert set(s.opportunity_tags) == {
        "low_competition",
        "high_margin",
        "premium_product",
        "high_velocity",
        "trending_up",
        "bulk_goldmine",
    }


def test_no_fba_competition_tag(ec):
    eco = ec(**{"individual.fba_sellers": 0})
    tags = _apply_tags(eco)
    assert "no_fba_competition" in tags
    assert "low_competition" not in tags
    s = score_opportunity(eco)
    assert s.competition_score == 1.0


def test_no_competition_tag_when_two_sellers(ec):
    eco = ec(**{"individual.fba_sellers": 2})
    tags = _apply_tags(eco)
    assert "no_fba_competition" not in tags
    assert "low_competition" not in tags


def test_low_opportunity_only_matches_bulk_goldmine(low):
    s = score_opportunity(low)
    assert s.opportunity_tags == ["bulk_goldmine"]


def test_tags_boundaries(ec):
    # margin exactly 40 -> no tag; just above -> tag.
    assert "high_margin" not in _apply_tags(ec(profit_margin_pct=40.0))
    assert "high_margin" in _apply_tags(ec(profit_margin_pct=40.5))
    # price exactly $25 -> no premium tag.
    assert "premium_product" not in _apply_tags(ec(amazon_price=25.0))
    assert "premium_product" in _apply_tags(ec(amazon_price=25.01))
    # pack ROI exactly 100% -> no goldmine tag.
    assert "bulk_goldmine" not in _apply_tags(ec(roi_per_costco_pack=100.0))
    assert "bulk_goldmine" in _apply_tags(ec(roi_per_costco_pack=100.5))


# ---------------------------------------------------------------------------
# Hard filters.
# ---------------------------------------------------------------------------


def test_demand_near_baseline_rating_escape(ec):
    # 450/mo is below 500 but within 80% of it -> rating >= min_rating saves it.
    passes = score_opportunity(ec(monthly_sales_estimate=450.0, review_rating=4.6))
    assert passes.passes_demand_floor is True
    # Same sales but rating 4.0 with min_rating 4.5 -> still fails.
    fails = score_opportunity(
        ec(monthly_sales_estimate=450.0, review_rating=4.0),
        min_rating=4.5,
    )
    assert fails.passes_demand_floor is False
    # Below the near-baseline band entirely -> fails regardless of rating.
    far = score_opportunity(ec(monthly_sales_estimate=300.0, review_rating=4.9))
    assert far.passes_demand_floor is False
    # At or above the floor -> passes without needing the rating.
    at_floor = score_opportunity(ec(monthly_sales_estimate=500.0, review_rating=2.0))
    assert at_floor.passes_demand_floor is True


def test_no_demand_data_fails_closed(unknown_data):
    s = score_opportunity(unknown_data)
    assert s.passes_demand_floor is False


def test_undercut_competition_escape(ec):
    # 6 FBA sellers but enough margin that a 2% undercut still clears $10.
    passes = score_opportunity(ec(**{"individual.fba_sellers": 6}, net_profit_per_unit=13.0, amazon_price=19.99))
    assert passes.passes_competition_ceiling is True
    # 6 FBA sellers and the undercut eats below the floor -> fails.
    fails = score_opportunity(ec(**{"individual.fba_sellers": 6}, net_profit_per_unit=10.20, amazon_price=19.99))
    assert fails.passes_competition_ceiling is False
    # No price data -> cannot verify undercut -> fails closed.
    no_price = score_opportunity(ec(**{"individual.fba_sellers": 6}, amazon_price=None))
    assert no_price.passes_competition_ceiling is False


def test_no_seller_data_fails_closed(unknown_data):
    s = score_opportunity(unknown_data)
    assert s.passes_competition_ceiling is False


def test_rating_below_health_floor_fails(ec):
    s = score_opportunity(ec(review_rating=3.4))
    assert s.passes_listing_health is False
    ok = score_opportunity(ec(review_rating=3.5))
    assert ok.passes_listing_health is True


def test_custom_roi_floor(ec):
    # $8/unit misses the default $10 floor but clears a $5 custom floor.
    s = score_opportunity(ec(net_profit_per_unit=8.0), roi_floor=5.0)
    assert s.passes_profit_floor is True
    assert s.profit_score < 0.5


# ---------------------------------------------------------------------------
# Batch scoring.
# ---------------------------------------------------------------------------


def test_score_batch_ordering_and_filtering(high, medium, low, reject):
    results = score_batch([reject, low, high, medium])
    assert [s.tier for s in results] == [TIER_HIGH, TIER_MEDIUM, TIER_LOW]
    assert results[0].asin == "B09GOLDDEMO1"
    composites = [s.composite_score for s in results]
    assert composites == sorted(composites, reverse=True)


def test_score_batch_include_rejected(high, medium, low, reject):
    results = score_batch([medium, reject, low, high], include_rejected=True)
    assert len(results) == 4
    assert results[-1].tier == TIER_REJECT
    assert [s.tier for s in results] == [TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_REJECT]


def test_score_batch_empty():
    assert score_batch([]) == []
    assert score_batch([], include_rejected=True) == []


def test_score_batch_all_rejected(reject):
    assert score_batch([reject, reject]) == []
    fully = score_batch([reject], include_rejected=True)
    assert len(fully) == 1 and fully[0].tier == TIER_REJECT


# ---------------------------------------------------------------------------
# Summary statistics.
# ---------------------------------------------------------------------------


def test_get_scoring_summary(high, medium, low, reject):
    scored = [
        score_opportunity(high),
        score_opportunity(medium),
        score_opportunity(low),
        score_opportunity(reject),
    ]
    summary = get_scoring_summary(scored)
    assert summary["total_evaluated"] == 4
    assert summary["high"] == 1
    assert summary["medium"] == 1
    assert summary["low"] == 1
    assert summary["rejected"] == 1
    assert summary["avg_profit"] == pytest.approx(8.27)  # (12.50+11.00+10.20-0.61)/4
    assert summary["avg_roi"] == pytest.approx(62.25)   # (125+60+72-8)/4
    assert summary["best_opportunity"].asin == "B09GOLDDEMO1"
    expected_tags = {
        "low_competition": 1,
        "high_margin": 1,
        "premium_product": 1,
        "high_velocity": 1,
        "trending_up": 1,
        "bulk_goldmine": 2,
    }
    assert summary["top_tags"] == expected_tags


def test_get_scoring_summary_empty():
    summary = get_scoring_summary([])
    assert summary["total_evaluated"] == 0
    assert summary["high"] == summary["medium"] == summary["low"] == summary["rejected"] == 0
    assert summary["avg_profit"] == 0.0
    assert summary["avg_roi"] == 0.0
    assert summary["best_opportunity"] is None
    assert summary["top_tags"] == {}


def test_get_scoring_summary_all_rejected(reject):
    summary = get_scoring_summary([score_opportunity(reject)])
    assert summary["rejected"] == 1
    assert summary["avg_profit"] == pytest.approx(-0.61)


# ---------------------------------------------------------------------------
# ROI percentage normalization.
# ---------------------------------------------------------------------------


def test_as_pct_normalization():
    assert _as_pct(None) is None
    assert _as_pct(0.45) == pytest.approx(45.0)   # ratio
    assert _as_pct(1.0) == pytest.approx(100.0)   # ratio boundary
    assert _as_pct(125.0) == pytest.approx(125.0)  # already a percentage
    assert _as_pct(0.0) == 0.0
    assert _as_pct(-8.0) == pytest.approx(-8.0)