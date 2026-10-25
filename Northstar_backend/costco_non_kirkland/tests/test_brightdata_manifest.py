"""Tests for the corrected (option B) Bright Data enrichment selector. Offline only."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.brightdata_costco_enrichment import (
    build_enrichment_manifest,
    classify_pack_state,
    category_proxy,
    previously_submitted_urls,
)
from .fixtures import source_fixture


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-man-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


def _rec(item, brand="Acme", price=19.99, url=None):
    url = url or f"https://www.costco.com/.product.{item}.html"
    return source_fixture(id=f"sp{item}", costco_item_number=str(item), brand_raw=brand,
                          brand_normalized=brand.lower(), costco_price=price, source_url=url,
                          normalized_unit_count=None, costco_pack_raw=None)


class PackStateTests(unittest.TestCase):
    def test_pack_unknown_pending(self):
        ps = classify_pack_state(_rec("123"))
        self.assertFalse(ps["pack_known"])
        self.assertTrue(ps["pack_unknown_pending_enrichment"])
        self.assertTrue(ps["split_status_unknown"])
        self.assertEqual(ps["split_evidence_source"], "none")

    def test_split_not_inferred_from_unit_count(self):
        r = _rec("123")
        r["normalized_unit_count"] = 52  # legacy selector would have inferred split
        ps = classify_pack_state(r)
        self.assertTrue(ps["pack_known"])
        self.assertFalse(ps["confirmed_split_review_required"])
        self.assertTrue(ps["split_status_unknown"])

    def test_explicit_split_preserved(self):
        r = _rec("123")
        r["split_pack_status"] = "manual_review_required"
        ps = classify_pack_state(r)
        self.assertTrue(ps["confirmed_split_review_required"])
        self.assertFalse(ps["split_status_unknown"])
        self.assertIn("explicit_field", ps["split_evidence_source"])


class SelectionTests(unittest.TestCase):
    def test_missing_pack_does_not_exclude(self):
        store = _isolated_store()
        store.upsert_source_product(_rec("123"), run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25)
        self.assertEqual(m["sample_size"], 1)
        self.assertEqual(m["filter_counts"]["after_filters"], 1)
        self.assertTrue(m["candidates"][0]["pack_unknown_pending_enrichment"])

    def test_no_brand_excluded(self):
        store = _isolated_store()
        r = _rec("123"); r["brand_raw"] = None; r["brand_normalized"] = None
        store.upsert_source_product(r, run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25)
        self.assertEqual(m["sample_size"], 0)
        self.assertEqual(m["filter_counts"]["no_brand"], 1)

    def test_no_price_excluded(self):
        store = _isolated_store()
        r = _rec("123"); r["costco_price"] = None
        store.upsert_source_product(r, run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25)
        self.assertEqual(m["filter_counts"]["no_price"], 1)

    def test_previously_submitted_url_excluded(self):
        store = _isolated_store()
        r = _rec("123")
        store.upsert_source_product(r, run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25,
                                      excluded_urls={"https://www.costco.com/.product.123.html"})
        self.assertEqual(m["sample_size"], 0)
        self.assertEqual(m["filter_counts"]["previously_submitted"], 1)

    def test_dedupe_by_url(self):
        store = _isolated_store()
        store.upsert_source_product(_rec("123"), run_id="run_m")
        r2 = _rec("123"); r2["id"] = "spdup"
        store.upsert_source_product(r2, run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25)
        self.assertEqual(m["distinct_urls"], m["sample_size"])
        self.assertEqual(m["filter_counts"]["duplicate_url"], 1)

    def test_oversized_poor_fit_excluded(self):
        store = _isolated_store()
        r = _rec("123"); r["title_raw"] = "Gertmenian Locksley Area Rug Collection"
        store.upsert_source_product(r, run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25)
        self.assertEqual(m["filter_counts"]["oversized_poor_fit"], 1)
        self.assertEqual(m["sample_size"], 0)

    def test_manifest_fields_present(self):
        store = _isolated_store()
        store.upsert_source_product(_rec("123"), run_id="run_m")
        m = build_enrichment_manifest(store, run_id="run_m", max_items=25)
        c = m["candidates"][0]
        for f in ("source_product_id", "costco_item_number", "url", "brand", "costco_price",
                  "category_proxy", "existing_pack_evidence", "pack_known",
                  "pack_unknown_pending_enrichment", "confirmed_split_review_required",
                  "split_status_unknown"):
            self.assertIn(f, c)
        self.assertEqual(m["network_calls_made"], 0)

    def test_category_proxy(self):
        self.assertEqual(category_proxy("Unitex Cotton Towel"), "cleaning")
        self.assertEqual(category_proxy("Tupperware Bowl Set"), "kitchen")

    def test_previously_submitted_urls_from_enrichment(self):
        store = _isolated_store()
        sp = _rec("123")
        store.upsert_source_product(sp, run_id="run_m")
        store.upsert_enrichment_record({"costco_item_number": "123", "source_product_id": sp["id"],
                                        "provider_name": "brightdata"})
        urls = previously_submitted_urls(store)
        self.assertIn("https://www.costco.com/.product.123.html", urls)

    def test_zero_network(self):
        import requests
        from network_guard import NetworkGuardViolation
        with self.assertRaises(NetworkGuardViolation):
            requests.get("http://127.0.0.1:9/", timeout=0.1)


if __name__ == "__main__":
    unittest.main()
