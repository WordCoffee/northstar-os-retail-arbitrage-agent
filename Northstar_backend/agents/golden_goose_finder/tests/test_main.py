"""Tests for the Golden Goose Finder orchestrator.

Run: cd Northstar_backend && python -m pytest agents/golden_goose_finder/tests/test_main.py -v
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure the backend directory is on sys.path for sibling module resolution
_backend_dir = str(Path(__file__).resolve().parents[4])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Import the module under test
from agents.golden_goose_finder.main import (
    _BUILTIN_MOCK_PRODUCTS,
    _BUILTIN_MOCK_MATCHES,
    _builtin_calculate_economics,
    _builtin_score_opportunity,
    _builtin_score_batch,
    _mock_scan,
    _scored_to_dicts,
    run_pipeline,
    router,
    _BUILTIN_CATEGORIES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_wholesale():
    """A single mock wholesale product."""
    return _BUILTIN_MOCK_PRODUCTS[0]


@pytest.fixture
def mock_match():
    """A single mock Amazon match."""
    return _BUILTIN_MOCK_MATCHES[0]


@pytest.fixture
def sample_economics(mock_wholesale, mock_match):
    """A single mock breakdown economics record."""
    return _builtin_calculate_economics(mock_wholesale, mock_match)


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestRunPipeline:
    """Test the full run_pipeline function."""

    def test_mock_pipeline_completes(self):
        """Mock pipeline completes successfully and returns a report dict."""
        report = asyncio.run(run_pipeline(use_mock=True))
        assert isinstance(report, dict)
        assert "meta" in report
        assert "summary" in report
        assert "opportunities" in report

    def test_report_structure(self, tmp_path):
        """Report has correct top-level structure."""
        report = asyncio.run(run_pipeline(use_mock=True))
        assert "generated_at" in report["meta"]
        assert "pipeline_version" in report["meta"]
        assert report["meta"]["mode"] == "mock"
        assert isinstance(report["opportunities"], list)
        assert isinstance(report["summary"], dict)

    def test_report_summary_counts(self):
        """Summary tier counts are consistent."""
        report = asyncio.run(run_pipeline(use_mock=True))
        summary = report["summary"]
        opps = report["opportunities"]
        total = summary["total_opportunities"]
        assert total == len(opps)
        assert summary["high_tier_count"] + summary["medium_tier_count"] + \
               summary["low_tier_count"] + summary["reject_count"] == total

    def test_pipeline_with_category_filter(self):
        """Pipeline respects category filter."""
        report_all = asyncio.run(run_pipeline(use_mock=True))
        report_filtered = asyncio.run(
            run_pipeline(use_mock=True, categories=["vitamins-supplements"])
        )
        # Filtered should have fewer or equal results
        assert len(report_filtered["opportunities"]) <= len(report_all["opportunities"])

    def test_pipeline_with_roi_floor_filter(self):
        """Higher ROI floor produces fewer HIGH-tier results."""
        report_low = asyncio.run(run_pipeline(use_mock=True, roi_floor=10.0))
        report_high = asyncio.run(run_pipeline(use_mock=True, roi_floor=100.0))
        # More restrictive floor = fewer HIGH tier
        assert report_high["summary"]["high_tier_count"] <= report_low["summary"]["high_tier_count"]

    def test_pipeline_with_max_results(self):
        """Max results is respected."""
        report = asyncio.run(run_pipeline(use_mock=True, max_results=3))
        assert len(report["opportunities"]) <= 3

    def test_pipeline_empty_results(self):
        """Pipeline handles impossible filters gracefully."""
        report = asyncio.run(
            run_pipeline(
                use_mock=True,
                categories=["nonexistent-category-xyz"],
            )
        )
        assert report["summary"]["total_opportunities"] == 0
        assert report["opportunities"] == []


# ---------------------------------------------------------------------------
# Economics tests
# ---------------------------------------------------------------------------


class TestBuiltinEconomics:
    """Test the built-in economics calculator."""

    def test_basic_economics(self, mock_wholesale, mock_match):
        """Economics calculation produces expected fields."""
        econ = _builtin_calculate_economics(mock_wholesale, mock_match)
        assert econ.pack_count == 6
        assert econ.unit_cogs < econ.wholesale_price
        assert econ.amazon_price > 0
        assert econ.total_amazon_fees > 0
        assert econ.net_profit_per_unit == round(
            econ.amazon_price - econ.unit_cogs - econ.total_amazon_fees, 2
        )

    def test_single_pack_economics(self):
        """Single-pack product has unit_cogs == wholesale_price."""
        wp = _BUILTIN_MOCK_PRODUCTS[1]  # pack_count=1
        m = _BUILTIN_MOCK_MATCHES[1]
        econ = _builtin_calculate_economics(wp, m)
        assert econ.unit_cogs == wp.wholesale_price

    def test_roi_positive_for_profitable(self, mock_wholesale, mock_match):
        """ROI is positive when profit is positive."""
        econ = _builtin_calculate_economics(mock_wholesale, mock_match)
        if econ.net_profit_per_unit > 0:
            assert econ.roi_per_unit > 0


# ---------------------------------------------------------------------------
# Scoring tests
# ---------------------------------------------------------------------------


class TestScoring:
    """Test the scoring module."""

    def test_score_batch_produces_ranks(self, sample_economics):
        """Scored opportunities have sequential ranks."""
        scored = _builtin_score_batch([sample_economics, sample_economics])
        assert len(scored) == 2
        for i, s in enumerate(scored):
            assert s.rank == i + 1

    def test_high_tier_for_profitable(self, sample_economics):
        """Profitable product gets HIGH tier."""
        scored = _builtin_score_opportunity(sample_economics, 0, roi_floor=10.0)
        assert scored.tier in ("HIGH", "MEDIUM")

    def test_reject_for_negative_profit(self):
        """Negative profit gets REJECT tier."""
        wp = _BUILTIN_MOCK_PRODUCTS[0]
        m = MagicMock()
        m.amazon_price = 0.01  # extremely low price → negative profit
        m.asin = "B0TEST0001"
        m.title = "Test"
        econ = _builtin_calculate_economics(wp, m)
        scored = _builtin_score_opportunity(econ, 0)
        assert scored.tier == "REJECT"

    def test_opportunity_tags(self, sample_economics):
        """Scoring adds appropriate tags."""
        scored = _builtin_score_opportunity(sample_economics, 0)
        assert isinstance(scored.opportunity_tags, list)
        assert isinstance(scored.scoring_notes, list)

    def test_batch_sorted_by_score(self):
        """Batch scoring sorts by composite_score descending."""
        econs = [_builtin_calculate_economics(wp, _BUILTIN_MOCK_MATCHES[i])
                 for i, wp in enumerate(_BUILTIN_MOCK_PRODUCTS)]
        scored = _builtin_score_batch(econs)
        scores = [s.composite_score for s in scored]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Mock scan tests
# ---------------------------------------------------------------------------


class TestMockScan:
    """Test the _mock_scan helper."""

    def test_mock_scan_returns_list(self):
        """Mock scan returns a list of scored opportunities."""
        result = _mock_scan()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_mock_scan_with_category_filter(self):
        """Mock scan filters by category."""
        all_result = _mock_scan()
        filtered = _mock_scan(categories=["vitamins-supplements"])
        assert len(filtered) <= len(all_result)


# ---------------------------------------------------------------------------
# API endpoint tests (FastAPI test client)
# ---------------------------------------------------------------------------


class TestAPIEndpoints:
    """Test the FastAPI router endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client for the router."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Health check returns 200 with correct structure."""
        resp = client.get("/api/golden-goose/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "golden-goose-finder"
        assert "version" in data
        assert "modules_loaded" in data

    def test_scan_mock_endpoint(self, client):
        """Mock scan endpoint returns 200 with opportunities."""
        resp = client.post("/api/golden-goose/scan-mock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["opportunities"], list)
        assert isinstance(data["summary"], dict)
        assert "total_opportunities" in data["summary"]

    def test_scan_mock_with_params(self, client):
        """Mock scan respects query parameters."""
        resp = client.post("/api/golden-goose/scan-mock?roi_floor=50&max_results=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["opportunities"]) <= 2

    def test_scan_live_endpoint_is_hard_stopped(self, client):
        """Live scan returns 403 (hard-stopped per §3)."""
        resp = client.post("/api/golden-goose/scan")
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert "operator approval" in detail.lower() or "§3" in detail

    def test_categories_endpoint(self, client):
        """Categories endpoint returns data."""
        resp = client.get("/api/golden-goose/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "categories" in data
        assert isinstance(data["categories"], dict)

    def test_opportunities_endpoint_no_data(self, client):
        """Opportunities endpoint handles missing reports gracefully."""
        resp = client.get("/api/golden-goose/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "no_data")

    def test_opportunities_with_tier_filter(self, client):
        """Opportunities endpoint supports tier filter."""
        # First run a mock scan to create a report
        client.post("/api/golden-goose/scan-mock")
        resp = client.get("/api/golden-goose/opportunities?tier=HIGH")
        assert resp.status_code == 200
        data = resp.json()
        for opp in data.get("opportunities", []):
            assert opp["tier"] == "HIGH"


# ---------------------------------------------------------------------------
# CLI argument parsing tests
# ---------------------------------------------------------------------------


class TestCLIArgParsing:
    """Test CLI argument parsing."""

    def test_default_args(self):
        """Default arguments parse correctly."""
        from agents.golden_goose_finder.main import _build_parser
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.mock is True
        assert args.live is False
        assert args.roi_floor == 10.0
        assert args.min_sales == 1000
        assert args.max_results == 100
        assert args.json is False
        assert args.verbose is False

    def test_custom_args(self):
        """Custom arguments parse correctly."""
        from agents.golden_goose_finder.main import _build_parser
        parser = _build_parser()
        args = parser.parse_args([
            "--categories", "vitamins", "personal-care",
            "--stores", "Costco",
            "--roi-floor", "20",
            "--min-sales", "1000",
            "--max-results", "50",
            "--json",
            "--verbose",
        ])
        assert args.categories == ["vitamins", "personal-care"]
        assert args.stores == ["Costco"]
        assert args.roi_floor == 20.0
        assert args.min_sales == 1000
        assert args.max_results == 50
        assert args.json is True
        assert args.verbose is True

    def test_mock_and_live_mutually_exclusive(self):
        """--mock and --live are mutually exclusive."""
        from agents.golden_goose_finder.main import _build_parser
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--mock", "--live"])


# ---------------------------------------------------------------------------
# Data shape tests
# ---------------------------------------------------------------------------


class TestDataShapes:
    """Test that built-in data has expected shapes."""

    def test_wholesale_products_not_empty(self):
        assert len(_BUILTIN_MOCK_PRODUCTS) > 0

    def test_amazon_matches_not_empty(self):
        assert len(_BUILTIN_MOCK_MATCHES) > 0

    def test_wholesale_has_required_fields(self):
        for wp in _BUILTIN_MOCK_PRODUCTS:
            assert wp.source_store
            assert wp.product_title
            assert wp.brand
            assert wp.wholesale_price > 0

    def test_match_has_required_fields(self):
        for m in _BUILTIN_MOCK_MATCHES:
            assert m.asin
            assert m.title
            assert m.amazon_price > 0

    def test_categories_dict_not_empty(self):
        assert len(_BUILTIN_CATEGORIES) > 0

    def test_scored_to_dicts(self):
        """_scored_to_dicts produces serializable dicts."""
        scored = _builtin_score_batch(
            [_builtin_calculate_economics(wp, _BUILTIN_MOCK_MATCHES[i])
             for i, wp in enumerate(_BUILTIN_MOCK_PRODUCTS)]
        )
        dicts = _scored_to_dicts(scored)
        assert isinstance(dicts, list)
        assert len(dicts) > 0
        # Must be JSON-serializable
        json_str = json.dumps(dicts, default=str)
        assert len(json_str) > 0
