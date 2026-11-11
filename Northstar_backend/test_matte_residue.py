"""D-020: a flat background must be flat everywhere, not only in the corners.

Found while closing D-017. A main image ships the product on 255 white, but a plate's
contact shadow can still sit under it:

* `check_background` samples the four **corner patches**;
* `check_alpha_matte`'s `white_matte` branch samples an **outer ring**;
* a shadow lives between them, so the two instruments that exist for this exact
  property both pass a picture a seller cannot list.

This module checks the new whole-frame instrument, and keeps the blind spot itself
under test: if someone widens `check_background` later, the first test here says so.

The rule: on a flat background, every pixel that differs from the asked value by more
than the tolerance and is **not inside the product's own silhouette** is residue. A thin
edge blend is tolerated (the silhouette is dilated) and isolated sparkle is dropped; a
shadow is neither.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tools.seller_tester.scorers import (
    DEFAULT_WEIGHTS,
    LoadedImage,
    check_alpha_matte,
    check_background,
    check_matte_residue,
    combine_checks,
    load_image,
    score_image,
)

WHITE_SPEC = {"mode": "uniform", "value": 255, "tolerance": 6}
MATTE_SPEC = {"mode": "white_matte", "value": 255, "tolerance": 6, "max_border_std": 6}
PRODUCT = (400, 280, 620, 820)
SHADOW = (210, 800, 700, 870)


def _png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _main_image(*, shadow: bool = True) -> Image.Image:
    """The product alone on 255 white, with an opaque grey shadow under it."""
    image = Image.new("RGB", (1000, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    if shadow:
        draw.ellipse(list(SHADOW), fill=(150, 150, 150))
    draw.rectangle(list(PRODUCT), fill=(120, 80, 40))
    return image


def _silhouette(*, pad: int = 0) -> np.ndarray:
    mask = np.zeros((1000, 1000), dtype=bool)
    mask[PRODUCT[1] - pad:PRODUCT[3] + pad, PRODUCT[0] - pad:PRODUCT[2] + pad] = True
    return mask


def _brief(*, background=WHITE_SPEC, matte=MATTE_SPEC, pass_score: int = 70) -> dict:
    return {
        "id": "PO-020", "category": "supplement_pouch",
        "situation": "white_background_main", "source_mode": "prompt_only",
        "constraints": {
            "dimensions": {"min_width": 800, "min_height": 800,
                           "max_width": 4000, "max_height": 4000},
            "aspect": {"ratio": 1.0, "tolerance": 0.02},
            "background": dict(background),
            "matte": dict(matte),
            "fill_pct": {"min": 20, "max": 60, "distance": 20},
            "text_rule": "no_text",
            "file_size": {"min_bytes": 1000, "max_bytes": 20000000},
        },
        "pass_score": pass_score,
    }


def _loaded(image: Image.Image) -> LoadedImage:
    return load_image(_png(image))


# ── the blind spot, held under test ───────────────────────────────────────────

def test_the_corner_and_ring_instruments_both_pass_a_shadowed_main_image():
    loaded = _loaded(_main_image(shadow=True))
    background = check_background(loaded.rgb, WHITE_SPEC)
    matte = check_alpha_matte(loaded, MATTE_SPEC)
    assert background["ok"] is True, background
    assert matte["ok"] is True, matte
    # …and the whole-frame instrument is the one that sees it
    residue = check_matte_residue(loaded.rgb, WHITE_SPEC, subject_mask=_silhouette())
    assert residue["ok"] is False, residue
    assert residue["shadow_px"] > 0.5 * 30000, residue
    assert "residue" in residue["detail"].lower()


def test_a_clean_main_image_has_no_residue():
    loaded = _loaded(_main_image(shadow=False))
    residue = check_matte_residue(loaded.rgb, WHITE_SPEC, subject_mask=_silhouette())
    assert residue["ok"] is True, residue
    assert residue["residue_pct"] <= 0.5, residue


def test_a_thin_edge_blend_is_tolerated():
    image = _main_image(shadow=False)
    draw = ImageDraw.Draw(image)
    # a 2 px halo outside the silhouette: what a resize leaves behind
    draw.rectangle([PRODUCT[0] - 2, PRODUCT[1] - 2, PRODUCT[2] + 2, PRODUCT[1] - 1],
                   fill=(210, 205, 200))
    residue = check_matte_residue(np.asarray(image), WHITE_SPEC,
                                  subject_mask=_silhouette())
    assert residue["ok"] is True, residue


def test_isolated_sparkle_is_dropped_and_a_shadow_is_not():
    image = _main_image(shadow=False)
    pixels = np.asarray(image).copy()
    pixels[100, 100] = (0, 0, 0)                       # one speck: not a shadow
    clean = check_matte_residue(pixels, WHITE_SPEC, subject_mask=_silhouette())
    assert clean["ok"] is True, clean
    shadowed = check_matte_residue(np.asarray(_main_image(shadow=True)), WHITE_SPEC,
                                   subject_mask=_silhouette())
    assert shadowed["ok"] is False, shadowed


# ── it never pretends to have checked what it could not ───────────────────────

def test_without_a_silhouette_the_check_is_skipped_with_a_reason():
    loaded = _loaded(_main_image(shadow=True))
    residue = check_matte_residue(loaded.rgb, WHITE_SPEC, subject_mask=None)
    assert residue["skipped"] is True
    assert "silhouette" in residue["detail"].lower()
    assert residue["ok"] is True, "a skip is not a failure; it is also not a pass"


def test_a_free_background_is_skipped():
    loaded = _loaded(_main_image(shadow=True))
    residue = check_matte_residue(loaded.rgb, {"mode": "free"}, subject_mask=_silhouette())
    assert residue["skipped"] is True


# ── the score: same denominator, a real tooth ─────────────────────────────────

def test_the_weight_is_paid_for_by_background_so_no_clean_score_moves():
    assert DEFAULT_WEIGHTS["background"] + DEFAULT_WEIGHTS["matte_residue"] == \
        pytest.approx(0.20)
    checks = {
        "dimensions": {"ok": True, "skipped": False},
        "aspect": {"ok": True, "skipped": False},
        "background": {"ok": True, "skipped": False},
        "matte_residue": {"ok": True, "skipped": False},
        "subject_fill": {"ok": True, "skipped": False},
        "alpha_matte": {"ok": True, "skipped": False},
        "file_size": {"ok": True, "skipped": False},
        "text_free": {"ok": True, "skipped": False},
        "reference_subject": {"ok": True, "skipped": True},
    }
    assert combine_checks(checks, _brief())["score"] == 100.0


def test_a_shadowed_picture_fails_even_though_every_old_check_passes():
    image = _main_image(shadow=True)
    cutout = np.dstack([np.asarray(image), (_silhouette() * 255).astype(np.uint8)])
    scored = score_image(_png(image), _brief(), route="product", composite_route=False,
                         cutout=cutout, product_box=list(PRODUCT))
    assert scored["checks"]["background"]["ok"] is True, scored["checks"]["background"]
    assert scored["checks"]["matte_residue"]["ok"] is False, scored["checks"]
    assert scored["passed"] is False
    assert "matte_residue" in scored["failed_checks"]


def test_a_clean_picture_still_passes():
    image = _main_image(shadow=False)
    cutout = np.dstack([np.asarray(image), (_silhouette() * 255).astype(np.uint8)])
    scored = score_image(_png(image), _brief(), route="product", composite_route=False,
                         cutout=cutout, product_box=list(PRODUCT))
    assert scored["checks"]["matte_residue"]["ok"] is True, scored["checks"]
    assert scored["passed"] is True, scored
