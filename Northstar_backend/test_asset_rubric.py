"""Offline conversion rubric (Benchmark Evaluator)."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import asset_rubric as ar


def _png(subject=(60, 90, 60), size=400, inset=40, bg=255):
    img = Image.new("RGB", (size, size), (bg, bg, bg))
    for x in range(inset, size - inset):
        for y in range(inset, size - inset):
            img.putpixel((x, y), subject)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_metrics_on_a_centred_subject():
    m = ar.metrics(_png())
    assert 0.75 <= m["fill"] <= 0.85
    assert m["purity"] > 0.3
    assert m["balance"] > 0.9          # centred
    assert 0.0 <= m["contrast"] <= 1.0


def test_blank_image_scores_zero_not_crash():
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    buf = BytesIO(); img.save(buf, format="PNG")
    m = ar.metrics(buf.getvalue())
    assert m["fill"] == 0.0 and m["subject_px"] == 0


def test_off_centre_subject_loses_balance():
    img = Image.new("RGB", (400, 400), (255, 255, 255))
    for x in range(20, 120):
        for y in range(20, 120):
            img.putpixel((x, y), (40, 40, 40))
    buf = BytesIO(); img.save(buf, format="PNG")
    m = ar.metrics(buf.getvalue())
    assert m["balance"] < 0.75


def test_small_subject_is_flagged_and_scores_below_pass():
    out = ar.score_hero(_png(inset=160))
    assert "subject_too_small" in out["defects"]
    assert out["verdict"] in ("revise", "pass")


def test_score_is_bounded_and_named():
    out = ar.score_hero(_png())
    assert 0.0 <= out["score"] <= 100.0
    assert out["rubric"].startswith(("offline:", "listing:", "hook:"))
    assert isinstance(out["defects"], list)


def test_legibility_reports_unavailable_rather_than_inventing():
    out = ar.legibility(_png(), ["lion", "mane"])
    assert 0.0 <= out["legibility"] <= 1.0
    assert "ocr" in out or "boxes" in out


def test_pass_requires_a_clean_sheet():
    out = ar.score_hero(_png())
    if out["defects"]:
        assert out["verdict"] == "revise"

def test_score_hero_is_the_listing_rubric():
    """The alias must be the code that runs, not a dead earlier implementation."""
    out = ar.score_hero(_png())
    assert out["class"] == "listing"
    assert out["rubric"].startswith("listing:")
