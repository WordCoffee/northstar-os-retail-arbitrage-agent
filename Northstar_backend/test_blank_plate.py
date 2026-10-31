"""Base-plate neutralisation + OCR refusal gate (blank-plate architecture)."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mockup_compositor as mc
import text_fidelity as tf


def _plate_with_text(w=400, h=500):
    """A kraft field with a black block where a label will land."""
    img = Image.new("RGB", (w, h), (196, 168, 132))
    for x in range(80, 320):
        for y in range(140, 360):
            img.putpixel((x, y), (240, 240, 240))
    for x in range(120, 280):
        for y in range(240, 260):
            img.putpixel((x, y), (20, 20, 20))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return img, buf.getvalue()


QUAD = [(80, 140), (320, 140), (320, 360), (80, 360)]


def test_neutralize_removes_contrast_under_the_quad():
    img, _ = _plate_with_text()
    out, info = mc.neutralize_quad(img, QUAD)
    assert info["neutralized"] is True
    assert info["area_px"] > 0
    # the dark block must be gone from the middle of the region
    before = img.getpixel((200, 250))
    after = out.getpixel((200, 250))
    assert min(before) < 60
    assert min(after) > 150


def test_neutralize_reports_the_sampled_field_colour():
    img, _ = _plate_with_text()
    _out, info = mc.neutralize_quad(img, QUAD)
    rgb = info["field_rgb"]
    assert len(rgb) == 3
    assert all(0 <= v <= 255 for v in rgb)


def test_neutralize_leaves_outside_pixels_untouched():
    img, _ = _plate_with_text()
    out, _ = mc.neutralize_quad(img, QUAD)
    assert out.getpixel((10, 10)) == img.getpixel((10, 10))


def test_neutralize_refuses_a_degenerate_quad():
    img, _ = _plate_with_text()
    out, info = mc.neutralize_quad(img, [(1, 1), (2, 2)])
    assert info["neutralized"] is False
    assert out.size == img.size


def test_assert_plate_clean_passes_on_a_blank_plate():
    buf = BytesIO()
    Image.new("RGB", (600, 600), (200, 190, 175)).save(buf, format="PNG")
    res = tf.assert_plate_clean(buf.getvalue())
    assert res["status"] in ("clean", "unavailable")


def test_assert_plate_clean_raises_on_a_plate_with_text():
    img = Image.new("RGB", (700, 400), (255, 255, 255))
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(img)
    d.text((20, 150), "LION'S MANE ORGANIC POWDER", fill=(0, 0, 0),
           font=ImageFont.truetype("arial.ttf", 46) if Path("C:/Windows/Fonts/arial.ttf").exists()
           else ImageFont.load_default())
    buf = BytesIO()
    img.save(buf, format="PNG")
    try:
        res = tf.assert_plate_clean(buf.getvalue())
        # OCR unavailable in this environment is a legitimate outcome, not a pass
        assert res["status"] == "unavailable"
    except tf.PlateNotClean as exc:
        assert exc.boxes >= 1
        assert "plate_not_clean" in str(exc)
