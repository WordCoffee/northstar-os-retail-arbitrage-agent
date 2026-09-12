"""Offline tests for the Easyparser market snapshot store.

Zero network, zero writes to real data files: store and run-report paths
are pointed at temp locations per test. Covers schema/snapshot building
from normalized Easyparser results, per-ASIN atomic persistence with
post-write verification, corrupt-store refusal, failed-write preservation
of the prior file, freshness labels, bounded retry eligibility, run
report persistence, and byte-identity guards proving the active candidate
cache and the Bright Data backup are untouched by this module.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import glob
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import market_snapshot_store as store

_TMP = tempfile.mkdtemp(prefix="market-snapshot-test-")

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REAL_CACHE = os.path.join(_BACKEND_DIR, "data", "scanner-search-cache.json")
_REAL_BACKUPS = sorted(
    glob.glob(os.path.join(_BACKEND_DIR, "data", "scanner-search-cache.brightdata-*.json"))
)

if os.path.exists(_REAL_CACHE):
    _CACHE_SHA = hashlib.sha256(open(_REAL_CACHE, "rb").read()).hexdigest()
else:
    _CACHE_SHA = None
if _REAL_BACKUPS:
    _BACKUP_SHA = hashlib.sha256(open(_REAL_BACKUPS[0], "rb").read()).hexdigest()
else:
    _BACKUP_SHA = None


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _result(asin="B00GYZWNY6", offer_count=12, offers=None, observed_at=None,
            gaps=None, credits_used=1, credits_remaining=999):
    offers = offers if offers is not None else []
    result = {
        "source": "easyparser",
        "asin": asin,
        "title": "Kirkland Test Product",
        "offer_count": offer_count,
        "offers_returned_count": len(offers),
        "buy_box_price": None,
        "buy_box_price_raw": None,
        "buy_box_seller": None,
        "buy_box_seller_id": None,
        "buy_box_is_fba": None,
        "buy_box_is_fbm": None,
        "buy_box_is_prime": None,
        "buy_box_condition": None,
        "observed_fba_offer_count": 0,
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": 0,
        "offers": offers,
        "request_zip_code": "75201",
        "observed_at": observed_at,
        "credits_used": credits_used,
        "credits_remaining": credits_remaining,
        "data_gaps": list(gaps or []),
    }
    return result


def _offer(price, fba=False, fbm=False, buybox=False, seller="Seller Co"):
    return {
        "position": 1,
        "buybox_winner": buybox,
        "price": {"value": price, "raw": "$%.2f" % price, "currency": "USD"},
        "condition": {"is_new": True, "title": "New"},
        "seller_id": "S1" if not buybox else "A1",
        "seller_name": "Amazon.com" if buybox and seller == "Amazon.com" else seller,
        "seller_rating": 4.5,
        "seller_positive_percentage": 90,
        "seller_ratings_total": 200,
        "is_prime": True,
        "is_fba": fba,
        "is_fbm": fbm,
        "is_sba": False,
        "fulfilled_by_amazon": fba,
        "shipping_text": "FREE Shipping" if fba else "Shipping",
        "shipping_is_free": fba,
        "ships_from": "US",
        "minimum_order_quantity": 1,
        "maximum_order_quantity": 10,
    }


class StoreEnvTests(unittest.TestCase):
    def setUp(self):
        self.store_path = os.path.join(_TMP, "store.json")
        self.report_path = os.path.join(_TMP, "report.json")
        self.env = patch.dict(
            os.environ,
            {
                "SCANNER_MARKET_SNAPSHOT_PATH": self.store_path,
                "SCANNER_ENRICH_RUN_REPORT_PATH": self.report_path,
            },
            clear=False,
        )
        self.env.start()
        for path in (self.store_path, self.report_path):
            if os.path.exists(path):
                os.remove(path)

    def tearDown(self):
        self.env.stop()


class SnapshotBuildTests(StoreEnvTests):
    def test_available_snapshot_full_normalization(self):
        offers = [
            _offer(56.66, fba=True, buybox=True, seller="Amazon.com"),
            _offer(49.99, fbm=True),
        ]
        result = _result(offer_count=2, offers=offers,
                         observed_at="2026-08-17T06:59:33+00:00")
        result["buy_box_price"] = 56.66
        result["buy_box_seller"] = "Amazon.com"
        result["buy_box_is_fba"] = True
        result["observed_fba_offer_count"] = 1
        result["observed_fbm_offer_count"] = 1
        result["observed_amazon_offer_count"] = 1
        snap = store.build_snapshot("B00GYZWNY6", result)

        self.assertEqual(snap["source"], "easyparser")
        self.assertEqual(snap["data_status"], store.DATA_STATUS_AVAILABLE)
        self.assertTrue(snap["offers_complete"])
        self.assertEqual(snap["offers_returned"], 2)
        self.assertEqual(len(snap["offers"]), 2)
        self.assertEqual(snap["seller_counts"]["observed_total"], 2)
        self.assertEqual(snap["seller_counts"]["claimed_total"], 2)
        self.assertEqual(snap["seller_counts"]["fba_observed"], 1)
        self.assertEqual(snap["seller_counts"]["fbm_observed"], 1)
        self.assertEqual(snap["seller_counts"]["amazon_observed"], 1)
        self.assertTrue(snap["seller_counts"]["counts_from_observed"])
        self.assertEqual(snap["buy_box"]["price"], 56.66)
        self.assertEqual(snap["buy_box"]["seller_name"], "Amazon.com")
        self.assertEqual(snap["buy_box"]["fulfillment"], "Amazon")
        self.assertTrue(snap["buy_box"]["available"])
        self.assertEqual(snap["credits_used"], 1)
        self.assertEqual(snap["credits_remaining"], 999)
        self.assertEqual(snap["observed_at"], "2026-08-17T06:59:33+00:00")
        self.assertEqual(snap["stages"]["detail"], "done")
        self.assertEqual(snap["stages"]["offers"], "done")
        self.assertEqual(snap["stages"]["sales"], "not_requested")
        self.assertEqual(snap["attempts"], 1)
        self.assertIsNone(snap["last_error"])
        self.assertFalse(snap["retry_eligible"])
        for field in ("upc", "ean", "gtin", "item_weight_lbs", "package_weight_lbs",
                      "package_dimensions_in", "fba_fee", "monthly_sales_estimate",
                      "sales_rank", "brand", "browse_node_id", "amazon_category"):
            self.assertIn(field, snap["missing_fields"])
        for key in ("offers_fresh_until", "sales_fresh_until", "identity_fresh_until"):
            self.assertIn(key, snap["freshness"])

    def test_partial_roster_never_claims_full_counts(self):
        offers = [_offer(49.99, fbm=True), _offer(56.66, fba=True)]
        result = _result(offer_count=12, offers=offers)
        result["observed_fba_offer_count"] = 1
        result["observed_fbm_offer_count"] = 1
        snap = store.build_snapshot("B00GYZWNY6", result)

        self.assertEqual(snap["data_status"], store.DATA_STATUS_PARTIAL)
        self.assertFalse(snap["offers_complete"])
        self.assertEqual(snap["seller_counts"]["observed_total"], 2)
        self.assertEqual(snap["seller_counts"]["claimed_total"], 12)
        self.assertEqual(snap["stages"]["offers"], "partial")
        self.assertEqual(len(snap["offers"]), 2)

    def test_failed_snapshot_records_gap_and_retry_eligibility(self):
        result = _result(gaps=["Easyparser request timed out."])
        snap = store.build_snapshot("B00GYZWNY6", result)
        self.assertEqual(snap["data_status"], store.DATA_STATUS_FAILED)
        self.assertFalse(snap["offers_complete"])
        self.assertIn("timed out", snap["last_error"])
        self.assertTrue(snap["retry_eligible"])
        self.assertEqual(snap["stages"]["offers"], "failed")
        self.assertEqual(snap["attempts"], 1)

    def test_explicit_zero_offer_set_is_available_complete(self):
        result = _result(offer_count=0, offers=[], gaps=[])
        snap = store.build_snapshot("B00GYZWNY6", result)
        self.assertEqual(snap["data_status"], store.DATA_STATUS_AVAILABLE)
        self.assertTrue(snap["offers_complete"])
        self.assertEqual(snap["stages"]["offers"], "done")
        self.assertEqual(snap["seller_counts"]["claimed_total"], 0)
        self.assertEqual(snap["seller_counts"]["observed_total"], 0)

    def test_unavailable_when_claim_absent_and_no_error(self):
        result = _result(offer_count=None, offers=[], gaps=[])
        snap = store.build_snapshot("B00GYZWNY6", result)
        self.assertEqual(snap["data_status"], store.DATA_STATUS_UNAVAILABLE)
        self.assertFalse(snap["offers_complete"])
        self.assertEqual(snap["stages"]["offers"], "unavailable")

    def test_unavailable_when_claim_positive_but_nothing_returned(self):
        result = _result(offer_count=12, offers=[], gaps=[])
        snap = store.build_snapshot("B00GYZWNY6", result)
        self.assertEqual(snap["data_status"], store.DATA_STATUS_UNAVAILABLE)
        self.assertFalse(snap["offers_complete"])

    def test_permanent_gap_blocks_retry(self):
        result = _result(gaps=["Easyparser API key is not configured."])
        snap = store.build_snapshot("B00GYZWNY6", result, prior_attempts=0)
        self.assertEqual(snap["data_status"], store.DATA_STATUS_FAILED)
        self.assertFalse(snap["retry_eligible"])
        self.assertTrue(store.permanent_gap(snap["data_gaps"]))

    def test_attempts_respected_from_prior(self):
        result = _result(gaps=["HTTP 500."])
        snap = store.build_snapshot("B00GYZWNY6", result, prior_attempts=2)
        self.assertEqual(snap["attempts"], 3)
        self.assertFalse(snap["retry_eligible"])


class PersistenceTests(StoreEnvTests):
    def test_save_and_load_roundtrip(self):
        offers = [_offer(49.99, fbm=True)]
        result = _result(offer_count=1, offers=offers)
        snap = store.build_snapshot("B00GYZWNY6", result)
        ok, err = store.save_snapshot("B00GYZWNY6", snap)
        self.assertTrue(ok, err)
        self.assertIsNone(err)

        loaded = store.load_snapshots()
        self.assertEqual(list(loaded.keys()), ["B00GYZWNY6"])
        self.assertEqual(loaded["B00GYZWNY6"], snap)
        self.assertEqual(store.get_snapshot("B00GYZWNY6"), snap)
        self.assertIsNone(store.get_snapshot("B0000000ZZ"))

        with open(self.store_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["schema_version"], 1)
        self.assertIn("generated_at", raw)

    def test_save_is_per_asin_atomic_and_upserts(self):
        first = store.build_snapshot("B000000001", _result(asin="B000000001", offer_count=0, offers=[]))
        ok, err = store.save_snapshot("B000000001", first)
        self.assertTrue(ok, err)
        second = store.build_snapshot("B000000002", _result(asin="B000000002", offer_count=0, offers=[]))
        ok, err = store.save_snapshot("B000000002", second)
        self.assertTrue(ok, err)
        loaded = store.load_snapshots()
        self.assertEqual(set(loaded.keys()), {"B000000001", "B000000002"})

        updated = dict(first)
        updated["data_status"] = store.DATA_STATUS_AVAILABLE
        ok, err = store.save_snapshot("B000000001", updated)
        self.assertTrue(ok, err)
        self.assertEqual(store.get_snapshot("B000000001")["data_status"],
                         store.DATA_STATUS_AVAILABLE)
        self.assertEqual(store.get_snapshot("B000000002"), second)

    def test_failed_write_preserves_prior_snapshot(self):
        first = store.build_snapshot("B00GYZWNY6", _result(offer_count=0, offers=[]))
        ok, err = store.save_snapshot("B00GYZWNY6", first)
        self.assertTrue(ok, err)
        before = _sha256(self.store_path)

        replacement = dict(first)
        replacement["data_status"] = store.DATA_STATUS_AVAILABLE
        with patch.object(store, "_atomic_write_json", return_value=False):
            ok, err = store.save_snapshot("B00GYZWNY6", replacement)
        self.assertFalse(ok)
        self.assertIn("failed", err)
        self.assertEqual(_sha256(self.store_path), before)
        self.assertEqual(store.get_snapshot("B00GYZWNY6"), first)

    def test_corrupt_store_refuses_overwrite(self):
        with open(self.store_path, "w", encoding="utf-8") as f:
            f.write("{ not json")
        snap = store.build_snapshot("B00GYZWNY6", _result(offer_count=0, offers=[]))
        ok, err = store.save_snapshot("B00GYZWNY6", snap)
        self.assertFalse(ok)
        self.assertIn("corrupt", err)
        with open(self.store_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "{ not json")

    def test_invalid_asin_refused(self):
        ok, err = store.save_snapshot("not-an-asin", {"x": 1})
        self.assertFalse(ok)
        ok, err = store.save_snapshot("B00GYZWNY6", None)
        self.assertFalse(ok)
        ok, err = store.save_snapshot("B00GYZWNY6", {})
        self.assertFalse(ok)

    def test_missing_store_loads_empty(self):
        self.assertEqual(store.load_snapshots(), {})
        self.assertIsNone(store.get_snapshot("B00GYZWNY6"))

    def test_run_report_roundtrip(self):
        report = {
            "mode": "dry-run",
            "generated_at": "2026-08-17T07:00:00+00:00",
            "counts": {"planned": 10},
        }
        ok, err = store.write_run_report(report)
        self.assertTrue(ok, err)
        loaded = store.read_run_report()
        self.assertEqual(loaded["mode"], "dry-run")
        self.assertEqual(loaded["schema_version"], 1)
        self.assertEqual(loaded["counts"]["planned"], 10)

    def test_run_report_write_failure_preserves_prior(self):
        store.write_run_report({"mode": "status", "generated_at": "2026-01-01T00:00:00+00:00"})
        before = _sha256(self.report_path)
        with patch.object(store, "_atomic_write_json", return_value=False):
            ok, err = store.write_run_report({"mode": "batch", "generated_at": "2026-02-01T00:00:00+00:00"})
        self.assertFalse(ok)
        self.assertEqual(_sha256(self.report_path), before)
        self.assertEqual(store.read_run_report()["mode"], "status")


class FreshnessTests(StoreEnvTests):
    def test_freshness_status_labels(self):
        snap = store.build_snapshot("B00GYZWNY6", _result(offer_count=0, offers=[]))
        self.assertEqual(store.snapshot_freshness_status(snap), "fresh")
        old = {
            "freshness": {
                "offers_fresh_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "sales_fresh_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "identity_fresh_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            }
        }
        self.assertEqual(store.snapshot_freshness_status(old), "stale")
        self.assertEqual(store.snapshot_freshness_status({}), "unknown")

    def test_fresh_success_and_retry_eligibility_policies(self):
        success = store.build_snapshot("B00GYZWNY6", _result(offer_count=2, offers=[_offer(10)]))
        success["data_status"] = store.DATA_STATUS_AVAILABLE
        self.assertTrue(store.is_fresh_success(success))

        failed = store.build_snapshot("B00GYZWNY6", _result(gaps=["HTTP 500."]))
        self.assertTrue(store.is_retry_eligible(failed))
        self.assertFalse(store.is_fresh_success(failed))

        exhausted = dict(failed)
        exhausted["attempts"] = store.MAX_ATTEMPTS
        self.assertFalse(store.is_retry_eligible(exhausted))

        permanent = store.build_snapshot("B00GYZWNY6", _result(gaps=["Easyparser API key is not configured."]))
        self.assertFalse(store.is_retry_eligible(permanent))

        self.assertFalse(store.is_retry_eligible(None))
        self.assertFalse(store.is_fresh_success(None))


class RealDataGuardTests(unittest.TestCase):
    def test_active_cache_and_backup_byte_identical(self):
        if _CACHE_SHA is not None:
            self.assertEqual(_sha256(_REAL_CACHE), _CACHE_SHA,
                             "active scanner-search-cache.json changed during tests")
        if _BACKUP_SHA is not None:
            self.assertEqual(_sha256(_REAL_BACKUPS[0]), _BACKUP_SHA,
                             "Bright Data backup snapshot changed during tests")


if __name__ == "__main__":
    unittest.main(verbosity=2)