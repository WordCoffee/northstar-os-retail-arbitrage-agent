"""Render init binding (Phase 3, item 1)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_bind import bind, environment_for, normalise_keywords, prompt_suffix, tier_for


def test_premium_tier_from_a_wide_margin():
    b = bind({"id": "p1"}, pricing={"target_price": 40.0, "unit_cost": 12.0})
    assert b.margin_pct == 0.7
    assert b.material_tier == "premium"
    assert "embossed" in b.materials["finish"]
    assert b.blocked == []


def test_standard_tier_band():
    b = bind({"id": "p1"}, pricing={"target_price": 40.0, "unit_cost": 22.0})   # 45%
    assert b.material_tier == "standard"


def test_value_tier_band():
    b = bind({"id": "p1"}, pricing={"target_price": 40.0, "unit_cost": 30.0})   # 25%
    assert b.material_tier == "value"
    assert "kraft" in b.materials["substrate"]


def test_missing_pricing_is_unknown_and_blocked_not_zero():
    b = bind({"id": "p1"})
    assert b.material_tier == "unknown"
    assert b.margin_pct is None
    assert "pricing_unknown" in b.blocked
    assert b.to_dict()["ready"] is False


def test_missing_product_id_blocks():
    b = bind({}, pricing={"target_price": 10, "unit_cost": 3})
    assert "product_id_missing" in b.blocked


def test_lifestyle_on_a_value_margin_is_refused_for_budget():
    b = bind({"id": "p"}, pricing={"target_price": 20, "unit_cost": 16}, lifestyle=True)
    assert "lifestyle_over_budget" in b.blocked


def test_keywords_are_normalised_deduped_and_capped():
    raw = ["  Mushroom   Powder ", "mushroom powder", "", 42, "x" * 80, "Lions Mane"]
    out = normalise_keywords(raw)
    assert out == ["mushroom powder", "lions mane"]


def test_keyword_cap_is_twenty():
    assert len(normalise_keywords([f"k{i}" for i in range(50)])) == 20


def test_negative_price_is_treated_as_unknown():
    b = bind({"id": "p"}, pricing={"target_price": -5, "unit_cost": 1})
    assert b.margin_pct is None


def test_lifestyle_environment_uses_the_buyer_room():
    assert environment_for(lifestyle=True, buyer={"room": "Kitchen"}) == "lifestyle-kitchen"
    assert environment_for(lifestyle=True, buyer={}) == "lifestyle-generic"
    assert environment_for(lifestyle=False) == "studio-white"


def test_prompt_suffix_carries_material_and_lighting():
    b = bind({"id": "p"}, pricing={"target_price": 30, "unit_cost": 6})
    s = prompt_suffix(b)
    assert "85mm" in s
    assert b.materials["substrate"] in s


def test_must_not_forbids_generated_text():
    b = bind({"id": "p"}, pricing={"target_price": 30, "unit_cost": 6})
    assert any("text" in rule for rule in b.must_not)


@pytest.mark.parametrize("margin,tier", [(0.9, "premium"), (0.55, "premium"),
                                         (0.5499, "standard"), (0.35, "standard"),
                                         (0.3499, "value"), (None, "unknown")])
def test_tier_boundaries(margin, tier):
    assert tier_for(margin) == tier
