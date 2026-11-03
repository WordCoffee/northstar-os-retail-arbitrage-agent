"""Contracts for a designed product picture.

The owner asked for a pouch picture and received flat label art. These tests pin
the three primitives that stop that happening again: a panel really lands on the
plate's face and nowhere else, a plate with no package is refused, and a picture
whose copy cannot be read is refused.

The executable acceptance lives in state/probes/t10..t12; this file keeps the
same behaviour under pytest with a few extra edges.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import mockup_compositor as mc
import mockup_quality as mq

QUAD = [(200, 150), (600, 170), (590, 880), (210, 860)]


def _plate(size=(800, 1000), colour=(236, 233, 227)) -> Image.Image:
    return Image.new("RGB", size, colour)


def _panel(size=(400, 600), margin=6) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([margin, margin, size[0] - margin - 1, size[1] - margin - 1],
                fill=(247, 243, 235, 255))
    d.rectangle([40, 60, size[0] - 40, 150], fill=(23, 23, 23, 255))
    return img


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── composite ───────────────────────────────────────────────────────────────

def test_composite_returns_the_plate_and_paints_the_face_only():
    plate = _plate()
    ImageDraw.Draw(plate).polygon(QUAD, fill=(213, 167, 122))
    before = np.asarray(plate).copy()

    out = mc.composite_panel_onto_quad(plate, _panel(), QUAD, feather=None)
    assert out.size == plate.size

    arr = np.asarray(out)
    out_quad = np.ones(plate.size[::-1], dtype=bool)
    mask = Image.new("L", plate.size, 0)
    ImageDraw.Draw(mask).polygon(QUAD, fill=255)
    out_quad = np.asarray(mask) > 0

    # every panel corner is stock, not the untouched plate
    for x, y in QUAD:
        assert arr[y, x, :3].sum() > 600, f"corner {(x, y)} was not painted: {arr[y, x]}"
    # nothing outside the face changed
    assert np.array_equal(arr[~out_quad], before[~out_quad])


def test_composite_crops_a_transparent_trim_margin():
    plate = _plate()
    out = mc.composite_panel_onto_quad(plate, _panel(margin=20), QUAD, feather=None)
    arr = np.asarray(out)
    for x, y in QUAD:
        assert arr[y, x, :3].sum() > 600


def test_composite_refuses_a_degenerate_quad():
    with pytest.raises(ValueError, match="degenerate"):
        mc.composite_panel_onto_quad(_plate(), _panel(), [(10, 10), (10, 10), (10, 10), (10, 10)])


# ── plate face detection ────────────────────────────────────────────────────

def test_a_plate_with_no_package_is_refused():
    with pytest.raises(ValueError, match="plate_face_not_found"):
        mc.find_panel_quad(_plate())


def test_a_real_pouch_plate_yields_a_quad_on_the_package():
    plate = _plate((600, 900))
    d = ImageDraw.Draw(plate)
    d.polygon([(190, 120), (410, 120), (430, 780), (170, 780)], fill=(213, 167, 122))
    quad = mc.find_panel_quad(plate)
    assert len(quad) == 4
    for x, y in quad:
        assert 150 <= x <= 450
        assert 100 <= y <= 820


# ── feather guard ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_failed_warp_fit_is_refused(bad):
    with pytest.raises(ValueError):
        mc.feather_sigma(bad)


def test_a_finite_residual_still_clamps_monotonically():
    assert mc.feather_sigma(0.0) <= mc.feather_sigma(6.0) <= mc.feather_sigma(50.0)
    assert mc.feather_sigma(50.0) == 12.0


# ── legibility gate (gate logic with synthetic OCR boxes) ───────────────────

def _readable(stock=(247, 243, 235), blur=0.0) -> Image.Image:
    img = Image.new("RGB", (1200, 1600), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 120, 1080, 1480], fill=stock)
    f = ImageFont.truetype(r"C:\Windows\Fonts\georgiab.ttf", 120)
    d.text((180, 300), "MOGRA", font=f, fill=(23, 23, 23))
    f2 = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 64)
    d.text((180, 1200), "6 oz (170 g)", font=f2, fill=(23, 23, 23))
    return img.filter(ImageFilter.GaussianBlur(blur)) if blur else img


def test_the_gate_sharpens_its_own_measurement(monkeypatch):
    """The gate must not trust words alone: a blurred box is a refusal."""
    img = _readable(blur=6)
    boxes = [(150, 280, 700, 380, "MOGRA"), (150, 1180, 520, 1260, "6 oz (170 g)")]
    monkeypatch.setattr(mq.tf, "_ocr_boxes", lambda _b: ((img, boxes), None))
    result = mq.assert_legible(img)
    assert result["ok"] is False
    assert "soft" in result["reason"] or "small" in result["reason"]


def test_the_gate_accepts_sharp_readable_type(monkeypatch):
    img = _readable()
    boxes = [(150, 280, 700, 380, "MOGRA"), (150, 1180, 520, 1260, "6 oz (170 g)")]
    monkeypatch.setattr(mq.tf, "_ocr_boxes", lambda _b: ((img, boxes), None))
    result = mq.assert_legible(img, wordmark="MOGRA", net_weight="6 oz")
    assert result["ok"] is True, result
    assert result["sharpness"] >= mq.MIN_BOX_SHARPNESS


def test_the_gate_refuses_a_picture_with_no_weight(monkeypatch):
    img = _readable()
    boxes = [(150, 280, 700, 380, "MOGRA")]
    monkeypatch.setattr(mq.tf, "_ocr_boxes", lambda _b: ((img, boxes), None))
    result = mq.assert_legible(img)
    assert result["ok"] is False
    assert result["reason"].startswith("net_weight_not_read")


def test_the_gate_is_fail_closed_when_ocr_is_unavailable(monkeypatch):
    monkeypatch.setattr(mq.tf, "_ocr_boxes", lambda _b: (None, "unavailable"))
    result = mq.assert_legible(_readable())
    assert result["ok"] is False
    assert result["reason"] == "ocr_unavailable"
