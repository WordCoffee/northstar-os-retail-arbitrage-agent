"""Script planning: the budget, the hook, the prompts.

A scene plan is a contract: its durations must add up to the placement window,
its frames to the preset target, and its prompts must survive the text-safe lane
without asking the model to paint words.
"""
from __future__ import annotations

import text_fidelity
import video_formats
import video_script as vsp

PRODUCT = {
    "brand": "MOGRA", "product": "LION'S MANE", "subtitle": "MUSHROOM POWDER",
    "weight": "6 oz (170 g)", "claims": ["100% PURE", "NO FILLERS"],
}


def test_the_durations_sum_to_the_window_exactly():
    for platform, seconds in (("tiktok", 15), ("tiktok", 30), ("shorts", 15)):
        plan = video_formats.plan(platform, seconds)
        result = vsp.plan_scenes(PRODUCT, platform=platform, seconds=seconds)
        assert result["sum_seconds"] == plan["seconds"]
        assert result["sum_frames"] == plan["target_frames"]
        assert all(result["checks"].values()), result["checks"]
        assert sum(s["seconds"] for s in result["scenes"]) == plan["seconds"]


def test_the_hook_is_complete_and_short():
    result = vsp.plan_scenes(PRODUCT, platform="tiktok", seconds=15, seed=7)
    hook = result["scenes"][0]["on_screen_text"]
    assert 3 <= len(hook.split()) <= 5, hook
    assert not hook.endswith((" the", " and", " you", " of", " to")), hook


def test_every_prompt_survives_the_text_safe_lane():
    import re

    result = vsp.plan_scenes(PRODUCT, platform="tiktok", seconds=15)
    for scene in result["scenes"]:
        prompt = scene["prompt"]
        prep = text_fidelity.sanitize_brief_for_render(prompt)
        assert prep["brief_empty"] is False
        assert prep["expected_terms"] == []
        # no digits and no all-caps runs: those are what the model paints
        assert not any(ch.isdigit() for ch in prompt), prompt
        assert not re.search(r"\b[A-Z]{2,}\b", prompt), prompt


def test_an_explicit_hook_and_cta_are_honoured():
    result = vsp.plan_scenes(PRODUCT, platform="tiktok", seconds=15,
                             hook="six ounces of focus",
                             cta="tap the shop")
    assert result["scenes"][0]["on_screen_text"] == "six ounces of focus"
    assert result["scenes"][-1]["on_screen_text"] == "tap the shop"


def test_the_compliance_flag_rides_along():
    amazon = vsp.plan_scenes(PRODUCT, platform="amazon-ad-16x9", seconds=15)
    assert amazon["compliance"]["verified"] is False
    tiktok = vsp.plan_scenes(PRODUCT, platform="tiktok", seconds=15)
    assert tiktok["compliance"]["verified"] is True
