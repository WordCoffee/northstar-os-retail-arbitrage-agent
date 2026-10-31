"""Box / bottle / tube compositors."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

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


def _quadrant_label(w=240, h=300):
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w // 2, h // 2], fill=(220, 30, 30))       # TL red
    d.rectangle([w // 2, 0, w, h // 2], fill=(30, 180, 30))       # TR green
    d.rectangle([0, h // 2, w // 2, h], fill=(30, 30, 220))       # BL blue
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def test_box_warp_keeps_the_label_upright_and_unflipped():
    out = fc.box_composite(_plate(), _quadrant_label(), QUAD, shade=0)
    img = _img(out["bytes"])
    tl = img.getpixel((90, 110))
    tr = img.getpixel((310, 110))
    bl = img.getpixel((90, 390))
    br = img.getpixel((310, 390))
    assert tl[0] > 150 and tl[1] < 100 and tl[2] < 100       # red top-left
    assert tr[1] > 120 and tr[0] < 100 and tr[2] < 100       # green top-right
    assert bl[2] > 150 and bl[0] < 100 and bl[1] < 100       # blue bottom-left
    assert min(br) > 180                                      # white bottom-right


def test_box_shading_never_touches_the_background_above_the_face():
    plate = (205, 180, 150)
    out = fc.box_composite(_plate(), _label(), QUAD, shade=0.5)
    img = _img(out["bytes"])
    assert img.getpixel((10, 10)) == plate          # outside the quad
    assert img.getpixel((200, 20)) == plate         # above the face, same columns


def test_bottle_shading_stays_inside_the_label_box():
    plate = (205, 180, 150)
    out = fc.bottle_composite(_plate(), _label(), QUAD, shade=0.5)
    img = _img(out["bytes"])
    assert img.getpixel((5, 5)) == plate
    assert img.getpixel((395, 5)) == plate
    assert img.getpixel((200, 250)) != plate        # the label is still painted


def test_tube_shading_stays_inside_the_label_box():
    plate = (205, 180, 150)
    out = fc.tube_composite(_plate(), _label(), QUAD, shade=0.5)
    img = _img(out["bytes"])
    assert img.getpixel((5, 5)) == plate
    assert img.getpixel((395, 495)) == plate


def test_every_compositor_returns_png_bytes_and_a_size():
    for kind in ("box", "bottle", "tube"):
        out = fc.composite(kind, _plate(), _label(), QUAD)
        assert out["bytes"][:4] == b"\x89PNG"
        assert out["size"] == [400, 500]
