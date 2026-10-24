"""Package design: templates, text-to-spec via provider, credits ledger, copy audit."""

from __future__ import annotations

import json

import pytest

import package_design as pd
from adapters.reasoning_provider import MockReasoningProvider


@pytest.fixture(autouse=True)
def _reset_credits():
    pd.reset_credits("default")
    yield
    pd.reset_credits("default")


def test_templates_are_non_empty_and_have_dimensions():
    assert set(pd.TEMPLATES) >= {"box", "bottle", "pouch", "can", "label"}
    for name, spec in pd.TEMPLATES.items():
        assert "name" in spec
        assert any(k.endswith("_mm") for k in spec)


def test_template_routing_from_prompt_keywords():
    d = pd.design_from_prompt("a 12oz aluminium energy drink can")
    assert d.template == "can"
    d2 = pd.design_from_prompt("stand-up pouch for coffee beans")
    assert d2.template == "pouch"
    d3 = pd.design_from_prompt("folding carton for tea")
    assert d3.template == "box"


def test_empty_prompt_is_rejected():
    with pytest.raises(ValueError):
        pd.design_from_prompt("   ")


def test_design_without_provider_is_offline_usable():
    d = pd.design_from_prompt("Stainless steel water bottle, 32 oz")
    assert d.template == "bottle"
    assert d.dieline_spec and d.dieline_spec.get("height_mm") == 180
    assert d.status == "draft"


def test_provider_fills_spec_and_runs_copy_audit():
    provider = MockReasoningProvider(response_text=json.dumps({
        "name": "Aurora Turmeric",
        "color_palette": ["#D4A017", "#1F3B2C"],
        "typography": "Libre Baskerville + DM Sans",
        "claims": ["organic turmeric", "small-farm sourced"],
        "dieline_spec": {"width_mm": 100, "height_mm": 150, "bleed_mm": 3, "safe_zone_mm": 5},
    }))
    d = pd.design_from_prompt("turmeric powder pouch", provider=provider)
    assert d.name == "Aurora Turmeric"
    assert d.color_palette == ["#D4A017", "#1F3B2C"]
    assert d.claims == ["organic turmeric", "small-farm sourced"]
    assert d.copy_audit is not None
    assert d.copy_audit["value"] in ("pass", "review", "block")


def test_blocked_claim_marks_design_draft():
    provider = MockReasoningProvider(response_text=json.dumps({
        "name": "Best seller turmeric",
        "color_palette": [],
        "typography": "",
        "claims": ["guaranteed results", "100% cure"],
        "dieline_spec": {},
    }))
    d = pd.design_from_prompt("turmeric", provider=provider)
    assert d.copy_audit["value"] == "block"
    assert d.status == "draft"


def test_skills_are_injected_into_the_system_prompt():
    captured = {}

    class CapturingProvider(MockReasoningProvider):
        def complete(self, request):
            captured["system"] = request.messages[0]["content"]
            return super().complete(request)

    provider = CapturingProvider(response_text=json.dumps({
        "name": "x", "color_palette": [], "typography": "", "claims": [], "dieline_spec": {},
    }))
    pd.design_from_prompt("a box", provider=provider)
    assert "product-marketing" in captured["system"] or "Product marketing" in captured["system"]


def test_credits_default_grant_and_spend():
    assert pd.credits() == 49
    out = pd.spend_credits("default", 5)
    assert out["ok"] is True and out["balance"] == 44
    assert pd.credits() == 44


def test_insufficient_credits_is_refused_not_overdrawn():
    out = pd.spend_credits("default", 1000)
    assert out["ok"] is False
    assert out["balance"] == 49   # unchanged


def test_grant_and_reset():
    pd.grant_credits("default", 10)
    assert pd.credits() == 59
    pd.reset_credits("default")
    assert pd.credits() == 49


def test_negative_amounts_are_rejected():
    with pytest.raises(ValueError):
        pd.spend_credits("default", -1)
    with pytest.raises(ValueError):
        pd.grant_credits("default", -1)


def test_to_dict_round_trips():
    d = pd.design_from_prompt("a box")
    blob = pd.to_dict(d)
    assert blob["template"] == d.template
    assert blob["id"] == d.id