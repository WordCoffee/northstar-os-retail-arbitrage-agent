"""pouch_calibration tests — parse, compare, verdict, durable record. Offline."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pouch_calibration as pc  # noqa: E402


def test_parse_size_variants():
    assert pc.parse_size("150x210+40") == {"width_mm": 150.0, "height_mm": 210.0,
                                           "gusset_mm": 40.0}
    assert pc.parse_size(" 140 X 200 + 80 ")["gusset_mm"] == 80.0
    # a pouch whose gusset was not stated parses with 0 (unknown), not an error
    assert pc.parse_size("100x150")["gusset_mm"] == 0.0
    for bad in ("abc", "0x210+40", "150x0+40", "150x210+-5"):
        with pytest.raises(ValueError):
            pc.parse_size(bad)


def test_spec_holds_when_the_measured_pouch_matches():
    res = pc.compare(spec=pc.parse_size("150x210+40"),
                     measured=pc.parse_size("152x208+41"), fill_g=227)
    assert res["verdict"] == "spec_holds", (res["deltas"], res["blockers"])
    assert res["blockers"] == []
    assert res["ladder_row"]["fill_g"] == 250


def test_spec_adjust_when_the_gusset_is_materially_different():
    res = pc.compare(spec=pc.parse_size("150x210+40"),
                     measured=pc.parse_size("148x205+78"), fill_g=227,
                     source="BrandX 8 oz")
    assert res["verdict"] == "spec_adjust"
    g = res["deltas"]["gusset_mm"]
    assert g["delta_mm"] == 38.0 and g["state"] == "mismatch"
    assert any("materially bigger" in b for b in res["blockers"])
    # and it says the MEASURED value agrees with the ladder, so the SPEC is wrong
    assert any("the SPEC is the outlier" in n for n in res["notes"])


def test_missing_measurement_is_reported_not_guessed():
    res = pc.compare(spec=pc.parse_size("150x210+40"),
                     measured={"width_mm": 150.0, "height_mm": 210.0})
    assert res["verdict"] == "inconclusive"
    assert any("incomplete" in b for b in res["blockers"])
    assert "gusset_mm" not in res["deltas"]


def test_near_state_sits_between_match_and_mismatch():
    # 8 % off: outside the 5 % match band, inside the 12 % mismatch threshold
    res = pc.compare(spec=pc.parse_size("150x210+40"),
                     measured=pc.parse_size("162x210+40"))
    assert res["deltas"]["width_mm"]["state"] == "near"
    assert res["verdict"] == "inconclusive"


def test_record_appends_and_survives_a_corrupt_file(tmp_path):
    p = tmp_path / "cal.json"
    r1 = pc.compare(spec=pc.parse_size("150x210+40"), measured=pc.parse_size("148x205+78"),
                    fill_g=227, source="BrandX")
    out = pc.record(r1, path=p)
    assert out["entries"] == 1
    r2 = pc.compare(spec=pc.parse_size("150x210+40"), measured=pc.parse_size("151x209+41"),
                    fill_g=227, source="BrandY")
    pc.record(r2, path=p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 2
    assert data["entries"][0]["source"] == "BrandX"
    assert "recorded_at" in data["entries"][0]

    p.write_text("{not json", encoding="utf-8")
    out3 = pc.record(r1, path=p)
    assert out3["entries"] == 1
    data2 = json.loads(p.read_text(encoding="utf-8"))
    assert data2.get("recovered_from_corrupt") is True


def test_no_fill_weight_skips_the_ladder_without_failing():
    res = pc.compare(spec=pc.parse_size("150x210+40"),
                     measured=pc.parse_size("150x210+40"))
    assert res["ladder_row"] is None
    assert res["verdict"] == "spec_holds"
