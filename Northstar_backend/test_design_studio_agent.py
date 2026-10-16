"""Design-brief agent tests — deterministic chat -> structured spec conversion.

RE build 2026-10-16. No LLM, no network: the LLM enhancement hook is only
exercised when DESIGN_AGENT_LLM=1, which tests do not set.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_agent as agent  # noqa: E402


def test_brief_shape_and_prompt_sections():
    spec = agent.build_brief(
        "matte black coffee bag for young professionals",
        {"title": "Mushroom Coffee", "category": "coffee"},
    )
    assert spec["product"]["title"] == "Mushroom Coffee"
    assert spec["palette"]["colors"]
    assert spec["format"]["suggested_templates"]
    for section in ("[PRODUCT]", "[FORMAT]", "[PALETTE]", "[COPY]", "[DIRECTIVES]", "[NEGATIVE]"):
        assert section in spec["prompt_text"], section
    assert spec["prompt_text"].splitlines()[0].startswith("[PRODUCT] Mushroom Coffee")


def test_palette_keyword_mapping():
    assert agent.pick_palette("eco friendly kraft packaging")["name"].startswith("natural kraft")
    assert agent.pick_palette("luxury gift set")["name"].startswith("deep charcoal")
    assert agent.pick_palette("plain mystery object")["name"] == agent._DEFAULT_PALETTE["name"]


def test_format_hints_map_keywords_to_templates():
    assert "label_rounded_rectangle" in agent.suggest_templates("stand-up pouch for loose tea")
    assert "rsc_box" in agent.suggest_templates("rigid gift box set")
    assert "label_circle" in agent.suggest_templates("face cream jar 50ml")
    fallback = agent.suggest_templates("quantum flux capacitor")
    assert fallback == ["label_rounded_rectangle", "rsc_box"]


def test_brief_is_deterministic_without_message_dependent_fields():
    a = agent.build_brief("shampoo bottle", {"title": "Herbal Shampoo"})
    b = agent.build_brief("shampoo bottle", {"title": "Herbal Shampoo"})
    assert a == b
    assert a.get("llm_enhanced") is None  # hook off by default


def test_negative_prompt_blocks_invented_claims():
    spec = agent.build_brief("protein powder tub", {"title": "Whey"})
    assert "no invented certifications" in spec["negative"]
