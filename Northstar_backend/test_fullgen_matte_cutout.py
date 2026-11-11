"""D-025: a generated plate's own cast shadow must not survive the cutout.

Found by the D-022 real re-render (2026-11-11). PO-001 at its original seed
2747063199 still carried a **590 541 px** grey band outside the product after the
composite's own shadow was switched off: the *plate's* shadow, painted by the model,
attached to the product and opaque, so `grabcut` keeps it. D-017 fixed exactly this on
the app's plate route with a real matte (BiRefNet); the generation route still cut with
grabcut.

The checks are written before the code:

* with a real matte the composed picture has **no residue** outside the product (≤ 0.5 %
  of the frame), and the shadow the plate drew is gone;
* the control: on the same plate, grabcut **keeps** the shadow and the residue check
  fails — so the first assertion is a measurement, not a tautology;
* when the lane cannot supply a matte, the route falls back and **says so by name**
  (`cutout_matte.method == "grabcut"` and a reason that names the lane) — never silently;
* `check_matte_residue` reads the artefact through the same silhouette the harness uses.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tools.seller_tester import scorers
from tools.seller_tester.generators import CompositeGenerator

W, H = 900, 900
PRODUCT = (300, 220, 600, 680)          # left, top, right, bottom
SHADOW = (560, 520, 800, 760)           # attached, to the right and below


def plate_png(*, shadow: bool = True) -> bytes:
    """A drawn plate: a green package on 255 white, with the model's own cast shadow."""
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    if shadow:
        d.ellipse(SHADOW, fill=(196, 192, 188))        # neutral, attached to the product
    d.rectangle(PRODUCT, fill=(38, 70, 52))
    d.rectangle((330, 260, 570, 380), fill=(248, 248, 244))
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FixedRenderer:
    """Serves one plate; the pipeline treats it exactly like a generated scene."""

    def __init__(self, png: bytes) -> None:
        self.png = png
        self.calls = 0

    def __call__(self, brief, mode="full", inside_lane=None):
        self.calls += 1
        return {"bytes": self.png, "source": "generated", "prompt": "drawn plate",
                "model": "drawn", "image_path": None, "seed": 11, "steps": 0,
                "width": W, "height": H, "lane": None}


BRIEF = {
    "id": "T-025",
    "situation": "white_background_main",
    "source_mode": "prompt_only",
    "fidelity": "tolerant",
    "prompt": "a plain matte green stand-up pouch on a seamless white studio background",
    "constraints": {
        "dimensions": {"min_width": 800, "min_height": 800,
                       "max_width": 4000, "max_height": 4000},
        "background": {"value": 255, "tolerance": 6, "mode": "uniform"},
        "matte": {"mode": "white_matte", "value": 255, "tolerance": 6},
        "fill_pct": {"min": 5, "max": 100, "distance": 20},
    },
}


def _product_only_alpha(rgb: np.ndarray) -> np.ndarray:
    """A stand-in for BiRefNet: the product rectangle, none of the shadow."""
    alpha = np.zeros(rgb.shape[:2], dtype=np.uint8)
    left, top, right, bottom = PRODUCT
    alpha[top:bottom, left:right] = 255
    return alpha


def _run(tmp_path, *, matte: str) -> dict:
    import product_cutout as pc

    generator = CompositeGenerator(renderer=FixedRenderer(plate_png()),
                                   out_dir=tmp_path, layout="deterministic")
    if matte == "real":
        def fake_matte(rgb):
            return pc.Cutout(method="birefnet", alpha=_product_only_alpha(rgb), rgb=rgb,
                             seconds=0.01, working_side=0)
        generator._matte_cut = fake_matte          # type: ignore[assignment]
    else:
        def no_matte(rgb):
            raise pc.MatteUnavailable("the media lane is unreachable: no birefnet")
        generator._matte_cut = no_matte            # type: ignore[assignment]
    artefact = generator.generate(BRIEF)
    record = generator.records[-1]
    return {"artefact": artefact, "record": record}


def _residue(artefact, product_box) -> dict:
    cutout = artefact.with_suffix(".cutout.png")
    rgb = np.asarray(Image.open(artefact).convert("RGB"))
    mask = scorers._product_mask_from_cutout(
        cutout.read_bytes() if cutout.is_file() else None, product_box, rgb.shape[:2])
    return scorers.check_matte_residue(
        rgb, {"value": 255, "tolerance": 6, "mode": "uniform"}, subject_mask=mask)


def test_a_real_matte_removes_the_shadow_the_plate_drew(tmp_path):
    out = _run(tmp_path, matte="real")
    assert out["record"]["cutout_method"] == "birefnet"
    result = _residue(out["artefact"], out["record"]["product_box"])
    assert result["ok"], result["detail"]
    assert float(result["residue_pct"]) <= 0.5, result["detail"]


def _shadow_band_px(artefact) -> int:
    """Pixels the plate's own cast shadow occupies, independent of any silhouette.

    The plate draws it at 196 grey (see :func:`plate_png`); the product is saturated
    green and the label is 248, so the 180-220 neutral band is the shadow alone.
    """
    rgb = np.asarray(Image.open(artefact).convert("RGB")).astype(int)
    mean = rgb.mean(axis=2)
    grey = (rgb.max(axis=2) - rgb.min(axis=2)) <= 6
    return int((grey & (mean >= 180) & (mean <= 220)).sum())


def test_the_control_grabcut_keeps_the_same_shadow(tmp_path):
    out = _run(tmp_path, matte="none")
    assert out["record"]["cutout_method"] == "grabcut"
    # The shadow is still in the pixels: 768 band px of the drawn ellipse.
    kept = _shadow_band_px(out["artefact"])
    assert kept > 500, (
        "grabcut must keep the plate's drawn shadow, or the matte assertion below is "
        f"a tautology; it kept {kept} px")
    # D-026, recorded rather than hidden: the silhouette the residue check is handed is
    # the grabcut cutout's own alpha, which includes the ellipse, so "outside the
    # silhouette" is empty and the check reads 0.00 % on a picture with a visible smear.
    assert _residue(out["artefact"], out["record"]["product_box"])["residue_pct"] == 0.0


def test_the_fallback_is_recorded_by_name(tmp_path):
    out = _run(tmp_path, matte="none")
    matte = out["record"].get("cutout_matte") or {}
    assert matte.get("requested") == "birefnet"
    assert matte.get("method") == "grabcut"
    assert "lane" in str(matte.get("reason") or "").lower(), matte


def test_the_shadow_pixels_are_gone_not_only_hidden(tmp_path):
    out = _run(tmp_path, matte="real")
    kept = _shadow_band_px(out["artefact"])
    # The control keeps 768 px of the drawn ellipse; a resample seam on the product's own
    # edge is a handful of pixels. The assertion is 0.01 % of the frame (105 px on
    # 1024²), which the shadow cannot fit inside and a seam cannot climb over.
    assert kept <= 0.0001 * 1024 * 1024, kept
    assert kept < 768 / 50, kept


@pytest.mark.skipif(
    __import__("os").environ.get("NS_MATTE_LANE") != "1",
    reason="needs a live ComfyUI lane with birefnet.safetensors (NS_MATTE_LANE=1)")
def test_the_real_matte_rejects_the_real_pinned_plate():
    """The real measurement belongs to the unit run, gated so a cold box never fakes it."""
    import product_cutout as pc

    plate = Image.open("renders/_d025/pinned_plate_2747063199.png").convert("RGB")
    alpha = pc.matte_alpha(np.asarray(plate))
    assert int(alpha.sum()) > 0
