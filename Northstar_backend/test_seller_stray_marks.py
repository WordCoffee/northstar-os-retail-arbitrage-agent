"""D-019: "is the picture free of stray marks" is a question about a population.

The label-conform unit asked a local vision judge that question of twelve prompt-only
artefacts and recorded 10 of 12. The two failures were not the same kind of thing:

* **PO-007** (an infographic page) failed on "a dashed rule line" and "a floating ring" —
  marks `deterministic.infographic` draws itself: the accent rule, the subtitle rule, the
  footer rule, the callout chips, their leader lines and their anchor dots. Asking a page
  the harness typeset to be "free of marks" fails a correct page for being a page. That is
  the acceptance bug, and this module pins the fix: a composed page is judged on the
  photograph inside its panel, with its own furniture named as exempt.
* **PO-006** failed on a dashed streak that is real — cutout residue pasted with the
  product. No scoping change may excuse it, which is why the control below adds a stray
  to a composed page and requires the same rule to fail it.

Every test is offline: PIL and numpy, no render lane, no model.
"""
from __future__ import annotations

import io
import json

import numpy as np
from PIL import Image, ImageDraw

from tools.seller_tester import deterministic, scorers
from tools.seller_tester.stray_report import synthetic_page


def _page(*, dash: bool = False, rim: bool = False, gradient: bool = False):
    """A flat page, a product block, and optionally one mark of a named kind."""
    height = width = 400
    image = np.full((height, width, 3), 250, dtype=np.uint8)
    if gradient:
        ramp = np.linspace(40, 210, width, dtype=np.uint8)
        image[:, :, 0] = ramp[None, :]
    image[140:300, 120:280] = np.array([70, 100, 80], dtype=np.uint8)
    picture = Image.fromarray(image)
    draw = ImageDraw.Draw(picture)
    if dash:
        draw.line((300, 340, 360, 300), fill=(15, 15, 15), width=6)
    if rim:
        draw.line((118, 140, 118, 300), fill=(240, 240, 240), width=2)
    mask = np.zeros((height, width), dtype=bool)
    mask[140:300, 120:280] = True
    return np.asarray(picture), mask


def test_a_detached_dash_on_a_flat_page_is_a_stray():
    rgb, mask = _page(dash=True)
    verdict = scorers.check_stray_marks(rgb, {}, subject_mask=mask)
    assert verdict["skipped"] is False
    assert verdict["ok"] is False
    assert verdict["mark_px"] >= 100
    assert "stray mark" in verdict["detail"]


def test_the_same_page_without_the_dash_is_clean():
    rgb, mask = _page()
    verdict = scorers.check_stray_marks(rgb, {}, subject_mask=mask)
    assert verdict["ok"] is True and verdict["mark_px"] == 0


def test_a_hairline_hugging_the_product_is_a_rim_not_an_object():
    rgb, mask = _page(rim=True)
    verdict = scorers.check_stray_marks(rgb, {}, subject_mask=mask)
    assert verdict["ok"] is True, verdict


def test_a_gradient_scene_cannot_be_attributed_and_says_so():
    rgb, mask = _page(dash=True, gradient=True)
    verdict = scorers.check_stray_marks(rgb, {}, subject_mask=mask)
    assert verdict["skipped"] is True
    assert "background is not a field" in verdict["detail"]


def test_without_a_silhouette_the_check_is_skipped_never_passed():
    rgb, _ = _page(dash=True)
    verdict = scorers.check_stray_marks(rgb, {}, subject_mask=None)
    assert verdict["skipped"] is True
    assert "silhouette" in verdict["detail"]


# ── the acceptance question ─────────────────────────────────────────────────

def _brief(situation: str) -> dict:
    return {"id": "PO-X", "situation": situation, "category": "food_jar",
            "prompt": "a matte forest-green stand-up pouch on a clean page"}


def test_a_composed_page_is_asked_about_the_photograph_not_the_page():
    rubric = scorers.judge_constraint(_brief("infographic"),
                                      {"kind": "deterministic", "panel": [10, 20, 300, 400]})
    assert rubric["scope"] == "composed_page"
    assert "photo panel" in rubric["constraint"]
    assert "NOT a stray" in rubric["constraint"]
    for furniture in ("accent rule", "footer", "callout chips", "anchor dots"):
        assert furniture in rubric["constraint"], furniture
    assert rubric["panel"] == [10, 20, 300, 400]


