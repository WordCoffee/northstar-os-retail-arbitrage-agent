"""Offline tests for the read-only cache inspector (inspect_cache.py).

Zero network, zero writes: the cache path is pointed at temp locations
BEFORE amazon_search imports. Covers missing/corrupt/valid states,
size + SHA-256 determinism, provenance fields, field coverage, freshness
labels, and 500/5,000-product scale.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="inspect-cache-test-")
import inspect_cache  # noqa: E402

# Module-private fixture path: never read from os.environ at import time.
# The env default (SCANNER_SEARCH_CACHE_PATH) belongs to other test
# modules, and the inspector reads it only via main([]) — patched per call.
CACHE_PATH = os.path.join(_TMP, "scanner-search-cache.json")


def _ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _write_cache(products, source="brightdata", fetched_at=None):
    payload = {
        "schema_version": 1,
        "source": source,
        "fetched_at": fetched_at or _ts(1),
        "candidate_count": len(products),
        "products": products,
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _product(i, price=None):
    return {
        "asin": "B0%08d" % i,
        "name": "Kirkland Signature Item %d" % i,
        "amazon_price": price,
        "product_url": "https://www.amazon.com/dp/B0%08d" % i,
        "brand": "Kirkland Signature",
        "sales_volume": None,
        "monthly_sales_estimate": None,
        "monthly_sales_estimated": False,
        "rating": None,
        "reviews_count": None,
    }


class InspectCacheTests(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(CACHE_PATH):
            os.remove(CACHE_PATH)

    def test_missing_file_reports_missing(self):
        report = inspect_cache.inspect_cache(CACHE_PATH)
        self.assertFalse(report["exists"])
        self.assertNotIn("parseable", report)

    def test_corrupt_json_reports_unparseable(self):
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            f.write("{not json")
        report = inspect_cache.inspect_cache(CACHE_PATH)
        self.assertTrue(report["exists"])
        self.assertFalse(report["parseable"])
        self.assertEqual(report["size_bytes"], os.path.getsize(CACHE_PATH))

    def test_valid_cache_provenance_and_coverage(self):
        products = [_product(i, 20.0 + i) for i in range(5)]
        _write_cache(products, source="brightdata", fetched_at="2026-08-17T06:59:33+00:00")
        report = inspect_cache.inspect_cache(CACHE_PATH)
        self.assertTrue(report["parseable"])
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["source"], "brightdata")
        self.assertEqual(report["fetched_at"], "2026-08-17T06:59:33+00:00")
        self.assertEqual(report["candidate_count"], 5)
        self.assertEqual(report["observed_count"], 5)
        self.assertEqual(report["size_bytes"], os.path.getsize(CACHE_PATH))
        self.assertIsNotNone(report["sha256"])
        self.assertEqual(len(report["sha256"]), 64)
        cov = report["coverage"]
        self.assertEqual(cov["total_products"], 5)
        self.assertEqual(cov["fields_present"]["asin"], 5)
        self.assertEqual(cov["fields_present"]["amazon_price"], 5)
        self.assertIn("upc", cov["fields_missing_everywhere"])
        self.assertIn("fba_fee", cov["fields_missing_everywhere"])

    def test_sha256_is_deterministic(self):
        _write_cache([_product(i) for i in range(3)])
        first = inspect_cache.inspect_cache(CACHE_PATH)["sha256"]
        second = inspect_cache.inspect_cache(CACHE_PATH)["sha256"]
        self.assertEqual(first, second)

    def test_freshness_labels(self):
        _write_cache([], fetched_at=_ts(1))
        self.assertEqual(inspect_cache.inspect_cache(CACHE_PATH)["freshness_label"], "Fresh (<7 days)")
        _write_cache([], fetched_at=_ts(14))
        self.assertEqual(inspect_cache.inspect_cache(CACHE_PATH)["freshness_label"], "Aging (8-30 days)")
        _write_cache([], fetched_at=_ts(45))
        self.assertEqual(inspect_cache.inspect_cache(CACHE_PATH)["freshness_label"], "Stale (>30 days)")
        _write_cache([], fetched_at="not-a-date")
        self.assertEqual(inspect_cache.inspect_cache(CACHE_PATH)["freshness_label"], "Unknown timestamp")

    def test_declared_count_mismatch_is_reported_honestly(self):
        products = [_product(i) for i in range(3)]
        payload = {
            "schema_version": 1,
            "source": "brightdata",
            "fetched_at": _ts(1),
            "candidate_count": 99,
            "products": products,
        }
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        report = inspect_cache.inspect_cache(CACHE_PATH)
        self.assertEqual(report["candidate_count"], 99)
        self.assertEqual(report["observed_count"], 3)

    def test_scale_500_and_5000(self):
        for count in (500, 5000):
            _write_cache([_product(i) for i in range(count)])
            start = time.time()
            report = inspect_cache.inspect_cache(CACHE_PATH)
            elapsed = time.time() - start
            print("inspect scale %d: %.2fs" % (count, elapsed))
            self.assertEqual(report["observed_count"], count)
            self.assertEqual(report["coverage"]["total_products"], count)
            self.assertEqual(report["coverage"]["fields_present"]["name"], count)

    def test_inspector_never_writes(self):
        before = set(os.listdir(_TMP))
        _write_cache([_product(i) for i in range(3)])
        inspect_cache.inspect_cache(CACHE_PATH)
        after = set(os.listdir(_TMP))
        self.assertEqual(before | {os.path.basename(CACHE_PATH)}, after)

    def test_cli_exit_zero(self):
        _write_cache([_product(0)])
        with mock.patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": CACHE_PATH}, clear=False):
            self.assertEqual(inspect_cache.main(["--path", CACHE_PATH]), 0)
            self.assertEqual(inspect_cache.main([]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
