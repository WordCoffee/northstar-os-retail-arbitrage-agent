"""Asset hand-off to Listing Forge (Phase 3, item 2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_handoff import aspect, handoff
from render_bind import bind


def _brief(**kw):
    return bind({"id": "prod-1"}, pricing={"target_price": 40, "unit_cost": 10},
                keywords=["mushroom powder", "lions mane"], **kw)


HERO = {"url": "https://x/hero.png", "width": 2000, "height": 2000,
        "role": "hero", "pure_white": True}
LIFE = {"url": "https://x/kitchen.png", "width": 1600, "height": 1200, "role": "lifestyle"}


def test_aspect_ratios_reduce():
    assert aspect(2000, 2000) == "1:1"
    assert aspect(970, 600) == "97:60"
    assert aspect(1600, 1200) == "4:3"
    assert aspect(0, 10) == "unknown"
    assert aspect("x", 10) == "unknown"


def test_handoff_accepts_a_compliant_hero():
    out = handoff(_brief(), [HERO, LIFE])
    assert out["ready"] is True
    assert out["hero_image"] == HERO["url"]
    assert out["hero_aspect"] == "1:1"
    assert out["secondary_images"] == [LIFE["url"]]
    assert out["keywords"] == ["mushroom powder", "lions mane"]


def test_a_non_white_hero_is_refused():
    bad = dict(HERO, pure_white=False)
    out = handoff(_brief(), [bad])
    assert out["ready"] is False
    assert "hero_not_pure_white" in out["blocked"]


def test_a_non_square_hero_is_flagged():
    wide = dict(HERO, width=1600, height=1200)
    out = handoff(_brief(), [wide])
    assert "hero_not_square" in out["blocked"]


def test_missing_hero_is_named():
    out = handoff(_brief(), [LIFE])
    assert out["blocked"][0] == "hero_missing"
    assert out["hero_image"] is None


def test_assets_without_a_url_are_dropped():
    out = handoff(_brief(), [HERO, {"role": "detail"}, {"url": ""}])
    assert out["secondary_images"] == []


def test_secondary_is_capped_and_role_ordered():
    assets = [HERO] + [
        {"url": f"https://x/{r}{i}.png", "width": 1000, "height": 1000, "role": r}
        for i in range(4) for r in ("detail", "lifestyle", "other")
    ]
    out = handoff(_brief(), assets)
    assert len(out["secondary_images"]) <= 6
    roles = [m["role"] for m in out["secondary_meta"]]
    assert roles == sorted(roles, key=lambda r: {"lifestyle": 0, "scale": 1, "detail": 2,
                                                 "packaging": 3, "other": 4}[r])


def test_brief_blockers_propagate_into_the_handoff():
    blind = bind({"id": "p2"})            # no pricing
    out = handoff(blind, [HERO])
    assert "pricing_unknown" in out["blocked"]
    assert out["ready"] is False


def test_alt_text_uses_the_first_keyword_and_carries_no_claims():
    out = handoff(_brief(), [HERO])
    assert out["alt_text"].startswith("mushroom powder")
    for banned in ("$", "sale", "free shipping", "best"):
        assert banned not in out["alt_text"].lower()


def test_tier_and_environment_are_carried_through():
    out = handoff(_brief(lifestyle=False), [HERO])
    assert out["material_tier"] == "premium"
    assert out["environment"] == "studio-white"


def test_empty_asset_list_is_ready_false():
    out = handoff(_brief(), [])
    assert out["ready"] is False and out["blocked"] == ["hero_missing"]
