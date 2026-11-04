"""The /generate contract for references and review.

No render is started here: these pin the refusals that happen before the engine
is touched, and the request fields the UI/agent use.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))


def _client(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    import design_studio_api
    import studio_generation

    monkeypatch.setattr(studio_generation, "engine_status",
                        lambda: {"armed": True, "reachable": True, "models": {}})
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-refs"
    return TestClient(app)


def _post(client, payload):
    return client.post("/api/design-studio/generate", json=payload)


def test_references_are_refused_for_video_renders(monkeypatch):
    from main import app

    try:
        client = _client(monkeypatch)
        r = _post(client, {"brief": "a 15 second pouch ad", "kind": "video",
                           "reference_asset_ids": ["asset-1"]})
        assert r.status_code == 422, r.text
        assert "reference_requires_image" in r.text
    finally:
        app.dependency_overrides = {}


def test_an_unknown_reference_asset_is_refused_before_rendering(monkeypatch):
    from main import app

    try:
        client = _client(monkeypatch)
        r = _post(client, {"brief": "a pouch on marble",
                           "reference_asset_ids": ["does-not-exist"]})
        assert r.status_code == 422, r.text
        assert "reference_asset_not_found" in r.text
    finally:
        app.dependency_overrides = {}


def test_generate_accepts_the_review_and_surface_fields(monkeypatch):
    from main import app

    try:
        client = _client(monkeypatch)
        # a canvas conflict is still refused before the engine, which proves the
        # new fields are accepted by the schema rather than rejected as unknown.
        r = _post(client, {"brief": "a pouch ad", "review": True,
                           "surface": "product_picture", "format": "story",
                           "width": 1024})
        assert r.status_code == 422 and "ad_format_dimension_conflict" in r.text
    finally:
        app.dependency_overrides = {}
