"""A+ module geometry (Phase 1, item 1)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aplus_layout import CANVAS, TILE, crop_rect, layout, pixel_plan, responsive_rules, validate

# Sizes verified in specialists/image_aplus.MODULES. For the tiled modules the
# planner's w/h is the TILE, so the contract is: tile size matches, row = 970.
VERIFIED = {
    "header": (970, 600), "logo": (600, 180), "banner": (970, 300),
    "sidebar": (300, 400), "sidebar_thumb": (350, 175),
    "single": (300, 300),
    "premium_desktop": (1464, 600), "premium_mobile": (600, 450),
}
VERIFIED_TILES = {"three_tiles": (300, 300), "four_tiles": (220, 220)}


def test_canvas_matches_the_verified_planner_sizes():
    for kind, size in VERIFIED.items():
        assert CANVAS[kind] == size, kind
    for kind, size in VERIFIED_TILES.items():
        assert TILE[kind] == size, kind
        assert CANVAS[kind] == (970, size[1]), kind


def test_every_module_validates():
    for kind in CANVAS:
        assert validate(layout(kind)) == [], kind


def test_header_copy_band_is_even_and_inside_the_canvas():
    m = pixel_plan("header")
    copy = m["copy"]
    assert copy["w"] % 2 == 0
    assert copy["x"] + copy["w"] <= 970
    assert copy["h"] == 600


def test_copy_side_flips_the_band():
    left = layout("banner", copy_side="left")["copy"]
    right = layout("banner", copy_side="right")["copy"]
    assert left["x"] == 24
    assert right["x"] == 970 - right["w"]
    assert left["w"] == right["w"]


def test_three_tiles_are_exactly_300_and_centred():
    tiles = layout("three_tiles")["tiles"]
    assert [t["w"] for t in tiles] == [300, 300, 300]
    assert tiles[0]["x"] == 15
    assert tiles[2]["x"] + 300 == 955
    # equal side margins
    assert tiles[0]["x"] == 970 - (tiles[2]["x"] + 300)


def test_four_tiles_fill_970_exactly():
    tiles = layout("four_tiles")["tiles"]
    total = sum(t["w"] for t in tiles) + 30 * 3
    assert total == 970
    assert tiles[0]["x"] == 0
    assert tiles[3]["x"] + tiles[3]["w"] == 970


def test_comparison_columns_are_contiguous_and_fit():
    comp = layout("comparison")["comparison"]
    label = comp["label_col"]
    cols = comp["columns"]
    assert label["w"] == 250
    assert cols[0]["x"] == 250
    assert cols[1]["x"] == cols[0]["x"] + cols[0]["w"]
    assert cols[1]["x"] + cols[1]["w"] <= 970
    assert comp["header"]["h"] == 90
    assert comp["rows"] == 4


def test_crop_rect_centres_a_wide_source():
    c = crop_rect(4000, 1000, 970, 600)   # source wider than the box
    assert c["source"]["h"] == 1000
    assert c["source"]["w"] == round(1000 * (970 / 600))
    assert c["source"]["x"] == (4000 - c["source"]["w"]) // 2


def test_crop_rect_centres_a_tall_source():
    c = crop_rect(1000, 4000, 970, 600)
    assert c["source"]["w"] == 1000
    assert c["source"]["h"] == round(1000 / (970 / 600))
    assert c["source"]["y"] == (4000 - c["source"]["h"]) // 2


def test_crop_rect_rejects_zero():
    with pytest.raises(ValueError):
        crop_rect(0, 100, 10, 10)


def test_responsive_scales_never_grow():
    r = responsive_rules(970, 600)
    assert r["desktop"]["scale"] == 1.0
    assert r["tablet"]["scale"] < 1.0
    assert r["mobile"]["scale"] < r["tablet"]["scale"]
    assert r["object_fit"] == "cover"


def test_unknown_kind_is_a_keyerror():
    with pytest.raises(KeyError):
        layout("does_not_exist")


def test_pixel_plan_marks_valid():
    assert pixel_plan("three_tiles")["valid"] is True
