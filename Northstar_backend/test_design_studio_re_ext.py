"""Endpoint smoke — print lane + design agent + auth boundary on the main app.

RE build 2026-10-16. Uses dependency overrides for identity (same trick the
repo's autothink route tests use with a patched user lookup), and NEVER touches
the engine or the network: dielines preview with persist=False and the agent
test does not enqueue.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import design_studio_api  # noqa: E402
from main import app  # noqa: E402


def _as_org():
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-smoke"


def _clear():
    app.dependency_overrides = {}


def test_print_templates_requires_session():
    # See test_text_fidelity: assert the hosted path with the dev shim off.
    previous = getattr(app.state, "dev_auto_session", False)
    app.state.dev_auto_session = False
    try:
        r = TestClient(app).get("/api/design-studio/print/templates")
        assert r.status_code == 401
    finally:
        app.state.dev_auto_session = previous


def test_print_health_and_dieline_roundtrip():
    _as_org()
    try:
        c = TestClient(app)
        r = c.get("/api/design-studio/print/health")
        assert r.status_code == 200, r.text
        assert r.json()["renderers"] == ["svg", "pdf"]

        r = c.get("/api/design-studio/print/templates")
        assert r.status_code == 200, r.text
        assert r.json()["units"] == "mm"
        assert len(r.json()["templates"]) >= 8

        r = c.post("/api/design-studio/print/dielines", json={
            "template_id": "label_circle",
            "params": {"width_mm": 50, "height_mm": 50},
            "persist": False,
            "include_svg": True,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert 'id="layer-trim"' in body["svg"]
        assert abs(body["size_mm"]["width"] - 56) < 0.01
        assert body["assets"] == []  # persist=False -> nothing stored

        r = c.post("/api/design-studio/print/dielines", json={
            "template_id": "rsc_box", "params": {"height_mm": 99999}, "persist": False,
        })
        assert r.status_code == 422

        r = c.post("/api/design-studio/print/dielines", json={
            "template_id": "rsc_box", "params": {"bogus_field": 5}, "persist": False,
        })
        assert r.status_code == 422
    finally:
        _clear()


def test_agent_brief_roundtrip_without_enqueue():
    _as_org()
    try:
        c = TestClient(app)
        r = c.post("/api/design-studio/agent/brief", json={
            "message": "eco soap bar box with kraft texture",
            "product": {"title": "Pine Tar Soap", "category": "personal care"},
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["brief"]["prompt_text"].startswith("[PRODUCT] Pine Tar Soap")
        assert body["enqueued"] is None
        assert body["reply"]

        r = c.post("/api/design-studio/agent/brief", json={"message": "x"})
        assert r.status_code == 422  # message too short
    finally:
        _clear()


def test_generate_model_accepts_long_design_briefs():
    """Regression (2026-10-16): MOGRA-style markdown briefs (>2000 chars) must
    validate - the old 2000 cap surfaced as a bare HTTP 422 in the studio queue."""
    from design_studio_api import GenerateIn
    long_brief = "# DESIGN BRIEF\n" + ("x" * 5000)
    m = GenerateIn(kind="image", brief=long_brief, tier="final")
    assert len(m.brief) == len(long_brief)


def test_generate_async_requires_session_before_engine_gate():
    previous = getattr(app.state, "dev_auto_session", False)
    app.state.dev_auto_session = False
    try:
        r = TestClient(app).post("/api/design-studio/generate-async",
                                 json={"brief": "a matte black box"})
        assert r.status_code == 401
    finally:
        app.state.dev_auto_session = previous
