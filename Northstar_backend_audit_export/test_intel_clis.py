"""Offline tests for the intel CLIs (demand/competition/portfolio
reports and the opportunity export).

Covers report content and honesty rules (unknown stays unknown,
explicit-zero proof only, revenue basis provenance, nulls-last export
ordering), write-only-when-requested CLI behavior, performance of the
offline demand model on large candidate sets, and byte-identity guards
proving real data files are untouched.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import csv
import glob
import hashlib
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import demand_report
import competition_report
import portfolio_report
import opportunity_export

_TMP = tempfile.mkdtemp(prefix="intel-cli-test-")

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REAL_CACHE = os.path.join(_BACKEND_DIR, "data", "scanner-search-cache.json")
_REAL_BACKUPS = sorted(
    glob.glob(os.path.join(_BACKEND_DIR, "data", "scanner-search-cache.brightdata-*.json"))
)
_REAL_SNAPSHOTS = os.path.join(_BACKEND_DIR, "data", "amazon-market-snapshots.json")

if os.path.exists(_REAL_CACHE):
    _CACHE_SHA = hashlib.sha256(open(_REAL_CACHE, "rb").read()).hexdigest()
else:
    _CACHE_SHA = None
if _REAL_BACKUPS:
    _BACKUP_SHA = hashlib.sha256(open(_REAL_BACKUPS[0], "rb").read()).hexdigest()
else:
    _BACKUP_SHA = None
if os.path.exists(_REAL_SNAPSHOTS):
    _SNAPSHOTS_SHA = hashlib.sha256(open(_REAL_SNAPSHOTS, "rb").read()).hexdigest()
else:
    _SNAPSHOTS_SHA = None


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _candidate(asin="B00GYZWNY6", name="Kirkland Signature Paper Towels 12 Pack", **extra):
    row = {"asin": asin, "name": name}
    row.update(extra)
    return row


class DemandReportTests(unittest.TestCase):
    def test_estimate_never_from_forbidden_signals(self):
        # A price/cost/title-only row must stay Unknown.
        candidates = [_candidate(amazon_price=29.99, costco_cost=15.0)]
        report = demand_report.build_report(candidates, "fixture.json")
        row = report["results"][0]
        self.assertIsNone(row["estimated_monthly_sales"])
        self.assertEqual(row["sales_estimation_source"], "unknown")
        self.assertFalse(row["monthly_sales_estimated"])
        self.assertEqual(report["summary"]["unknown"], 1)

    def test_provider_estimate_and_bsr_signals(self):
        candidates = [
            _candidate(asin="B0PROV0001", monthly_sales_estimate=500),
            _candidate(asin="B0BSR00001", sales_rank=2000, amazon_category="Home & Kitchen"),
        ]
        report = demand_report.build_report(candidates, "fixture.json")
        by_asin = {r["asin"]: r for r in report["results"]}
        self.assertEqual(by_asin["B0PROV0001"]["estimated_monthly_sales"], 500)
        self.assertEqual(by_asin["B0PROV0001"]["sales_estimation_source"], "provider_estimate")
        self.assertIsNotNone(by_asin["B0BSR00001"]["estimated_monthly_sales"])
        self.assertEqual(by_asin["B0BSR00001"]["sales_estimation_source"], "bsr_category_model")
        self.assertEqual(report["model"]["version"], demand_report.demand_estimator.CALIBRATION_MODEL_VERSION)
        self.assertIn("not a forecast", report["disclaimer"].lower())

    def test_main_writes_only_output(self):
        out = os.path.join(_TMP, "demand-report.json")
        cache = os.path.join(_TMP, "fake-cache.json")
        with patch(
            "amazon_search.load_cached_candidates",
            return_value=[_candidate(monthly_sales_estimate=500)],
        ), patch("amazon_search.cache_meta", return_value={"fetched_at": "2026-01-01T00:00:00Z"}):
            rc = demand_report.main(["--input", cache, "--output", out])
        self.assertEqual(rc, 0)
        report = json.load(open(out, encoding="utf-8"))
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["summary"]["estimated"], 1)

    def test_main_no_candidates_returns_1(self):
        with patch("amazon_search.load_cached_candidates", return_value=[]):
            rc = demand_report.main(["--input", os.path.join(_TMP, "empty.json"), "--output", os.path.join(_TMP, "x.json")])
        self.assertEqual(rc, 1)

    def test_large_set_performance(self):
        for count in (234, 500, 5000):
            candidates = []
            for i in range(count):
                row = {"asin": "B0PERF%05d" % i, "name": "Kirkland Item %d" % i}
                if i % 3 == 0:
                    row["monthly_sales_estimate"] = 100 + i
                elif i % 3 == 1:
                    row["sales_rank"] = 500 + i
                    row["amazon_category"] = "Home & Kitchen"
                candidates.append(row)
            start = time.monotonic()
            report = demand_report.build_report(candidates, "perf.json")
            elapsed = time.monotonic() - start
            self.assertEqual(report["candidate_count"], count)
            self.assertLess(elapsed, 5.0, "demand report for %d rows took %.2fs" % (count, elapsed))


class CompetitionReportTests(unittest.TestCase):
    def _snap(self, status="available", offers=None, offers_returned=0, offers_complete=True, claimed=0):
        return {
            "data_status": status,
            "title": "Kirkland Test",
            "offers": offers or [],
            "offers_returned": offers_returned,
            "offers_complete": offers_complete,
            "seller_counts": {"claimed_total": claimed, "observed_total": len(offers or []),
                              "fba_observed": 0, "fbm_observed": 0, "amazon_observed": 0,
                              "counts_from_observed": True},
            "buy_box": {},
        }

    def test_roster_states_summary(self):
        snaps = {
            "B0ZERO0001": self._snap(status="available", offers=[], offers_returned=0,
                                     offers_complete=True, claimed=0),
            "B0FAIL0001": self._snap(status="failed", offers=[], offers_returned=0,
                                     offers_complete=False, claimed=5),
            "B0OBSV0001": self._snap(status="partial", offers=[{"price": {"value": 10.0},
                                      "is_fba": True, "seller_name": "S"}],
                                     offers_returned=1, offers_complete=False, claimed=9),
        }
        report = competition_report.build_report(snaps)
        self.assertEqual(report["summary"]["roster_states"],
                         {"explicit_zero": 1, "unknown_roster": 1, "observed_rows": 1})
        by_asin = {r["asin"]: r for r in report["results"]}
        self.assertEqual(by_asin["B0ZERO0001"]["observed_total_sellers"], 0)
        self.assertIsNone(by_asin["B0FAIL0001"]["observed_total_sellers"])
        self.assertEqual(by_asin["B0FAIL0001"]["offer_roster_reason"], "offer_roster_unavailable")
        self.assertEqual(by_asin["B0OBSV0001"]["observed_total_sellers"], 1)
        self.assertIn("Unknown", report["disclaimer"])

    def test_main_writes_only_output(self):
        out = os.path.join(_TMP, "competition-report.json")
        store = os.path.join(_TMP, "fake-store.json")
        with patch(
            "market_snapshot_store.load_snapshots",
            return_value={"B0ZERO0001": self._snap()},
        ):
            rc = competition_report.main(["--input", store, "--output", out])
        self.assertEqual(rc, 0)
        report = json.load(open(out, encoding="utf-8"))
        self.assertEqual(report["snapshot_count"], 1)


class PortfolioReportTests(unittest.TestCase):
    def _analysis(self, rows):
        return {"all_results": rows}

    def _row(self, score, readiness="complete_opportunity", category="test_buy_candidate", **extra):
        row = {
            "asin": "B0ROWA%04d" % abs(hash(extra.get("name", score))) if False else "B0ROWA0001",
            "name": "Kirkland Item",
            "opportunity_score": score,
            "portfolio_readiness": readiness,
            "portfolio_category": category,
            "risk_flags": [],
            "total_completeness_score": 100,
        }
        row.update(extra)
        return row

    def test_sums_only_over_rows_with_values(self):
        rows = [
            self._row(10, estimated_monthly_revenue=1000.0, monthly_revenue_basis="observed_buy_box_landed_price",
                      estimated_monthly_profit_pool=90.0),
            self._row(5, estimated_monthly_revenue=None, monthly_revenue_basis=None,
                      estimated_monthly_profit_pool=None),
            self._row(3, estimated_monthly_revenue=2000.0, monthly_revenue_basis="candidate_amazon_price",
                      estimated_monthly_profit_pool=180.0),
        ]
        report = portfolio_report.build_report(self._analysis(rows))
        summary = report["summary"]
        self.assertEqual(summary["estimated_monthly_revenue"]["sum"], 3000.0)
        self.assertEqual(summary["estimated_monthly_revenue"]["rows_with_value"], 2)
        self.assertEqual(summary["estimated_monthly_profit_pool"]["sum"], 270.0)
        self.assertEqual(report["row_count"], 3)
        self.assertIn("not a forecast", report["disclaimer"].lower())

    def test_main_writes_only_output(self):
        out = os.path.join(_TMP, "portfolio-report.json")
        with patch(
            "amazon_search.load_cached_candidates", return_value=[_candidate()]
        ), patch(
            "product_analysis.analyze_kirkland_products",
            return_value=self._analysis([self._row(10, estimated_monthly_revenue=100.0)]),
        ):
            rc = portfolio_report.main(["--input", os.path.join(_TMP, "fake.json"), "--output", out])
        self.assertEqual(rc, 0)
        report = json.load(open(out, encoding="utf-8"))
        self.assertEqual(report["summary"]["estimated_monthly_revenue"]["sum"], 100.0)


class OpportunityExportTests(unittest.TestCase):
    def test_nulls_sort_after_all_scored_rows(self):
        rows = [
            {"name": "no-score", "opportunity_score": None, "asin": "B0NONE0001"},
            {"name": "low", "opportunity_score": 5, "asin": "B0LOW00001"},
            {"name": "high", "opportunity_score": 95, "asin": "B0HIGH0001"},
            {"name": "no-score-2", "opportunity_score": None, "asin": "B0NONE0002"},
        ]
        out = opportunity_export.export_rows({"all_results": rows}, top=10)
        names = [r["name"] for r in out]
        self.assertEqual(names, ["high", "low", "no-score", "no-score-2"])

    def test_top_limit_respected(self):
        rows = [{"name": "r%d" % i, "opportunity_score": 100 - i} for i in range(10)]
        out = opportunity_export.export_rows({"all_results": rows}, top=3)
        self.assertEqual(len(out), 3)
        self.assertEqual([r["rank"] for r in out], [1, 2, 3])

    def test_export_csv_writes_header_and_cells(self):
        path = os.path.join(_TMP, "top.csv")
        rows = [{"rank": 1, "name": "Kirkland Item", "opportunity_score": 95,
                 "risk_flags": "thin_margin", "asin": "B0TEST0001"}]
        count = opportunity_export.write_export_csv(rows, path)
        self.assertEqual(count, 1)
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, opportunity_export.EXPORT_COLUMNS)
            first = next(reader)
            self.assertEqual(first["opportunity_score"], "95")
            self.assertEqual(first["risk_flags"], "thin_margin")

    def test_main_writes_only_output(self):
        out = os.path.join(_TMP, "main-top.csv")
        with patch(
            "amazon_search.load_cached_candidates", return_value=[_candidate()]
        ), patch(
            "product_analysis.analyze_kirkland_products",
            return_value={"all_results": [{"name": "Kirkland Item", "opportunity_score": 95,
                                           "asin": "B0TEST0001", "portfolio_readiness": "complete_opportunity",
                                           "portfolio_category": "test_buy_candidate",
                                           "portfolio_next_step": "review_top_opportunity",
                                           "risk_flags": [], "portfolio_score_reasons": []}]},
        ):
            rc = opportunity_export.main(["--input", os.path.join(_TMP, "fake.json"), "--output", out, "--top", "5"])
        self.assertEqual(rc, 0)
        with open(out, newline="", encoding="utf-8") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)


class RealDataByteIdentityTests(unittest.TestCase):
    def test_real_cache_untouched(self):
        if _CACHE_SHA is None:
            self.skipTest("real cache missing")
        self.assertEqual(_sha256(_REAL_CACHE), _CACHE_SHA)

    def test_real_backup_untouched(self):
        if _BACKUP_SHA is None:
            self.skipTest("real backup missing")
        self.assertEqual(_sha256(_REAL_BACKUPS[0]), _BACKUP_SHA)

    def test_real_snapshot_store_untouched(self):
        if _SNAPSHOTS_SHA is None:
            self.skipTest("real snapshot store missing")
        self.assertEqual(_sha256(_REAL_SNAPSHOTS), _SNAPSHOTS_SHA)


if __name__ == "__main__":
    unittest.main()