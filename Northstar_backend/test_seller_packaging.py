"""sel-04: packaging deliverables — the app's own dielines, scored like a print shop.

The checks below are the brief's acceptance list: sheet size, the panels the manufactured
package actually has, bleed, safe margin, the layered SVG, the PDF page, and the app's own
readiness verdict. A dieline is not a picture: it either folds into the package or it does
not, so every check here is mechanical and a refusal is the engine's own words.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.seller_tester import packaging as pk

BRIEF = {
    "id": "PK-T1",
    "product": "MOGRA organic lion's mane, 170 g",
    "brand": "MOGRA ORGANICS",
    "template": "doypack",
    "params": {"width_mm": 140, "height_mm": 220, "gusset_mm": 40, "bleed_mm": 3,
               "safe_mm": 5, "fill_g": 170},
    "expect": {"panels": ["front", "back", "gusset"], "min_bleed_mm": 3,
               "min_safe_mm": 5, "layers": ["trim", "fold", "safe", "bleed"]},
}


def _built(tmp_path, brief=BRIEF):
    record = pk.build_packaging(brief, out_dir=tmp_path / "out")
    svg = Path(record["svg_path"]).read_text(encoding="utf-8")
    pdf = Path(record["pdf_path"]).read_bytes()
    return record, svg, pdf


def test_a_doypack_brief_builds_a_layered_svg_and_a_pdf(tmp_path):
    record, svg, pdf = _built(tmp_path)
    assert Path(record["svg_path"]).is_file() and Path(record["pdf_path"]).is_file()
    assert record["width_mm"] > 0 and record["height_mm"] > 0
    assert {"trim", "fold", "safe", "bleed"} <= set(record["layers"]), record["layers"]
    panels = record["meta"]["panels"]
    for name in ("front", "back", "gusset"):
        assert name in panels and panels[name][2] > 0 and panels[name][3] > 0, panels
    assert pdf.startswith(b"%PDF")


def test_a_freshly_built_dieline_scores_100(tmp_path):
    record, svg, pdf = _built(tmp_path)
    scored = pk.score_packaging(BRIEF, record, svg, pdf)
    assert scored["passed"] is True, json.dumps(scored["checks"], indent=1)
    assert scored["score"] == 100.0


def test_the_geometry_gate_refuses_by_name_and_writes_nothing(tmp_path):
    bad = dict(BRIEF, id="PK-BAD", template="rsc_box",
               params={"length_mm": 120, "width_mm": 80, "height_mm": 60,
                       "flap_mm": 200, "glue_mm": 15, "bleed_mm": 3},
               expect={"panels": ["front"]})
    with pytest.raises(pk.PackagingRefused) as caught:
        pk.build_packaging(bad, out_dir=tmp_path / "bad")
    assert "tab_deeper_than_body" in str(caught.value), str(caught.value)
    assert not (tmp_path / "bad" / "PK-BAD.svg").exists()


def test_a_missing_layer_fails_the_layers_check(tmp_path):
    record, svg, _ = _built(tmp_path)
    tampered = svg.replace('inkscape:label="fold"', 'inkscape:label="fold-removed"')
    assert tampered != svg
    record = dict(record, layers=[name for name in record["layers"] if name != "fold"])
    verdict = pk.check_layers(record, BRIEF["expect"])
    assert verdict["ok"] is False and verdict["missing"] == ["fold"]


def test_the_pdf_page_is_the_sheet_in_points(tmp_path):
    record, _, pdf = _built(tmp_path)
    verdict = pk.check_pdf(pdf, record)
    assert verdict["ok"] is True, verdict
    wrong = dict(record, width_mm=record["width_mm"] + 20)
    assert pk.check_pdf(pdf, wrong)["ok"] is False


def test_bleed_below_the_brief_fails(tmp_path):
    record, _, _ = _built(tmp_path)
    strict = dict(BRIEF["expect"], min_bleed_mm=6)
    verdict = pk.check_bleed(record, strict)
    assert verdict["ok"] is False and "6" in verdict["detail"]


def test_run_pass_records_a_refusal_and_files_a_gap(tmp_path):
    catalog = {
        "briefs": [
            BRIEF,
            dict(BRIEF, id="PK-BAD", template="rsc_box",
                 params={"length_mm": 120, "width_mm": 80, "height_mm": 60,
                         "flap_mm": 200, "glue_mm": 15, "bleed_mm": 3}),
        ]
    }
    catalog_path = tmp_path / "packaging.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    summary = pk.run_pass(catalog=catalog_path, out_dir=tmp_path / "out",
                          summary_path=tmp_path / "summary.json",
                          gaps_path=tmp_path / "gaps.json")
    assert summary["selected"] == 2
    assert summary["scored"] == 1 and summary["passed"] == 1
    assert summary["refused"] == 1
    gaps = json.loads((tmp_path / "gaps.json").read_text(encoding="utf-8"))
    assert gaps["gaps"] and gaps["gaps"][0]["brief_id"] == "PK-BAD"
    assert "tab_deeper_than_body" in gaps["gaps"][0]["reason"]


def test_the_shipped_catalog_is_four_real_templates_and_eight_briefs():
    briefs = pk.load_catalog()
    assert len(briefs) == 8
    assert {b["template"] for b in briefs} == {"doypack", "tuck_end", "rsc_box", "sleeve"}
    for brief in briefs:
        assert brief.get("product") and brief.get("brand")
        expect = brief["expect"]
        assert expect.get("panel_names") or expect.get("min_panels")
        assert expect.get("layers")


def test_a_carton_s_bodies_span_its_sheet(tmp_path):
    """A carton reports its faces as widths; they must add up to the sheet."""
    brief = {
        "id": "PK-T2", "product": "Harbor body oil carton", "brand": "HARBOR",
        "template": "tuck_end",
        "params": {"length_mm": 45, "width_mm": 45, "height_mm": 120, "bleed_mm": 3},
        "expect": {"min_panels": 4, "sheet_span": True, "min_bleed_mm": 3,
                   "min_safe_mm": 3, "layers": ["trim", "fold", "safe", "bleed"]},
    }
    record, svg, pdf = _built(tmp_path, brief)
    verdict = pk.check_panels(record, brief["expect"])
    assert verdict["ok"] is True, verdict
    assert verdict["shape"] == "widths" and verdict["span_ok"] is True
    # a face dropped from the layout no longer spans the sheet
    tampered = dict(record, meta=dict(record["meta"], panels=list(record["meta"]["panels"])[:-1]))
    assert pk.check_panels(tampered, brief["expect"])["ok"] is False
