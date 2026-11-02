"""Dieline geometry: impossible specs are refused, valid ones still build.

The defect class under test is "silently clamped": a builder that shrinks a bad
number to something drawable produces a printable-looking file whose type sits on
the trim line. Every refusal below used to be a silent correction or a crash-free
wrong answer.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_studio_print as dp  # noqa: E402
import dieline_geometry as dg  # noqa: E402


def _label(**kw):
    return dp.build_label("rounded_rectangle", 90, 60, **kw)


def _codes(exc: Exception) -> list:
    assert isinstance(exc, dg.DielineGeometryError)
    return [v["code"] for v in exc.violations]


# --- positive controls: the gate must not invent violations ------------------

@pytest.mark.parametrize("template,params", [
    ("label_rounded_rectangle", {"width_mm": 90, "height_mm": 60}),
    ("label_circle", {"width_mm": 50, "height_mm": 50}),
    ("rsc_box", {"length_mm": 150, "width_mm": 120, "height_mm": 90}),
    ("tuck_end", {}),
    ("sleeve", {}),
    ("doypack", {"width_mm": 150, "height_mm": 210, "gusset_mm": 80}),
])
def test_every_shipping_template_passes_the_audit(template, params):
    build = dp.build_from_template(template, params)
    report = dg.audit(build)
    assert report["ok"], report["violations"]


# --- refusals ----------------------------------------------------------------

def test_a_safe_margin_wider_than_the_label_is_refused_not_clamped():
    with pytest.raises(dg.DielineGeometryError) as caught:
        dp.build_label("rounded_rectangle", 20, 20, bleed_mm=3, safe_mm=12)
    assert "safe_inverted" in _codes(caught.value)


def test_a_safe_margin_equal_to_half_the_face_is_refused():
    # exactly half leaves a zero-width safe area: the same defect, at the boundary
    with pytest.raises(dg.DielineGeometryError):
        dp.build_label("rectangle", 20, 40, bleed_mm=3, safe_mm=10)


def test_zero_bleed_is_refused():
    build = _label(bleed_mm=3, safe_mm=3)
    build["meta"]["bleed_mm"] = 0.0
    report = dg.audit(build)
    assert "bleed_missing" in [v["code"] for v in report["violations"]]


def test_a_face_below_the_tooling_floor_is_refused():
    with pytest.raises(dg.DielineGeometryError) as caught:
        dp.build_label("rectangle", 8, 8, bleed_mm=2, safe_mm=2)
    assert "face_below_min" in _codes(caught.value)


def test_a_negative_panel_is_refused():
    build = dp.build_from_template("rsc_box", {"length_mm": 150, "width_mm": 120,
                                               "height_mm": 90})
    build["meta"]["panels"] = [150.0, -120.0, 150.0, 120.0, 15.0]
    report = dg.audit(build)
    assert "panels_invalid" in [v["code"] for v in report["violations"]]


def test_a_flap_deeper_than_the_body_is_refused():
    build = _label()
    build["meta"].update({"panels": [90.0], "body_h": 40.0,
                          "top_depths": [55.0], "bottom_depths": [10.0]})
    assert "tab_deeper_than_body" in [v["code"] for v in dg.audit(build)["violations"]]


# --- artwork placement -------------------------------------------------------

def test_each_carton_panel_gets_its_own_safe_box():
    build = dp.build_from_template("rsc_box", {"length_mm": 150, "width_mm": 120,
                                               "height_mm": 90})
    boxes = dg.art_boxes(build)
    assert len(boxes) == len(build["meta"]["panels"])
    for box in boxes:
        assert box["w"] > 0 and box["h"] > 0
        assert box["safe_source"] in ("declared", "default")


def test_artwork_that_fits_a_panel_is_accepted():
    build = dp.build_from_template("rsc_box", {"length_mm": 150, "width_mm": 120,
                                               "height_mm": 90})
    box = dg.art_boxes(build)[1]
    verdict = dg.audit_artwork(build, {"x": box["x"] + 1, "y": box["y"] + 1,
                                       "w": box["w"] - 2, "h": box["h"] - 2})
    assert verdict["ok"], verdict["violations"]


def test_artwork_straddling_a_fold_is_refused():
    build = dp.build_from_template("rsc_box", {"length_mm": 150, "width_mm": 120,
                                               "height_mm": 90})
    boxes = dg.art_boxes(build)
    a, b = boxes[0], boxes[1]
    spanning = {"x": a["x"], "y": a["y"], "w": (b["x"] + b["w"]) - a["x"], "h": a["h"]}
    verdict = dg.audit_artwork(build, spanning)
    assert verdict["ok"] is False
    assert verdict["violations"][0]["code"] == "artwork_outside_safe"


def test_artwork_in_the_bleed_margin_is_refused():
    build = _label()
    trim = dg._layer_bounds(build, "trim")
    verdict = dg.audit_artwork(build, {"x": 0.5, "y": trim[1] + 2,
                                       "w": 10, "h": 10})
    assert verdict["ok"] is False


# --- the doypack regression found by this audit ------------------------------

def test_doypack_panels_sit_inside_the_trim_after_the_weld_fix():
    build = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                               "gusset_mm": 80})
    trim = dg._layer_bounds(build, "trim")
    back = build["meta"]["panels"]["back"]
    assert back[1] + back[3] <= trim[3] + dg.TOL, (
        "the back panel used to run one weld thickness past the trim line")
    assert dg.audit(build)["ok"]


# --- the endpoint refuses instead of drawing ---------------------------------

def test_the_dieline_endpoint_refuses_an_inverted_safe_margin():
    from fastapi.testclient import TestClient
    from main import app
    import design_studio_api

    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-geom"
    try:
        r = TestClient(app).post("/api/design-studio/print/dielines",
                                 json={"template_id": "label_rounded_rectangle",
                                       "params": {"width_mm": 20, "height_mm": 20,
                                                  "safe_mm": 12}})
        assert r.status_code == 422, r.text
        assert "safe_inverted" in r.text
    finally:
        app.dependency_overrides = {}
