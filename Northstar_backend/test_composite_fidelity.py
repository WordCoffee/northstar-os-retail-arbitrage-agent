"""Composite fidelity: does the output contain the real product region?

And: is `tolerant` doing its job, or is it a loophole? Both are checkable, so both are checked.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from seller_tester import composite_check as C  # noqa: E402
from seller_tester import fidelity as F  # noqa: E402


def rgba_product(size=120, colour=(30, 120, 70), alpha=255):
    """A textured product: real products are never flat, and a flat square has no structure
    for a correlation to find (the template match is undefined on zero variance)."""
    image = np.zeros((size, size, 4), dtype=np.uint8)
    image[:, :] = (255, 255, 255, 0)
    inner = size // 6
    box = image[inner:size - inner, inner:size - inner]
    ramp = np.linspace(-26, 26, box.shape[0]).astype(np.int16)[:, None]
    texture = np.clip(np.array(colour, dtype=np.int16)[None, None, :] + ramp[:, :, None], 0, 255)
    box[:, :, :3] = texture.astype(np.uint8)
    box[:, :, 3] = alpha
    return image


def frame_with(cutout, at=(40, 30), size=(400, 400), background=(240, 236, 226)):
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    frame[:, :] = background
    x, y = at
    height, width = cutout.shape[:2]
    region = frame[y:y + height, x:x + width]
    alpha = cutout[:, :, 3:4].astype(np.float32) / 255.0
    rgb = cutout[:, :, :3].astype(np.float32)
    blended = (rgb * alpha + region.astype(np.float32) * (1 - alpha))
    region[:] = blended.astype(np.uint8)
    return frame


# ------------------------------------------------------------------ region similarity
def test_a_placement_that_used_the_real_product_scores_high():
    cutout = rgba_product()
    produced = frame_with(cutout, at=(40, 30))
    verdict = C.check_composite(produced, cutout, placement=[40, 30, 120, 120])
    assert verdict["ok"] is True, verdict
    assert verdict["similarity"] >= 0.99
    assert verdict["found_by"] == "placement"


def test_a_placement_with_a_different_product_scores_low():
    cutout = rgba_product(colour=(30, 120, 70))
    wrong = rgba_product(colour=(190, 40, 40))
    produced = frame_with(wrong, at=(40, 30))
    verdict = C.check_composite(produced, cutout, placement=[40, 30, 120, 120])
    assert verdict["ok"] is False, verdict
    assert verdict["similarity"] < 0.82


def test_a_placement_outside_the_frame_is_a_named_failure():
    cutout = rgba_product()
    verdict = C.check_composite(frame_with(cutout), cutout, placement=[380, 30, 120, 120])
    assert verdict["ok"] is False and verdict["cannot_verify"] is True


def test_a_transparent_cutout_cannot_be_verified():
    empty = np.zeros((100, 100, 4), dtype=np.uint8)
    verdict = C.check_composite(np.zeros((300, 300, 3), dtype=np.uint8), empty,
                                placement=[10, 10, 100, 100])
    assert verdict["ok"] is False and verdict["cannot_verify"] is True


def test_the_product_is_found_without_a_recorded_placement():
    cutout = rgba_product()
    produced = frame_with(cutout, at=(90, 70))
    verdict = C.locate_and_compare(produced, cutout)
    assert verdict.get("cannot_verify") is not True, verdict
    assert verdict["found_by"] == "template_match"
    assert verdict["similarity"] >= 0.9, verdict


def test_a_frame_without_the_product_does_not_pass():
    cutout = rgba_product()
    empty = np.full((400, 400, 3), 240, dtype=np.uint8)
    verdict = C.locate_and_compare(empty, cutout)
    # either it cannot find it, or it finds a match that scores nothing like the product
    assert verdict["ok"] is False


# ------------------------------------------------------------------ fidelity rules
def test_default_fidelity_is_exact():
    brief = {"id": "B1"}
    assert F.normalise(brief)["fidelity"] == F.EXACT
    assert F.product_in_frame(brief) is True  # safe default


def test_tolerant_is_refused_when_a_product_is_in_frame():
    brief = {"id": "B2", "fidelity": "tolerant"}          # product_in_frame defaults true
    lawful = F.normalise(brief)
    assert lawful["fidelity"] == F.EXACT
    assert "product is in frame" in lawful["fidelity_note"]


def test_tolerant_is_allowed_only_with_no_product_in_frame():
    brief = {"id": "B3", "fidelity": "tolerant", "product_in_frame": False}
    assert F.is_tolerant_allowed(brief) is True
    assert F.normalise(brief)["fidelity"] == F.TOLERANT


def test_an_unknown_fidelity_is_coerced_to_exact():
    lawful = F.normalise({"id": "B4", "fidelity": "whatever"})
    assert lawful["fidelity"] == F.EXACT
    assert "unknown fidelity" in lawful["fidelity_note"]


def test_the_count_names_the_tolerant_briefs_and_the_downgrades():
    briefs = [{"id": "A"}, {"id": "B", "fidelity": "tolerant"},
              {"id": "C", "fidelity": "tolerant", "product_in_frame": False}]
    counted = F.counts(briefs)
    assert counted["total"] == 3
    assert counted["exact"] == 2
    assert counted["tolerant"] == 1
    assert counted["tolerant_ids"] == ["C"]
    assert counted["downgraded_ids"] == ["B"]
    assert counted["tolerant_share"] == pytest.approx(0.333, abs=0.001)


def test_the_live_catalog_declares_fidelity_for_every_brief():
    import json

    data = json.loads((ROOT / "ty" / "seller_briefs.json").read_text(encoding="utf-8"))
    briefs = data["briefs"]
    counted = F.counts(briefs)
    assert counted["total"] == len(briefs)
    assert counted["exact"] + counted["tolerant"] == len(briefs)
    # the catalogue is product pictures: nothing may be tolerant by default
    assert counted["tolerant"] == 0, counted["tolerant_ids"]
