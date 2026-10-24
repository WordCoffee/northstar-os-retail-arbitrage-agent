"""Tests for the PPC bulk writer — validate, then write; never an empty upload."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specialists import ppc_agent, ppc_bulk  # noqa: E402

ROWS = [
    {"Campaign": "A", "Ad Group": "G1", "Customer Search Term": "lions mane powder",
     "Impressions": 900, "Clicks": 40, "Spend": 12.0, "Sales": 60.0, "Orders": 3},
    {"Campaign": "A", "Ad Group": "G1", "Customer Search Term": "mushroom coffee",
     "Impressions": 800, "Clicks": 25, "Spend": 9.0, "Sales": 0.0, "Orders": 0},
]


def _analysis():
    return ppc_agent.analyze(ROWS, target_acos=0.35)


def test_rows_carry_their_source():
    rows = ppc_bulk.build_rows(_analysis())
    assert len(rows) == 2
    assert all(r["source row"] for r in rows)
    assert any(r["match type"] == "negative exact" for r in rows)


def test_a_valid_plan_writes_a_real_xlsx(tmp_path):
    out = ppc_bulk.write_bulk_file(_analysis(), source=ROWS,
                                   out_path=tmp_path / "plan.xlsx", bid=0.9)
    assert out["ok"] is True
    p = Path(out["path"])
    assert p.is_file() and p.stat().st_size > 2000
    assert p.read_bytes()[:2] == b"PK"  # xlsx is a zip


def test_an_empty_plan_is_refused(tmp_path):
    with pytest.raises(ppc_bulk.BulkFileError):
        ppc_bulk.to_xlsx([])


def test_a_row_for_an_unknown_campaign_is_refused(tmp_path):
    rows = [{"operation": "update", "campaign": "Z", "ad group": "G9",
             "targeting": "x", "match type": "exact", "bid": 1.0, "budget": "",
             "state": "enabled", "reason": "", "source row": "{}"}]
    check = ppc_bulk.validate_rows(rows, ROWS)
    assert check["ok"] is False
    assert any("not in the source report" in p for p in check["problems"])


def test_an_invalid_analysis_cannot_be_written():
    with pytest.raises(ppc_bulk.BulkFileError):
        ppc_bulk.build_rows({"ok": False, "error": "rejected"})


def test_a_negative_bid_is_refused():
    rows = ppc_bulk.build_rows(_analysis())
    rows[0]["bid"] = -1
    check = ppc_bulk.validate_rows(rows, ROWS)
    assert check["ok"] is False
    assert any("negative bid" in p for p in check["problems"])
