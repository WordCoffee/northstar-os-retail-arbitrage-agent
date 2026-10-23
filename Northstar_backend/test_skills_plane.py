"""Skills plane: loader, routing, budget, and the four injection points.

The skills are prompt text, so the assertions are about *what reaches the
prompt* and about the fail-closed contract (no directory, no block, no raise).
"""

from __future__ import annotations

import json

import pytest

import skills_plane


def test_catalog_loads_every_skill_base_first():
    rows = skills_plane.catalog()
    ids = [r["id"] for r in rows]
    assert ids[0] == "product-marketing"
    assert {"listing-copy", "ad-creative", "competitor-profiling"} <= set(ids)
    base = rows[0]
    assert base["always"] is True
    assert base["chars"] > 500
    assert "fact" in base["body"].lower()


def test_route_matches_listing_language():
    assert "listing-copy" in skills_plane.route("write five amazon bullets for this sku")


def test_route_matches_ads_language():
    assert "ad-creative" in skills_plane.route("sponsored products headline and cta")


def test_route_matches_competitor_language():
    assert "competitor-profiling" in skills_plane.route("teardown this competitor listing")


def test_route_returns_nothing_for_an_unrelated_query():
    assert skills_plane.route("what is the weather in Lisbon") == []


def test_context_block_includes_base_plus_routed_skill():
    block = skills_plane.context_block("amazon title and bullets")
    assert block.startswith("\n\n[Skills")
    assert "## product-marketing" in block
    assert "## listing-copy" in block
    assert "## ad-creative" not in block


def test_explicit_ids_still_carry_the_base_skill():
    block = skills_plane.context_block(ids=["ad-creative"])
    assert "## product-marketing" in block and "## ad-creative" in block
    assert "## listing-copy" not in block


def test_no_query_and_no_ids_returns_empty_string():
    assert skills_plane.context_block() == ""
    assert skills_plane.context_block(query=None, ids=None) == ""


def test_budget_truncates_at_a_line_boundary():
    block = skills_plane.context_block(ids=["listing-copy", "ad-creative"],
                                       budget_chars=900)
    assert len(block) <= 900
    assert block.endswith("\n…(truncated)")


def test_missing_directory_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_plane, "skills_dir", lambda: tmp_path / "nope")
    assert skills_plane.catalog() == []
    assert skills_plane.context_block("amazon listing") == ""


def test_chat_prompt_gains_the_skill_block_only_with_a_query():
    import chat_adapter

    msgs = chat_adapter.build_chat_messages(
        [{"role": "user", "content": "write amazon bullets"}],
        query="write amazon bullets")
    system = msgs[0]["content"]
    assert "[Skills" in system
    assert "prohibited" in system.lower()

    plain = chat_adapter.build_chat_messages([{"role": "user", "content": "hi"}])
    assert "[Skills" not in plain[0]["content"]
    assert plain[0]["content"] == (chat_adapter.CHAT_SYSTEM_PROMPT
                                   + chat_adapter.DELIVERABLE_ROUTING)


def test_listing_forge_prompts_lead_with_the_skill_block():
    import listing_forge

    product = {"title": "Mogul Organics Turmeric", "brand": "Mogul Organics",
               "category": "Grocery"}
    prompt = listing_forge._build_title_prompt(product, None, None, None)["prompt"]
    assert prompt.startswith("\n\n[Skills")
    assert "## product-marketing" in prompt

    bullets = listing_forge._build_bullets_prompt(product, None, None)
    desc = listing_forge._build_description_prompt(product, None)
    assert "## listing-copy" in bullets and "## listing-copy" in desc


def test_reasoning_tasks_send_skills_to_the_provider():
    from adapters.reasoning_provider import MockReasoningProvider
    from reasoning_tasks import ad_copy_proposal, listing_proposal

    seen = []

    class Capturing(MockReasoningProvider):
        def complete(self, request):
            seen.append(request)
            return super().complete(request)

    provider = Capturing(response_text=json.dumps({
        "sku": "SKU-1",
        "proposed": {"title": "T", "bullets": ["a", "b", "c", "d", "e"],
                     "description": "d", "attributes": {}},
        "reasons": [], "missing_evidence": [], "warnings": [],
    }))
    listing_proposal(sku="SKU-1", title="old", bullets=["a"] * 5,
                     description="old", provider=provider)
    system = seen[-1].messages[0]["content"]
    assert "## product-marketing" in system and "## listing-copy" in system

    provider2 = Capturing(response_text=json.dumps({
        "headlines": ["h1", "h2"], "body": "b", "cta": "c",
        "brand_tone": "plain", "unsupported_claims": [], "warnings": [],
    }))
    ad_copy_proposal({"sku": "SKU-1", "title": "x"}, provider=provider2)
    system2 = seen[-1].messages[0]["content"]
    assert "## product-marketing" in system2 and "## ad-creative" in system2


def test_skill_files_have_frontmatter_and_stay_small():
    for row in skills_plane.catalog():
        assert row["description"], f"{row['id']} has no description"
        assert row["chars"] <= 8000, f"{row['id']} is too long for a prompt budget"
