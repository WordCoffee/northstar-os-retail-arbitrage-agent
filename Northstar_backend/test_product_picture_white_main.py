"""The main-image path: the product alone on a flat canvas, not on a sweep.

Contract under test (D-015, unit `white-cutout-main`):

* a brief that asks for a uniform background or a white matte is a **main-image**
  brief: the product is cut out of its plate and stood on that value;
* the cutout happens on the **plate**, before the label is composed — cutting the
  finished picture punched the label's own light panel out and took the wordmark
  with it (measured 2026-10-11 on the first real plate);
* the product's share of the frame is set from the brief's own fill band, as an
  area, so a brief with an upper bound is not overshot;
* a blank plate is refused by name and no picture is written;
* a brief with a free (scene) background keeps the photograph.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import brand_art as ba
import mockup_quality as mq
import product_picture as pp
from tools.seller_tester.generators import ProductPipelineGenerator
from tools.seller_tester.scene_render import synthetic_plate


def _png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _sweep_plate(width: int = 1200, height: int = 1200, box=(360, 210, 840, 1010)):
    """A kraft pouch on a mid-grey sweep: a real contrast to cut out of."""
    plate = Image.new("RGB", (width, height), (176, 178, 180))
    draw = ImageDraw.Draw(plate)
    draw.polygon([(box[0], box[1]), (box[2], box[1]), (box[2] + 8, box[3]),
                  (box[0] - 8, box[3])], fill=(213, 167, 122))
    draw.rectangle([box[0], box[1], box[2], box[1] + 26], fill=(196, 152, 110))
    return plate


def _generator(image: Image.Image):
    def inner(brief, *, width, height, tier, seed):
        return {"bytes": _png(image), "seed": seed, "model": "supplied-plate",
                "width": image.width, "height": image.height,
                "used_brief": brief, "contains_text": False}
    return inner


def _corners(rgb: np.ndarray, patch: int = 24):
    return np.concatenate([rgb[:patch, :patch].reshape(-1, 3),
                           rgb[:patch, -patch:].reshape(-1, 3),
                           rgb[-patch:, :patch].reshape(-1, 3),
                           rgb[-patch:, -patch:].reshape(-1, 3)])


# ── the picture the brief asked for ─────────────────────────────────────────

def test_a_flat_background_brief_gets_the_product_on_that_value(tmp_path):
    result = pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "w"),
                      out_root=str(tmp_path), faces=("front",), width=1200,
                      height=1200, generator=_generator(_sweep_plate()),
                      background="white", background_value=255, fill=0.5)
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    record = result["faces"][0]
    assert record["background"]["mode"] == "flat"
    assert record["background"]["value"] == 255
    rgb = np.asarray(Image.open(record["file"]).convert("RGB")).astype(np.float32)
    corners = _corners(rgb)
    assert corners.min() >= 250, corners.min()
    assert float(corners.std()) <= 4.0, float(corners.std())


def test_a_flat_background_brief_records_where_the_product_stands(tmp_path):
    """D-018: the picture must carry the box and the cutout the fill check needs."""
    result = pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "w"),
                      out_root=str(tmp_path), faces=("front",), width=1200,
                      height=1200, generator=_generator(_sweep_plate()),
                      background="white", background_value=255, fill=0.5)
    record = result["faces"][0]
    assert record["product_box"] == record["background"]["box"]
    left, top, right, bottom = record["product_box"]
    assert right > left and bottom > top
    cutout = Path(record["file"]).with_suffix(".cutout.png")
    assert cutout.is_file(), "the product's own silhouette must sit beside the picture"
    alpha = Image.open(cutout).convert("RGBA").getchannel("A")
    assert alpha.getextrema()[1] == 255


def test_the_label_survives_the_cutout(tmp_path):
    """Regression: cutting the finished picture removed the label's light panel."""
    design = ba.design_for("mogra-lions-mane")
    result = pp.build(design, out_dir=str(tmp_path / "w"), out_root=str(tmp_path),
                      faces=("front",), width=1200, height=1200,
                      generator=_generator(_sweep_plate()), background="white")
    record = result["faces"][0]
    assert record["gate_ok"] is True, record["reason"]
    words = " ".join(record["legibility"]["words"]).upper()
    assert "MOGRA" in words, words
    assert "LION" in words, words


