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
