"""The product-picture scorecard: one number, and honest when it cannot measure.

These tests use synthetic images and `scoring=False`, so they test the
*mechanism* - thresholds, the compliance rule, the bar arithmetic - without
loading HPSv2, PickScore or a vision model.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import picture_scorecard as ps  # noqa: E402


def _png(*, fill: float = 0.9, size: tuple[int, int] = (1200, 1200),
         colour: tuple[int, int, int] = (180, 150, 120)) -> bytes:
    w, h = size
    im = Image.new("RGB", (w, h), (255, 255, 255))
    px = im.load()
    fw, fh = int(w * fill), int(h * fill)
    x0, y0 = (w - fw) // 2, (h - fh) // 2
    for x in range(x0, x0 + fw):
        for y in range(y0, y0 + fh):
            px[x, y] = colour
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_main_image_with_good_fill_is_compliant():
    row = ps.score_case(image_bytes=_png(fill=0.90),
                        case={"id": "c1", "surface": "main", "brief": "x"},
                        scoring=False)
    block = row["dimensions"]["marketplace_compliance"]
    assert block["status"] == "measured"
    assert block["score"] == 100.0


def test_main_image_with_poor_fill_is_refused():
    row = ps.score_case(image_bytes=_png(fill=0.40),
                        case={"id": "c2", "surface": "main", "brief": "x"},
                        scoring=False)
    block = row["dimensions"]["marketplace_compliance"]
    assert block["score"] == 0.0
    assert block["detail"]


def test_compliance_is_not_scored_on_a_lifestyle_surface():
    row = ps.score_case(image_bytes=_png(), case={"id": "c3", "surface": "lifestyle"},
                        scoring=False)
    assert row["dimensions"]["marketplace_compliance"]["status"] == "not_applicable"


def test_speed_decays_between_good_and_fail():
    fast = ps.score_case(image_bytes=_png(), case={"id": "s1", "surface": "x"},
                         seconds=10, scoring=False)["dimensions"]["speed"]
    slow = ps.score_case(image_bytes=_png(), case={"id": "s2", "surface": "x"},
                         seconds=400, scoring=False)["dimensions"]["speed"]
    mid = ps.score_case(image_bytes=_png(), case={"id": "s3", "surface": "x"},
                        seconds=190, scoring=False)["dimensions"]["speed"]
    assert fast["score"] == 100.0
    assert slow["score"] == 0.0
    assert 0 < mid["score"] < 100


def test_aggregate_does_not_turn_an_unmeasured_dimension_into_a_pass():
    row = ps.score_case(image_bytes=_png(), case={"id": "a1", "surface": "main"},
                        scoring=False)
    summary = ps.aggregate([row])
    assert "instruction_fidelity" in summary["bar"]["dimensions_unmeasured"]
    assert summary["production_ready"] is False


def test_aggregate_is_ready_only_when_every_measured_dimension_clears_the_bar():
    rows = []
    for i in range(3):
        row = ps.score_case(image_bytes=_png(fill=0.90),
                            case={"id": f"r{i}", "surface": "main"},
                            seconds=10, scoring=False)
        # Supply the model dimensions explicitly: this test is about arithmetic.
        for dim in ("instruction_fidelity", "photographic_quality"):
            row["dimensions"][dim] = {"score": 90.0, "status": "measured", "detail": "t"}
        row["dimensions"]["failure_recovery"] = {"score": 100.0, "status": "measured",
                                                 "detail": "t"}
        rows.append(row)
    summary = ps.aggregate(rows)
    assert summary["bar"]["dimensions_below_bar"] == []
    assert summary["compliance_rate"] == 1.0
    assert summary["production_ready"] is True


def test_aggregate_flags_a_dimension_below_the_bar():
    row = ps.score_case(image_bytes=_png(fill=0.90),
                        case={"id": "b1", "surface": "main"}, seconds=10, scoring=False)
    row["dimensions"]["instruction_fidelity"] = {"score": 40.0, "status": "measured",
                                                "detail": "off brief"}
    summary = ps.aggregate([row])
    assert "instruction_fidelity" in summary["bar"]["dimensions_below_bar"]
    assert summary["production_ready"] is False


def test_set_consistency_is_measured_inside_a_scenario_not_across_scenarios():
    """A white packshot and a lifestyle shot are supposed to look different."""
    same_a = {"case_id": "a", "scenario": "series", "phash": 0b11110000,
              "dimensions": {}}
    same_b = {"case_id": "b", "scenario": "series", "phash": 0b11110001,
              "dimensions": {}}
    other = {"case_id": "c", "scenario": "lifestyle",
             "phash": 0b00001111, "dimensions": {}}
    summary = ps.aggregate([same_a, same_b, other])
    block = summary["dimensions"]["set_consistency"]
    assert block["measured"] == 1              # only the pair inside "series"
    assert block["detail"]["mean_phash_distance"] == 1.0
    assert summary["sets"] == {"lifestyle": 1, "series": 2}


def test_set_consistency_is_unmeasured_when_no_scenario_has_a_pair():
    rows = [{"case_id": "a", "scenario": "one", "phash": 1, "dimensions": {}},
            {"case_id": "b", "scenario": "two", "phash": 2, "dimensions": {}}]
    block = ps.aggregate(rows)["dimensions"]["set_consistency"]
    assert block["mean"] is None
    assert "two images" in block["detail"]


def test_config_overlay_changes_the_rule(tmp_path):
    cfg_file = tmp_path / "scorecard.json"
    cfg_file.write_text('{"marketplace": {"min_fill": 0.30}}', encoding="utf-8")
    cfg = ps.load_config(cfg_file)
    assert cfg["marketplace"]["min_fill"] == 0.30
    # A 40 percent fill is refused at 0.85 and compliant at 0.30.
    row = ps.score_case(image_bytes=_png(fill=0.40),
                        case={"id": "o1", "surface": "main"},
                        cfg=cfg, scoring=False)
    assert row["dimensions"]["marketplace_compliance"]["score"] == 100.0
