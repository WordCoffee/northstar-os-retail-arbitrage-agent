"""Offline tests for the read-only coverage report (coverage_report.py).

Zero network, zero writes to real files: the cache path and every Costco
store (CSV, detail, invoice, ledger) are pointed at temp locations via
env BEFORE the backend modules import. Fixtures include a
234-candidate representative cache (real cache shape: asin/name/price/
url/brand/sales only) plus 500- and 5,000-candidate scale caches.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import csv
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

_TMP = tempfile.mkdtemp(prefix="coverage-report-test-")
os.environ["SCANNER_OFFER_ENRICHMENT"] = "OFF"
os.environ["SCANNER_SEARCH_CACHE_PATH"] = os.path.join(_TMP, "scanner-search-cache.json")
os.environ["COSTCO_CSV_PATH"] = os.path.join(_TMP, "costco-items.csv")
os.environ["COSTCO_CATALOG_DETAIL_PATH"] = os.path.join(_TMP, "costco-product-detail.json")
os.environ["COSTCO_INVOICE_PATH"] = os.path.join(_TMP, "costco-invoice-confirmed.json")
os.environ["COSTCO_AMAZON_MAPPING_PATH"] = os.path.join(_TMP, "costco-amazon-mapping.json")

import amazon_search  # noqa: E402
import costco_api_client  # noqa: E402
import costco_client  # noqa: E402
import coverage_report  # noqa: E402

CACHE_PATH = os.environ["SCANNER_SEARCH_CACHE_PATH"]
CSV_PATH = os.environ["COSTCO_CSV_PATH"]
LEDGER_PATH = os.environ["COSTCO_AMAZON_MAPPING_PATH"]


def _asin(i: int) -> str:
    return "B0%08d" % i


def _write_cache(products, source="brightdata", fetched_at="2026-08-17T06:59:33+00:00"):
    payload = {
        "schema_version": 1,
        "source": source,
        "fetched_at": fetched_at,
        "candidate_count": len(products),
        "products": products,
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _write_csv(rows):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["item_name", "costco_cost"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_ledger(mapping):
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f)


def _clear_stores():
    for path in (CSV_PATH, LEDGER_PATH,
                 os.environ["COSTCO_CATALOG_DETAIL_PATH"],
                 os.environ["COSTCO_INVOICE_PATH"]):
        if os.path.exists(path):
            os.remove(path)


def _product(i, name, price=None, upc=None):
    return {
        "asin": _asin(i),
        "name": name,
        "amazon_price": price,
        "product_url": "https://www.amazon.com/dp/%s" % _asin(i),
        "brand": "Kirkland Signature",
        "sales_volume": None,
        "monthly_sales_estimate": None,
        "monthly_sales_estimated": False,
        "rating": None,
        "reviews_count": None,
    }


def _representative_products(count=234):
    """Real cache shape: no upc/weight/sellers/fee fields anywhere."""
    names = [
        "Kirkland Signature K-Cups (120 ct)",
        "Kirkland Signature Organic Olive Oil (2 x 1 L)",
        "Kirkland Signature Paper Towels (12 rolls)",
        "Kirkland Signature Batteries AA (48 count)",
        "Kirkland Signature Trash Bags (200 ct)",
    ]
    return [_product(i, names[i % len(names)], 20.0 + (i % 40)) for i in range(count)]


class ReportMetricsTests(unittest.TestCase):
    def setUp(self):
        _clear_stores()

    def tearDown(self):
        _clear_stores()

    def test_empty_cache_report_has_zero_denominators(self):
        _write_cache([])
        report = coverage_report.analyze_candidates()
        t = report["totals"]
        self.assertEqual(t["total_candidates"], 0)
        self.assertEqual(t["eligible"], 0)
        self.assertEqual(t["match_coverage_percent"], 0.0)
        self.assertEqual(t["cogs_coverage_percent"], 0.0)
        self.assertEqual(t["economics_ready_percent"], 0.0)
        self.assertEqual(t["opportunity_complete_percent"], 0.0)

    def test_missing_cache_file_yields_empty_report(self):
        if os.path.exists(CACHE_PATH):
            os.remove(CACHE_PATH)
        report = coverage_report.analyze_candidates()
        self.assertEqual(report["totals"]["total_candidates"], 0)
        self.assertEqual(report["cache"]["candidates"], 0)

    def test_234_representative_fixture_buckets(self):
        _write_cache(_representative_products(234))
        # CSV rows WITHOUT count tokens (one-sided evidence): the K-Cups and
        # Batteries groups land in high_confidence via title identity; only
        # the ledger-confirmed ASIN is exact; the other three fixture names
        # have no local row at all (unmatched).
        _write_csv([
            {"item_name": "Kirkland Signature K-Cups 120", "costco_cost": 39.99},
            {"item_name": "Kirkland Signature Batteries AA 48", "costco_cost": 21.99},
        ])
        _write_ledger({_asin(0): "Kirkland Signature K-Cups 120"})
        report = coverage_report.analyze_candidates()
        t = report["totals"]
        self.assertEqual(t["total_candidates"], 234)
        self.assertEqual(t["eligible"], 234)
        self.assertEqual(t["exact"], 1)  # ledger-confirmed only
        self.assertGreaterEqual(t["high_confidence"], 47)  # one-sided batteries row
        self.assertEqual(report["ledger_hits"], 1)
        # Every bucket sums to 234.
        bucket_sum = sum(t[k] for k in ("exact", "invoice_confirmed", "high_confidence",
                                        "candidate", "mismatch", "unknown", "unmatched"))
        self.assertEqual(bucket_sum, 234)
        self.assertEqual(t["unmatched"], 140)
        # Percentage = count/denominator, visible.
        self.assertEqual(t["match_coverage_count"], t["exact"] + t["invoice_confirmed"] + t["high_confidence"])
        self.assertEqual(
            t["match_coverage_percent"],
            round(t["match_coverage_count"] / 234 * 100, 1),
        )

    def test_mismatch_rows_are_blocked_with_reasons(self):
        _write_cache([
            _product(0, "Kirkland Signature K-Cups (120 ct)", 48.87),
            _product(1, "Kirkland Signature Batteries AA (24 count)", 25.0),
        ])
        _write_csv([
            {"item_name": "Kirkland Signature K-Cups (120 ct)", "costco_cost": 39.99},
            {"item_name": "Kirkland Signature Batteries AA (48 count)", "costco_cost": 21.99},
        ])
        report = coverage_report.analyze_candidates()
        tasks = report["verification_task_counts"]
        self.assertIn("blocked_mismatch", tasks)
        self.assertIn("verify_fba_fee", tasks)
        readiness = report["opportunity_readiness_counts"]
        self.assertIn("blocked_mismatch", readiness)
        # The legacy diagnostic fallback still maps a count conflict to a
        # confirm-pack task when invoked directly.
        self.assertEqual(
            coverage_report._verification_task("mismatch", "Pack/count differs (Amazon 24 vs Costco 48)"),
            "confirm_pack",
        )
        self.assertEqual(
            coverage_report._verification_task("high_confidence", None),
            "confirm_variant",
        )

    def test_unknown_and_zero_never_invented(self):
        _write_cache([_product(0, "Some Random Product With No Match", 9.99)])
        report = coverage_report.analyze_candidates()
        t = report["totals"]
        self.assertEqual(t["exact"], 0)
        self.assertEqual(t["high_confidence"], 0)
        self.assertEqual(t["unmatched"], 1)
        self.assertEqual(t["costco_cogs_found"], 0)
        row = report["rows"][0]
        self.assertIsNone(row["costco_cost"])
        self.assertIsNone(row["costco_item_name"])
        self.assertEqual(row["costco_match_quality"], "unmatched")
        self.assertIn("costco_cost", row["missing_fields"])


class ReviewQueueCsvTests(unittest.TestCase):
    def setUp(self):
        _clear_stores()
        _write_cache(_representative_products(234))
        _write_csv([
            {"item_name": "Kirkland Signature K-Cups (120 ct)", "costco_cost": 39.99},
            {"item_name": "Kirkland Signature Organic Olive Oil (2 x 1 L)", "costco_cost": 14.99},
            {"item_name": "Kirkland Signature Paper Towels (12 rolls)", "costco_cost": 19.99},
            {"item_name": "Kirkland Signature Batteries AA (48 count)", "costco_cost": 21.99},
            {"item_name": "Kirkland Signature Trash Bags (200 ct)", "costco_cost": 24.99},
        ])
        _write_ledger({_asin(0): "Kirkland Signature K-Cups (120 ct)"})
        self.tmpdir = tempfile.mkdtemp(prefix="coverage-report-csv-")

    def tearDown(self):
        _clear_stores()

    def test_review_queue_has_exactly_24_spec_columns(self):
        out = os.path.join(self.tmpdir, "review.csv")
        report = coverage_report.analyze_candidates()
        coverage_report.export_review_queue(report, out)
        with open(out, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        self.assertEqual(tuple(header), coverage_report.REVIEW_QUEUE_COLUMNS)
        self.assertEqual(len(header), 24)
        for col in ("verification_task", "opportunity_readiness", "recommended_next_step",
                    "cache_source", "observed_at", "enriched_at", "missing_fields"):
            self.assertIn(col, header)

    def test_review_queue_rows_carry_provenance(self):
        out = os.path.join(self.tmpdir, "review.csv")
        report = coverage_report.analyze_candidates()
        coverage_report.export_review_queue(report, out)
        with open(out, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 234)
        self.assertEqual(rows[0]["cache_source"], "brightdata")
        self.assertEqual(rows[0]["asin"], _asin(0))

    def test_top_opportunities_only_non_mismatch_sorted_null_last(self):
        out = os.path.join(self.tmpdir, "review.csv")
        report = coverage_report.analyze_candidates()
        tops = report["top_opportunities"]
        self.assertTrue(all(r["costco_match_quality"] != "mismatch" for r in tops))
        scores = [r["score"] for r in tops]
        seen_none = False
        for s in scores:
            if s is None:
                seen_none = True
            else:
                self.assertFalse(seen_none)
        numeric = [s for s in scores if s is not None]
        self.assertEqual(numeric, sorted(numeric, reverse=True))
        coverage_report.export_top_opportunities(report, out)
        with open(out, "r", newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        self.assertEqual(header[0], "rank")

    def test_cli_writes_review_queue_and_top_file(self):
        out = os.path.join(self.tmpdir, "queue.csv")
        rc = coverage_report.main(["--csv", out])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))
        top_path = out.rsplit(".", 1)[0] + "-top-50.csv"
        self.assertTrue(os.path.exists(top_path))
        with open(top_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertLessEqual(len(rows), 50)

    def test_top_requires_csv(self):
        self.assertEqual(coverage_report.main(["--top", "10"]), 2)
        self.assertEqual(coverage_report.main(["--top", "0", "--csv", "x.csv"]), 2)


class ScaleTests(unittest.TestCase):
    """500 and 5,000-candidate caches complete within generous bounds;
    measured timings are printed, never asserted on."""

    def setUp(self):
        _clear_stores()

    def tearDown(self):
        _clear_stores()

    def _run_scale(self, count):
        _write_cache(_representative_products(count))
        _write_csv([
            {"item_name": "Kirkland Signature K-Cups (120 ct)", "costco_cost": 39.99},
            {"item_name": "Kirkland Signature Organic Olive Oil (2 x 1 L)", "costco_cost": 14.99},
        ])
        start = time.time()
        report = coverage_report.analyze_candidates()
        elapsed = time.time() - start
        print("coverage report scale %d: %.2fs" % (count, elapsed))
        self.assertEqual(report["totals"]["total_candidates"], count)
        self.assertEqual(report["totals"]["eligible"], count)

    def test_500_candidates_complete(self):
        self._run_scale(500)

    def test_5000_candidates_complete(self):
        self._run_scale(5000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
