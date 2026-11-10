"""Tests for the bounded Bright Data identity-enrichment CAMPAIGN planner. Offline."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.brightdata_costco_enrichment import (
    build_campaign_manifest,
    CAMPAIGN_MAX_URLS,
    CREDIT_CAP_FREE,
    PAID_CAP_USD,
    CHUNK_SIZE,
    GTIN_MPN_COVERAGE_MIN_PCT,
    MAPPING_FAILURE_MAX_PCT,
    CAMPAIGN_STOP_CONDITIONS,
)
from costco_non_kirkland.brightdata_costco_live import import_collector_response
from costco_non_kirkland.enrichment import assess_identity_readiness
from .fixtures import source_fixture


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-camp-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


def _rec(i, brand="Acme", price=19.99, title=None):
    item = 1000000 + i
    r = source_fixture(id=f"sp{i}", costco_item_number=str(item), brand_raw=brand,
                       brand_normalized=brand.lower(), costco_price=price,
                       title_raw=title or f"{brand} Widget {i}",
                       source_url=f"https://www.costco.com/.product.{item}.html")
    r["normalized_unit_count"] = None
    r["costco_pack_raw"] = None
    return r


class CampaignPlannerTests(unittest.TestCase):
    def test_manifest_max_urls_and_limits(self):
        store = _isolated_store()
        for i in range(200):
            store.upsert_source_product(_rec(i, brand=f"Brand{i % 40}"), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c", max_urls=150)
        self.assertLessEqual(m["manifest_size"], CAMPAIGN_MAX_URLS)
        self.assertEqual(m["credit_cap_free"], CREDIT_CAP_FREE)
        self.assertEqual(m["paid_balance_cap_usd"], PAID_CAP_USD)
        self.assertEqual(m["network_calls_made"], 0)

    def test_url_dedupe_and_previously_submitted(self):
        store = _isolated_store()
        store.upsert_source_product(_rec(1), run_id="run_c")
        dup = _rec(1); dup["id"] = "spdup"
        store.upsert_source_product(dup, run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c",
                                    excluded_urls={"https://www.costco.com/.product.1000002.html"})
        self.assertEqual(m["filter_counts"]["duplicate_url"], 1)

    def test_previously_submitted_excluded(self):
        store = _isolated_store()
        r = _rec(1)
        store.upsert_source_product(r, run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c", excluded_urls={r["source_url"]})
        self.assertEqual(m["manifest_size"], 0)
        self.assertEqual(m["filter_counts"]["previously_submitted"], 1)

    def test_food_beverage_excluded(self):
        store = _isolated_store()
        store.upsert_source_product(_rec(1, title="Ocean Spray Cranberry Juice"), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c")
        self.assertEqual(m["filter_counts"]["food_beverage"], 1)

    def test_missing_pack_allowed_but_not_identity_ready(self):
        store = _isolated_store()
        store.upsert_source_product(_rec(1), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c")
        self.assertEqual(m["manifest_size"], 1)
        c = m["candidates"][0]
        self.assertTrue(c["pack_unknown_pending_enrichment"])
        self.assertTrue(c["split_status_unknown"])
        res = assess_identity_readiness({"eligible_for_costco_non_kirkland_workflow": True,
                                         "brand_normalized": "acme", "costco_price": 1.0,
                                         "observed_at": "2026-01-01T00:00:00Z"}, None)
        self.assertFalse(res.identity_ready)

    def test_split_not_inferred(self):
        store = _isolated_store()
        r = _rec(1); r["normalized_unit_count"] = 24
        store.upsert_source_product(r, run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c")
        c = m["candidates"][0]
        self.assertFalse(c["confirmed_split_review_required"])
        self.assertTrue(c["split_status_unknown"])

    def test_high_cogs_over_100_excluded(self):
        store = _isolated_store()
        store.upsert_source_product(_rec(1, price=250.0), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c")
        self.assertEqual(m["filter_counts"]["high_cogs_over_100"], 1)

    def test_brand_concentration_cap(self):
        store = _isolated_store()
        for i in range(10):
            store.upsert_source_product(_rec(i, brand="SameBrand"), run_id="run_c")
        for i in range(10, 20):
            store.upsert_source_product(_rec(i, brand=f"Other{i}"), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c", max_urls=15, per_brand_max=5)
        self.assertLessEqual(m["diversification"]["max_brand_count"], 5)

    def test_category_proxy_concentration_cap(self):
        store = _isolated_store()
        for i in range(20):
            store.upsert_source_product(_rec(i, brand=f"B{i}", title=f"Brand{i} Bowl Set"), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c", max_urls=150, per_category_max=15)
        self.assertLessEqual(m["diversification"]["category_proxy_distribution"].get("kitchen", 0), 15)

    def test_chunk_plan_and_thresholds(self):
        store = _isolated_store()
        for i in range(60):
            store.upsert_source_product(_rec(i, brand=f"B{i}"), run_id="run_c")
        m = build_campaign_manifest(store, run_id="run_c", max_urls=150)
        self.assertEqual(m["chunk_size"], CHUNK_SIZE)
        self.assertEqual(m["chunk_count"], (m["manifest_size"] + CHUNK_SIZE - 1) // CHUNK_SIZE)
        self.assertIn("gtin_mpn_coverage_under_25pct_after_first_50", CAMPAIGN_STOP_CONDITIONS)
        self.assertEqual(GTIN_MPN_COVERAGE_MIN_PCT, 25)
        self.assertEqual(MAPPING_FAILURE_MAX_PCT, 20)

    def test_url_keyed_import_preserves_item_number_vs_item_id(self):
        store = _isolated_store()
        sp = _rec(1)
        store.upsert_source_product(sp, run_id="run_c")
        tmp = Path(tempfile.mkdtemp(prefix="cnk-camp-imp-"))
        p = tmp / "resp.json"
        p.write_text('{"records":[{"input":"' + sp["source_url"] + '","item_id":"7777777","gtin":"842032131990","brand":"Acme"}]}', encoding="utf-8")
        out = import_collector_response(str(p), store)
        self.assertTrue(out["item_mapping"][0]["matched_to_local"])
        self.assertFalse(out["item_mapping"][0]["item_id_matches_local"])
        rec = store.get_enrichment_record(sp["costco_item_number"])
        self.assertEqual(rec["costco_item_number"], sp["costco_item_number"])
        self.assertEqual(rec["gtin"], "842032131990")

    def test_no_live_or_amazon_or_browser_imports(self):
        src = Path(__file__).resolve().parents[1] / "brightdata_costco_enrichment.py"
        text = src.read_text(encoding="utf-8").lower()
        self.assertNotIn("import requests", text)
        self.assertNotIn("playwright", text)
        self.assertNotIn("amazon.com", text)

    def test_zero_network(self):
        import requests
        from network_guard import NetworkGuardViolation
        with self.assertRaises(NetworkGuardViolation):
            requests.get("http://127.0.0.1:9/", timeout=0.1)


if __name__ == "__main__":
    unittest.main()
