#!/usr/bin/env python3
"""Tests for the Kirkland Costco evidence merge (kirkland_costco_merge.py)."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kirkland_costco_merge as merge


def _evidence_file(run_dir, filename, body):
    path = os.path.join(run_dir, "run-test", "normalized", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f)


def _item(item_id, title, price, captured_at, ts_attr="captured_at", **extra):
    item = {
        "requested_item_id": str(item_id),
        "returned_costco_item_id": str(item_id),
        "exact_title": title,
        "brand": "Kirkland Signature",
        "listed_price": price,
        "currency": "USD",
        "unit_price": None,
        "quantity_or_pack": None,
        "size_or_weight": None,
        "UPC_GTIN_EAN": None,
        "availability": None,
        "product_url": "https://www.costco.com/.product.%s.html" % item_id,
        ts_attr: captured_at,
        "identity_match_status": "probable_match",
        "missing_fields": [],
    }
    return {
        "run_id": "test-run",
        "attempt": "brightdata_costco_%s" % item_id,
        "requested_at": "2026-09-01T00:00:00Z",
        "provider": "BRIGHTDATA_WEB_UNLOCKER",
        "platform": "web_unlocker_costco_page",
        "endpoint": "https://api.brightdata.com/request",
        "url": "https://www.costco.com/.product.%s.html" % item_id,
        "http_status": 200,
        "failure_type": None,
        "retries": 0,
        "stop_on_block": "sequential_batch",
        "scrubbed": True,
        "item": item,
    }


class MergeStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.runs = os.path.join(self.tmpdir.name, "runs")
        self.store = os.path.join(self.tmpdir.name, "product-detail.json")

    def _run(self):
        with mock.patch.dict(
            "os.environ",
            {"COSTCO_CATALOG_DETAIL_PATH": self.store, "COSTCO_CATALOG_SOURCE": "UNWRANGLE"},
            clear=False,
        ):
            return merge.run_merge(runs_root=self.runs)

    def _load_store(self):
        with open(self.store, encoding="utf-8") as f:
            return json.load(f)

    def test_imports_priced_item_with_canonical_schema(self):
        _evidence_file(self.runs, "items_AAAA_brightdata.json",
                       _item("AAAA", "Kirkland Signature Fish Oil 1000 mg, 400 Softgels", 20.99,
                             "2026-09-05T01:00:00Z"))
        summary = self._run()
        self.assertEqual(summary["records_imported"], 1)
        rows = self._load_store()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["costco_item_id"], "AAAA")
        self.assertEqual(r["item_name"], "Kirkland Signature Fish Oil 1000 mg, 400 Softgels")
        self.assertEqual(r["current_price"], 20.99)
        self.assertEqual(r["cost_basis"], "brightdata_costco_page")
        self.assertEqual(r["cost_status"], "detail_only")
        self.assertEqual(r["source"], "brightdata_web_unlocker")
        self.assertEqual(r["fetched_at"], "2026-09-05T01:00:00Z")
        self.assertEqual(r["identity_match_status"], "probable_match")

    def test_latest_wins_per_item_id_by_captured_at(self):
        _evidence_file(self.runs, "items_BBBB_v1.json",
                       _item("BBBB", "Kirkland Signature Dental Chews, 72-count", 36.99,
                             "2026-09-05T00:00:00Z"))
        _evidence_file(self.runs, "items_BBBB_v2.json",
                       _item("BBBB", "Kirkland Signature Dental Chews, 72-count", 33.65,
                             "2026-09-07T00:00:00Z"))
        summary = self._run()
        rows = self._load_store()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["current_price"], 33.65)
        self.assertEqual(summary["evidence_files_scanned"], 2)
        self.assertEqual(summary["unique_item_ids_with_evidence"], 1)

    def test_invalid_price_and_empty_item_skipped(self):
        _evidence_file(self.runs, "items_CCCC.json",
                       _item("CCCC", "Kirkland Signature Three Berry Blend, 4 lbs", 0.01,
                             "2026-09-05T00:00:00Z"))
        _evidence_file(self.runs, "items_DDDD.json", {
            "requested_at": "2026-09-05T00:00:00Z", "item": {}})
        summary = self._run()
        # The $0.01 capture artifact is rejected; the empty-item file never
        # becomes an evidence winner, so nothing imports.
        self.assertEqual(summary["records_imported"], 0)
        self.assertEqual(len(self._load_store()), 0)
        self.assertEqual(summary["skipped"]["no_price"], 1)
        self.assertEqual(summary["unique_item_ids_with_evidence"], 1)

    def test_preserves_existing_records_and_purges_stale_invalid_price(self):
        # Pre-seed store: a valid unrelated record and a stale $0.01 artifact.
        with open(self.store, "w", encoding="utf-8") as f:
            json.dump([
                {"costco_item_id": "0001", "item_name": "Kirkland Signature CoQ10 300 mg, 200 Softgels",
                 "current_price": 26.99, "cost_basis": "costco_online", "cost_status": "detail_only",
                 "source": "product_detail", "fetched_at": "2026-08-01T00:00:00Z"},
                {"costco_item_id": "0002", "item_name": "Kirkland Signature Three Berry Blend, 4 lbs",
                 "current_price": 0.01, "cost_basis": "brightdata_costco_page", "cost_status": "detail_only",
                 "source": "brightdata_web_unlocker", "fetched_at": "2026-08-01T00:00:00Z"},
            ], f)
        _evidence_file(self.runs, "items_EEEE.json",
                       _item("EEEE", "Kirkland Signature Nitrile Exam Gloves, 400-count, Size Medium", 21.99,
                             "2026-09-06T00:00:00Z"))
        summary = self._run()
        rows = self._load_store()
        ids = {r["costco_item_id"] for r in rows}
        self.assertEqual(ids, {"0001", "EEEE"})  # stale $0.01 purged, valid preserved
        self.assertEqual(summary["records_preserved"], 1)
        self.assertEqual(summary["records_imported"], 1)

    def test_fresh_evidence_replaces_existing_by_id(self):
        with open(self.store, "w", encoding="utf-8") as f:
            json.dump([
                {"costco_item_id": "EEEE", "item_name": "old name", "current_price": 17.99,
                 "cost_basis": "costco_online", "cost_status": "detail_only",
                 "source": "product_detail", "fetched_at": "2026-01-01T00:00:00Z"},
            ], f)
        _evidence_file(self.runs, "items_EEEE.json",
                       _item("EEEE", "Kirkland Signature Nitrile Exam Gloves, 400-count, Size Medium", 21.99,
                             "2026-09-06T00:00:00Z"))
        self._run()
        rows = self._load_store()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["current_price"], 21.99)
        self.assertEqual(rows[0]["item_name"], "Kirkland Signature Nitrile Exam Gloves, 400-count, Size Medium")


if __name__ == "__main__":
    unittest.main()