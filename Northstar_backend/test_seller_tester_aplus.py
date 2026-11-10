"""A+ content modules: brief validation, the deterministic producer, and page scoring.

Offline only: the shipping catalog is read from disk, the passing/failing modules are built
from a synthetic upload in `tmp_path`, and OCR is injected. Nothing here touches a GPU, the
network, or Amazon.

The two claims under test are the owner's:

* an A+ module is built on the seller's **uploaded** reference, not a prompt or a stored
  generation; validation refuses anything else;
* the same brief and the same upload produce the same bytes, which is measured by producing
  each page twice and comparing every module and the assembled page.
"""
from __future__ import annotations

import copy
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seller_tester import aplus  # noqa: E402
from tools.seller_tester.briefs import load_catalog  # noqa: E402


# --------------------------------------------------------------------------- fixtures
def _upload(path: Path) -> Path:
    """A synthetic seller upload: a textured pouch on a near-white seamless background."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (600, 600), (250, 248, 244))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((190, 110, 410, 500), radius=28, fill=(30, 92, 62))
    draw.rectangle((190, 180, 410, 230), fill=(24, 70, 48))
    draw.ellipse((250, 270, 350, 370), fill=(238, 232, 214))
    draw.ellipse((278, 298, 322, 342), fill=(196, 160, 74))
    for y in range(120, 500, 23):
        draw.line((200, y, 400, y), fill=(26, 84, 56), width=2)
    image.save(path, format="PNG")
    return path


def _brief(tmp_path: Path) -> dict:
    _upload(tmp_path / "renders" / "seller_upload.png")
    return {
        "id": "AP-T01",
        "content_type": "hero_band",
        "category": "supplement_pouch",
        "difficulty": 1,
        "source_mode": "uploaded_reference",
        "fidelity": "exact",
        "product_in_frame": True,
        "reference": {
            "kind": "uploaded_file",
            "path": "renders/seller_upload.png",
            "descriptor": {"filename": "seller_upload.png",
                           "mime_type": "image/png",
                           "subject": "test pouch, front"},
        },
        "page": {"width": 400, "gap_px": 0, "background": {"value": 248}},
        "modules": [
            {
                "id": "hero", "kind": "hero_band", "width": 400, "height": 260,
                "background": {"value": 248}, "product_in_frame": True,
                "text_required": ["TEST BRAND", "HERO LINE"],
                "text_box": [0.05, 0.10, 0.40, 0.78], "text_align": "left",
                "font_scale": 0.08, "rules": False, "scene": "flat",
                "product_anchor": [0.70, 0.55], "product_scale": 0.60,
            },
            {
                "id": "story", "kind": "brand_story", "width": 400, "height": 120,
                "background": {"value": 240}, "product_in_frame": False,
                "text_required": ["OUR STORY"], "text_box": [0.06, 0.10, 0.88, 0.78],
                "text_align": "center", "font_scale": 0.10, "rules": False,
                "scene": "flat",
            },
        ],
    }


def _ocr_for(brief: dict):
    text = " ".join(line for module in brief["modules"]
                    for line in module["text_required"])

    def fake_ocr(rgb: np.ndarray) -> dict:
        assert rgb.ndim == 3
        return {"text": text}

    return fake_ocr


# ------------------------------------------------------------------ brief validation
def test_the_shipped_a_plus_family_is_valid_and_built_on_uploads():
    payload = load_catalog()
    assert aplus.validate_aplus_briefs(payload) == []
    briefs = aplus.load_aplus_briefs(payload)
    assert len(briefs) >= aplus.MIN_APLUS_BRIEFS
    for brief in briefs:
        assert brief["source_mode"] == "uploaded_reference", brief["id"]
        assert brief["reference"]["kind"] == "uploaded_file", brief["id"]
        assert brief["reference"]["descriptor"]["filename"], brief["id"]
        for module in brief["modules"]:
            assert module["scene"] == "flat", (brief["id"], module["id"])


def test_a_stored_reference_is_refused_for_a_plus():
    payload = copy.deepcopy(load_catalog())
    brief = payload["aplus_briefs"][0]
    brief["source_mode"] = "stored_reference"
    brief["reference"] = {"kind": "stored_asset", "path": "renders/smoke_main_2000.png"}
    errors = aplus.validate_aplus_briefs(payload)
    assert any("uploaded reference" in error and brief["id"] in error
               for error in errors), errors


def test_a_non_uploaded_reference_kind_is_refused():
    payload = copy.deepcopy(load_catalog())
    brief = payload["aplus_briefs"][0]
    brief["reference"]["kind"] = "stored_asset"
    errors = aplus.validate_aplus_briefs(payload)
    assert any("kind 'uploaded_file'" in error for error in errors), errors


def test_a_product_module_must_be_exact_fidelity():
    payload = copy.deepcopy(load_catalog())
    brief = payload["aplus_briefs"][0]
    brief["fidelity"] = "tolerant"
    errors = aplus.validate_aplus_briefs(payload)
    assert any("must be fidelity 'exact'" in error for error in errors), errors


def test_a_module_that_is_wider_than_the_page_is_refused():
    payload = copy.deepcopy(load_catalog())
    brief = payload["aplus_briefs"][0]
    brief["modules"][0]["width"] = brief["page"]["width"] + 20
    errors = aplus.validate_aplus_briefs(payload)
    assert any("does not match page width" in error for error in errors), errors


def test_duplicate_module_ids_are_refused():
    payload = copy.deepcopy(load_catalog())
    payload["aplus_briefs"][0]["modules"][1]["id"] = \
        payload["aplus_briefs"][0]["modules"][0]["id"]
    errors = aplus.validate_aplus_briefs(payload)
    assert any("duplicate module id" in error for error in errors), errors


def test_page_height_must_match_the_module_grid():
    payload = copy.deepcopy(load_catalog())
    payload["aplus_briefs"][0]["page"]["height"] = 999
    errors = aplus.validate_aplus_briefs(payload)
    assert any("does not match the module grid" in error for error in errors), errors


# ------------------------------------------------------------------ the producer
def test_a_module_is_produced_at_its_declared_size(tmp_path):
    brief = _brief(tmp_path)
    produced = aplus.produce_page(brief, repo_root=tmp_path,
                                  out_dir=tmp_path / "renders" / "aplus",
                                  method="grabcut")
    assert produced["cutout"]["ok"], produced["cutout"]
    assert produced["page"]["error"] is None
    for record in produced["modules"]:
        with Image.open(BytesIO(record["bytes"])) as image:
            assert image.size == (record["width"], record["height"]), record["id"]
        assert record["cannot_verify"] is False, record["cannot_verify_reason"]
        assert record["layout"]["variant"] in ("band", "copy")
    widths = {record["width"] for record in produced["modules"]}
    assert widths == {brief["page"]["width"]}


def test_the_same_brief_and_upload_produce_the_same_bytes(tmp_path):
    brief = _brief(tmp_path)
    first = aplus.produce_page(brief, repo_root=tmp_path,
                               out_dir=tmp_path / "first", method="grabcut")
    second = aplus.produce_page(brief, repo_root=tmp_path,
                                out_dir=tmp_path / "second", method="grabcut")
    assert [row["bytes"] for row in first["modules"]] == \
           [row["bytes"] for row in second["modules"]]
    assert Path(first["page"]["path"]).read_bytes() == \
           Path(second["page"]["path"]).read_bytes()


def test_a_product_module_without_a_cutout_is_refused(tmp_path):
    brief = _brief(tmp_path)
    module = aplus.module_grid(brief)[0]
    record = aplus.produce_module(brief, module)
    assert record["bytes"] is None
    assert record["cannot_verify"] is True
    assert "no cutout" in record["cannot_verify_reason"], record


# ------------------------------------------------------------------ page scoring
def test_a_page_whose_modules_all_pass_scores_one_hundred(tmp_path):
    brief = _brief(tmp_path)
    produced = aplus.produce_page(brief, repo_root=tmp_path,
                                  out_dir=tmp_path / "renders" / "aplus",
                                  method="grabcut")
    page = Path(produced["page"]["path"]).read_bytes()
    score = aplus.score_aplus_page(brief, produced["modules"], page_bytes=page,
                                   ocr=_ocr_for(brief))
    assert score["passed"] is True, score["reasons"]
    assert score["score"] == 100.0
    assert score["module_pass_count"] == score["module_count_total"] == 2
    assert score["module_order"]["ok"] is True
    assert score["page"]["ok"] is True


def test_one_missing_module_fails_the_page_without_skipping_it(tmp_path):
    brief = _brief(tmp_path)
    produced = aplus.produce_page(brief, repo_root=tmp_path,
                                  out_dir=tmp_path / "renders" / "aplus",
                                  method="grabcut")
    records = [dict(row) for row in produced["modules"]]
    records[0]["bytes"] = None
    records[0]["path"] = None
    page = Path(produced["page"]["path"]).read_bytes()
    score = aplus.score_aplus_page(brief, records, page_bytes=page,
                                   ocr=_ocr_for(brief))
    assert score["passed"] is False
    assert score["module_count"]["ok"] is True
    assert "hero" in score["failed_modules"]
    hero = next(row for row in score["modules"] if row["id"] == "hero")
    assert hero["checks"]["present"]["ok"] is False
    assert any("hero" in reason for reason in score["reasons"]), score["reasons"]


def test_a_page_of_the_wrong_height_fails_the_page_check(tmp_path):
    brief = _brief(tmp_path)
    produced = aplus.produce_page(brief, repo_root=tmp_path,
                                  out_dir=tmp_path / "renders" / "aplus",
                                  method="grabcut")
    page = Path(produced["page"]["path"]).read_bytes()
    cropped = BytesIO()
    with Image.open(BytesIO(page)) as image:
        image.crop((0, 0, image.width, image.height - 10)).save(cropped, format="PNG")
    score = aplus.score_aplus_page(brief, produced["modules"],
                                   page_bytes=cropped.getvalue(), ocr=_ocr_for(brief))
    assert score["passed"] is False
    assert score["page"]["ok"] is False
    assert any("page:" in reason for reason in score["reasons"]), score["reasons"]
