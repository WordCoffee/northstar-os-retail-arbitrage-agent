"""P5-T1 Resale Score tests: missing-component behavior + determinism."""
from __future__ import annotations

from Northstar_backend.foundation import resale_score as rs


def test_deterministic_for_identical_inputs():
    inp = {"net_per_unit": 8.0, "est_monthly_sales": 150, "seller_count": 4,
           "buy_box_type": "FBA", "match_confidence": 0.9, "sourcing_ease": 0.7,
           "roi_pct": 42.0}
    a = rs.score(inp)
    b = rs.score(inp)
    assert a == b
    assert a["scorer_version"] == "resale-score-1.0.0"


def test_missing_component_is_unavailable_not_zero():
    out = rs.score({"net_per_unit": 10.0, "est_monthly_sales": 300})
    assert out["component_scores"]["net_profit_per_unit"] == 1.0
    assert out["component_scores"]["demand"] == 1.0
    assert out["component_scores"]["bsr_stability"] is None
    assert out["component_availability"]["bsr_stability"] is False
    assert "bsr_stability" in out["missing_information"]
    # overall = weighted mean of the two available only
    w = out["component_weights"]
    expect = round((1.0 * w["net_profit_per_unit"] + 1.0 * w["demand"])
                   / (w["net_profit_per_unit"] + w["demand"]), 4)
    assert out["overall_score"] == expect


def test_all_missing_means_no_score():
    out = rs.score({})
    assert out["overall_score"] is None
    assert out["overall_confidence"] == 0.0
    assert len(out["missing_information"]) == len(rs.COMPONENTS)


def test_net_below_floor_and_negative():
    assert rs.score({"net_per_unit": 2.5})["component_scores"]["net_profit_per_unit"] == 0.5
    assert rs.score({"net_per_unit": -1})["component_scores"]["net_profit_per_unit"] == 0.0
    assert rs.score({})["component_scores"]["net_profit_per_unit"] is None


def test_roi_is_informational_only():
    base = rs.score({"net_per_unit": 8.0, "match_confidence": 0.9})
    with_roi = rs.score({"net_per_unit": 8.0, "match_confidence": 0.9, "roi_pct": 999})
    assert base["overall_score"] == with_roi["overall_score"]
    assert with_roi["informational"]["roi_pct"] == 999


def test_uncertainty_penalty_is_separate_and_reduces_overall():
    no_pen = rs.score({"net_per_unit": 8.0, "match_confidence": 1.0})
    pen = rs.score({"net_per_unit": 8.0, "match_confidence": 1.0, "uncertainty_penalty": 0.25})
    assert pen["uncertainty_penalty"] == 0.25
    assert pen["overall_score"] < no_pen["overall_score"]


def test_weights_are_config_driven():
    inp = {"net_per_unit": 10.0, "est_monthly_sales": 0}
    # demand 0, net 1 -> default weights
    default = rs.score(inp)
    heavy = rs.score(inp, config={"WEIGHTS": {"net_profit_per_unit": 100.0, "demand": 1.0}})
    assert default["overall_score"] is not None and heavy["overall_score"] is not None
    assert heavy["overall_score"] > default["overall_score"]


def test_score_never_authorizes_purchase():
    out = rs.score({"net_per_unit": 100, "est_monthly_sales": 1000, "match_confidence": 1.0})
    assert out["purchase_ready"] is False