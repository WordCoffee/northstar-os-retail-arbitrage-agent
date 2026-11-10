"""Tests for the Bojo campaign tool (`plan_campaign`).

Offline: no Ads API, no network, no spend. The real ``ad_pilot`` plan maths runs
for the pass path so the assertions pin the production budget split and ACoS
formula; a fake planner proves the injection seam.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bojo_tools import campaigns as camp  # noqa: E402
from bojo_tools.campaigns import TOOLS, plan_campaign  # noqa: E402

KEYWORDS = ["matcha", "green tea", "ceremonial matcha"]


class FakePlanner:
    def __init__(self, structure=None, acos=None, error=None):
        self.structure = structure
        self._acos = acos
        self.error = error
        self.calls = []

    def generate_campaign_structure(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.structure

    def compute_target_acos(self, **kwargs):
        self.calls.append(kwargs)
        return self._acos


def test_tools_registry_exports_plan_campaign():
    assert set(TOOLS) == {"plan_campaign"}
    assert TOOLS["plan_campaign"] is plan_campaign


def test_plan_campaign_builds_the_four_tier_plan_and_acos_maths():
    result = plan_campaign(
        asin="B0TEST123",
        keywords=KEYWORDS,
        product_title="Northstar Matcha",
        daily_budget=60.0,
        target_acos=30.0,
        product_cost=8.0,
        amazon_price=25.0,
        fba_fee=4.0,
    )

    assert result["ok"] is True
    assert result["tool"] == "plan_campaign"
    data = result["data"]
    assert data["structure"] == "four_tier"
    assert data["total_daily_budget"] == 60.0
    assert data["no_spend"] is True

    campaigns = {c["type"]: c for c in data["campaigns"]}
    assert set(campaigns) == {"SP-AUTO", "SP-BROAD", "SP-PHRASE", "SP-EXACT"}
    # Production split: 30 / 25 / 25 / 20 percent of the daily budget.
    assert campaigns["SP-AUTO"]["daily_budget"] == 18.0
    assert campaigns["SP-BROAD"]["daily_budget"] == 15.0
    assert campaigns["SP-PHRASE"]["daily_budget"] == 15.0
    assert campaigns["SP-EXACT"]["daily_budget"] == 12.0

    acos = data["acos_math"]
    assert acos["referral_fee"] == 3.75
    assert acos["total_fees"] == 7.75
    assert acos["gross_profit"] == 9.25
    assert acos["breakeven_acos"] == 37.0
    assert acos["target_acos"] == 29.6
    json.dumps(result)


def test_plan_campaign_without_cost_inputs_omits_the_acos_maths():
    result = plan_campaign(asin="B0TEST123", keywords=KEYWORDS)

    assert result["ok"] is True
    assert result["data"]["acos_math"] is None
    assert "product_cost and amazon_price" in result["data"]["acos_note"]


def test_plan_campaign_uses_an_injected_planner():
    planner = FakePlanner(
        structure={"structure": "four_tier", "total_daily_budget": 10.0,
                   "target_acos": 20.0,
                   "campaigns": [{"type": "SP-AUTO", "daily_budget": 10.0}]},
        acos={"target_acos": 12.5, "breakeven_acos": 15.0},
    )

    result = plan_campaign(
        asin="B0TEST123", keywords=KEYWORDS, daily_budget=10.0, target_acos=20.0,
        product_cost=5.0, amazon_price=20.0, planner=planner,
    )

    assert result["ok"] is True
    assert result["data"]["campaigns"] == [{"type": "SP-AUTO", "daily_budget": 10.0}]
    assert result["data"]["acos_math"] == {"target_acos": 12.5, "breakeven_acos": 15.0}
    # The planner got the production call shape, not a re-implementation.
    assert planner.calls[0]["keywords"] == KEYWORDS
    assert planner.calls[0]["daily_budget"] == 10.0


def test_plan_campaign_with_no_keywords_is_a_business_failure():
    result = plan_campaign(asin="B0TEST123", keywords=["  "])

    assert result == {
        "ok": False,
        "tool": "plan_campaign",
        "reason": "no keywords supplied to target",
    }


def test_plan_campaign_rejects_a_non_positive_budget_and_bad_acos():
    zero = plan_campaign(asin="B0TEST123", keywords=KEYWORDS, daily_budget=0)
    assert zero["ok"] is False
    assert zero["reason"] == "daily_budget must be greater than zero"

    wide = plan_campaign(asin="B0TEST123", keywords=KEYWORDS, target_acos=130)
    assert wide["ok"] is False
    assert wide["reason"] == "target_acos must be a percentage in (0, 100]"


def test_plan_campaign_planner_error_is_reported_not_raised():
    planner = FakePlanner(error=RuntimeError("plan maths exploded"))

    result = plan_campaign(
        asin="B0TEST123", keywords=KEYWORDS, planner=planner
    )

    assert result["ok"] is False
    assert result["reason"].startswith("campaign planning failed: RuntimeError")


def test_plan_campaign_programmer_errors_raise():
    with pytest.raises(TypeError):
        plan_campaign(5, KEYWORDS)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        plan_campaign("B0TEST123", "matcha")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        plan_campaign("B0TEST123", [1])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        plan_campaign("B0TEST123", KEYWORDS, daily_budget="lots")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        plan_campaign("B0TEST123", KEYWORDS, product_cost="cheap")  # type: ignore[arg-type]


def test_default_planner_is_the_real_ad_pilot_module():
    import ad_pilot

    assert camp._default_planner() is ad_pilot
    assert plan_campaign.__defaults__[-1] is None
