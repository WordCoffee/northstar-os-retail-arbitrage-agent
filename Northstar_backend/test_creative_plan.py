"""Creative plan contract — inference, plan, quote options, confirmation.

The plan is the operator's decision surface: it must name real steps, admit what it
does not know, price both qualities, and never execute anything on its own.
"""
from __future__ import annotations

import pytest

import creative_plan as cplan
import creative_pricing as cp


# ── inference ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("request_text,expected", [
    ("design a stand-up pouch for mushroom powder", "package_design"),
    ("make a print-ready label for a 4 oz jar", "label_design"),
    ("ultra realistic man holding the product on a porch", "portrait_photo"),
    ("amazon main image on white background", "listing_image"),
    ("a set of facebook ad creatives", "ad_creative"),
    ("a 15s product video for reels", "video_short"),
])
def test_inference_picks_the_right_job(request_text, expected):
    out = cplan.infer_job(request_text, "video" if "video" in request_text else "image")
    assert out["job"] == expected, out
    assert out["confidence"] >= 0.9
    assert out["reason"]


def test_inference_falls_back_honestly():
    out = cplan.infer_job("do something nice", "image")
    assert out["job"] == "product_shot"
    assert out["confidence"] == 0.5
    assert "defaulted" in out["reason"]


def test_media_lane_is_respected():
    assert cplan.infer_job("product video", "image")["job"] != "video_short"
    assert cplan.infer_job("package design", "video")["job"] == "video_short"


# ── the plan itself ──────────────────────────────────────────────────────────

def test_plan_names_real_tools_and_admits_what_is_missing():
    plan = cplan.build_plan("design a stand-up pouch for mushroom powder")
    assert plan["ok"] is True and plan["plan_id"].startswith("plan_")
    assert plan["job"] == "package_design"
    tools = [s["tool"] for s in plan["steps"]]
    assert "design_brief" in tools and "create_dieline" in tools
    # The registry check is real: any unregistered tool is marked unavailable.
    for step in plan["steps"]:
        if not step["tool"].startswith("_"):
            import chat_tools
            assert step["available"] is (step["tool"] in chat_tools.TOOLS)
    assert plan["unknowns"], "a packaging plan must say what it needs from the operator"


def test_plan_admits_missing_size_and_brand():
    plan = cplan.build_plan("design a pouch")
    blob = " ".join(plan["unknowns"]).lower()
    assert "size" in blob
    assert "brand" in blob


def test_size_and_brand_are_no_longer_unknowns_when_stated():
    plan = cplan.build_plan("design a 6 oz stand-up pouch using our brand logo")
    blob = " ".join(plan["unknowns"]).lower()
    assert "size" not in blob or "fill weight is not stated" not in blob
    assert "brand assets" not in blob


def test_detailed_plan_has_more_steps_than_quick():
    quick = cplan.build_plan("design a pouch", detail="quick")
    detailed = cplan.build_plan("design a pouch", detail="detailed")
    assert len(detailed["steps"]) > len(quick["steps"])


def test_options_price_both_qualities_from_the_engine():
    plan = cplan.build_plan("design a pouch", subscription="mover")
    d, f = plan["options"]["draft"], plan["options"]["final"]
    assert d["credits"] == cp.quote_for_plan("mover", "package_design", "draft")["credits"]
    assert f["credits"] == cp.quote_for_plan("mover", "package_design", "final")["credits"]
    assert d["credits"] < f["credits"]
    assert d["allowed"] and f["allowed"]


def test_entry_tier_sees_the_denial_and_the_reason():
    plan = cplan.build_plan("design a pouch", subscription="foundation")
    final = plan["options"]["final"]
    assert final["allowed"] is False
    assert "tier or above" in final["reason"]


def test_unknown_media_or_detail_fails_closed():
    with pytest.raises(ValueError):
        cplan.build_plan("x", media="hologram")
    with pytest.raises(ValueError):
        cplan.build_plan("x", detail="novel")


# ── confirmation ────────────────────────────────────────────────────────────

