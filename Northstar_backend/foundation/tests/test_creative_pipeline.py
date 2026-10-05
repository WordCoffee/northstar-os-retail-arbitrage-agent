"""Local creative media suite — offline, no downloads, no generation.

Verifies the model-chaining registry/planner: stage coverage, per-model install
state, commercial-safe preference, render modes, and unknown-goal handling.
"""
from __future__ import annotations

import json

from Northstar_backend import creative_pipeline as cp


def test_engine_is_comfyui():
    assert cp.ENGINE == "comfyui"
    assert cp.pipeline_status()["engine"] == "comfyui"


def test_status_covers_all_stages():
    s = cp.pipeline_status()
    stages = {x["stage"] for x in s["stages"]}
    assert {"image", "video_fast", "video_hero", "lipsync", "voice",
            "music", "upscale", "interpolate", "mux"} <= stages
    for x in s["stages"]:
        assert x["install_state"] in ("installed", "missing", "unknown")
        for m in x["models"]:
            assert m["install_state"] in ("installed", "missing", "unknown")
            assert isinstance(m["commercial_ok"], bool)
            assert m["license"]


def test_plan_ugc_is_commercial_safe():
    p = cp.plan_pipeline("ugc_talking_head")
    assert p["known"] is True
    assert [s["stage"] for s in p["steps"]] == ["image", "voice", "lipsync", "mux"]
    for s in p["steps"]:
        assert s["model"]["commercial_ok"] is True


def test_plan_prefer_commercial_false_allows_non_commercial():
    p = cp.plan_pipeline("product_image", prefer_commercial=False)
    image = next(s for s in p["steps"] if s["stage"] == "image")
    assert image["model"]["key"] in ("flux-dev-fp8", "flux2", "qwen-image-edit")


def test_unknown_goal_is_rejected():
    p = cp.plan_pipeline("does_not_exist")
    assert p["known"] is False
    assert p["reason"] == "unknown_goal"
    assert "ugc_talking_head" in p["available_goals"]


def test_plan_lists_owner_gated_steps():
    p = cp.plan_pipeline("cinematic_short")
    assert isinstance(p["owner_gated_steps"], list)


def test_render_modes_draft_and_final():
    assert set(cp.RENDER_MODES) == {"draft", "final"}
    d = cp.render_plan("cinematic_short", "draft")
    assert d["mode"] == "draft" and d["engine"] == "comfyui"
    assert "finish_stack" in d
    bad = cp.render_plan("cinematic_short", "nope")
    assert bad["known"] is False


def test_no_secrets_in_status():
    blob = json.dumps(cp.pipeline_status()).lower()
    for forbidden in ("api_key", "token", "secret", "password", "http://", "https://"):
        assert forbidden not in blob
