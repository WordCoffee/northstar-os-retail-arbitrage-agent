"""Print lane unit tests — layered SVG/PDF dielines (no providers, no DB, no cost).

RE build 2026-10-16: verifies the parametric dieline geometry + renderers that
close the "print lane" gap identified against Packify.ai / DYP.ai.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_print as dp  # noqa: E402


def test_templates_catalog_covers_labels_and_cartons():
    ids = {t["id"] for t in dp.TEMPLATES}
    for required in ("label_rounded_rectangle", "label_circle", "rsc_box", "tuck_end", "sleeve"):
        assert required in ids, required
    for t in dp.TEMPLATES:
        assert t["kind"] in ("label", "carton")
        for key in t["editable"]:
            assert key in t["params"], (t["id"], key)


def test_label_build_layers_and_dimensions():
    build = dp.build_label("rounded_rectangle", 90, 60, bleed_mm=3, safe_mm=3)
    assert abs(build["width_mm"] - 96) < 0.01
    assert abs(build["height_mm"] - 66) < 0.01
    layers = {it["layer"] for it in build["layers"]}
    assert {"bleed", "trim", "safe", "info"} <= layers
    assert build["meta"]["shape"] == "rounded_rectangle"


def test_rsc_blank_geometry_math():
    build = dp.build_carton("rsc_box", 200, 150, 100, flap_mm=75, glue_mm=15, bleed_mm=3)
    meta = build["meta"]
    assert meta["panels"] == [200, 150, 200, 150, 15]
    # blank width = 2*(L+W) + glue + 2*bleed ; height = H + 2*flap + 2*bleed
    assert abs(build["width_mm"] - (2 * 200 + 2 * 150 + 15 + 6)) < 0.5
    assert abs(build["height_mm"] - (100 + 2 * 75 + 6)) < 0.5
    # fold lines present (top/bottom + 4 vertical boundaries) and cut slits exist
    folds = [it for it in build["layers"] if it["layer"] == "fold"]
    assert len(folds) >= 6
    trims = [it for it in build["layers"] if it["layer"] == "trim" and it["kind"] == "line"]
    assert trims  # outline + equal-depth slits


def test_tuck_end_with_mixed_depths_builds():
    build = dp.build_carton("tuck_end", 90, 60, 160)
    assert build["meta"]["template"] == "tuck_end"
    assert build["meta"]["tuck_mm"] > build["meta"]["dust_mm"]


def test_svg_layers_units_and_determinism():
    build = dp.build_from_template("label_circle", {"width_mm": 50, "height_mm": 50})
    svg = dp.render_svg(build)
    for layer_id in ("layer-bleed", "layer-trim", "layer-fold", "layer-safe", "layer-info"):
        assert f'id="{layer_id}"' in svg
    assert svg.startswith("<svg") and 'width="56mm"' in svg and "viewBox=" in svg
    again = dp.render_svg(dp.build_from_template("label_circle", {"width_mm": 50, "height_mm": 50}))
    # generated_at differs; geometry must be identical
    import re
    strip = lambda s: re.sub(r"<desc>.*?</desc>", "", s, flags=re.S)
    assert strip(svg) == strip(again)


def test_pdf_renders_real_bytes():
    build = dp.build_from_template("rsc_box", {"length_mm": 150, "width_mm": 120, "height_mm": 90})
    pdf = dp.render_pdf(build)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 800


def test_sanitize_empty_values_keep_defaults():
    """A cleared field must never 422 - it falls back to the template default."""
    clean = dp.sanitize_params("rsc_box", {"height_mm": "", "width_mm": None, "length_mm": "  "})
    defaults = dp._TEMPLATE_BY_ID["rsc_box"]["params"]
    assert clean["height_mm"] == defaults["height_mm"]
    assert clean["width_mm"] == defaults["width_mm"]
    assert clean["length_mm"] == defaults["length_mm"]


def test_sanitize_rejects_unknown_keys_and_ranges():
    with pytest.raises(ValueError):
        dp.sanitize_params("rsc_box", {"heigth_mm": 100})  # typo key
    with pytest.raises(ValueError):
        dp.sanitize_params("rsc_box", {"height_mm": 99999})
    with pytest.raises(ValueError):
        dp.sanitize_params("no_such_template", {})
    with pytest.raises(ValueError):
        dp.build_label("square", 60, 40)  # square requires w == h
    with pytest.raises(ValueError):
        dp.build_label("hexagon", 60, 40)
    with pytest.raises(ValueError):
        dp.build_carton("mailer", 100, 100, 100)
