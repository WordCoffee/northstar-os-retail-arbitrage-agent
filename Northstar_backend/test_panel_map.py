"""Tests for per-surface panel mapping (the 2-D answer to Packify's UVs)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_studio_print as dsp  # noqa: E402
from specialists import panel_map  # noqa: E402

FACE = [[100.0, 50.0], [900.0, 50.0], [860.0, 1150.0], [140.0, 1150.0]]


def test_a_doypack_splits_into_three_surfaces():
    build = dsp.build_from_template("doypack", {"width_mm": 95, "height_mm": 200,
                                                "gusset_mm": 80})
    parts = panel_map.panel_quads(FACE, build["meta"]["panels"])
    names = [p["surface"] for p in parts]
    assert names == ["gusset_left", "front", "gusset_right"]
    shares = [p["share"] for p in parts]
    assert abs(sum(shares) - 1.0) < 1e-9
    # 95 mm front + 2 x (80 mm gusset x 0.35 foreshortening)
    expected_front = 95 / (95 + 2 * 80 * panel_map.GUSSET_FORESIGHTEN)
    assert abs(parts[1]["share"] - expected_front) < 1e-9
    # the front is the dominant surface once the gusset is foreshortened
    assert parts[1]["share"] > parts[0]["share"]


def test_quads_tile_the_face_without_gaps_or_overlap():
    build = dsp.build_from_template("doypack", {"width_mm": 120, "height_mm": 200,
                                                "gusset_mm": 40})
    parts = panel_map.panel_quads(FACE, build["meta"]["panels"])
    assert parts[0]["quad"][0] == FACE[0]          # starts at the left edge
    assert parts[-1]["quad"][1] == FACE[1]         # ends at the right edge
    for a, b in zip(parts, parts[1:]):
        assert a["quad"][1] == b["quad"][0]        # shared top-edge point
        assert a["quad"][2] == b["quad"][3]        # shared bottom-edge point


def test_a_pack_without_a_gusset_returns_the_original_quad():
    parts = panel_map.panel_quads(FACE, {"front": [0, 0, 100, 100], "gusset": [0, 0, 0, 0]})
    assert len(parts) == 1 and parts[0]["surface"] == "front"
    assert parts[0]["quad"] == FACE


def test_missing_panel_meta_degrades_to_a_single_surface():
    parts = panel_map.panel_quads(FACE, {})
    assert len(parts) == 1 and parts[0]["share"] == 1.0


def test_a_bad_quad_is_rejected():
    with pytest.raises(ValueError):
        panel_map.panel_quads([[0, 0], [1, 1]], {})


def test_describe_is_readable():
    build = dsp.build_from_template("doypack", {"width_mm": 95, "height_mm": 200,
                                                "gusset_mm": 80})
    text = panel_map.describe(build["meta"]["panels"])
    assert "front" in text and "%" in text
