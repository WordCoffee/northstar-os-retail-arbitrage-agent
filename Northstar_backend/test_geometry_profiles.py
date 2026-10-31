"""Packaging geometry profiles: box, bottle, tube, pouch."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geometry_profiles as gp


def test_box_perimeter_and_panels():
    b = gp.rigid_box(width=100, depth=50, height=200, glue_tab=15)
    assert b["dieline"]["perimeter"] == 300          # 2*(100+50)
    assert b["dieline"]["width"] == 315              # perimeter + glue tab
    assert [p["name"] for p in b["panels"]] == ["front", "right", "back", "left", "glue"]
    assert b["panels"][2]["x"] == 150                # back starts after front+depth
    assert b["clearances"]["corner_bleed_mm"] == 3


def test_box_rejects_zero_dimension():
    with pytest.raises(ValueError):
        gp.rigid_box(width=0, depth=50, height=200)


def test_bottle_wrap_fraction_and_seam():
    b = gp.bottle(diameter=60, height=200, label_height=80, label_top_offset=30,
                  cap_height=25, seam_clearance=6)
    circ = 3.141592653589793 * 60
    assert abs(b["circumference_mm"] - circ) < 0.01
    assert b["wrap_fraction"] == round((circ - 6) / circ, 4)
    assert b["arc_map"]["seam_angle_deg"] > 0
    assert b["usable_height_mm"] == 200 - 25 - 6


def test_bottle_refuses_a_label_taller_than_the_usable_area():
    with pytest.raises(ValueError):
        gp.bottle(diameter=60, height=100, label_height=90, label_top_offset=30)


def test_bottle_refuses_a_label_inside_the_cap():
    with pytest.raises(ValueError):
        gp.bottle(diameter=60, height=200, label_height=40, label_top_offset=10)


def test_bottle_quad_matches_the_pixel_scale():
    b = gp.bottle(diameter=60, height=200, label_height=80, label_top_offset=30, px_per_mm=6)
    assert b["radius_px"] == 180
    top = b["quad"][0][1]
    bottom = b["quad"][2][1]
    assert bottom - top == pytest.approx(80 * 6)


def test_tube_clearances_add_up():
    t = gp.tube(diameter=40, height=160, crimp_top=8, crimp_bottom=8, cap_height=20)
    assert t["usable_height_mm"] == 160 - 8 - 8 - 20
    assert t["label_aspect"] > 0.35


def test_tube_refuses_a_squat_label():
    with pytest.raises(ValueError, match="squat"):
        gp.tube(diameter=120, height=160, crimp_top=8, crimp_bottom=8, cap_height=20)


def test_tube_refuses_negative_usable_area():
    with pytest.raises(ValueError):
        gp.tube(diameter=40, height=30, crimp_top=10, crimp_bottom=10, cap_height=20)


def test_pouch_quad_excludes_weld_and_gusset():
    p = gp.pouch(width=100, height=200, top_weld=12, bottom_gusset=30, px_per_mm=6)
    assert p["usable_height_mm"] == 158
    assert p["quad"][0][1] == 72            # 12mm * 6
    assert p["quad"][3][1] == pytest.approx((12 + 158) * 6)


def test_pouch_refuses_impossible_heights():
    with pytest.raises(ValueError):
        gp.pouch(width=100, height=30, top_weld=12, bottom_gusset=30)


def test_profile_dispatch_and_unknown_format():
    assert gp.profile("box", width=10, depth=10, height=10)["kind"] == "box"
    with pytest.raises(KeyError):
        gp.profile("sachet", width=10)


def test_dpi_check_flags_a_low_resolution_scale():
    low = gp.profile("pouch", width=100, height=200, px_per_mm=1)
    high = gp.profile("pouch", width=100, height=200, px_per_mm=12)
    assert low["dpi_check"]["ok"] is False
    assert high["dpi_check"]["ok"] is True


def test_every_profile_is_json_serialisable():
    import json
    for kind, kw in {
        "box": {"width": 80, "depth": 40, "height": 180},
        "bottle": {"diameter": 60, "height": 200, "label_height": 80, "label_top_offset": 30},
        "tube": {"diameter": 40, "height": 160},
        "pouch": {"width": 100, "height": 200},
    }.items():
        json.dumps(gp.profile(kind, **kw))
