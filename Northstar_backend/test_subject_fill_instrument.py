"""Subject fill: two instruments, chosen by the background the brief asked for.

Measured 2026-11-11: PO-002 and PO-010 (lifestyle, `background.mode == "free"`) reported
"subject fill 94.3 % vs 8-50 %" on a correct picture. The instrument measured the share of
pixels that differ from the *corner colour*, and on a generated scene the corner colour is a
wall — so every pixel differs and the number is a property of the scene, not of the product.
The product's box is the honest measure there; with no box the check is skipped with a reason,
never passed by default.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from seller_tester.scorers import check_subject_fill  # noqa: E402
from seller_tester import scorers  # noqa: E402


def _scene(size=400, product=0.4) -> tuple[np.ndarray, list[int]]:
    """A non-flat background with one product rectangle in the middle."""
    h = w = size
    ramp = np.linspace(60, 140, h, dtype=np.float32)[:, None]
    rgb = np.repeat(ramp[:, :, None], w, axis=1).repeat(3, axis=2)
    rgb = np.clip(rgb + np.random.default_rng(3).normal(0, 6, rgb.shape), 0, 255).astype(np.uint8)
    side = int(size * product)
    left = (w - side) // 2
    top = (h - side) // 2
    rgb[top:top + side, left:left + side] = (38, 84, 58)
    return rgb, [left, top, left + side, top + side]


FREE = {"mode": "free"}
FLAT = {"mode": "uniform", "value": 255}


def test_a_scene_background_uses_the_product_box():
    rgb, box = _scene(product=0.4)          # 40% x 40% = 16% of the frame
    out = check_subject_fill(rgb, {"min": 15, "max": 85}, FREE, product_box=box)

    assert out["skipped"] is False
    assert out["instrument"] == "product_box"
    assert 15.5 <= out["fill_pct"] <= 16.5
    assert out["ok"] is True


def test_a_scene_background_without_a_box_is_skipped_with_a_reason():
    rgb, _ = _scene()
    out = check_subject_fill(rgb, {"min": 15, "max": 85}, FREE)

    assert out["skipped"] is True
    assert "no product box" in out["detail"] or "cannot be measured" in out["detail"]
    # A skip must never read as a pass that measured something.
    assert "fill_pct" not in out


def test_the_box_instrument_can_fail():
    rgb, box = _scene(product=0.9)          # 81% of the frame, outside a lifestyle window
    out = check_subject_fill(rgb, {"min": 15, "max": 50}, FREE, product_box=box)

    assert out["ok"] is False
    assert out["fill_pct"] > 50


def test_a_flat_background_keeps_the_corner_colour_instrument():
    rgb = np.full((200, 200, 3), 255, dtype=np.uint8)
    rgb[60:140, 60:140] = (30, 30, 30)      # 40% x 40%
    out = check_subject_fill(rgb, {"min": 10, "max": 25}, FLAT)

    assert out["instrument"] == "corner_colour"
    assert out["ok"] is True
    assert 15.5 <= out["fill_pct"] <= 16.5


def test_no_fill_spec_is_a_skip_not_a_pass():
    rgb, box = _scene()
    out = check_subject_fill(rgb, {}, FREE, product_box=box)
    assert out["skipped"] is True


# ── D-018: a white product on a white canvas has no colour difference to measure ──

def test_a_white_product_on_white_is_measured_by_its_cutout():
    rgb = np.full((200, 200, 3), 255, dtype=np.uint8)
    rgb[40:160, 40:160] = (250, 250, 250)          # 36 % of the frame, 5 levels off the canvas

    blind = check_subject_fill(rgb, {"min": 30, "max": 45}, FLAT)
    assert blind["instrument"] == "corner_colour"
    assert blind["fill_pct"] < 2, "the corner instrument cannot see white on white"
    assert blind["ok"] is False

    cutout = np.zeros((120, 120, 4), dtype=np.uint8)
    cutout[..., 3] = 255
    mask = scorers._product_mask_from_cutout(cutout, [40, 40, 160, 160], rgb.shape[:2])
    seen = check_subject_fill(rgb, {"min": 30, "max": 45}, FLAT,
                              product_box=[40, 40, 160, 160], subject_mask=mask)
    assert seen["instrument"] == "cutout_mask"
    assert 35.0 <= seen["fill_pct"] <= 37.0
    assert seen["ok"] is True
    assert seen["corner_fill_pct"] < 2, "the blind reading is kept beside the real one"


def test_the_cutout_is_only_a_fallback_for_a_blind_instrument():
    """A visible product keeps exactly the instrument it was scored with before."""
    rgb = np.full((200, 200, 3), 255, dtype=np.uint8)
    rgb[40:160, 40:160] = (30, 30, 30)             # a dark product, 36 %
    cutout = np.zeros((10, 10, 4), dtype=np.uint8)
    cutout[..., 3] = 255
    mask = scorers._product_mask_from_cutout(cutout, [0, 0, 20, 20], rgb.shape[:2])
    out = check_subject_fill(rgb, {"min": 30, "max": 45}, FLAT,
                             product_box=[0, 0, 20, 20], subject_mask=mask)
    assert out["instrument"] == "corner_colour"
    assert out["ok"] is True


def test_the_flat_path_records_the_box_and_keeps_the_cutout():
    """Without the box and the cutout the fallback above cannot fire on a real picture."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    import product_picture as pp

    plate = Image.new("RGB", (600, 600), (206, 206, 203))
    ImageDraw.Draw(plate).rounded_rectangle([180, 120, 420, 500], radius=30,
                                            fill=(58, 104, 72))
    placed = pp._place_on_flat(plate, value=255, fill=0.5)

    left, top, right, bottom = placed["box"]
    assert right > left and bottom > top
    cut = Image.open(BytesIO(placed["cutout"])).convert("RGBA")
    assert cut.getchannel("A").getextrema()[1] == 255
    # the cutout is trimmed to the product, so its aspect is the box's aspect
    assert abs((cut.width / cut.height) - ((right - left) / (bottom - top))) < 0.05
