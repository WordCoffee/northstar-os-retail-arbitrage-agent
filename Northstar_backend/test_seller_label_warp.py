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
