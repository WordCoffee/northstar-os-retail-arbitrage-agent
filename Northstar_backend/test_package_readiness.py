"""package_readiness tests — the one-call verdict, fully offline.

Synthetic inputs only. OCR-dependent assertions skip loudly when the engine is
unavailable (never a fake pass).
"""

from __future__ import annotations

import io
import os
import sys

import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_print as dp  # noqa: E402
import package_readiness as pr  # noqa: E402


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _flat(rgb=(243, 234, 214), size=(400, 400)) -> bytes:
    return _png(Image.new("RGB", size, rgb))


def _cutout(size=(400, 400), box=(150, 100, 250, 300)) -> bytes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=(30, 60, 45, 255))
    return _png(img)


def _text_png(text: str, size=(640, 200)) -> bytes:
    img = Image.new("RGB", size, "white")
    ImageDraw.Draw(img).text((20, 60), text, fill="black",
                             font=ImageFont.load_default(size=48))
    return _png(img)


# ── dieline ─────────────────────────────────────────────────────────────────

def test_dieline_check_passes_a_good_build_and_keeps_confidence_honest():
    build = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                               "gusset_mm": 80, "fill_g": 250})
    res = pr.assess_dieline(build)
    assert res["assessed"] is True
    assert res["blockers"] == [], res["blockers"]
    assert {"trim", "fold", "safe"} <= set(res["layers_present"])
    assert any("planning dieline" in w for w in res["warnings"])


def test_dieline_check_blocks_thin_bleed_and_missing_layers():
    build = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                               "gusset_mm": 80, "bleed_mm": 0.5})
    res = pr.assess_dieline(build)
    assert any("bleed" in b for b in res["blockers"])
    stripped = {"meta": {"template": "doypack", "bleed_mm": 3.0},
                "layers": [{"layer": "trim"}], "width_mm": 100, "height_mm": 100}
    res2 = pr.assess_dieline(stripped)
    assert any("'fold'" in b for b in res2["blockers"])
    assert any("'safe'" in b for b in res2["blockers"])


def test_dieline_proportion_warnings_surface_but_do_not_block():
    build = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                               "gusset_mm": 40, "fill_g": 227})
    res = pr.assess_dieline(build)
    assert res["proportion_status"] == "warnings"
    assert any("proportion" in w for w in res["warnings"])
    assert res["blockers"] == [], "a proportion risk is a warning, not a blocker"


def test_no_dieline_is_not_assessed():
    assert pr.assess_dieline(None)["assessed"] is False


# ── main image ──────────────────────────────────────────────────────────────

def test_main_check_blocks_a_raw_render_and_passes_a_framed_cutout():
    raw = pr.assess_main(_flat((240, 238, 230)), min_side=200)
    assert raw["assessed"] is True and raw["verdict"] == "blocked"
    import image_prep as ip
    framed = ip.frame_on_white_bytes(_cutout(), fill=0.88, size=2000)
    good = pr.assess_main(framed["bytes"])
    assert good["verdict"] == "compliant", good["blockers"]


# ── copy ────────────────────────────────────────────────────────────────────

def test_copy_check_reports_unavailable_rather_than_passing(monkeypatch):
    monkeypatch.setattr(pr.text_fidelity, "check_text_in_image",
                        lambda b: {"status": "unavailable", "error": "no engine"})
    res = pr.assess_copy(_flat(), ["MOGRA ORGANICS"])
    assert res["assessed"] is False
    assert "UNVERIFIED" in res["reason"]


def test_copy_check_matches_and_flags_expected_terms():
    res = pr.assess_copy(_text_png("MOGRA ORGANICS"), ["MOGRA ORGANICS", "KIWI"])
    if not res.get("assessed"):
        pytest.skip("OCR unavailable")
    assert "MOGRA ORGANICS" in res["matched"]
    assert "KIWI" in res["missing"]
    assert any("KIWI" in b for b in res["blockers"])


# ── the verdict ─────────────────────────────────────────────────────────────

def test_verdict_is_not_assessed_with_no_inputs():
    out = pr.assess_package()
    assert out["verdict"] == "not_assessed"
    assert set(out["not_assessed"]) == {"prepress", "copy", "main", "dieline"}


def test_verdict_needs_work_lists_grouped_blockers():
    out = pr.assess_package(artwork=_flat((240, 238, 230)),
                            main_image=_flat((240, 238, 230)))
    assert out["verdict"] == "needs_work"
    assert any(b.startswith("main:") for b in out["blockers"])
    assert "dieline" in out["not_assessed"]


def test_verdict_retail_ready_when_every_supplied_check_passes():
    import image_prep as ip
    framed = ip.frame_on_white_bytes(_cutout(), fill=0.88, size=2000)
    clean = _flat()                      # cream: in gamut, low TAC
    build = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                               "gusset_mm": 80, "fill_g": 250})
    out = pr.assess_package(artwork=clean, main_image=framed["bytes"], dieline=build)
    if not out["evidence"]["prepress"].get("assessed"):
        pytest.skip("no CMYK profile on this machine")
    assert out["verdict"] == "retail_ready", (out["blockers"], out["warnings"])
    assert out["blockers"] == []


def test_out_of_gamut_artwork_blocks_the_verdict():
    art = _png(_green_square())
    out = pr.assess_package(artwork=art)
    if not out["evidence"]["prepress"].get("assessed"):
        pytest.skip("no CMYK profile on this machine")
    assert out["verdict"] == "needs_work"
    assert any("dE" in b for b in out["blockers"])


def _green_square(size=(300, 300)) -> Image.Image:
    img = Image.new("RGB", size, (243, 234, 214))
    ImageDraw.Draw(img).rectangle([20, 20, 280, 280], fill=(0, 255, 0))
    return img


# -- copy matching: fuzzy hits are reported, never silently accepted -----------

def test_norm_and_similarity_helpers():
    assert pr._norm("Lion'\''s  Mane") == "LIONSMANE"
    assert pr._best_similarity("MOGRA ORGANICS", ["MOGRA ORGANCS"]) > 0.9
    assert pr._best_similarity("MOGRA ORGANICS", ["SOMETHING ELSE"]) < 0.5
    assert pr._best_similarity("", ["x"]) == 0.0


def test_copy_fuzzy_match_warns_without_blocking(monkeypatch):
    # a stylised wordmark read one character off must not read as "missing"
    fake = {"status": "ok", "contains_text": True, "boxes": 2,
            "words": ["MOGRA ORGANCS", "Healthy & Organie"], "error": None}
    monkeypatch.setattr(pr.text_fidelity, "check_text_in_image", lambda b: fake)
    res = pr.assess_copy(b"x", ["MOGRA ORGANICS"])
    assert res["matched"] == [] and res["missing"] == []
    assert res["matched_fuzzy"][0]["term"] == "MOGRA ORGANICS"
    assert res["matched_fuzzy"][0]["ratio"] > 0.9
    assert res["blockers"] == []
    assert any("fuzzily" in w for w in res["warnings"])


def test_copy_absent_term_still_blocks(monkeypatch):
    fake = {"status": "ok", "contains_text": True, "boxes": 1,
            "words": ["MUSHROOM POWDER"], "error": None}
    monkeypatch.setattr(pr.text_fidelity, "check_text_in_image", lambda b: fake)
    res = pr.assess_copy(b"x", ["MUSHROOM POWDER", "KIWI EXTRACT"])
    assert res["matched"] == ["MUSHROOM POWDER"]
    assert res["missing"] == ["KIWI EXTRACT"]
    assert any("KIWI EXTRACT" in b for b in res["blockers"])
