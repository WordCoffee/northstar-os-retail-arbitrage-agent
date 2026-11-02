"""Quality gate: five axes, four of them blocking, none of them fabricated."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quality_gate as qg  # noqa: E402
import text_fidelity as tf  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _vision(**over):
    base = {
        "available": True, "parsed": True, "model": "qwen3.5:4b", "seconds": 3.0,
        "subject_matches": True, "form": "pouch", "form_raw": "pouch",
        "layout_balanced": True, "layout_note": "centred",
        "text_visible": False, "legible": None, "typography_note": "",
        "material_finish": "matte", "material_note": "soft matte film",
        "design_note": "a mushroom powder pouch",
    }
    base.update(over)
    return base


def _ocr(**over):
    base = {"engine": "rapidocr", "status": "ok", "contains_text": False,
            "boxes": 0, "words": [], "error": None}
    base.update(over)
    return base


@pytest.fixture()
def wired(monkeypatch):
    def apply(vision=None, ocr=None):
        monkeypatch.setattr(qg, "_observe", lambda *a, **k: _vision(**(vision or {})))
        monkeypatch.setattr(tf, "check_text_in_image", lambda *a, **k: _ocr(**(ocr or {})))
    return apply


def _score(**kw):
    return qg.score(PNG, brief="a 6 oz pouch of mushroom powder", requested_form="pouch",
                    text_requested=False, **kw)


def test_a_clean_text_free_render_passes(wired):
    wired()
    result = qg.score(PNG, brief="b", requested_form="pouch", text_requested=False)
    verdict = qg.verdict(result)
    assert verdict["ok"] is True
    assert verdict["score"] == "3/3"           # typography is n/a for a text-free brief
    assert verdict["failed"] == []
    assert verdict["not_applicable"] == ["typography"]


def test_the_wrong_container_fails(wired):
    wired(vision={"form": "box"})
    verdict = qg.verdict(_score())
    assert verdict["ok"] is False
    assert verdict["failed"] == ["form"]
    assert verdict["reasons"][0]["reason"] == "form_mismatch"


def test_a_render_that_does_not_match_the_brief_fails(wired):
    wired(vision={"subject_matches": False})
    verdict = qg.verdict(_score())
    assert "design_alignment" in verdict["failed"]


def test_an_unbalanced_composition_fails(wired):
    wired(vision={"layout_balanced": False, "layout_note": "product cut off at right"})
    verdict = qg.verdict(_score())
    assert "layout" in verdict["failed"]
    assert verdict["reasons"][0]["reason"] == "layout_unbalanced"


def test_a_missing_layout_answer_fails_closed(wired):
    wired(vision={"layout_balanced": None})
    assert "layout" in qg.verdict(_score())["failed"]


def test_requested_text_that_is_absent_fails(wired):
    wired(ocr={"contains_text": False})
    verdict = qg.verdict(qg.score(PNG, brief="b", requested_form="pouch",
                                  text_requested=True))
    assert "typography" in verdict["failed"]
    assert verdict["reasons"][0]["reason"] == "typography_missing"


def test_requested_text_that_is_garbled_fails(wired):
    wired(vision={"text_visible": True, "legible": False,
                  "typography_note": "letters melt into blobs"},
          ocr={"contains_text": True, "boxes": 4, "words": ["MUSHROO"]})
    verdict = qg.verdict(qg.score(PNG, brief="b", requested_form="pouch",
                                  text_requested=True))
    assert verdict["reasons"][0]["reason"] == "typography_illegible"


def test_requested_text_present_and_legible_passes(wired):
    wired(vision={"text_visible": True, "legible": True},
          ocr={"contains_text": True, "boxes": 3, "words": ["LION'S MANE"]})
    verdict = qg.verdict(qg.score(PNG, brief="b", requested_form="pouch",
                                  text_requested=True))
    assert verdict["ok"] is True
    assert verdict["score"] == "4/4"


def test_lettering_on_a_text_free_brief_fails(wired):
    wired(ocr={"contains_text": True, "boxes": 2, "words": ["SALE"]})
    verdict = qg.verdict(_score())
    assert "typography" in verdict["failed"]
    assert verdict["reasons"][0]["reason"] == "typography_unwanted_text"


def test_text_free_brief_with_no_ocr_is_not_a_failure(wired):
    # the suppression lane is the control for a text-free brief; absence of OCR
    # is recorded as unverified rather than blocking delivery
    wired(ocr={"status": "unavailable", "contains_text": None,
               "engine": None, "error": "unavailable"})
    verdict = qg.verdict(_score())
    assert verdict["ok"] is True
    assert verdict["not_applicable"] == ["typography"]


def test_requested_text_with_no_ocr_fails_closed(wired):
    wired(ocr={"status": "unavailable", "contains_text": None,
               "engine": None, "error": "unavailable"})
    verdict = qg.verdict(qg.score(PNG, brief="b", requested_form="pouch",
                                  text_requested=True))
    assert verdict["reasons"][0]["reason"] == "typography_unverified"


def test_an_unreachable_vision_lane_fails_every_blocking_axis(monkeypatch):
    monkeypatch.setattr(qg, "_observe", lambda *a, **k: {
        "available": False, "error": "URLError: connection refused", "model": "m",
        "seconds": 0.1})
    result = qg.score(PNG, brief="b", requested_form="pouch", text_requested=False)
    verdict = qg.verdict(result)
    assert verdict["ok"] is False
    assert set(verdict["failed"]) == set(qg.BLOCKING)
    assert result["error"].startswith("URLError")


def test_material_is_recorded_and_never_blocks(wired):
    wired(vision={"material_finish": "unknown"})
    result = qg.score(PNG, brief="b", requested_form="pouch", text_requested=False)
    assert result["axes"]["material"]["status"] == "recorded"
    assert qg.verdict(result)["ok"] is True


def test_a_reply_without_json_is_unavailable_not_a_pass(wired):
    wired(vision={"available": False, "parsed": False, "reason": "reply is not a JSON object",
                  "raw": "I cannot help with that", "error": None})
    verdict = qg.verdict(_score())
    assert verdict["ok"] is False
    assert verdict["available"] is False


def test_the_manifest_block_holds_no_nulls(wired):
    wired(ocr={"status": "unavailable", "contains_text": None, "engine": None,
               "error": "unavailable"})
    scored = qg.score(PNG, brief="b", requested_form="pouch", text_requested=False)
    block = qg.manifest_block(scored, qg.verdict(scored))

    def nulls(obj, path="quality"):
        found = []
        if obj is None:
            found.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                found.extend(nulls(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(nulls(v, f"{path}[{i}]"))
        return found

    assert nulls(block) == []
    assert set(block["axes"]) == set(qg.AXES)
    assert block["verdict"]["ok"] is True


def test_the_parser_finds_json_inside_prose():
    parsed = qg._parse('Sure! {"form": "stand-up pouch", "subject_matches": true, '
                       '"layout": {"balanced": true, "note": "ok"}, '
                       '"typography": {"text_visible": false, "legible": null}, '
                       '"material": {"finish": "matte"}}')
    assert parsed["parsed"] is True
    assert parsed["form"] == "pouch"
    assert parsed["layout_balanced"] is True


def test_the_parser_does_not_invent_a_form():
    parsed = qg._parse('{"form": "hexagonal prism", "subject_matches": true}')
    assert parsed["form"] == "other"


# --- requested copy, not just "some text" ------------------------------------

def test_term_coverage_ignores_case_and_punctuation():
    cov = qg.term_coverage(["LION'S MANE"], ["lion", "mane"])
    assert cov["applicable"] is True
    assert cov["coverage"] == 1.0


def test_term_coverage_reports_what_is_missing():
    cov = qg.term_coverage(["LION MANE", "6 oz"], ["LION", "MANE"])
    assert cov["coverage"] == 0.5
    assert cov["missing"] == ["6 oz"]


def test_requested_copy_that_is_mostly_absent_fails(wired):
    wired(vision={"text_visible": True, "legible": True},
          ocr={"contains_text": True, "boxes": 1, "words": ["SPECIAL OFFER"]})
    verdict = qg.verdict(qg.score(PNG, brief="b", requested_form="pouch",
                                  text_requested=True,
                                  expected_terms=["LION MANE", "6 oz"]))
    assert "typography" in verdict["failed"]
    assert verdict["reasons"][0]["reason"] == "typography_text_mismatch"


def test_requested_copy_that_is_present_passes_with_coverage_evidence(wired):
    wired(vision={"text_visible": True, "legible": True},
          ocr={"contains_text": True, "boxes": 2, "words": ["LION MANE", "6 oz"]})
    result = qg.score(PNG, brief="b", requested_form="pouch", text_requested=True,
                      expected_terms=["LION MANE", "6 oz"])
    axis = result["axes"]["typography"]
    assert axis["status"] == "pass"
    assert axis["coverage"]["coverage"] == 1.0


def test_without_expected_terms_the_axis_does_not_claim_coverage(wired):
    wired(vision={"text_visible": True, "legible": True},
          ocr={"contains_text": True, "boxes": 1, "words": ["ANYTHING"]})
    result = qg.score(PNG, brief="b", requested_form="pouch", text_requested=True)
    assert "coverage" not in result["axes"]["typography"]


# --- gibberish anywhere in the frame blocks the ad ---------------------------

def test_garbled_lettering_elsewhere_blocks_even_when_the_label_is_clean(wired):
    wired(vision={"text_visible": True, "legible": True, "garbled_text": True},
          ocr={"contains_text": True, "boxes": 9,
               "words": ["LION MANE", "MSNHES CIRSIE TUION", "MORIA ILIIP RGEHET"]})
    verdict = qg.verdict(qg.score(PNG, brief="b", requested_form="pouch",
                                  text_requested=True,
                                  expected_terms=["LION MANE"]))
    assert verdict["ok"] is False
    assert verdict["reasons"][0]["reason"] == "typography_garbled"


def test_a_clean_frame_reports_garbled_false_and_passes(wired):
    wired(vision={"text_visible": True, "legible": True, "garbled_text": False},
          ocr={"contains_text": True, "boxes": 2, "words": ["LION MANE", "6 oz"]})
    result = qg.score(PNG, brief="b", requested_form="pouch", text_requested=True,
                      expected_terms=["LION MANE"])
    assert result["axes"]["typography"]["status"] == "pass"
    assert result["axes"]["typography"]["vision_garbled"] is False


def test_no_requested_form_is_not_applicable_not_a_mismatch(wired):
    wired()
    result = qg.score(PNG, brief="b", requested_form="", text_requested=False)
    assert result["axes"]["form"]["status"] == "not_applicable"
    verdict = qg.verdict(result)
    assert verdict["ok"] is True
    assert "form" in verdict["not_applicable"]
    assert verdict["failed"] == []
