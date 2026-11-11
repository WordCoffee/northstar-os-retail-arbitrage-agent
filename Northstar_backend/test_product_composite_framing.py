"""The shadow is part of the subject: it must sit inside the frame, not be cut by it.

Measured 2026-11-11: a 2000 px prompt-only main image at scale 0.62 / anchor 0.6 put the
product's base at y=1820 and the contact shadow's out to y≈2032, so the bottom twenty rows
carried a clipped grey band (mean luminance 243.5) and the white-matte ring check failed at
"border mean 252.1, std 7.19 (<= 6.0)" on six held-out briefs. These tests hold the frame
edge clean without giving up the product's size.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import product_composite as pc  # noqa: E402


def _canvas(size=(2000, 2000), colour=(255, 255, 255)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, colour).save(buf, format="PNG")
    return buf.getvalue()


def _pouch(w=1251, h=1240, colour=(38, 84, 58)) -> bytes:
    """A tall cutout with transparent margins, like a BiRefNet matte of a pouch."""
    pad = 40
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (w, h), (*colour, 255)), (pad, pad))
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _ring_std(png: bytes, ratio: float = 0.01) -> float:
    a = np.asarray(Image.open(BytesIO(png)).convert("RGB"), dtype=np.uint8)
    h, w = a.shape[:2]
    t = max(4, int(min(h, w) * ratio))
    ring = np.concatenate([a[:t].reshape(-1, 3), a[-t:].reshape(-1, 3),
                           a[:, :t].reshape(-1, 3), a[:, -t:].reshape(-1, 3)])
    lum = ring.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return float(lum.std())


def test_a_tall_product_at_the_prompt_only_scale_leaves_the_ring_clean():
    out = pc.place_product(_canvas(), _pouch(), scale=0.62, anchor=(0.5, 0.6))

    assert out["shadow_inside_frame"] is True
    assert _ring_std(out["bytes"]) == 0.0, (
        "the outer ring must be the untouched canvas: a clipped shadow is a visible "
        f"defect, measured std {_ring_std(out['bytes']):.2f}")


def test_the_shadow_is_moved_up_rather_than_the_product_shrunk():
    """Slack exists, so the fix is placement, not a smaller product."""
    out = pc.place_product(_canvas(), _pouch(), scale=0.62, anchor=(0.5, 0.6))

    assert 0.61 <= out["product_scale"] <= 0.63
    assert out["scale_clamped"] is False
    assert out["product_box"][3] + out["shadow_below_px"] <= 2000 - 40 + 1


def test_a_white_main_at_085_keeps_its_fill_and_still_fits_the_shadow():
    out = pc.place_product(_canvas(), _pouch(), scale=0.85, anchor=(0.5, 0.55))

    assert out["product_scale"] >= 0.84, "the brief's fill requirement is not negotiable"
    assert out["shadow_inside_frame"] is True
    assert _ring_std(out["bytes"]) == 0.0


def test_the_shadow_footprint_shrinks_when_the_frame_has_no_slack():
    """A full-frame product leaves no room: the shadow gives way, the product does not."""
    out = pc.place_product(_canvas((1000, 1000)), _pouch(900, 960), scale=0.9,
                           anchor=(0.5, 0.5))

    assert out["product_scale"] >= 0.88
    assert out["shadow_inside_frame"] is True


def test_a_shadowless_placement_is_untouched_by_the_reservation():
    out = pc.place_product(_canvas(), _pouch(), scale=0.62, anchor=(0.5, 0.6),
                           shadow=False)
    assert out["shadow"] is False
    assert out["shadow_below_px"] == 0
    assert out["shadow_inside_frame"] is True
