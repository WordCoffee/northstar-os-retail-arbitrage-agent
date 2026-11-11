"""D-026: an instrument must not police the mask it is calibrated against.

`check_matte_residue` counts pixels outside the **recorded** silhouette. On the
generation route the silhouette comes from the cutout, and a colour cut
(`grabcut`, `background_distance`, `otsu_lab`) keeps a shadow that is attached to
the product — so the shadow is *inside* the silhouette, "outside" is empty, and a
picture with a visible smear scored 0.00 % (measured 2026-11-11 on PO-001 at seed
2747063199: 590 541 px of shadow, 0.00 % reported).

The rule these tests hold: a colour-cut silhouette may **not** be reported as
clean. The check says it cannot verify, in words, and never returns a pass
number. A matte silhouette is still measured exactly as before.
"""
from __future__ import annotations

import numpy as np
import pytest

from tools.seller_tester import scorers

WHITE = {"value": 255, "tolerance": 6, "mode": "uniform"}
FRAME = 200


def _frame(shadow: bool) -> np.ndarray:
    rgb = np.full((FRAME, FRAME, 3), 255, dtype=np.uint8)
    rgb[40:160, 40:160] = (30, 80, 50)             # product
    if shadow:
        rgb[150:190, 150:195] = (196, 192, 188)    # attached, opaque
    return rgb


def _mask(shadow: bool) -> np.ndarray:
    mask = np.zeros((FRAME, FRAME), dtype=bool)
    mask[40:160, 40:160] = True
    if shadow:                                     # a colour cut keeps it
        mask[150:190, 150:195] = True
    return mask


@pytest.mark.parametrize("method", scorers.COLOUR_CUT_METHODS)
def test_a_colour_cut_silhouette_is_unverified_not_clean(method):
    verdict = scorers.check_matte_residue(
        _frame(shadow=True), WHITE, subject_mask=_mask(shadow=True),
        silhouette_source=method)
    assert verdict["skipped"] is True, verdict
    assert verdict.get("residue_pct") is None, verdict
    assert "colour cut" in verdict["detail"], verdict
    assert "UNVERIFIED" in verdict["detail"], verdict


def test_a_matte_silhouette_is_still_measured_exactly():
    clean = scorers.check_matte_residue(
        _frame(shadow=False), WHITE, subject_mask=_mask(shadow=False),
        silhouette_source="birefnet")
    assert clean["skipped"] is False
    assert clean["residue_pct"] == 0.0

    dirty = scorers.check_matte_residue(
        _frame(shadow=True), WHITE, subject_mask=_mask(shadow=False),
        silhouette_source="birefnet")
    assert dirty["ok"] is False, dirty
    assert float(dirty["residue_pct"]) > 0.5


def test_an_undeclared_source_keeps_the_old_behaviour():
    """Callers that do not know how the cutout was made are not silently downgraded."""
    verdict = scorers.check_matte_residue(
        _frame(shadow=False), WHITE, subject_mask=_mask(shadow=False))
    assert verdict["skipped"] is False
    assert verdict["residue_pct"] == 0.0


def test_score_image_carries_the_declared_source_into_the_check():
    from PIL import Image
    from io import BytesIO

    buf = BytesIO()
    Image.fromarray(_frame(shadow=True)).save(buf, format="PNG")
    # The cutout the generator saves beside the artefact: an RGBA canvas whose alpha is
    # the silhouette, plus the product box on the frame.
    cutout = np.zeros((FRAME, FRAME, 4), dtype=np.uint8)
    cutout[40:160, 40:160, 3] = 255
    brief = {"id": "T-026", "situation": "white_background_main",
             "source_mode": "prompt_only", "fidelity": "tolerant",
             "constraints": {"background": WHITE,
                             "matte": {"mode": "white_matte", "value": 255,
                                       "tolerance": 6}}}
    out = scorers.score_image(
        buf.getvalue(), brief, route="full_generation", composite_route=False,
        cutout=cutout, product_box=[40, 40, 160, 160],
        silhouette_source="grabcut")
    residue = out["checks"]["matte_residue"]
    assert residue["skipped"] is True, residue
    assert "colour cut" in residue["detail"], residue
