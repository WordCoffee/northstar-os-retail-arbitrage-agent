"""A main image must ship without text; the guard must prove it, not assume it."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_text_guard as g  # noqa: E402


def _detector(sequence):
    """A detector that returns the next scripted verdict each call."""
    calls = {"n": 0}

    def detect(_png):
        i = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        boxes = sequence[i]
        return {"status": "ok", "boxes": boxes, "contains_text": boxes > 0}

    return detect


def test_a_clean_image_is_left_alone():
    called = {"clean": 0}

    def clean(_png):
        called["clean"] += 1
        return {"bytes": b"changed"}

    out = g.ensure_text_free(b"png", detect=_detector([0]), clean=clean)
    assert out["cleaned"] is False
    assert out["boxes_before"] == 0
    assert out["passes"] == 0
    assert called["clean"] == 0
    assert out["bytes"] == b"png"


def test_text_is_cleaned_and_verified_on_the_second_read():
    out = g.ensure_text_free(b"png", detect=_detector([4, 0]),
                             clean=lambda _png: {"bytes": b"clean"})
    assert out["cleaned"] is True
    assert out["passes"] == 1
    assert out["boxes_before"] == 4 and out["boxes_after"] == 0
    assert out["bytes"] == b"clean"


def test_a_second_pass_runs_when_the_first_left_glyphs():
    out = g.ensure_text_free(b"png", detect=_detector([3, 1, 0]),
                             clean=lambda _png: {"bytes": b"clean"})
    assert out["passes"] == 2
    assert out["cleaned"] is True


def test_it_never_claims_a_clean_render_it_could_not_clean():
    out = g.ensure_text_free(b"png", detect=_detector([5, 5, 5]),
                             clean=lambda _png: {"bytes": b"still-dirty"},
                             max_passes=2)
    assert out["cleaned"] is False
    assert out["boxes_after"] == 5
    assert out["reason"] == "text still detected"


def test_an_ocr_failure_is_reported_not_treated_as_clean():
    def broken(_png):
        return {"status": "unavailable", "error": "engine missing", "boxes": None}

    out = g.ensure_text_free(b"png", detect=broken, clean=lambda _png: {"bytes": b"x"})
    assert out["cleaned"] is False
    assert out["boxes_before"] is None
    assert "ocr_unavailable" in out["reason"]


def test_an_empty_image_is_refused():
    with pytest.raises(ValueError):
        g.ensure_text_free(b"")
