"""Box / bottle / tube compositors."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import format_compositors as fc

QUAD = [[80, 100], [320, 100], [320, 400], [80, 400]]


def _plate(w=400, h=500):
    img = Image.new("RGB", (w, h), (205, 180, 150))
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _label(w=240, h=300):
    img = Image.new("RGB", (w, h), (250, 248, 240))
    for x in range(20, w - 20):
        for y in range(40, 60):
            img.putpixel((x, y), (30, 30, 30))
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _img(png_bytes):
    return Image.open(BytesIO(png_bytes)).convert("RGB")


def test_box_warp_changes_the_plate_inside_the_quad_only():
    out = fc.box_composite(_plate(), _label(), QUAD, shade=0)
    img = _img(out["bytes"])
    assert out["warp"] == "perspective-quad"
    assert img.getpixel((0, 0)) == (205, 180, 150)      # outside untouched
    assert img.getpixel((200, 250)) != (205, 180, 150)  # inside composited


def test_box_rejects_a_bad_quad():
    with pytest.raises(ValueError):
        fc.box_composite(_plate(), _label(), [[0, 0], [10, 10]])


def test_bottle_resample_keeps_size_and_masks_the_seam():
    out = fc.bottle_composite(_plate(), _label(), QUAD, seam_gap_px=8)
    img = _img(out["bytes"])
    assert out["warp"] == "cylindrical"
    assert img.size == (400, 500)
    # the seam strip must stay plate-coloured, not label-coloured
    assert img.getpixel((82, 250)) == (205, 180, 150)


def test_bottle_reports_its_wrap_fraction():
    out = fc.bottle_composite(_plate(), _label(), QUAD, wrap_fraction=0.8)
    assert out["wrap_fraction"] == 0.8


def test_tube_masks_the_crimp_bands():
    out = fc.tube_composite(_plate(), _label(), QUAD, crimp_top=20, crimp_bottom=20)
    img = _img(out["bytes"])
    assert out["warp"] == "taper+quad"
    # just inside the top of the quad: masked, so still plate colour
    assert img.getpixel((200, 108)) == (205, 180, 150)


def test_tube_paints_below_the_crimp():
    out = fc.tube_composite(_plate(), _label(), QUAD, crimp_top=20, crimp_bottom=20)
    img = _img(out["bytes"])
    assert img.getpixel((200, 250)) != (205, 180, 150)


def test_dispatch_and_unknown_format():
    assert fc.composite("box", _plate(), _label(), QUAD)["warp"] == "perspective-quad"
    with pytest.raises(KeyError):
        fc.composite("sachet", _plate(), _label(), QUAD)


def test_every_compositor_returns_png_bytes_and_a_size():
    for kind in ("box", "bottle", "tube"):
        out = fc.composite(kind, _plate(), _label(), QUAD)
        assert out["bytes"][:4] == b"\x89PNG"
        assert out["size"] == [400, 500]
