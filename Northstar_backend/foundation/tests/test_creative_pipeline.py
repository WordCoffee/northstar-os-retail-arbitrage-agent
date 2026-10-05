"""Local creative media suite — offline, no downloads, no generation.

Verifies the model-chaining registry/planner: stage coverage, per-model install
state, commercial-safe preference, and unknown-goal handling.
"""
from __future__ import annotations

from Northstar_backend import creative_pipeline as cp


def test_status_covers_all_stages():
    s = cp.pipeline_status()
    stages = {x["stage"] for x in s["stages"]}
    assert {"image", "voice", "lipsync", "video", "music", "upscale", "mux"} <= stages
    for x in s["stages"]:
        assert x["install_state"] in ("installed", "missing", "unknown")
        for m in x["models"]:
            assert m["install_state"] in ("installed", "missing", "unknown")
            assert isinstance(m["commercial_ok"], bool)
            assert m["license"]


def test_plan_ugc_is_commercial_safe():
    p = cp.plan_pipeline("ugc_talking_head")
    assert p["known"] is True
    stages = [s["stage"] for s in p["steps"]]
    assert stages == ["image", "voice", "lipsync", "mux"]
    for s in p["steps"]:
        assert s["model"]["commercial_ok"] is True


def test_plan_prefer_commercial_false_allows_non_commercial():
    p = cp.plan_pipeline("product_image", prefer_commercial=False)
    # image stage may then pick the already-installed non-commercial FLUX dev
    image = next(s for s in p["steps"] if s["stage"] == "image")
    assert image["model"]["key"] in ("flux-dev-fp8", "flux2-klein-4b")


def test_unknown_goal_is_rejected():
    p = cp.plan_pipeline("does_not_exist")
    assert p["known"] is False
    assert p["reason"] == "unknown_goal"
    assert "ugc_talking_head" in p["available_goals"]


def test_plan_lists_owner_gated_steps():
    p = cp.plan_pipeline("cinematic_short")
    # video/music are not installed in CI -> gated steps are listed
    assert isinstance(p["owner_gated_steps"], list)


def test_no_secrets_in_status():
    import json
    blob = json.dumps(cp.pipeline_status()).lower()
    for forbidden in ("api_key", "token", "secret", "password", "http://", "https://"):
        assert forbidden not in blob
