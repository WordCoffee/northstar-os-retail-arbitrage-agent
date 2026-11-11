"""D-017: a plate's opaque contact shadow must be removed by a real matte.

Defect (filed 2026-11-11, unit `white-cutout-main`): a studio plate carries a contact
shadow under the product. The colour cut keeps it, because the shadow differs from the
sweep by more than the threshold and is *attached* to the product, so the largest-blob
pass cannot drop it. On 255 white the picture then ships with a grey smear under the
product — the main-image brief says the product alone on white.

The fix is a real matte (BiRefNet through the media lane), not another colour cut: on
the real FLUX plate measured here the sweep is 199, the shadow reaches 130 and the
product's own dark base is 120, so there is no threshold that keeps the product and
drops the shadow. This module writes the checks first:

* the colour cut **keeps** an opaque shadow on a fixture whose truth is exact;
* a real matte **removes** it and keeps the product (same fixture, matte supplied);
* `matte_alpha` **refuses by name** when the lane is unreachable — never a silent
  substitution with the colour cut;
* `matte="auto"` falls back to the colour cut and *records* that it did;
* the manifest carries the matte's own record, so a delivered picture states which
  matte produced it.

`NS_PLATE_MATTE=1` adds the real-plate measurement (needs the media lane up).
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import brand_art as ba
import product_cutout as pc
import product_picture as pp

ROOT = Path(__file__).resolve().parents[1]
REAL_PLATE = ROOT / "renders" / "comfy_plate7" / "ST-002" / "_rejected" / "front_plate.png"

#: the fixture's truth, in plate pixels
PRODUCT = (420, 300, 780, 880)
SHADOW = (300, 880, 860, 940)


def _shadow_plate(width: int = 1200, height: int = 1200) -> Image.Image:
    """A kraft-brown pack on a grey sweep with an OPAQUE, attached contact shadow."""
    plate = Image.new("RGB", (width, height), (200, 200, 200))
    draw = ImageDraw.Draw(plate)
    draw.rectangle(list(SHADOW), fill=(150, 150, 150))          # opaque: no alpha
    draw.rectangle(list(PRODUCT), fill=(140, 90, 50))           # brown, not neutral
    draw.rectangle([PRODUCT[0], PRODUCT[1], PRODUCT[2], PRODUCT[1] + 24],
                   fill=(126, 80, 44))
    return plate


def _png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _canvas(result) -> np.ndarray:
    return np.asarray(result["image"].convert("RGB")).astype(np.int16)


def _neutral_shadow_px(array: np.ndarray, *, ceiling: int = 190, glow: int = 100) -> int:
    """Neutral grey pixels darker than the canvas.

    The fixture's product is brown (R-B = 90) and the canvas is 255 white, so a
    *neutral* pixel below the ceiling can only be shadow. It is the instrument this
    defect needs: "is there grey under the product", not "how big is the product".
    """
    red, green, blue = array[..., 0], array[..., 1], array[..., 2]
    neutral = (np.abs(red - green) < 8) & (np.abs(green - blue) < 8)
    return int((neutral & (red < ceiling) & (red > glow)).sum())


def _brown_px(array: np.ndarray) -> int:
    return int(((array[..., 0] - array[..., 2]) > 40).sum())


def _perfect_matte(rgb: np.ndarray, **_kwargs) -> np.ndarray:
    """A matte that is right by construction: the fixture's product, nothing else."""
    brown = (rgb[..., 0].astype(np.int16) - rgb[..., 2].astype(np.int16)) > 40
    return (brown.astype(np.uint8)) * 255


# ── the colour cut keeps the shadow ────────────────────────────────────────────

def test_the_colour_cut_keeps_an_opaque_contact_shadow():
    placed = pp._place_on_flat(_shadow_plate(), fill=0.5, matte="none")
    array = _canvas(placed)
    shadow = _neutral_shadow_px(array)
    assert shadow > 0.5 * 300 * 60, (
        f"the colour cut was expected to keep the opaque shadow; it found {shadow} px")
    assert placed["matte"]["method"] == "none"
    assert placed["matte"]["reason"], "a fallback must state why it is not a real matte"


# ── a real matte removes it and keeps the product ──────────────────────────────

def test_a_real_matte_removes_the_shadow_and_keeps_the_product(monkeypatch):
    monkeypatch.setattr(pc, "matte_alpha", _perfect_matte)
    placed = pp._place_on_flat(_shadow_plate(), fill=0.2, matte="birefnet")
    array = _canvas(placed)
    assert _neutral_shadow_px(array) < 200, (
        f"shadow survived the matte: {_neutral_shadow_px(array)} neutral px")
    # the product is still the product: its brown area is the truth's area, scaled by
    # the fill the caller asked for (0.2 of the canvas)
    brown = _brown_px(array)
    truth = (PRODUCT[2] - PRODUCT[0]) * (PRODUCT[3] - PRODUCT[1])
    assert brown > 0.10 * truth, f"the matte lost the product: {brown} brown px of {truth}"
    assert placed["matte"]["method"] == "birefnet"
    assert placed["matte"]["seconds"] >= 0.0
    # the crop is the product, not the product plus its shadow: the colour cut's box
    # spans the shadow's width (560 px) while the matte's is the product (360 px)
    width = placed["box"][2] - placed["box"][0]
    height = placed["box"][3] - placed["box"][1]
    assert width / height < 0.75, (
        f"the crop still spans the shadow: {width}x{height}")


