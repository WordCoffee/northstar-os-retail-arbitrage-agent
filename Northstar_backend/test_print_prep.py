"""Print prepress: measured DPI report, print gate, dieline sidecar."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geometry_profiles as gp
import print_prep as pp

BOX = gp.profile("box", width=80, depth=40, height=180)
BOTTLE = gp.profile("bottle", diameter=60, height=200,
                    label_height=80, label_top_offset=30)
TUBE = gp.profile("tube", diameter=40, height=160)
POUCH = gp.profile("pouch", width=100, height=200)


def test_face_pixels_uses_opposite_edge_means():
    px = pp.face_pixels([[0, 0], [100, 0], [90, 200], [10, 200]])
    assert px["width"] == 90.0          # mean of 100 px top and 80 px bottom
    assert px["height"] == pytest.approx(200.25, abs=0.01)


def test_box_face_below_300_dpi_is_reported():
    rep = pp.dpi_report(BOX, (1024, 1024),
                        [[0, 0], [570, 0], [570, 700], [0, 700]])
    assert rep["ok"] is False
    assert rep["worst"] < 300
    assert rep["deficit_px"]["width"] > 0
    assert rep["px_per_mm"]["target"] == pytest.approx(11.811, abs=0.01)


def test_box_face_at_target_dpi_passes():
    # 80 mm * 11.811 = 944.9 px; 180 mm * 11.811 = 2126 px.
    rep = pp.dpi_report(BOX, (2400, 2400),
                        [[0, 0], [945, 0], [945, 2126], [0, 2126]])
    assert rep["ok"] is True
    assert rep["worst"] >= 299.9


def test_validate_print_raises_below_target():
    with pytest.raises(pp.PrintDPIError):
        pp.validate_print(BOX, (1024, 1024),
                          [[0, 0], [570, 0], [570, 700], [0, 700]])


def test_validate_print_returns_report_at_target():
    rep = pp.validate_print(BOX, (2400, 2400),
                            [[0, 0], [945, 0], [945, 2126], [0, 2126]])
    assert rep["ok"] is True


def test_every_format_has_a_physical_face():
    for profile in (BOX, BOTTLE, TUBE, POUCH):
        face = pp.physical_face(profile)
        assert face["width"] > 0 and face["height"] > 0


def test_sidecar_writes_quad_scale_dpi_and_colour_profile(tmp_path):
    path = tmp_path / "02_labelled.dieline.json"
    data = pp.emit_sidecar(
        path, kind="box", profile=BOX, image_size=(1024, 1024),
        quad=[[397.1, 169.0], [817.2, 164.9], [816.0, 820.8], [397.1, 873.1]],
        method="box-quad", residual_px=0.159)
    assert path.is_file()
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["schema"] == pp.SCHEMA
    assert on_disk["quad"][0] == [397.1, 169.0]
    assert on_disk["scale_factors"]["px_per_mm_x"] > 0
    assert on_disk["dpi"]["target"] == 300
    assert on_disk["color_profile"]["working"] == "RGB"
    assert on_disk["color_profile"]["target"] == "CMYK"
    assert on_disk["print_ready"] is False
    assert data["face_px"]["width"] > 0


def test_sidecar_can_be_print_ready(tmp_path):
    path = tmp_path / "02_labelled.dieline.json"
    data = pp.emit_sidecar(
        path, kind="box", profile=BOX, image_size=(2400, 2400),
        quad=[[0, 0], [945, 0], [945, 2126], [0, 2126]], method="box-quad")
    assert data["print_ready"] is True
