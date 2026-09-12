"""Offline tests for the manual import workflow (manual_import.py).

Proves the offline manual import writes the existing candidate cache
(data/scanner-search-cache.json via amazon_search._cache_path() and
save_cached_candidates()), that the imported cache runs through the
cache-only scanner (SCANNER_OFFER_ENRICHMENT=OFF) with zero HTTP and
zero provider calls, that imported market data drives the existing
fee-engine economics honestly (never 0, never fabricated), that cache
protections hold (no overwrite without --replace, --dry-run never
writes, write failure preserves the prior cache), and that 500+
candidates / 5,000+ nested offers import and scan within generous
bounds. Measured timings are printed — no unmeasured claims.

Never touches the network (test_network_guard blocks all real requests),
never runs test_scavio.py, and never reads or writes real data files:
the cache path and Costco inputs are pointed at temp/mocked locations.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import requests

# Pin the cache-only mode and a temp cache BEFORE importing the backend
# modules that read these settings at call time. setdefault (never clobber):
# other test modules may already have pinned hermetic temp paths at their
# own import (e.g. test_coverage_report), and every test here forces the
# mode/cache per call anyway — unconditional writes made the whole suite
# order-dependent.
_TMP = tempfile.mkdtemp(prefix="manual-import-test-")
os.environ.setdefault("SCANNER_OFFER_ENRICHMENT", "OFF")
os.environ.setdefault("SCANNER_SEARCH_CACHE_PATH", os.path.join(_TMP, "scanner-search-cache.json"))

import amazon_search  # noqa: E402
import costco_api_client  # noqa: E402
import costco_client  # noqa: E402
import main  # noqa: E402
import manual_import  # noqa: E402
import offer_enrichment  # noqa: E402
import product_analysis  # noqa: E402


FAKE_DISCOVERY = {
    "run_report_exists": True,
    "archive_record_count": 24,
    "threshold_days": 8,
    "location": {"delivery_zip": "75201", "business_center": "Dallas Business Center"},
    "freshness": "fresh",
    "last_run_at": "2026-08-16T03:00:00+00:00",
    "last_fetched_at": "2026-08-16T03:00:00+00:00",
    "status": "ok",
    "stop_reason": None,
    "last_fetched_count": 24,
}


def fake_costco(costco_cost=15.99, weight_lbs=None, match_quality="exact"):
    row = {
        "costco_cost": costco_cost,
        "costco_cost_basis": "estimated",
        "match_quality": match_quality,
        "match_reason": None,
        "source": "csv",
    }
    if weight_lbs is not None:
        row["weight_lbs"] = weight_lbs
    return row


def fake_economics(net=None, roi=None, confidence="provisional", status="needs_fee_verification"):
    return {
        "net_profit": net,
        "roi_pct": roi,
        "economics_confidence": confidence,
        "economics_status": status,
        "economics_note": "test economics",
    }


def fake_profile(status="need_cost_data", profit=None, roi=None, gaps=()):
    return {
        "amazon_sale_price": None,
        "referral_fee": None,
        "fba_fulfillment_fee": None,
        "amazon_fees_total": None,
        "amazon_payout_before_inventory_costs": None,
        "cogs": None,
        "prep_cost": None,
        "inbound_shipping_cost": None,
        "landed_cost": None,
        "projected_net_profit": profit,
        "projected_roi_pct": roi,
        "financial_status": status,
        "financial_data_gaps": list(gaps),
    }


def _provider_called(*args, **kwargs):
    raise AssertionError("provider/HTTP call made in cache-only mode")


def write_cache(path, products, fetched_at="2026-08-15T12:00:00+00:00", source="brightdata", terms=("kirkland",)):
    payload = {
        "schema_version": 1,
        "fetched_at": fetched_at,
        "source": source,
        "search_terms": list(terms),
        "candidate_count": len(products),
        "products": products,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return payload


def json_candidate(asin, title="Kirkland Signature Fictional Item 3 lb", **extra):
    row = {"asin": asin, "title": title}
    row.update(extra)
    return row


def write_import_json(path, candidates, source="manual_import"):
    payload = {"source": source, "candidates": candidates}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


class ManualImportTests(unittest.TestCase):
    cache_path = os.path.join(_TMP, "scanner-search-cache.json")

    def _fresh_cache_path(self):
        """Per-test cache path so tests never share state."""
        return os.path.join(_TMP, "cache-%d.json" % id(self))

    def _route_patches(self):
        return [
            patch.object(product_analysis, "search_kirkland_products", side_effect=_provider_called),
            patch.object(requests.api, "get", side_effect=_provider_called),
            patch.object(requests.api, "post", side_effect=_provider_called),
            patch.object(offer_enrichment, "get_scanner_offer", side_effect=_provider_called),
            patch.object(product_analysis, "get_costco_price", return_value=fake_costco()),
            patch.object(
                product_analysis,
                "calculate_unit_economics",
                side_effect=lambda product, costco: fake_economics(),
            ),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(costco_client, "catalog_state", return_value="ready"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]

    def _get(self, patches):
        """Run the cache-only scanner with all provider/HTTP routes patched.

        SCANNER_OFFER_ENRICHMENT is forced to OFF at call time: other test
        modules (e.g. test_scanner_endpoint) overwrite the env var at their
        import, so the module-level setting cannot be trusted in a full
        discovery run.
        """
        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                with patch.dict(
                    os.environ, {"SCANNER_OFFER_ENRICHMENT": "OFF"}, clear=False
                ):
                    return main.get_kirkland_scanner()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

    def _run(self, path, source_label="manual_import", dry_run=False, replace=False,
             cache_path=None, costco_prices=None):
        """Run an import against a dedicated cache path for this test.

        The Costco resolver and catalog state are stubbed during the import
        so the match_ready report count is hermetic (read-only, zero
        network, zero real data files).
        """
        if cache_path is None:
            cache_path = self._fresh_cache_path()
        if costco_prices is None:
            costco_prices = {}
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False), \
                patch.object(costco_client, "catalog_state", return_value="ready"), \
                patch.object(
                    product_analysis, "get_costco_price",
                    side_effect=lambda name: (
                        costco_prices[name] if name in costco_prices else fake_costco()
                    ),
                ):
            return manual_import.run_import(
                path, source_label=source_label, dry_run=dry_run, replace=replace
            )

    # --- 1/2. JSON and CSV imports write a cache readable by cache-only mode ---

    def test_json_import_writes_cache_readable_by_cache_only_scanner(self):
        path = write_import_json(
            os.path.join(_TMP, "json-import.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99, buy_box_price=24.99,
                            total_sellers=4, fba_seller_count=2,
                            estimated_monthly_sales=600, fba_fee=7.25,
                            observed_at="2026-08-10T12:00:00Z")],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["accepted"], 1)

        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["source"], "manual_import")
        self.assertEqual(payload["search_terms"], ["manual_import"])
        self.assertEqual(payload["candidate_count"], 1)
        product = payload["products"][0]
        self.assertEqual(product["asin"], "B0FICT0001")
        self.assertEqual(product["amazon_price"], 24.99)
        self.assertIsNotNone(product["imported_at"])
        self.assertEqual(product["observed_at"], "2026-08-10T12:00:00+00:00")
        self.assertIs(product["live_observed"], True)

        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._route_patches())
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")
        self.assertEqual(body["summary"]["cache_source"], "manual_import")
        self.assertEqual(body["summary"]["candidates_returned"], 1)
        self.assertEqual(body["products"][0]["asin"], "B0FICT0001")

    def test_csv_import_writes_cache_readable_by_cache_only_scanner(self):
        path = os.path.join(_TMP, "csv-import.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(
                "asin,title,amazon_url,amazon_price,buy_box_price,total_sellers,"
                "fba_seller_count,estimated_monthly_sales,monthly_sales_estimated,"
                "fba_fee,weight_lbs,observed_at\n"
                "B0FICT0011,Kirkland Signature Mixed Nuts 40 oz,"
                "https://www.amazon.com/dp/B0FICT0011,27.99,27.99,5,3,500,true,8.10,2.5,"
                "2026-08-12T09:00:00Z\n"
            )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["accepted"], 1)

        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
            body = self._get(self._route_patches())
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["products"][0]["name"], "Kirkland Signature Mixed Nuts 40 oz")
        self.assertEqual(payload["products"][0]["total_sellers"], 5)
        self.assertEqual(payload["products"][0]["fba_sellers"], 3)
        self.assertEqual(payload["products"][0]["fba_fee"], 8.10)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["summary"]["cache_source"], "manual_import")

    # --- 3/4. Integration + zero HTTP/provider/fallback calls ---

    def test_imported_cache_integrates_with_scanner_imported_fields_usable(self):
        path = write_import_json(
            os.path.join(_TMP, "integration.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99, buy_box_price=24.99,
                            amazon_shipping=4.99, buy_box_shipping=0.0,
                            total_sellers=4, fba_seller_count=2, fbm_seller_count=1,
                            buy_box_seller_name="Example Seller A",
                            buy_box_fulfillment="FBA",
                            estimated_monthly_sales=600, fba_fee=7.25,
                            amazon_category="Grocery & Gourmet Food",
                            browse_node_id=16310101,
                            observed_at="2026-08-10T12:00:00Z",
                            offers=[{"seller_name": "Example Seller A", "fulfillment": "FBA",
                                     "item_price": 24.99, "is_buy_box_winner": True}])],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)

        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        cached = payload["products"][0]
        # Shipping / FBM count / Buy Box seller / fulfillment / offers are
        # preserved in the cache (no UI or response-contract expansion).
        self.assertEqual(cached["amazon_shipping"], 4.99)
        self.assertEqual(cached["buy_box_shipping"], 0.0)
        self.assertEqual(cached["fbm_sellers"], 1)
        self.assertEqual(cached["buy_box_seller_name"], "Example Seller A")
        self.assertEqual(cached["buy_box_fulfillment"], "FBA")
        self.assertEqual(cached["offers"][0]["seller_name"], "Example Seller A")

        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._route_patches())
        product = body["products"][0]
        self.assertEqual(product["asin"], "B0FICT0001")
        self.assertEqual(product["amazon_price"], 24.99)
        self.assertEqual(product["total_sellers"], 4)
        self.assertEqual(product["fba_sellers"], 2)
        self.assertEqual(product["monthly_sales_estimate"], 600.0)
        self.assertIs(product["monthly_sales_estimated"], True)
        self.assertEqual(product["fba_fee"], 7.25)
        self.assertEqual(product["offer_data_provider"], "manual_import")
        self.assertEqual(product["enrichment_status"], "offline")
        self.assertEqual(product["enriched_at"], "2026-08-10T12:00:00+00:00")
        self.assertEqual(body["summary"]["cache_source"], "manual_import")
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")

    def test_scanner_cache_only_zero_http_zero_provider_zero_fallback(self):
        path = write_import_json(
            os.path.join(_TMP, "zero-calls.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._route_patches())
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["summary"]["enrichment_source"], "OFF")
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")

    # --- 5-8. Validation rejections ---

    def test_invalid_asin_rejected(self):
        path = write_import_json(
            os.path.join(_TMP, "bad-asin.json"),
            [
                json_candidate("NOTANASIN", amazon_price=10.0),
                json_candidate(1234567890, amazon_price=10.0),
                json_candidate("B0FICT0001", amazon_price=10.0),
            ],
        )
        report = self._run(path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["rejected"], 2)
        self.assertEqual(report["counts"]["accepted"], 1)
        reasons = " | ".join(r["reason"] for r in report["rejected_rows"])
        self.assertIn("invalid ASIN", reasons)

    def test_invalid_negative_and_malformed_numbers_rejected(self):
        cases = [
            {"amazon_price": -5.0},
            {"amazon_price": "abc"},
            {"amazon_price": float("nan")},
            {"amazon_price": float("inf")},
            {"total_sellers": -1},
            {"total_sellers": 2.5},
            {"fba_fee": -0.01},
            {"weight_lbs": "heavy"},
            {"amazon_price": True},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                path = write_import_json(
                    os.path.join(_TMP, "bad-number.json"),
                    [json_candidate("B0FICT0001", **extra)],
                )
                report = self._run(path)
                self.assertEqual(report["status"], "no_valid_candidates")
                self.assertEqual(report["counts"]["accepted"], 0)
                self.assertEqual(report["counts"]["rejected"], 1)
                self.assertIn("invalid", report["rejected_rows"][0]["reason"])

    def test_invalid_fulfillment_rejected(self):
        path = write_import_json(
            os.path.join(_TMP, "bad-fulfillment.json"),
            [
                json_candidate("B0FICT0001", buy_box_fulfillment="UPS"),
                json_candidate("B0FICT0002", buy_box_fulfillment="FBA"),
                json_candidate("B0FICT0003", buy_box_fulfillment="unknown"),
            ],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["rejected"], 1)
        self.assertEqual(report["counts"]["accepted"], 2)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["products"][0]["buy_box_fulfillment"], "FBA")
        self.assertIsNone(payload["products"][1]["buy_box_fulfillment"])

    def test_invalid_timestamp_rejected(self):
        path = write_import_json(
            os.path.join(_TMP, "bad-date.json"),
            [
                json_candidate("B0FICT0001", observed_at="2026-13-45T99:99:00Z"),
                json_candidate("B0FICT0002", observed_at="yesterday"),
                json_candidate("B0FICT0003", observed_at="2026-08-10T12:00:00Z"),
            ],
        )
        report = self._run(path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["rejected"], 2)
        self.assertEqual(report["counts"]["accepted"], 1)

    # --- 9. Duplicate ASIN resolution (deterministic) ---

    def test_duplicate_asin_newest_observed_at_wins(self):
        path = write_import_json(
            os.path.join(_TMP, "dupe-newest.json"),
            [
                json_candidate("B0FICT0001", amazon_price=10.0, observed_at="2026-08-10T12:00:00Z"),
                json_candidate("B0FICT0001", amazon_price=20.0, observed_at="2026-08-12T12:00:00Z"),
                json_candidate("B0FICT0001", amazon_price=30.0, observed_at="2026-08-11T12:00:00Z"),
            ],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["counts"]["accepted"], 1)
        self.assertEqual(report["counts"]["duplicated"], 2)
        self.assertEqual(report["counts"]["input_rows"], 3)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            product = amazon_search._read_cache_file()["products"][0]
        self.assertEqual(product["amazon_price"], 20.0)

    def test_duplicate_asin_ties_and_missing_observed_at_last_row_wins(self):
        path = write_import_json(
            os.path.join(_TMP, "dupe-tie.json"),
            [
                # Both missing observed_at: last valid row wins.
                json_candidate("B0FICT0001", amazon_price=10.0),
                json_candidate("B0FICT0001", amazon_price=11.0),
                # Equal observed_at: last row wins.
                json_candidate("B0FICT0002", amazon_price=20.0, observed_at="2026-08-12T12:00:00Z"),
                json_candidate("B0FICT0002", amazon_price=21.0, observed_at="2026-08-12T12:00:00Z"),
                # Missing observed_at never beats an existing observed_at.
                json_candidate("B0FICT0003", amazon_price=30.0, observed_at="2026-08-12T12:00:00Z"),
                json_candidate("B0FICT0003", amazon_price=31.0),
            ],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["counts"]["accepted"], 3)
        self.assertEqual(report["counts"]["duplicated"], 3)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            products = {p["asin"]: p for p in amazon_search._read_cache_file()["products"]}
        self.assertEqual(products["B0FICT0001"]["amazon_price"], 11.0)
        self.assertEqual(products["B0FICT0002"]["amazon_price"], 21.0)
        self.assertEqual(products["B0FICT0003"]["amazon_price"], 30.0)

    def test_duplicate_asin_naive_and_offset_timestamps_compare_in_utc(self):
        path = write_import_json(
            os.path.join(_TMP, "dupe-tz.json"),
            [
                json_candidate("B0FICT0001", amazon_price=10.0, observed_at="2026-08-12T10:00:00-05:00"),
                json_candidate("B0FICT0001", amazon_price=20.0, observed_at="2026-08-12T14:00:00Z"),
            ],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["counts"]["duplicated"], 1)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            product = amazon_search._read_cache_file()["products"][0]
        # 10:00-05:00 == 15:00Z, which is NEWER than 14:00Z: the offset row
        # wins once both are compared in UTC.
        self.assertEqual(product["amazon_price"], 10.0)
        self.assertEqual(product["observed_at"], "2026-08-12T15:00:00+00:00")

    # --- 10-12. Cache protections ---

    def test_fully_invalid_import_preserves_existing_valid_cache(self):
        existing = [{"name": "Old Alpha", "asin": "B000000001", "product_url": "u1", "amazon_price": 40.0}]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        path = write_import_json(
            os.path.join(_TMP, "all-invalid.json"),
            [json_candidate("BADASIN1", amazon_price=10.0), json_candidate("BADASIN2", amazon_price=10.0)],
        )
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "no_valid_candidates")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["fetched_at"], "2026-08-15T12:00:00+00:00")
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["source"], "brightdata")

    def test_empty_import_preserves_existing_valid_cache(self):
        existing = [{"name": "Old Alpha", "asin": "B000000001", "product_url": "u1", "amazon_price": 40.0}]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        path = write_import_json(os.path.join(_TMP, "empty.json"), [])
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "no_valid_candidates")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["source"], "brightdata")

    def test_empty_json_file_preserves_cache_and_exits_nonzero(self):
        existing = [{"name": "Old Alpha", "asin": "B000000001", "product_url": "u1", "amazon_price": 40.0}]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        empty_path = os.path.join(_TMP, "empty-file.json")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            code = manual_import.main(["--input", empty_path])
        self.assertEqual(code, 2)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["candidate_count"], 1)

    def test_atomic_write_failure_preserves_existing_valid_cache(self):
        """A swallowed atomic-write error (save_cached_candidates never
        raises) must be detected by the post-write verification and the
        existing cache must remain in place."""
        existing = [{"name": "Old Alpha", "asin": "B000000001", "product_url": "u1", "amazon_price": 40.0}]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        path = write_import_json(
            os.path.join(_TMP, "good-import.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        with patch.object(
            amazon_search, "save_cached_candidates",
            side_effect=lambda products, search_terms=None, source=None: None,
        ):
            # The existing cache is valid, so --replace is required to even
            # attempt the write; the no-op writer then fails verification.
            report = self._run(path, cache_path=cache_path, replace=True)
        self.assertEqual(report["status"], "write_failed")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["source"], "brightdata")
        self.assertEqual(payload["fetched_at"], "2026-08-15T12:00:00+00:00")

    # --- 13. Economics stay honest: Unknown, never 0 ---

    def _real_economics_patches(self, costco_by_name):
        return [
            patch.object(product_analysis, "search_kirkland_products", side_effect=_provider_called),
            patch.object(requests.api, "get", side_effect=_provider_called),
            patch.object(requests.api, "post", side_effect=_provider_called),
            patch.object(product_analysis, "get_costco_price", side_effect=lambda name, **kwargs: costco_by_name.get(name)),
            patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0),
            patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0),
            patch.object(product_analysis, "estimate_financial_profile", return_value=fake_profile()),
            patch.object(costco_client, "catalog_state", return_value="ready"),
            patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY),
        ]

    def test_missing_price_cost_fee_keep_economics_unknown_or_honest(self):
        """Real fee engine: missing price/Costco cost => net/ROI None;
        missing FBA fee => existing provisional behavior (fee excluded,
        never 0); imported fba_fee => estimated economics."""
        costco_by_name = {
            "Kirkland Signature Priced 3 lb": fake_costco(costco_cost=15.99, weight_lbs=3.5),
            "Kirkland Signature Priced NoFee 3 lb": fake_costco(costco_cost=15.99),
            "Kirkland Signature NoCost 3 lb": {"match_quality": "unknown"},
        }
        path = write_import_json(
            os.path.join(_TMP, "economics.json"),
            [
                json_candidate("B0FICT0001", title="Kirkland Signature Priced 3 lb",
                               amazon_price=39.99, fba_fee=7.25),
                json_candidate("B0FICT0002", title="Kirkland Signature Priced NoFee 3 lb",
                               amazon_price=39.99),
                json_candidate("B0FICT0003", title="Kirkland Signature NoCost 3 lb",
                               amazon_price=39.99),
                json_candidate("B0FICT0004", title="Kirkland Signature Priced 3 lb",
                               fba_fee=7.25),
            ],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._real_economics_patches(costco_by_name))
        by_asin = {p["asin"]: p for p in body["products"]}

        estimated = by_asin["B0FICT0001"]
        self.assertEqual(estimated["economics_confidence"], "estimated")
        self.assertIsNotNone(estimated["net_profit"])
        self.assertIsNotNone(estimated["roi_pct"])
        self.assertEqual(estimated["fba_fee"], 7.25)

        provisional = by_asin["B0FICT0002"]
        self.assertEqual(provisional["economics_confidence"], "provisional")
        self.assertEqual(provisional["economics_status"], "needs_fee_verification")
        self.assertIsNone(provisional["fba_fee"])
        self.assertEqual(provisional["verdict"], "Needs Fee Verification")
        self.assertIsNotNone(provisional["net_profit"])  # price+COGS, fee excluded
        self.assertIn("fee", (provisional["economics_note"] or "").lower())

        no_cost = by_asin["B0FICT0003"]
        self.assertEqual(no_cost["economics_confidence"], "unavailable")
        self.assertEqual(no_cost["economics_status"], "missing_costco_cogs")
        self.assertIsNone(no_cost["net_profit"])
        self.assertIsNone(no_cost["roi_pct"])
        self.assertIsNone(no_cost["fba_fee"])

        no_price = by_asin["B0FICT0004"]
        self.assertEqual(no_price["economics_confidence"], "unavailable")
        self.assertEqual(no_price["economics_status"], "missing_amazon_price")
        self.assertIsNone(no_price["net_profit"])
        self.assertIsNone(no_price["roi_pct"])
        # The imported FBA fee is still preserved on the row (never 0, and
        # never dropped just because the price is missing).
        self.assertEqual(no_price["fba_fee"], 7.25)

    def test_shipping_is_preserved_but_never_used_in_economics(self):
        """Imported shipping must not alter unit economics."""
        costco_by_name = {"Kirkland Signature Fictional Item 3 lb": fake_costco(costco_cost=15.99)}
        base = json_candidate("B0FICT0001", amazon_price=39.99, fba_fee=7.25)
        with_ship = dict(base)
        with_ship["amazon_shipping"] = 4.99
        with_ship["buy_box_shipping"] = 0.0
        path = write_import_json(
            os.path.join(_TMP, "shipping.json"),
            [base, with_ship],
        )
        # Different ASINs so both rows survive, same price/fee/cost inputs.
        base["asin"] = "B0FICT0001"
        with_ship["asin"] = "B0FICT0002"
        path = write_import_json(
            os.path.join(_TMP, "shipping.json"),
            [base, with_ship],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._real_economics_patches(costco_by_name))
        by_asin = {p["asin"]: p for p in body["products"]}
        self.assertEqual(by_asin["B0FICT0001"]["net_profit"], by_asin["B0FICT0002"]["net_profit"])
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        by_asin_cached = {p["asin"]: p for p in payload["products"]}
        self.assertEqual(by_asin_cached["B0FICT0002"]["amazon_shipping"], 4.99)
        self.assertEqual(by_asin_cached["B0FICT0002"]["buy_box_shipping"], 0.0)

        # --- 14-16. Provenance: never presented as live / provider data ---

    def test_source_provenance_and_timestamp_in_scanner_output(self):
        path = write_import_json(
            os.path.join(_TMP, "provenance.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99,
                            observed_at="2026-08-10T12:00:00Z")],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "ok")
        self.assertIn("+", report["fetched_at"])  # UTC ISO with offset
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._route_patches())
        product = body["products"][0]
        self.assertEqual(product["offer_data_provider"], "manual_import")
        self.assertEqual(product["enrichment_status"], "offline")
        self.assertEqual(product["enriched_at"], "2026-08-10T12:00:00+00:00")

    def test_provider_rows_without_imported_at_keep_offline_behavior(self):
        """Cache rows generated by a provider (no imported_at) must NOT get
        the manual-import overlay: bare offline placeholder behavior."""
        existing = [{
            "name": "Kirkland Signature Provider Row 3 lb",
            "asin": "B0FICT0001",
            "product_url": "https://www.amazon.com/dp/B0FICT0001",
            "amazon_price": 24.99,
            "total_sellers": 4,
            "fba_sellers": 2,
            "fba_fee": 7.25,
        }]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(self._route_patches())
        product = body["products"][0]
        self.assertEqual(product["offer_data_provider"], "offline")
        self.assertEqual(product["enrichment_status"], "offline")
        self.assertIsNone(product["enriched_at"])
        self.assertIsNone(product["total_sellers"])
        self.assertIsNone(product["fba_sellers"])
        self.assertIsNone(product["fba_fee"])

    def test_explicit_source_label_provenance(self):
        path = write_import_json(
            os.path.join(_TMP, "explicit-source.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, source_label="my_label", cache_path=cache_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["source"], "my_label")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
            body = self._get(self._route_patches())
        self.assertEqual(payload["source"], "my_label")
        self.assertEqual(body["summary"]["cache_source"], "my_label")
        self.assertEqual(body["products"][0]["offer_data_provider"], "my_label")

    def test_live_observed_flag(self):
        path = write_import_json(
            os.path.join(_TMP, "live-observed.json"),
            [
                json_candidate("B0FICT0001", amazon_price=10.0,
                               observed_at="2026-08-10T12:00:00Z"),
                json_candidate("B0FICT0002", amazon_price=10.0),
            ],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            products = {p["asin"]: p for p in amazon_search._read_cache_file()["products"]}
        self.assertIs(products["B0FICT0001"]["live_observed"], True)
        self.assertIs(products["B0FICT0002"]["live_observed"], False)
        self.assertIsNone(products["B0FICT0002"]["observed_at"])

    def test_monthly_sales_value_defaults_flag_true(self):
        path = write_import_json(
            os.path.join(_TMP, "sales-flag.json"),
            [json_candidate("B0FICT0001", estimated_monthly_sales=450)],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            product = amazon_search._read_cache_file()["products"][0]
        self.assertEqual(product["monthly_sales_estimate"], 450.0)
        self.assertIs(product["monthly_sales_estimated"], True)

    def test_high_confidence_manual_import_verify_note(self):
        """High-confidence manual-import rows keep their economics and get
        the explicit import-verification warning appended to the note."""
        path = write_import_json(
            os.path.join(_TMP, "verify-note.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        cache_path = self._fresh_cache_path()
        self._run(path, cache_path=cache_path)
        patches = self._route_patches()
        patches[4] = patch.object(
            product_analysis, "get_costco_price",
            return_value=fake_costco(costco_cost=15.99, match_quality="high_confidence"),
        )
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            body = self._get(patches)
        product = body["products"][0]
        note = product["economics_note"] or ""
        self.assertIn("test economics", note)
        self.assertIn("Verify UPC, pack size, and variant before buying.", note)
        self.assertEqual(product["pack_match"], "high_confidence")

    # --- 17-19. Cache protection: --replace, --dry-run, malformed files ---

    def test_default_refuses_overwrite_without_replace_and_replace_overwrites(self):
        existing = [{"name": "Old Alpha", "asin": "B000000001", "product_url": "u1", "amazon_price": 40.0}]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        path = write_import_json(
            os.path.join(_TMP, "replace.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        report = self._run(path, cache_path=cache_path)
        self.assertEqual(report["status"], "cache_exists_requires_replace")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["source"], "brightdata")
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["fetched_at"], "2026-08-15T12:00:00+00:00")

        report = self._run(path, cache_path=cache_path, replace=True)
        self.assertEqual(report["status"], "ok")
        self.assertIs(report["replaced"], True)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["source"], "manual_import")
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["products"][0]["asin"], "B0FICT0001")

    def test_dry_run_never_writes(self):
        path = write_import_json(
            os.path.join(_TMP, "dry-run.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        cache_path = self._fresh_cache_path()
        report = self._run(path, cache_path=cache_path, dry_run=True)
        self.assertEqual(report["status"], "dry_run")
        self.assertFalse(os.path.exists(cache_path))

        write_cache(cache_path, [{"name": "Old", "asin": "B000000001", "product_url": "u1"}])
        report = self._run(path, cache_path=cache_path, dry_run=True)
        self.assertEqual(report["status"], "dry_run")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["source"], "brightdata")

    def test_malformed_json_preserves_cache_and_exits_2(self):
        existing = [{"name": "Old Alpha", "asin": "B000000001", "product_url": "u1", "amazon_price": 40.0}]
        cache_path = self._fresh_cache_path()
        write_cache(cache_path, existing)
        bad_path = os.path.join(_TMP, "malformed.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write('{"candidates": [{"asin": "B0FICT0001"')
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            with self.assertRaises(ValueError):
                manual_import.run_import(bad_path)
            code = manual_import.main(["--input", bad_path])
        self.assertEqual(code, 2)
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            payload = amazon_search._read_cache_file()
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["source"], "brightdata")

    def test_cli_exit_codes_and_report_file(self):
        path = write_import_json(
            os.path.join(_TMP, "cli-good.json"),
            [json_candidate("B0FICT0001", amazon_price=24.99)],
        )
        report_path = os.path.join(_TMP, "cli-report.json")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": self._fresh_cache_path()}, clear=False):
            code = manual_import.main(["--input", path, "--report", report_path])
        self.assertEqual(code, 0)
        with open(report_path, encoding="utf-8") as f:
            written = json.load(f)
        self.assertEqual(written["status"], "ok")
        self.assertEqual(written["counts"]["accepted"], 1)

        bad_path = os.path.join(_TMP, "cli-bad.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("")
        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": self._fresh_cache_path()}, clear=False):
            code = manual_import.main(["--input", bad_path])
        self.assertEqual(code, 2)

    # --- 20-21. Report counts are complete and honest ---

    def test_report_counts_are_complete(self):
        path = write_import_json(
            os.path.join(_TMP, "counts.json"),
            [
                json_candidate("B0FICT0001", amazon_price=10.0),
                json_candidate("B0FICT0002", amazon_price=10.0),
                json_candidate("B0FICT0003", amazon_price=10.0),
                json_candidate("B0FICT0004", amazon_price=10.0),
                json_candidate("B0FICT0005", amazon_price=10.0),
                json_candidate("B0FICT0001", amazon_price=11.0),
                json_candidate("B0FICT0002", amazon_price=12.0),
                json_candidate("NOTANASIN", amazon_price=10.0),
            ],
        )
        report = self._run(path)
        counts = report["counts"]
        self.assertEqual(report["status"], "ok")
        self.assertEqual(counts["input_rows"], 8)
        self.assertEqual(counts["accepted"], 5)
        self.assertEqual(counts["duplicated"], 2)
        self.assertEqual(counts["rejected"], 1)
        self.assertEqual(
            counts["input_rows"],
            counts["accepted"] + counts["duplicated"] + counts["rejected"],
        )
        self.assertEqual(len(report["rejected_rows"]), 1)
        self.assertEqual(report["rejected_rows"][0]["asin"], "NOTANASIN")

    def test_missing_market_data_and_match_ready_counts(self):
        prices = {
            "Kirkland Exact 3 lb": fake_costco(costco_cost=15.99, match_quality="exact"),
            "Kirkland High 3 lb": fake_costco(costco_cost=15.99, match_quality="high_confidence"),
            "Kirkland Unknown 3 lb": {"match_quality": "unknown"},
        }
        path = write_import_json(
            os.path.join(_TMP, "match-ready.json"),
            [
                json_candidate("B0FICT0001", title="Kirkland Exact 3 lb", amazon_price=24.99),
                json_candidate("B0FICT0002", title="Kirkland High 3 lb", buy_box_price=24.99),
                json_candidate("B0FICT0003", title="Kirkland Exact 3 lb"),  # no market data
                json_candidate("B0FICT0004", title="Kirkland Unknown 3 lb", amazon_price=24.99),
            ],
        )
        report = self._run(path, costco_prices=prices)
        counts = report["counts"]
        self.assertEqual(counts["accepted"], 4)
        self.assertEqual(counts["missing_market_data"], 1)
        self.assertEqual(counts["match_ready"], 2)

    # --- 22. Scale: 500 candidates, 5,000 nested offers (measured) ---

    def test_scale_500_candidates_5000_offers_performance(self):
        candidates = []
        for i in range(500):
            offers = [
                {
                    "seller_name": "Example Seller %d" % j,
                    "seller_id": "SELLER%05d" % j,
                    "fulfillment": "FBA" if j % 2 == 0 else "FBM",
                    "item_price": 19.99 + j * 0.01,
                    "shipping_price": 0.0 if j % 2 == 0 else 4.99,
                    "landed_price": 19.99 + j * 0.01,
                    "condition": "New",
                    "is_buy_box_winner": j == 0,
                    "is_prime": j % 2 == 0,
                    "seller_rating": 4.5,
                    "rating_count": 1000 + j,
                    "observed_at": "2026-08-10T12:00:00Z",
                    "source": "manual_import",
                }
                for j in range(10)
            ]
            candidates.append(json_candidate(
                "B0FICT%04d" % (1000 + i),
                title="Kirkland Signature Scale Item %d 3 lb" % i,
                amazon_price=round(24.99 + i * 0.01, 2),
                fba_fee=7.25,
                estimated_monthly_sales=300 + i,
                offers=offers,
            ))
        path = os.path.join(_TMP, "scale-import.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"candidates": candidates}, f)
        cache_path = self._fresh_cache_path()

        t0 = time.perf_counter()
        report = self._run(path, cache_path=cache_path)
        import_elapsed = time.perf_counter() - t0
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["accepted"], 500)
        self.assertEqual(report["counts"]["offers_accepted"], 5000)
        self.assertEqual(report["counts"]["rejected"], 0)
        self.assertEqual(report["counts"]["duplicated"], 0)

        with patch.dict(os.environ, {"SCANNER_SEARCH_CACHE_PATH": cache_path}, clear=False):
            t0 = time.perf_counter()
            body = self._get(self._route_patches())
            scan_elapsed = time.perf_counter() - t0
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["summary"]["candidates_returned"], 500)

        print("\nscale: import of 500 candidates / 5,000 offers took %.2fs; "
              "cache-only scan took %.2fs" % (import_elapsed, scan_elapsed))
        self.assertLess(import_elapsed, 60.0, "import took %.2fs" % import_elapsed)
        self.assertLess(scan_elapsed, 60.0, "scan took %.2fs" % scan_elapsed)


if __name__ == "__main__":
    unittest.main()