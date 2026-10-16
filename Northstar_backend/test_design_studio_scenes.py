"""Mockup scene/product gallery tests (RE build 2026-10-16, item 2).

Offline: no engine, no provider; enqueue is faked.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import design_studio_api  # noqa: E402
import design_studio_print as dp  # noqa: E402
import design_studio_scenes as scenes  # noqa: E402
from main import app  # noqa: E402


def test_catalog_integrity_and_template_cross_check():
    ids = [s["id"] for s in scenes.SCENES]
    assert len(ids) == len(set(ids)) == 8
    pids = [p["id"] for p in scenes.PRODUCTS]
    assert len(pids) == len(set(pids)) == 8
    template_ids = {t["id"] for t in dp.TEMPLATES}
    for p in scenes.PRODUCTS:
        assert p["templates"], p["id"]
        for t in p["templates"]:
            assert t in template_ids, (p["id"], t)


def test_assemble_prompt_sections():
    prompt = scenes.assemble_mockup_prompt(
        scene=scenes.SCENES[0], product=scenes.PRODUCTS[0],
        custom_prompt="add dried orange slices", message="holiday listing")
    for section in ("[PRODUCT]", "[SCENE]", "[CUSTOM PROMPT]", "[BRIEF]", "[NEGATIVE]"):
        assert section in prompt


def _as_org():
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-scenes"


def _clear():
    app.dependency_overrides = {}


def test_scenes_requires_session():
    r = TestClient(app).get("/api/design-studio/scenes")
    assert r.status_code == 401


def test_mockup_plan_roundtrip():
    _as_org()
    try:
        c = TestClient(app)
        r = c.get("/api/design-studio/scenes")
        assert r.status_code == 200 and len(r.json()["scenes"]) == 8

        r = c.post("/api/design-studio/mockup/plan", json={
            "product_id": "standup-pouch", "scene_id": "kitchen-marble",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["prompt"].startswith("[PRODUCT] Stand-up pouch")
        assert "[SCENE] Kitchen — marble counter" in body["prompt"]
        assert body["suggested_templates"] == ["label_rounded_rectangle"]
        assert body["enqueued"] is None

        r = c.post("/api/design-studio/mockup/plan", json={"scene_id": "nope"})
        assert r.status_code == 422
        r = c.post("/api/design-studio/mockup/plan", json={})
        assert r.status_code == 422
    finally:
        _clear()


def test_mockup_plan_enqueue_calls_async_lane(monkeypatch):
    _as_org()
    called = {}

    def fake_submit(acct, **kw):
        called.update({"acct": acct, **kw})
        return {"job": {"id": "job-scene-1", "status": "queued"}, "enforce": False}

    monkeypatch.setattr(scenes, "submit_generation", fake_submit)
    try:
        c = TestClient(app)
        r = c.post("/api/design-studio/mockup/plan", json={
            "product_id": "cream-jar", "scene_id": "bathroom-spa", "enqueue": True,
        })
        assert r.status_code == 200, r.text
        assert r.json()["enqueued"]["job"]["id"] == "job-scene-1"
        assert called["purpose"] == "mockup-plan" and called["kind"] == "image"
    finally:
        _clear()
