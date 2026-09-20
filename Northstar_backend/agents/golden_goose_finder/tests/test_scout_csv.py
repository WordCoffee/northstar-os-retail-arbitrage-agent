"""Phase G — FIXES_50 #43 Scout CSV export tests."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.goose_report import (  # noqa: E402
    SCOUT_CSV_HEADERS,
    scout_rows_from_report,
    write_scout_csv,
)

FAKE_REPORT = {
    "opportunities": [
        {
            "amazon_asin": "B0X", "amazon_title": "Nicorette Gum 2mg",
            "brand": "Nicorette", "unit_cogs": 5.5, "amazon_price": 19.99,
            "total_amazon_fees": 6.4, "net_profit_per_unit": 8.0,
            "roi_per_unit": 145.0, "monthly_sales_estimate": 300,
            "tier": "HIGH", "fba_sellers": 1, "seller_name": "TestSeller",
            "source_store": "Costco", "pack_count": 200, "weight_oz": 4.0,
        },
        {
            "amazon_asin": "B0Y", "amazon_title": "Claritin 10mg",
            "brand": "Claritin", "unit_cogs": 7.0, "amazon_price": 12.0,
            "total_amazon_fees": 4.0, "net_profit_per_unit": 1.0,
            "roi_per_unit": 14.3, "monthly_sales_estimate": 10,
            "tier": "REJECT", "fba_sellers": None, "seller_name": None,
            "source_store": "Sam's Club", "pack_count": 365,
        },
    ]
}


def test_scout_rows_shape():
    rows = scout_rows_from_report(FAKE_REPORT)
    assert len(rows) == 2
    first = rows[0]
    assert first["asin"] == "B0X" and first["tier"] == "HIGH"
    assert first["competition"] == "Competitive"
    # absent fields honest-empty
    assert rows[1]["seller"] == "" and rows[1]["competition"] == ""


def test_scout_csv_roundtrip(tmp_path):
    p = tmp_path / "scout.csv"
    rows = scout_rows_from_report(FAKE_REPORT)
    assert write_scout_csv(rows, p) == 2
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        data = list(reader)
    assert reader.fieldnames == SCOUT_CSV_HEADERS
    assert len(data) == 2 and data[0]["brand"] == "Nicorette"
    assert data[1]["competition"] == ""


def test_scout_csv_empty_rows_writes_header(tmp_path):
    p = tmp_path / "empty.csv"
    assert write_scout_csv([], p) == 0
    with p.open(encoding="utf-8", newline="") as fh:
        assert list(csv.DictReader(fh)) == []