"""Ad formats: a placement fixes the canvas, and a contradiction is refused."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_formats as af  # noqa: E402


def test_the_three_placements_resolve_to_their_canvases():
    assert af.resolve("square")["width"] == 1024
    assert af.resolve("story")["height"] > af.resolve("story")["width"]
    assert af.resolve("wide")["width"] > af.resolve("wide")["height"]


@pytest.mark.parametrize("name", ["square", "story", "wide"])
def test_every_canvas_is_a_multiple_of_the_latent_step(name):
    preset = af.resolve(name)
    assert preset["width"] % af.LATENT_STEP == 0
    assert preset["height"] % af.LATENT_STEP == 0


def test_the_ratio_matches_the_canvas():
    for name in ("square", "story", "wide"):
        preset = af.resolve(name)
        assert af.ratio_of(preset["width"], preset["height"]) == preset["ratio"]


def test_an_unknown_format_is_refused_with_a_code():
    with pytest.raises(ValueError) as caught:
        af.resolve("billboard")
    assert "ad_format_unknown" in str(caught.value)


def test_a_contradictory_width_is_refused_not_overridden():
    with pytest.raises(ValueError) as caught:
        af.resolve("story", width=1024)
    message = str(caught.value)
    assert "ad_format_dimension_conflict" in message
    assert "864x1536" in message


def test_the_matching_width_is_accepted():
    preset = af.resolve("wide", width=1536, height=864)
    assert preset["format"] == "wide"


def test_no_format_and_no_size_means_the_provider_default():
    assert af.resolve(None) is None


def test_a_free_size_must_still_be_sampleable():
    assert af.resolve(None, width=1024, height=1024) is None
    with pytest.raises(ValueError) as caught:
        af.resolve(None, width=1023, height=1024)
    assert "ad_format_invalid_size" in str(caught.value)


def test_ratio_of_two_thirds_is_reduced():
    assert af.ratio_of(864, 576) == "3:2"
    assert af.ratio_of(1024, 1024) == "1:1"


def test_describe_lists_placements_for_the_ui():
    described = af.describe()
    assert len(described["formats"]) == 3
    story = next(f for f in described["formats"] if f["format"] == "story")
    assert "shorts" in story["placements"]


# --- the endpoint refuses before it renders ---------------------------------

def test_the_endpoint_refuses_a_conflicting_canvas_before_touching_the_engine():
    from fastapi.testclient import TestClient
    from main import app
    import design_studio_api

    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-ads"
    try:
        client = TestClient(app)
        r = client.post("/api/design-studio/generate",
                        json={"brief": "a pouch ad", "format": "story", "width": 1024})
        assert r.status_code == 422, r.text
        assert "ad_format_dimension_conflict" in r.text

        r = client.post("/api/design-studio/generate",
                        json={"brief": "a pouch ad", "format": "billboard"})
        assert r.status_code == 422
        assert "ad_format_unknown" in r.text

        listed = client.get("/api/design-studio/ad-formats")
        assert listed.status_code == 200
        assert {f["format"] for f in listed.json()["formats"]} == {"square", "story", "wide"}
    finally:
        app.dependency_overrides = {}