def test_the_matte_records_what_the_colour_cut_had_kept(monkeypatch):
    monkeypatch.setattr(pc, "matte_alpha", _perfect_matte)
    placed = pp._place_on_flat(_shadow_plate(), fill=0.5, matte="birefnet")
    rejected = int(placed["matte"]["rejected_px"])
    assert rejected > 0.5 * 300 * 60, (
        "the record must say how many pixels the colour cut had kept that the matte "
        f"rejected; it says {rejected}")


# ── refusal by name, never a substitution ──────────────────────────────────────

def test_the_real_matte_refuses_by_name_when_the_lane_is_down():
    rgb = np.asarray(_shadow_plate())
    with pytest.raises(pc.MatteUnavailable) as caught:
        pc.matte_alpha(rgb, url="http://127.0.0.1:1", timeout=1.0)
    assert "unreachable" in str(caught.value).lower()


def test_an_explicit_matte_request_never_falls_back_to_a_colour_cut():
    with pytest.raises(pc.MatteUnavailable):
        pp._place_on_flat(_shadow_plate(), fill=0.5, matte="birefnet",
                          matte_url="http://127.0.0.1:1")


def test_auto_records_the_fallback_it_took():
    placed = pp._place_on_flat(_shadow_plate(), fill=0.5, matte="auto",
                               matte_url="http://127.0.0.1:1")
    assert placed["matte"]["method"] == "none"
    assert "unreachable" in placed["matte"]["reason"].lower()
    assert placed["method"] in pc.METHODS


# ── the manifest states which matte produced the picture ───────────────────────

def _generator(image: Image.Image):
    def inner(brief, *, width, height, tier, seed):
        return {"bytes": _png(image), "seed": seed, "model": "supplied-plate",
                "width": image.width, "height": image.height,
                "used_brief": brief, "contains_text": False}
    return inner


def test_the_manifest_carries_the_matte_record(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "matte_alpha", _perfect_matte)
    result = pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "w"),
                      out_root=str(tmp_path), faces=("front",), width=1200,
                      height=1200, generator=_generator(_shadow_plate()),
                      background="white", fill=0.5)
    record = result["faces"][0]
    assert record["matte"]["method"] == "birefnet", json.dumps(record.get("matte"))
    assert record["matte"]["rejected_px"] > 0
    manifest = json.loads((tmp_path / "w" / "product_picture_manifest.json")
                          .read_text(encoding="utf-8"))
    assert manifest["faces"][0]["matte"]["method"] == "birefnet"


# ── the real plate: measured, not asserted ────────────────────────────────────

@pytest.mark.skipif(os.environ.get("NS_PLATE_MATTE") != "1",
                    reason="needs the media lane up (NS_PLATE_MATTE=1)")
def test_a_real_plate_shadow_is_measured_against_the_real_matte(tmp_path):
    assert REAL_PLATE.is_file(), f"no real plate at {REAL_PLATE}"
    plate = Image.open(REAL_PLATE).convert("RGB")
    colour = pp._place_on_flat(plate, fill=0.55, matte="none")
    matte = pp._place_on_flat(plate, fill=0.55, matte="birefnet")
    assert matte["matte"]["method"] == "birefnet", matte["matte"].get("reason")
    plate_rgb = np.asarray(plate).astype(np.int16)
    # the pixels the colour cut kept that the matte rejected, described by the plate
    colour_alpha = pc.cutout(plate_rgb, "background_distance").alpha > 200
    real_alpha = pc.matte_alpha(plate_rgb)
    solid = real_alpha > 128
    rejected = colour_alpha & ~solid
    dark_neutral = rejected & (np.abs(plate_rgb[..., 0] - plate_rgb[..., 2]) < 14) & \
        (plate_rgb.mean(axis=2) < 190)
    metrics = pc.alpha_metrics(real_alpha)
    ys, xs = np.nonzero(solid)
    box_w, box_h = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    record = {
        "plate": str(REAL_PLATE.relative_to(ROOT)),
        "matte_seconds": round(float(matte["matte"]["seconds"]), 2),
        "colour_box": colour["box"], "matte_box": matte["box"],
        "colour_box_aspect": round((colour["box"][2] - colour["box"][0]) /
                                   max(1, colour["box"][3] - colour["box"][1]), 3),
        "matte_box_aspect": round((matte["box"][2] - matte["box"][0]) /
                                  max(1, matte["box"][3] - matte["box"][1]), 3),
        "matte_subject_px": int(solid.sum()),
        "matte_subject_box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        "matte_subject_w": box_w, "matte_subject_h": box_h,
        "matte_border_contact": metrics["border_contact"],
        "matte_edge_gradient_px": metrics["edge_gradient_px"],
        "colour_alpha_px": int(colour_alpha.sum()),
        "colour_kept_of_matte": round(float((colour_alpha & solid).sum()) /
                                      max(1, int(solid.sum())), 4),
        "rejected_px": int(rejected.sum()),
        "rejected_dark_neutral_px": int(dark_neutral.sum()),
        "rejected_share_dark_neutral": round(float(dark_neutral.sum()) /
                                             max(1, int(rejected.sum())), 4),
    }
    out = ROOT / "reports" / "ty" / "d017_matte_measure.json"
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    for name, picture in (("colour", colour), ("matte", matte)):
        picture["image"].save(tmp_path / f"real_{name}.png")
        picture["image"].save(ROOT / "renders" / "_d017" / f"real_{name}.png")
    # what the measurement must show: the matte takes the product, not the light
    assert record["rejected_share_dark_neutral"] > 0.9, record
    assert record["matte_border_contact"] <= 0.01, record
    # the colour cut does not isolate this product at all: it cuts a band of the sweep
    assert record["colour_box_aspect"] > record["matte_box_aspect"] + 0.2, record
    assert record["colour_kept_of_matte"] < 0.95, record