def test_a_photograph_keeps_the_plain_question_with_no_exemption():
    rubric = scorers.judge_constraint(_brief("main_image"), None)
    assert rubric["scope"] == "photograph"
    assert rubric["furniture_exempt"] == []
    assert "free of stray marks" in rubric["constraint"]


def test_a_refused_or_absent_layout_is_judged_as_a_photograph():
    """The stricter question, never the weaker one: an unproven layout is no exemption."""
    for layout in (None, {}, {"kind": "refused", "reason": "cannot lay out"},
                   {"kind": "error", "error": "boom"}):
        rubric = scorers.judge_constraint(_brief("infographic"), layout)
        assert rubric["scope"] == "photograph", layout


def test_a_composed_page_with_a_dash_inside_the_panel_still_fails():
    """The control: the fix must not launder a real stray into "layout furniture"."""
    clean = synthetic_page(dash=False)
    dirty = synthetic_page(dash=True)
    assert clean["ok"] is True and clean["mark_px"] == 0
    assert dirty["ok"] is False and dirty["mark_px"] >= 100
    assert dirty["panel"] == clean["panel"]


# ── the score does not move ─────────────────────────────────────────────────

def _picture_bytes() -> bytes:
    image = np.full((600, 600, 3), 255, dtype=np.uint8)
    image[180:420, 180:420] = np.array([90, 120, 100], dtype=np.uint8)
    stream = io.BytesIO()
    Image.fromarray(image).save(stream, format="PNG")
    return stream.getvalue()


BRIEF = {"id": "D019-1", "situation": "infographic", "category": "food_jar",
         "source_mode": "prompt_only", "difficulty": 1,
         "constraints": {"dimensions": {"min_width": 400, "min_height": 400,
                                        "max_width": 4000, "max_height": 4000},
                         "aspect": {"ratio": 1.0, "tolerance": 0.01},
                         "background": {"value": 255, "tolerance": 4, "mode": "uniform"},
                         "fill_pct": {"min": 5, "max": 90, "distance": 20},
                         "text_rule": "allowed",
                         "file_size": {"min_bytes": 100, "max_bytes": 8000000}}}


def test_the_judge_rubric_records_its_scope_and_the_score_does_not_move():
    from tools.seller_tester.judge import FakeJudge

    judge = FakeJudge(passed=True)
    plain = scorers.score_image(_picture_bytes(), BRIEF, judge=FakeJudge(passed=True))
    laid = scorers.score_image(
        _picture_bytes(), BRIEF, judge=judge,
        layout={"kind": "deterministic", "panel": [50, 50, 500, 500]})
    assert laid["score"] == plain["score"], "a diagnostic must not move a published score"
    assert laid["passed"] == plain["passed"]
    assert laid["judge_scope"] == "composed_page"
    assert "photo panel" in judge.calls[0]["rubric"]["constraint"]
    assert "stray_marks" in laid
    assert json.dumps(laid["stray_marks"], default=str)


def test_the_infographic_layout_declares_the_panel_its_furniture_lives_outside():
    """The evidence for PO-007: the rule and the callout dot are the layout's own."""
    scene = np.full((400, 400, 3), 210, dtype=np.uint8)
    scene[120:280, 120:280] = np.array([70, 100, 80], dtype=np.uint8)
    stream = io.BytesIO()
    Image.fromarray(scene).save(stream, format="PNG")
    brief = {"id": "SYN-1", "situation": "infographic",
             "constraints": {"background": {"value": 255, "mode": "free"}}}
    laid = deterministic.infographic(stream.getvalue(), [120, 120, 160, 160], brief,
                                     copy_lines=["170 g of a single ingredient"])
    meta = laid["meta"]
    assert meta["layout"] == "infographic"
    assert meta["callouts"] == len(deterministic.CALLOUTS)
    panel = meta["panel"]
    assert panel[0] > 0 and panel[1] > int(400 * 0.018), "the accent rule sits above"
    # The accent rule is drawn in the top band, outside the panel's top edge.
    assert int(400 * 0.026) <= panel[1], (panel, "the rule would be inside the panel")
