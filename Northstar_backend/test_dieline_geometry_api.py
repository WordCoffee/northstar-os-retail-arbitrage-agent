"""U8 final — the dieline guide-geometry endpoint the studio overlay draws from.

The overlay must never disagree with the dieline it sits on, so this endpoint is
the SAME builder the print lane uses and returns only the guide layers.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_geometry_returns_the_guide_layers_for_a_doypack(client):
    r = client.post("/api/design-studio/print/dielines/geometry",
                    json={"template_id": "doypack",
                          "params": {"width_mm": 150, "height_mm": 210, "gusset_mm": 40}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["template"] == "doypack"
    assert body["width_mm"] > 0 and body["height_mm"] > 0
    assert set(body["guides"]) >= {"bleed", "trim", "safe", "fold"}
    assert body["panels"]["front"][2] == pytest.approx(150, abs=0.5)
    assert body["panels"]["back"][2] == pytest.approx(150, abs=0.5)
    # The response carries the print lane's own caveat, not a stronger claim.
    assert "confirm" in (body.get("note") or "").lower()


def test_geometry_is_the_same_builder_as_the_dieline(client):
    """A guide that disagrees with the dieline would be a lie drawn on artwork."""
    from design_studio_print import build_from_template

    params = {"width_mm": 150, "height_mm": 210, "gusset_mm": 40}
    build = build_from_template("doypack", params)
    r = client.post("/api/design-studio/print/dielines/geometry",
                    json={"template_id": "doypack", "params": params})
    body = r.json()
    assert body["width_mm"] == build["width_mm"]
    assert body["height_mm"] == build["height_mm"]
    trim_layers = [l for l in build["layers"] if l.get("layer") == "trim"]
    assert len(body["guides"]["trim"]) == len(trim_layers)


def test_an_unknown_template_is_refused(client):
    r = client.post("/api/design-studio/print/dielines/geometry",
                    json={"template_id": "not-a-dieline", "params": {}})
    assert r.status_code == 422, r.text
