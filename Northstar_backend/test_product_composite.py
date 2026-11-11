"""Identity by construction: the product pasted into a scene is the product that went in.

These tests are synthetic and CPU-only on purpose. The point of the module is
that it does not need a model, so it must be provable without a GPU.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import product_composite as pc  # noqa: E402


def _scene(size=(800, 800), colour=(210, 210, 214)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, colour).save(buf, format="PNG")
    return buf.getvalue()


def _cutout(size=(200, 300), margin=40, colour=(170, 60, 40)) -> bytes:
    """An opaque product on a transparent margin, like a BiRefNet output."""
    w, h = size
    im = Image.new("RGBA", (w + 2 * margin, h + 2 * margin), (0, 0, 0, 0))
    box = Image.new("RGBA", (w, h), (*colour, 255))
    im.paste(box, (margin, margin))
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_product_is_placed_at_the_requested_scale():
    out = pc.place_product(_scene(), _cutout(), scale=0.5, anchor=(0.5, 0.5))
    assert out["width"] == 800 and out["height"] == 800
    assert 0.49 <= out["product_scale"] <= 0.51
    left, top, right, bottom = out["product_box"]
    assert right > left and bottom > top
    assert 0 <= left and 0 <= top and right <= 800 and bottom <= 800


def test_identity_is_preserved_by_construction():
    scene, cut = _scene(), _cutout()
    out = pc.place_product(scene, cut, scale=0.6, anchor=(0.5, 0.5))
    check = pc.identity_check(out["bytes"], cut, tuple(out["product_box"]))
    assert check["verdict"] == "identity_preserved"
    assert check["ssim"] >= 0.95


def test_the_placed_pixels_really_are_the_product():
    out = pc.place_product(_scene(), _cutout(colour=(170, 60, 40)), scale=0.6)
    left, top, right, bottom = out["product_box"]
    with Image.open(BytesIO(out["bytes"])) as im:
        cx, cy = (left + right) // 2, (top + bottom) // 2
        r, g, b = im.convert("RGB").getpixel((cx, cy))
    assert r > 120 and 30 < g < 110 and b < 90, (r, g, b)


def test_oversized_product_is_clamped_inside_the_frame():
    out = pc.place_product(_scene((400, 400)), _cutout((600, 200)), scale=1.0,
                           anchor=(0.5, 0.5))
    assert out["scale_clamped"] is True
    left, top, right, bottom = out["product_box"]
    assert right <= 400 and bottom <= 400


def test_anchor_keeps_the_product_in_frame_at_the_edges():
    for anchor in ((0.0, 0.0), (1.0, 1.0)):
        out = pc.place_product(_scene(), _cutout(), scale=0.8, anchor=anchor)
        left, top, right, bottom = out["product_box"]
        assert left >= 0 and top >= 0 and right <= 800 and bottom <= 800


def test_shadow_darkens_below_the_product_and_can_be_disabled():
    scene, cut = _scene(), _cutout()
    with_shadow = pc.place_product(scene, cut, scale=0.5, shadow=True)
    without = pc.place_product(scene, cut, scale=0.5, shadow=False)
    left, top, right, bottom = with_shadow["product_box"]
    # The shadow is now reserved inside the margin, so the two placements do not share a
    # box: probe below *both* of them, at the same absolute pixel, so the comparison is
    # "is there a shadow here" and not "is one product 70 px lower than the other".
    deepest = max(bottom, without["product_box"][3])
    probe = ((left + right) // 2, min(799, deepest + 6))
    with Image.open(BytesIO(with_shadow["bytes"])) as a, \
            Image.open(BytesIO(without["bytes"])) as b:
        shaded = sum(a.convert("RGB").getpixel(probe)) / 3
        plain = sum(b.convert("RGB").getpixel(probe)) / 3
    assert shaded < plain


def test_empty_cutout_is_refused():
    empty = BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(empty, format="PNG")
    try:
        pc.place_product(_scene(), empty.getvalue())
    except ValueError as exc:
        assert "no visible pixels" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a fully transparent cutout must be refused")
