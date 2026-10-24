"""Tests for the deterministic Amazon main-image validator.

Each rule comes from a cited source (see specialists/image_rules.py). The tests
build synthetic images so the check is proven without depending on any render.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specialists import image_rules  # noqa: E402


def _white(size=(1200, 1200)) -> Image.Image:
    return Image.new("RGB", size, (255, 255, 255))


def _with_product(size=(1200, 1200), frac=0.9, colour=(40, 90, 60)) -> Image.Image:
    img = _white(size)
    d = ImageDraw.Draw(img)
    w, h = size
    side = int(min(w, h) * frac)
    x0 = (w - side) // 2
    y0 = (h - side) // 2
    d.rectangle([x0, y0, x0 + side, y0 + side], fill=colour)
    return img


def _save(tmp_path, img, name="main.png"):
    p = tmp_path / name
    img.save(p)
    return p


def test_a_compliant_main_image_passes(tmp_path):
    out = image_rules.check_main_image(_save(tmp_path, _with_product()))
    assert out["ok"] is True, out["violations"]
    assert out["metrics"]["coverage"] >= image_rules.MIN_COVERAGE


def test_a_grey_background_is_rejected(tmp_path):
    img = _with_product()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1199, 20], fill=(230, 230, 230))
    out = image_rules.check_main_image(_save(tmp_path, img))
    assert out["ok"] is False
    assert any("pure white" in v for v in out["violations"])


def test_a_small_product_is_rejected(tmp_path):
    out = image_rules.check_main_image(_save(tmp_path, _with_product(frac=0.5)))
    assert out["ok"] is False
    assert any("fills" in v for v in out["violations"])


def test_an_undersized_image_is_rejected(tmp_path):
    out = image_rules.check_main_image(_save(tmp_path, _with_product(size=(800, 800))))
    assert out["ok"] is False
    assert any("required for zoom" in v for v in out["violations"])


def test_a_blank_image_is_rejected(tmp_path):
    out = image_rules.check_main_image(_save(tmp_path, _white()))
    assert out["ok"] is False
    assert any("blank" in v for v in out["violations"])


def test_an_alpha_channel_is_reported(tmp_path):
    img = _with_product().convert("RGBA")
    out = image_rules.check_main_image(_save(tmp_path, img, "main.png"))
    assert any("alpha" in v for v in out["violations"])


def test_the_validator_says_what_it_could_not_measure(tmp_path):
    out = image_rules.check_main_image(_save(tmp_path, _with_product()))
    joined = " ".join(out["not_measured"]).lower()
    assert "ocr" in joined and "focus" in joined
    assert "amazon-white-background" in out["rules_source"]


def test_a_missing_file_is_an_honest_failure(tmp_path):
    out = image_rules.check_main_image(tmp_path / "nope.png")
    assert out["ok"] is False
    assert "not found" in out["violations"][0]


def test_check_many_summarises(tmp_path):
    good = _save(tmp_path, _with_product(), "good.png")
    bad = _save(tmp_path, _with_product(frac=0.4), "bad.png")
    out = image_rules.check_many([good, bad])
    assert out["ok"] is False and out["checked"] == 2 and out["failed"] == 1
