"""Provider-neutral media-generation architecture — offline, no provider calls.

Verifies the Path B interface: provider roster, capability→cost routing hooks,
planning spend caps, and that generation stays UNARMED with no secret leakage.
No provider is contacted and no credits are consumed.
"""
from __future__ import annotations

import json

from Northstar_backend import media_providers as mp


def test_spend_caps_are_planning_only():
    assert mp.SPEND_CAPS["enforced"] is False
    assert mp.SPEND_CAPS["per_call_usd"] > 0


def test_provider_roster_is_secret_free():
    roster = mp.list_providers()
    assert isinstance(roster, list) and roster
    for rec in roster:
        assert isinstance(rec["key_present"], bool)
        assert isinstance(rec["armed"], bool)
        assert "key_env" not in rec  # env var names are not exposed
    blob = json.dumps(roster).lower()
    for forbidden in ("api_key", "secret", "token", "password", "http://", "https://"):
        assert forbidden not in blob


def test_capabilities_cover_image_and_video():
    caps = {c["capability"] for c in mp.capabilities()}
    assert {"image.generate", "image.edit", "video.generate"} <= caps


def test_route_hook_returns_provider_and_model():
    r = mp.route("image", "draft")
    assert r and r["provider"] and r["model"]
    assert r["unit_cost_usd"] is not None


def test_estimate_cost_math():
    assert mp.estimate_cost("per_image", 0.03) == 0.03
    assert mp.estimate_cost("per_second", 0.10, seconds=5) == 0.5
    assert mp.estimate_cost("per_15s", 2.10, seconds=15) == 2.1
    assert mp.estimate_cost("per_15s", 0.75, seconds=30) == 1.5
    assert mp.estimate_cost("per_image", None) is None


def test_plan_is_not_armed_by_default():
    plan = mp.plan_generation("image", "draft")
    assert plan["status"] == "not_armed"
    assert plan["reason"] == "media_gate_off"
    assert plan["armed"] is False
    assert plan["key_present"] is False
    assert plan["within_spend_cap"] is True
    assert "no provider is contacted" in plan["note"].lower()


def test_plan_never_calls_a_provider(monkeypatch):
    # Even with the gate "on", no provider call happens here — status is only
    # 'ready' (a plan), never an execution.
    monkeypatch.setattr(mp, "media_live_armed", lambda: True)
    plan = mp.plan_generation("video", "draft", seconds=15)
    assert plan["status"] in ("provider_required", "ready")
    assert plan["status"] != "generated"
