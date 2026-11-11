"""The label is composed, not drawn by the model, and it lands on the body's face.

Prompt-only briefs ask for a pouch "printed ORGANIC LION'S MANE". A text-to-image model draws
plausible letters that no OCR reads, so the brief's own text rule fails — and the fix is not a
looser rule. The fix is to stop asking the model for lettering: it draws the body, and the label is
composed here and warped on with a measured quad.

These tests pin the three properties that make that worthwhile: the label is deterministic, it is
readable (ink where the copy is), and the warp moves the label's own pixels rather than pasting a
rectangle over the product.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image  # noqa: E402

from seller_tester import label_warp as L  # noqa: E402

BRIEF = {"id": "PO-T", "product_line": "lions-mane",
         "label": {"brand": "Mogra Organics", "product": "Organic Lion's Mane",
                   "weight": "6 oz (170 g)", "lines": ["Mushroom Powder", "85 servings"]}}


def _body(size=(600, 800)):
    canvas = np.full((size[1], size[0], 3), 40, dtype=np.uint8)
    canvas[:, :] = (34, 96, 62)
    canvas[60:200, 80:520] = (60, 130, 90)      # a lighter band where a label would sit
    return canvas


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_the_label_is_deterministic():
    assert L.compose_label(BRIEF) == L.compose_label(BRIEF)


def test_the_label_carries_ink_where_the_copy_is():
    label = np.asarray(Image.open(BytesIO(L.compose_label(BRIEF))).convert("RGB"))
    assert label.shape[:2] == (L.LABEL_H, L.LABEL_W)
    dark = (label.mean(axis=2) < 120).mean()
    assert dark > 0.002, f"only {dark:.4%} of the label is ink; the copy did not render"


def test_the_warp_changes_pixels_inside_the_quad_and_nowhere_else():
    body = _png(Image.fromarray(_body()))
    result = L.warp_label(body, [60, 40, 480, 700], L.compose_label(BRIEF))
    before = np.asarray(Image.open(BytesIO(body)))
    after = np.asarray(Image.open(BytesIO(result["bytes"])))
    quad = result["quad"]
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    inside = np.zeros(before.shape[:2], dtype=bool)
    inside[min(ys):max(ys) + 1, min(xs):max(xs) + 1] = True   # inclusive bbox
    assert not np.array_equal(before[inside], after[inside]), "the label was not applied"
    assert np.array_equal(before[~inside], after[~inside]), "the warp leaked outside the quad"


def test_the_warp_is_deterministic():
    body = _png(Image.fromarray(_body()))
    first = L.warp_label(body, [60, 40, 480, 700], L.compose_label(BRIEF))
    second = L.warp_label(body, [60, 40, 480, 700], L.compose_label(BRIEF))
    assert first["bytes"] == second["bytes"]
    assert first["quad"] == second["quad"]


def test_the_quad_sits_on_the_upper_front_and_inside_the_product_box():
    quad = L._quad_for([100, 100, 400, 600])
    assert all(100 <= x <= 500 for x, _ in quad)
    assert all(100 <= y <= 700 for _, y in quad)
    assert max(y for _, y in quad) < 100 + 600 * 0.75, "the label should not reach the base"


def test_an_empty_quad_is_refused_rather_than_crashing():
    body = _png(Image.fromarray(_body()))
    with pytest.raises(ValueError):
        L.warp_label(body, [60, 40, 480, 700], L.compose_label(BRIEF),
                     quad=[[10, 10], [10, 10], [10, 10], [10, 10]])


# ── fix-label-conform: the panel is conformed to the pack and clipped to it ──

def _pouch_on_scene(size=(600, 800), *, taper: float = 0.20):
    """A tapered pouch silhouette on a pale scene, and its mask.

    Truth: at the top row of the label band the body is `1 - taper` of the width
    it has at the bottom row, exactly like a stand-up pouch.
    """
    w, h = size
    canvas = np.full((h, w, 3), 232, dtype=np.uint8)
    mask = np.zeros((h, w), dtype=np.uint8)
    x0, x1 = 120, 480
    top_y, bot_y = 80, 720
    for y in range(top_y, bot_y):
        t = (y - top_y) / float(bot_y - top_y)
        half = (x1 - x0) / 2.0 * (1.0 - taper + taper * t)
        cx = (x0 + x1) / 2.0
        lo, hi = int(cx - half), int(cx + half)
        mask[y, lo:hi] = 255
        canvas[y, lo:hi] = (52, 112, 74)
    return _png(Image.fromarray(canvas)), _png(Image.fromarray(mask)), mask


def test_the_face_follows_the_pack_taper():
    """A rectangle over a taper is the 'flat card stuck on' defect."""
    _, mask_png, mask = _pouch_on_scene(taper=0.20)
    quad = L.face_quad(np.asarray(Image.open(BytesIO(mask_png))), [120, 80, 360, 640])
    top_w = quad[1][0] - quad[0][0]
    bottom_w = quad[2][0] - quad[3][0]
    assert bottom_w > top_w * 1.05, (quad, top_w, bottom_w)
    assert all(0 <= p[0] < mask.shape[1] and 0 <= p[1] < mask.shape[0] for p in quad)


def test_the_label_never_paints_the_scene_beside_the_product():
    body, mask_png, mask = _pouch_on_scene(taper=0.20)
    result = L.warp_label(body, [120, 80, 360, 640], L.compose_label(BRIEF),
                          mask_png=mask_png)
    before = np.asarray(Image.open(BytesIO(body)))
    after = np.asarray(Image.open(BytesIO(result["bytes"])))
    changed = np.any(before != after, axis=2)
    assert changed.any(), "the label was not applied at all"
    outside = changed & (mask < 128)
    assert not outside.any(), f"{int(outside.sum())} label pixels landed on the scene"
    assert result["meta"]["conformed"] is True
    assert result["meta"]["panel_px_outside_silhouette"] == 0
    assert result["meta"]["panel_px"] > 1000


def test_the_label_fills_the_measured_face_not_the_bounding_box():
    """A narrow body in a wide box: the quad is the body, not the box."""
    body, mask_png, mask = _pouch_on_scene(taper=0.0)
    quad = L.face_quad(np.asarray(Image.open(BytesIO(mask_png))), [0, 0, 600, 800])
    xs = [p[0] for p in quad]
    assert min(xs) >= 120 and max(xs) <= 480, quad


def test_a_thin_feature_above_the_body_does_not_make_the_label_a_sliver():
    """PO-001 measured 2026-11-11: a 22 px top edge on a body 1 200 px wide."""
    mask = np.zeros((800, 600), dtype=np.uint8)
    mask[80:150, 296:304] = 255          # a thin upright feature above the body
    mask[150:720, 120:480] = 255         # the body
    quad = L.face_quad(mask, [120, 80, 360, 640])
    top_w = quad[1][0] - quad[0][0]
    assert top_w > 0.55 * 360, quad
    assert all(p[1] >= 150 for p in quad), "the label must sit on the body, not the feature"


def test_a_detached_speck_is_dropped_and_a_three_unit_bundle_is_kept():
    import product_composite as composite

    def unit(x0, y0, w=90, h=260):
        a = np.zeros((400, 400), dtype=np.uint8)
        a[y0:y0 + h, x0:x0 + w] = 255
        return a

    one = Image.new("RGBA", (400, 400), (60, 120, 80, 0))
    one.putalpha(Image.fromarray(unit(60, 120), "L"))
    with_speck = one.copy()
    alpha = np.asarray(with_speck.getchannel("A")).copy()
    alpha[10:40, 20:26] = 255          # a thin stick, detached, above and to the left
    with_speck.putalpha(Image.fromarray(alpha, "L"))

    cleaned, dropped = composite.drop_detached_specks(with_speck)
    assert dropped == 1
    assert np.asarray(cleaned.getchannel("A"))[10:40, 20:26].max() == 0
    assert np.asarray(cleaned.getchannel("A"))[120:380, 60:150].min() == 255

    three = Image.new("RGBA", (400, 400), (60, 120, 80, 0))
    a = np.zeros((400, 400), dtype=np.uint8)
    for x0 in (40, 160, 280):
        a[100:360, x0:x0 + 80] = 255
    three.putalpha(Image.fromarray(a, "L"))
    kept, dropped_three = composite.drop_detached_specks(three)
    assert dropped_three == 0
    assert int((np.asarray(kept.getchannel("A")) > 8).sum()) == int((a > 8).sum())


def test_a_thin_attached_stick_is_removed_but_a_bottle_neck_survives():
    """PO-001's cutout: a 20 px stick above a 650 px body, attached to it."""
    import product_composite as composite

    def rgba_from(mask):
        im = Image.new("RGBA", (mask.shape[1], mask.shape[0]), (60, 120, 80, 0))
        im.putalpha(Image.fromarray(mask, "L"))
        return im

    body = np.zeros((900, 700), dtype=np.uint8)
    body[420:860, 200:520] = 255         # 320 px wide body
    body[120:420, 355:365] = 255         # 10 px stick, 300 rows, attached above
    cleaned, erased = composite.drop_thin_runs(rgba_from(body))
    assert erased >= 300
    alpha = np.asarray(cleaned.getchannel("A"))
    # the image is cropped to what is left: the stick is gone, the body is whole
    assert alpha.shape[0] < 500, alpha.shape
    assert int((alpha > 8).sum()) == int((body[420:860, 200:520] > 8).sum())
    rows_with_pixels = np.nonzero((alpha > 8).any(axis=1))[0]
    widths = ((alpha > 8).sum(axis=1))[rows_with_pixels]
    assert widths.min() >= 300, "the body was damaged"

    bottle = np.zeros((900, 700), dtype=np.uint8)
    bottle[420:860, 200:520] = 255       # body
    bottle[180:420, 300:420] = 255       # a 120 px neck: 37 % of the body width
    kept, erased_neck = composite.drop_thin_runs(rgba_from(bottle))
    assert erased_neck == 0
    assert int((np.asarray(kept.getchannel("A")) > 8).sum()) == int((bottle > 8).sum())

