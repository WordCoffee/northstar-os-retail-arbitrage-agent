"""Tests for the Golden Goose report / output generator.

Covers: the full JSON report schema (with 5+ opportunities), the discarded
list, run metadata, file saving (explicit and default directory), the
console table format (ordering, no ANSI on non-tty), and the SourceScout
UI panel export — plus empty-data behavior throughout.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

from agents.golden_goose_finder.goose_report import (
    export_to_scout_panel,
    generate_console_display,
    generate_json_report,
    save_report,
)
from agents.golden_goose_finder.opportunity_scorer import TIER_HIGH, TIER_MEDIUM, score_opportunity


def _full_scored(ec, high, medium, low, reject):
    """5 scored opportunities: 2x HIGH, MEDIUM, LOW, REJECT (raw, unfiltered)."""
    high2 = ec(
        asin="B09GOLDDEMO2",
        title="Kirkland Signature Parchment Paper (600 sq ft)",
        amazon_price=27.99,
        bsr=2800,
        monthly_sales_estimate=2500.0,
        **{"wholesale.wholesale_pack_title": "Kirkland Signature Parchment Paper 600 sq ft"},
    )
    return [
        score_opportunity(high),
        score_opportunity(high2),
        score_opportunity(medium),
        score_opportunity(low),
        score_opportunity(reject),
    ]


# ---------------------------------------------------------------------------
# JSON report.
# ---------------------------------------------------------------------------


def test_json_report_schema_with_full_data(ec, high, medium, low, reject):
    scored = _full_scored(ec, high, medium, low, reject)
    report = generate_json_report(scored, run_metadata={"source_scan": "costco_20260916"})

    assert set(report.keys()) == {
        "report_version", "generated_at", "run_metadata", "summary",
        "opportunities", "discarded",
    }
    assert report["report_version"] == "1.0"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T.+", report["generated_at"])
    assert report["run_metadata"] == {"source_scan": "costco_20260916"}

    # Opportunities exclude rejects; discarded carries them.
    assert len(report["opportunities"]) == 4
    assert len(report["discarded"]) == 1
    assert report["discarded"][0]["asin"] == "B09REJECT01"
    assert "Failed filters" in report["discarded"][0]["reason"]
    assert report["discarded"][0]["details"]

    # Summary counts.
    summary = report["summary"]
    assert summary["total_evaluated"] == 5
    assert summary["high"] == 2
    assert summary["medium"] == 1
    assert summary["low"] == 1
    assert summary["rejected"] == 1
    assert summary["best_opportunity"]["asin"] == "B09GOLDDEMO1"

    # Sorted by composite score descending.
    scores = [o["scoring"]["composite_score"] for o in report["opportunities"]]
    assert scores == sorted(scores, reverse=True)

    # Report must be JSON-serializable.
    assert json.loads(json.dumps(report)) == report


def test_json_report_full_entry_shape(high):
    report = generate_json_report([score_opportunity(high)])
    entry = report["opportunities"][0]

    assert set(entry.keys()) == {
        "asin", "product_title", "brand", "category", "gating_status",
        "amazon_metrics", "sourcing_data", "financial_breakdown", "scoring",
        "economics_confidence", "notes",
    }
    assert entry["asin"] == "B09GOLDDEMO1"
    assert entry["product_title"] == "Kirkland Signature Laundry Detergent Pods (152 ct)"
    assert entry["brand"] == "Kirkland Signature"
    assert entry["category"] == "health-household"
    assert entry["gating_status"] == "APPROVED"  # 1 live FBA seller
    assert entry["economics_confidence"] == "estimated"

    assert entry["amazon_metrics"] == {
        "est_monthly_sales": 3000,
        "review_rating": 4.7,
        "review_count": 1200,
        "current_fba_sellers": 1,
        "buy_box_price": 29.99,
        "bsr": 3500,
    }
    assert entry["sourcing_data"] == {
        "source_store": "Costco",
        "wholesale_pack_title": "Kirkland Signature Laundry Detergent Pods 152 ct",
        "wholesale_cost": 24.99,
        "pack_count": 152,
        "unit_cogs": 0.24,
    }
    fb = entry["financial_breakdown"]
    assert fb["resale_price"] == 29.99
    assert fb["referral_fee"] is None      # split not provided -> honest nulls
    assert fb["fulfillment_fee"] is None
    assert fb["repackaging_cost"] is None
    assert fb["total_fees"] == 6.50
    assert fb["total_costs_per_unit"] == 6.74      # 0.24 cogs + 6.50 fees
    assert fb["breakeven_price"] == 6.74
    assert fb["net_profit_per_unit"] == 12.50
    assert fb["net_profit_per_costco_pack"] == 1900.00
    assert fb["roi_percentage"] == 125.0
    assert fb["roi_per_costco_pack_pct"] == 152.0
    assert fb["profit_margin_pct"] == 45.0

    scoring = entry["scoring"]
    assert scoring["tier"] == TIER_HIGH
    assert scoring["composite_score"] >= 0.7
    assert scoring["tags"] == [
        "low_competition", "high_margin", "premium_product",
        "high_velocity", "trending_up", "bulk_goldmine",
    ]
    assert any("breakeven approximated" in n for n in entry["notes"])


def test_json_report_medium_entry_financials(medium):
    report = generate_json_report([score_opportunity(medium)])
    fb = report["opportunities"][0]["financial_breakdown"]
    assert fb["total_costs_per_unit"] == 5.30       # 2.10 cogs + 3.20 fees
    assert fb["net_profit_per_unit"] == 11.00
    assert fb["roi_percentage"] == 60.0
    assert report["opportunities"][0]["scoring"]["tier"] == TIER_MEDIUM


def test_json_report_with_ratio_style_roi_is_normalized(ec):
    # Ratio values in (0, 1.0] are converted to percentages; already-percent
    # values pass through unchanged (documented _as_pct convention).
    eco = ec(roi_per_unit=0.45, roi_per_costco_pack=152.0, profit_margin_pct=0.45)
    report = generate_json_report([score_opportunity(eco)])
    fb = report["opportunities"][0]["financial_breakdown"]
    assert fb["roi_percentage"] == 45.0
    assert fb["roi_per_costco_pack_pct"] == 152.0
    assert fb["profit_margin_pct"] == 45.0


def test_json_report_empty_data():
    report = generate_json_report([])
    assert report["opportunities"] == []
    assert report["discarded"] == []
    assert report["summary"]["total_evaluated"] == 0
    assert report["summary"]["best_opportunity"] is None
    assert report["summary"]["top_tags"] == {}


def test_gating_status_values(ec):
    # No live sellers -> CAN_APPLY (would need approval); no data -> UNKNOWN.
    can_apply = generate_json_report([score_opportunity(ec(**{"individual.fba_sellers": 0}))])
    assert can_apply["opportunities"][0]["gating_status"] == "CAN_APPLY"

    unknown = generate_json_report([score_opportunity(ec(**{"individual.fba_sellers": None}))])
    assert unknown["opportunities"][0]["gating_status"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# File saving.
# ---------------------------------------------------------------------------


def test_save_report_creates_files(tmp_path, ec, high, medium, low, reject):
    report = generate_json_report(_full_scored(ec, high, medium, low, reject))
    path = save_report(report, str(tmp_path))

    assert path == str(tmp_path / "report.json")
    assert Path(path).exists()
    assert (tmp_path / "summary.txt").exists()

    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    assert loaded["report_version"] == "1.0"
    assert len(loaded["opportunities"]) == 4

    summary_text = (tmp_path / "summary.txt").read_text(encoding="utf-8")
    assert "Golden Goose Finder Report" in summary_text
    assert "Ranked opportunities (4)" in summary_text
    assert "REJECTED 1" in summary_text
    assert "B09REJECT01" in summary_text  # discarded section present


def test_save_report_default_directory(ec, high, medium, low, reject):
    report = generate_json_report(_full_scored(ec, high, medium, low, reject))
    path = save_report(report)

    json_path = Path(path)
    run_dir = json_path.parent
    # <repo>/reports/golden_goose/<YYYYmmddTHHMMSS>/
    assert run_dir.parent.name == "golden_goose"
    assert re.fullmatch(r"\d{8}T\d{6}", run_dir.name)
    assert json_path.name == "report.json"
    assert (run_dir / "summary.txt").exists()
    shutil.rmtree(run_dir, ignore_errors=True)  # keep the repo clean


def test_save_report_empty(tmp_path):
    path = save_report(generate_json_report([]), str(tmp_path))
    assert Path(path).exists()
    assert (tmp_path / "summary.txt").exists()


# ---------------------------------------------------------------------------
# Console display.
# ---------------------------------------------------------------------------


def test_console_display_format(ec, high, medium, low, reject):
    text = generate_console_display(_full_scored(ec, high, medium, low, reject))
    for header in ("Rank", "ASIN", "Brand", "Product", "Profit", "ROI", "Score", "Tier", "Monthly", "FBA"):
        assert header in text
    # Ranked: HIGH first.
    first_data = text.splitlines()[2]
    assert first_data.lstrip().startswith("1 |")
    assert TIER_HIGH in first_data
    assert "$12.50" in text
    assert "125.0%" in text
    assert "3000" in text
    assert "B09GOLDDEMO1" in text
    # NO ANSI color codes on a non-tty stdout.
    assert "\x1b" not in text


def test_console_display_rank_numbering(high, medium, low):
    text = generate_console_display([score_opportunity(medium), score_opportunity(low), score_opportunity(high)])
    data_lines = text.splitlines()[2:]
    assert data_lines[0].lstrip().startswith("1 |")
    assert data_lines[1].lstrip().startswith("2 |")
    assert data_lines[2].lstrip().startswith("3 |")


def test_console_display_empty():
    text = generate_console_display([])
    assert "(no opportunities)" in text
    assert "Rank" in text


# ---------------------------------------------------------------------------
# SourceScout panel export.
# ---------------------------------------------------------------------------


def test_export_to_scout_panel_fields(ec, high, medium, low, reject):
    rows = export_to_scout_panel(_full_scored(ec, high, medium, low, reject))
    assert len(rows) == 5  # rejects included so the panel can show why

    first = rows[0]
    assert set(first.keys()) == {
        "id", "asin", "name", "brand", "cost", "amazonPrice", "fbaFee",
        "net", "roi", "competition", "estMonthly", "tier", "status",
        "sourceStore", "wholesalePack", "packCount", "tags",
    }
    assert first["id"] == "B09GOLDDEMO1"
    assert first["asin"] == "B09GOLDDEMO1"
    assert first["name"] == "Kirkland Signature Laundry Detergent Pods (152 ct)"
    assert first["brand"] == "Kirkland Signature"
    assert first["cost"] == 0.24
    assert first["amazonPrice"] == 29.99
    assert first["fbaFee"] == 6.50
    assert first["net"] == 12.50
    assert first["roi"] == 125.0
    assert first["competition"] == "Low"   # 1 FBA seller
    assert first["estMonthly"] == 3000
    assert first["tier"] == "Pass"
    assert first["status"] == "scored"
    assert first["sourceStore"] == "Costco"
    assert first["wholesalePack"] == "Kirkland Signature Laundry Detergent Pods 152 ct"
    assert first["packCount"] == 152
    assert first["tags"]

    by_asin = {r["asin"]: r for r in rows}
    assert by_asin["B09MEDIUM001"]["tier"] == "Hold"
    assert by_asin["B09MEDIUM001"]["competition"] == "Medium"  # 3 FBA sellers
    assert by_asin["B09LOWX00001"]["tier"] == "Reject"
    assert by_asin["B09LOWX00001"]["competition"] == "High"    # 6 FBA sellers
    assert by_asin["B09REJECT01"]["tier"] == "Reject"
    # JSON-safe.
    json.loads(json.dumps(rows))


def test_export_to_scout_panel_unknown_values(unknown_data):
    rows = export_to_scout_panel([score_opportunity(unknown_data)])
    row = rows[0]
    assert row["competition"] == "Unknown"
    assert row["estMonthly"] is None
    assert row["net"] is None
    assert row["roi"] is None


def test_export_to_scout_panel_empty():
    assert export_to_scout_panel([]) == []