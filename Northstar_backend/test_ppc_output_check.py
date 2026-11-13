"""The PPC output checks: format, delta reconciliation, and the seller's bid ceiling.

Each of these is a way a bulk file can look fine and still be unusable: it opens in our parser but
not in the ads console, it re-types a row nobody approved, or it bids past what the seller agreed to
spend. The checks are pure functions, so the cases are synthetic and exact.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from seller_tester import ppc_output_check as check  # noqa: E402

HEADER = ["product", "entity", "operation", "campaign_id", "ad_group_id", "keyword_id", "bid"]


def _sheet(rows):
    return {"sheets": [{"name": "Sponsored Products Campaigns", "headers": HEADER,
                        "normalized": rows}]}


SOURCE_ROWS = [
    {"sheet": "Sponsored Products Campaigns", "row_index": 0, "product": "Sponsored Products",
     "entity": "Campaign", "operation": "Update", "campaign_id": "C1", "bid": ""},
    {"sheet": "Sponsored Products Campaigns", "row_index": 1, "product": "Sponsored Products",
     "entity": "Keyword", "operation": "Update", "campaign_id": "C1", "ad_group_id": "A1",
     "keyword_id": "K1", "keyword_text": "mushroom coffee", "campaign_name": "Launch",
     "bid": "1.10"},
    {"sheet": "Sponsored Products Campaigns", "row_index": 2, "product": "Sponsored Products",
     "entity": "Keyword", "operation": "Update", "campaign_id": "C1", "ad_group_id": "A1",
     "keyword_id": "K2", "keyword_text": "lion's mane", "bid": "0.75"},
]

DELTA_ROW = {"sheet": "Sponsored Products Campaigns", "row_index": 0, "product": "Sponsored Products",
             "entity": "Keyword", "operation": "Update", "campaign_id": "C1", "ad_group_id": "A1",
             "keyword_id": "K1", "keyword_text": "mushroom coffee", "campaign_name": "Launch",
             "bid": "0.90"}


def test_a_written_delta_file_conforms_to_the_app_format():
    result = check.check_format(_sheet([DELTA_ROW]), _sheet(SOURCE_ROWS),
                                ("product", "entity", "operation"))
    assert result["ok"] is True
    assert result["rows"] == 1
    assert result["missing_columns"] == []


def test_a_missing_required_column_is_named():
    sheet = {"sheets": [{"name": "Sponsored Products Campaigns",
                         "headers": [h for h in HEADER if h != "entity"],
                         "normalized": [DELTA_ROW]}]}
    result = check.check_format(sheet, _sheet(SOURCE_ROWS),
                                ("product", "entity", "operation"))
    assert result["ok"] is False
    assert "entity" in result["missing_columns"]


def test_an_empty_file_fails_format():
    result = check.check_format(_sheet([]), _sheet(SOURCE_ROWS),
                                ("product", "entity", "operation"))
    assert result["ok"] is False
    assert "rows=0" in result["detail"]


def test_the_approved_delta_reconciles():
    result = check.reconcile(_sheet(SOURCE_ROWS), _sheet([DELTA_ROW]), {1: {"bid": "0.90"}})
    assert result["ok"] is True, result["problems"]


def test_a_row_nobody_approved_is_refused():
    result = check.reconcile(_sheet(SOURCE_ROWS), _sheet([DELTA_ROW]), {})
    assert result["ok"] is False
    assert any("never approved" in p for p in result["problems"])


def test_a_change_outside_the_approved_columns_is_refused():
    tampered = dict(DELTA_ROW, campaign_name="Renamed Without Approval", bid="0.90")
    result = check.reconcile(_sheet(SOURCE_ROWS), _sheet([tampered]), {1: {"bid": "0.90"}})
    assert result["ok"] is False
    assert any("campaign_name" in p for p in result["problems"])


def test_a_wrong_approved_value_is_refused():
    result = check.reconcile(_sheet(SOURCE_ROWS), _sheet([DELTA_ROW]), {1: {"bid": "0.50"}})
    assert result["ok"] is False
    assert any("row 1 bid" in p for p in result["problems"])


def test_a_missing_approved_row_is_refused():
    result = check.reconcile(_sheet(SOURCE_ROWS), _sheet([]), {1: {"bid": "0.90"}})
    assert result["ok"] is False
    assert any("missing" in p for p in result["problems"])


def test_a_row_not_in_the_source_is_refused():
    stranger = dict(DELTA_ROW, keyword_id="K9")
    result = check.reconcile(_sheet(SOURCE_ROWS), _sheet([stranger]), {1: {"bid": "0.90"}})
    assert result["ok"] is False
    assert any("not in the source" in p for p in result["problems"])


def test_bids_over_the_cap_fail_and_name_the_value():
    result = check.bids_within_caps(_sheet([DELTA_ROW]), max_bid=0.80)
    assert result["ok"] is False
    assert result["over"] == [0.9]
    assert result["max_bid"] == 0.80


def test_a_bid_below_the_floor_fails():
    result = check.bids_within_caps(_sheet([dict(DELTA_ROW, bid="0.00")]), max_bid=2.0)
    assert result["ok"] is False
    assert result["under"] == [0.0]


def test_no_bid_at_all_is_not_a_pass():
    result = check.bids_within_caps(_sheet([dict(DELTA_ROW, bid="")]), max_bid=2.0)
    assert result["ok"] is False
    assert result["bids_seen"] == 0


def test_a_bid_at_the_cap_passes():
    result = check.bids_within_caps(_sheet([dict(DELTA_ROW, bid="2.00")]), max_bid=2.0)
    assert result["ok"] is True
