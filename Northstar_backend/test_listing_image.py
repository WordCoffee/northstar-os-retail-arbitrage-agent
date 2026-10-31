"""Listing hero isolation + contact shadow (Phase 1, item 3)."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from listing_image import audit_white, hero_on_white


def _cutout(size=400, colour=(190, 60, 40, 255), inset=80):
    """An opaque square on a transparent field - a stand-in for a real cutout."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for x in range(inset, size - inset):
        for y in range(inset, size - inset):
            img.putpixel((x, y), colour)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_output_is_pure_white_at_every_corner():
    png = hero_on_white(_cutout(), size=600)
    audit = audit_white(png)
    assert audit["corners_pure_white"] is True
    assert audit["corner_values"] == [(255, 255, 255)] * 8


def test_output_is_the_requested_square_size():
    png = hero_on_white(_cutout(), size=512)
    assert audit_white(png)["size"] == [512, 512]


def test_background_stays_mostly_pure_white():
    png = hero_on_white(_cutout(), size=600, fill=0.40, shadow=False)
    audit = audit_white(png)
    assert audit["pure_white_ratio"] > 0.5


def test_subject_fills_about_the_requested_fraction():
    png = hero_on_white(_cutout(inset=100), size=600, fill=0.8, shadow=False)
    img = Image.open(BytesIO(png)).convert("RGB")
    px = img.load()
    w = img.size[0]
    dark = [x for x in range(w) if px[x, w // 2] != (255, 255, 255)]
    span = (max(dark) - min(dark) + 1) / w if dark else 0
    assert 0.70 <= span <= 0.90, span


def test_shadow_darkens_under_the_subject_but_not_the_corners():
    png = hero_on_white(_cutout(), size=600, shadow=True)
    img = Image.open(BytesIO(png)).convert("RGB")
    px = img.load()
    w, h = img.size
    # Just under the subject's lower edge, somewhere near the centre column.
    under = [px[w // 2, y] for y in range(int(h * 0.86), int(h * 0.93))]
    assert any(sum(p) < 750 for p in under), "expected a contact shadow"
    assert px[0, 0] == (255, 255, 255)


def test_empty_input_is_refused_not_papered_over():
    blank = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    buf = BytesIO()
    blank.save(buf, format="PNG")
    with pytest.raises(ValueError, match="empty_subject"):
        hero_on_white(buf.getvalue())


def test_audit_reports_the_sampled_values():
    png = hero_on_white(_cutout(), size=400, shadow=False)
    audit = audit_white(png)
    assert len(audit["corner_values"]) == 8
    assert 0.0 <= audit["pure_white_ratio"] <= 1.0