def test_cancel_and_edit_hold_no_credits():
    plan = cplan.build_plan("design a pouch")
    for action in ("cancel", "edit"):
        out = cplan.confirm(plan, action)
        assert out["ok"] is True and out["credits"] == 0 and out["reserve"] is None


def test_draft_returns_a_reserve_instruction_and_never_executes():
    plan = cplan.build_plan("design a pouch", subscription="mover")
    out = cplan.confirm(plan, "draft")
    assert out["ok"] is True and out["quality"] == "draft"
    assert out["reserve"]["amount"] == plan["options"]["draft"]["credits"]
    assert out["reserve"]["class"] == "creative"
    assert out["reserve"]["idempotency_key"] == f"{plan['plan_id']}:draft"
    assert out["instruction"]["job"] == "package_design"
    assert "ledger hold is the caller's" in out["message"]


def test_final_is_refused_when_the_tier_cannot_reach_it():
    plan = cplan.build_plan("design a pouch", subscription="foundation")
    out = cplan.confirm(plan, "final")
    assert out["ok"] is False
    assert "tier or above" in out["error"]
    assert out["reserve"] is None


def test_unknown_action_or_missing_plan_fails_closed():
    plan = cplan.build_plan("design a pouch")
    with pytest.raises(ValueError):
        cplan.confirm(plan, "publish")
    with pytest.raises(ValueError):
        cplan.confirm({}, "draft")


# ── the card Bojo renders ──────────────────────────────────────────────────

def test_card_carries_four_actions_and_the_cost():
    plan = cplan.build_plan("design a pouch", subscription="foundation")
    card = cplan.render_card(plan)
    assert card["kind"] == "generation_plan"
    assert card["plan_id"] == plan["plan_id"]
    ids = [a["id"] for a in card["options"]]
    assert ids == ["draft", "final", "edit", "cancel"]
    draft = next(a for a in card["options"] if a["id"] == "draft")
    final = next(a for a in card["options"] if a["id"] == "final")
    assert draft["credits"] > 0 and draft["enabled"] is True
    assert final["enabled"] is False and final["note"]
    assert card["title"].startswith("Plan ready")
    assert card["rows"]


# ── the chat tool Bojo actually calls ──────────────────────────────────────

def test_chat_tool_builds_a_plan_card_and_can_confirm_it():
    import chat_tools

    assert "creative_plan" in chat_tools.TOOLS
    made = chat_tools.run_tool("creative_plan", {
        "request": "design a 6 oz stand-up pouch for mushroom powder",
        "subscription": "mover", "detail": "detailed"})
    assert made["ok"] is True
    card = made["data"]["card"]
    plan = made["data"]["plan"]
    assert card["kind"] == "generation_plan"
    assert cplan.get(plan["plan_id"]) is not None       # remembered for the next turn

    confirmed = chat_tools.run_tool("creative_plan", {
        "plan_id": plan["plan_id"], "action": "final"})
    assert confirmed["ok"] is True
    assert confirmed["data"]["reserve"]["class"] == "creative"
    assert confirmed["data"]["reserve"]["amount"] == plan["options"]["final"]["credits"]

    cancelled = chat_tools.run_tool("creative_plan", {
        "plan_id": plan["plan_id"], "action": "cancel"})
    assert cancelled["ok"] is True
    assert cplan.get(plan["plan_id"]) is None            # cancelled plans are dropped


def test_chat_tool_reports_an_expired_plan_instead_of_inventing_one():
    import chat_tools

    out = chat_tools.run_tool("creative_plan", {"plan_id": "plan_nope", "action": "draft"})
    assert out["ok"] is False
    assert "no longer open" in out["summary"]


def test_chat_tool_requires_a_request_to_plan():
    import chat_tools

    out = chat_tools.run_tool("creative_plan", {})
    assert out["ok"] is False and "Tell me what to make" in out["summary"]


def test_create_focus_offers_the_creative_planner():
    import shell_focus

    assert "creative_plan" in (shell_focus.tools_for_focus("create") or [])
    # auto/autothink take all tools, so it is reachable there too by definition.
    assert shell_focus.tools_for_focus("auto") is None