def test_the_product_share_follows_the_band_it_is_given(tmp_path):
    design = ba.design_for("mogra-lions-mane")
    small = pp.build(design, out_dir=str(tmp_path / "a"), out_root=str(tmp_path),
                     faces=("front",), width=1200, height=1200,
                     generator=_generator(_sweep_plate()), background="white",
                     fill=0.20)
    large = pp.build(design, out_dir=str(tmp_path / "b"), out_root=str(tmp_path),
                     faces=("front",), width=1200, height=1200,
                     generator=_generator(_sweep_plate()), background="white",
                     fill=0.60)
    assert small["faces"][0]["background"]["fill"] < large["faces"][0]["background"]["fill"]
    assert 0.18 <= small["faces"][0]["background"]["fill"] <= 0.22
    assert 0.55 <= large["faces"][0]["background"]["fill"] <= 0.65


def test_a_blank_plate_is_refused_by_name_and_writes_nothing(tmp_path):
    flat = Image.new("RGB", (1200, 1200), (255, 255, 255))
    result = pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "w"),
                      out_root=str(tmp_path), faces=("front",), width=1200,
                      height=1200, generator=_generator(flat), background="white")
    assert result["ok"] is False
    assert "cutout_empty" in result["faces"][0]["reason"]
    assert not (tmp_path / "w" / "product_front.png").exists()


def test_a_scene_background_is_left_as_the_photograph(tmp_path):
    result = pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "s"),
                      out_root=str(tmp_path), faces=("front",), width=1200,
                      height=1200, generator=_generator(_sweep_plate()))
    record = result["faces"][0]
    assert "background" not in record
    rgb = np.asarray(Image.open(record["file"]).convert("RGB")).astype(np.float32)
    assert float(_corners(rgb).min()) < 200, "the sweep must still be in the picture"


# ── the harness decides from the brief, not from a flag ─────────────────────

def _brief(brief_id: str, *, background_mode: str, matte_mode: str = "any",
           value: int = 255, fill=(20, 60)) -> dict:
    return {
        "id": brief_id, "category": "supplement_pouch", "situation": "white_background_main",
        "product_line": "lions-mane", "label_mode": "warp",
        "body_prompt": "a blank kraft pouch", "fidelity": "exact",
        "constraints": {
            "dimensions": {"min_width": 1000, "min_height": 1000,
                           "max_width": 4000, "max_height": 4000},
            "aspect": {"ratio": 1.0, "tolerance": 0.02},
            "background": {"mode": background_mode, "value": value, "tolerance": 6},
            "matte": {"mode": matte_mode, "value": value, "tolerance": 6,
                      "max_border_std": 6},
            "fill_pct": {"min": fill[0], "max": fill[1], "distance": 20},
            "text_rule": "no_text",
            "file_size": {"min_bytes": 1000, "max_bytes": 20000000},
        },
        "pass_score": 70,
    }


def test_the_harness_cuts_a_uniform_background_brief_onto_white(tmp_path):
    plate = _sweep_plate(1536, 1536)
    generator = ProductPipelineGenerator(
        renderer=lambda brief, mode="plate", inside_lane=None, size=None: {
            "bytes": _png(plate), "source": "synthetic_plate", "prompt": "sweep",
            "model": None, "width": plate.width, "height": plate.height, "seed": 1,
            "note": None},
        renderer_name="injected", out_dir=tmp_path, repo_root=tmp_path, seed=7,
        skip_unavailable=False)
    path = generator.generate(_brief("PO-W1", background_mode="uniform"))
    record = generator.record_for("PO-W1")
    assert record["flat_background"] is True
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    assert _corners(rgb).min() >= 250


def test_the_harness_leaves_a_free_background_alone(tmp_path):
    plate = _sweep_plate(1536, 1536)
    generator = ProductPipelineGenerator(
        renderer=lambda brief, mode="plate", inside_lane=None, size=None: {
            "bytes": _png(plate), "source": "synthetic_plate", "prompt": "sweep",
            "model": None, "width": plate.width, "height": plate.height, "seed": 1,
            "note": None},
        renderer_name="injected", out_dir=tmp_path, repo_root=tmp_path, seed=7,
        skip_unavailable=False)
    generator.generate(_brief("PO-W2", background_mode="free"))
    assert generator.record_for("PO-W2")["flat_background"] is False
