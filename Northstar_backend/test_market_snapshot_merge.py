"""Offline tests for merging local market snapshots into the cache-only
scanner output.

Proves the read-time merge: zero provider/HTTP calls, candidate behavior
unchanged when no snapshot exists, honest value overlay only from stored
snapshot fields, observed-only seller counts, no Costco-match forcing or
upgrading, snapshot provenance preserved, and the store file left
byte-identical. The merge activates only when
SCANNER_LOCAL_SNAPSHOT_MERGE is enabled (strict flag) and
SCANNER_OFFER_ENRICHMENT is OFF/unset.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import hashlib
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import requests

import amazon_search
import costco_client
import costco_api_client
import main
import market_snapshot_store as store
import offer_enrichment
import product_analysis

_TMP = tempfile.mkdtemp(prefix="market-snapshot-merge-test-")

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


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _offer(price, fba=False, fbm=False, buybox=False):
    return {
        "position": 1,
        "buybox_winner": buybox,
        "price": {"value": price, "raw": "$%.2f" % price, "currency": "USD"},
        "condition": {"is_new": True, "title": "New"},
        "seller_id": "A1" if buybox else "S1",
        "seller_name": "Amazon.com" if buybox else "Seller Co",
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


def _easyparser_result(asin, offer_count, offers, gaps=None):
    return {
        "source": "easyparser",
        "asin": asin,
        "title": "Kirkland Snapshot Product",
        "offer_count": offer_count,
        "offers_returned_count": len(offers),
        "buy_box_price": next((o["price"]["value"] for o in offers if o["buybox_winner"]), None),
        "buy_box_price_raw": None,
        "buy_box_seller": next((o["seller_name"] for o in offers if o["buybox_winner"]), None),
        "buy_box_seller_id": None,
        "buy_box_is_fba": next((o["is_fba"] for o in offers if o["buybox_winner"]), None),
        "buy_box_is_fbm": None,
        "buy_box_is_prime": True,
        "buy_box_condition": None,
        "observed_fba_offer_count": sum(1 for o in offers if o["is_fba"]),
        "observed_fbm_offer_count": sum(1 for o in offers if o["is_fbm"]),
        "observed_amazon_offer_count": sum(1 for o in offers if o["seller_name"] == "Amazon.com"),
        "offers": offers,
        "request_zip_code": "75201",
        "observed_at": "2026-08-17T06:59:33+00:00",
        "credits_used": 1,
        "credits_remaining": 999,
        "data_gaps": list(gaps or []),
    }


def fake_candidate(asin, name, amazon_price=48.87):
    return {
        "name": name,
        "product_url": "https://www.amazon.com/dp/%s" % asin,
        "asin": asin,
        "amazon_price": amazon_price,
        "monthly_sales_estimate": None,
        "monthly_sales_estimated": False,
    }


def fake_costco(costco_cost=15.99, match_quality="exact"):
    return {"costco_cost": costco_cost, "match_quality": match_quality}


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
    raise AssertionError("provider/HTTP call made in cache-only merge test")


class SnapshotMergeTests(unittest.TestCase):
    cache_path = os.path.join(_TMP, "cache.json")
    store_path = os.path.join(_TMP, "store.json")

    def setUp(self):
        for path in (self.cache_path, self.store_path):
            if os.path.exists(path):
                os.remove(path)
        self.env = patch.dict(
            os.environ,
            {
                "SCANNER_SEARCH_CACHE_PATH": self.cache_path,
                "SCANNER_MARKET_SNAPSHOT_PATH": self.store_path,
                "SCANNER_OFFER_ENRICHMENT": "OFF",
                "SCANNER_LOCAL_SNAPSHOT_MERGE": "1",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def write_cache(self, products):
        payload = {
            "schema_version": 1,
            "fetched_at": "2026-08-15T12:00:00+00:00",
            "source": "brightdata",
            "search_terms": ["kirkland"],
            "candidate_count": len(products),
            "products": products,
        }
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def seed_snapshot(self, asin, offers, offer_count=None, gaps=None):
        result = _easyparser_result(asin, offer_count if offer_count is not None else len(offers), offers, gaps)
        snap = store.build_snapshot(asin, result)
        ok, err = store.save_snapshot(asin, snap)
        self.assertTrue(ok, err)
        return snap

    def _get(self, costco=fake_costco()):
        with patch.object(requests.api, "get", side_effect=_provider_called), \
             patch.object(requests.api, "post", side_effect=_provider_called), \
             patch.object(product_analysis, "get_costco_price", return_value=costco), \
             patch.object(product_analysis, "calculate_unit_economics",
                          side_effect=lambda product, costco: fake_economics()), \
             patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0), \
             patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0), \
             patch.object(product_analysis, "estimate_financial_profile",
                          return_value=fake_profile()), \
             patch.object(costco_client, "catalog_state", return_value="ready"), \
             patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY):
            return main.get_kirkland_scanner()

    def row_for(self, asin):
        data = self._get()
        for p in data["products"]:
            if p.get("asin") == asin:
                return p
        self.fail("row %s not found in scanner output" % asin)

    def test_merge_overlays_snapshot_values_zero_network(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test")])
        self.seed_snapshot(
            asin,
            [_offer(56.66, fba=True, buybox=True), _offer(49.99, fbm=True)],
            offer_count=2,
        )
        row = self.row_for(asin)
        self.assertEqual(row["amazon_price"], 56.66)
        self.assertEqual(row["total_sellers"], 2)
        self.assertEqual(row["fba_sellers"], 1)
        self.assertEqual(row["lowest_price"], 49.99)
        self.assertEqual(row["highest_price"], 56.66)
        self.assertEqual(row["snapshot_status"], "available")
        self.assertEqual(row["snapshot_source"], "easyparser")
        self.assertEqual(row["snapshot_offers_complete"], True)
        self.assertEqual(row["snapshot_buy_box_price"], 56.66)
        self.assertEqual(row["snapshot_buy_box_fulfillment"], "Amazon")
        self.assertEqual(row["snapshot_freshness"], "fresh")
        self.assertEqual(row["snapshot_fbm_sellers"], 1)
        self.assertEqual(row["enriched_at"], "2026-08-17T06:59:33+00:00")

    def test_no_snapshot_leaves_candidate_behavior_unchanged(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test", amazon_price=48.87)])
        row = self.row_for(asin)
        self.assertEqual(row["amazon_price"], 48.87)
        self.assertIsNone(row["total_sellers"])
        self.assertIsNone(row["snapshot_status"])
        self.assertIsNone(row["snapshot_buy_box_price"])

    def test_merge_disabled_flag_keeps_current_behavior(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test", amazon_price=48.87)])
        self.seed_snapshot(asin, [_offer(56.66, fba=True, buybox=True)], offer_count=1)
        os.environ["SCANNER_LOCAL_SNAPSHOT_MERGE"] = "0"
        row = self.row_for(asin)
        self.assertEqual(row["amazon_price"], 48.87)
        self.assertIsNone(row["snapshot_status"])

    def test_partial_roster_uses_observed_counts_only(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test")])
        self.seed_snapshot(
            asin,
            [_offer(49.99, fbm=True), _offer(56.66, fba=True)],
            offer_count=12,
        )
        row = self.row_for(asin)
        self.assertEqual(row["snapshot_status"], "partial")
        self.assertEqual(row["snapshot_offers_complete"], False)
        self.assertEqual(row["total_sellers"], 2)
        self.assertEqual(row["fba_sellers"], 1)
        self.assertNotEqual(row["total_sellers"], 12)

    def test_failed_snapshot_never_overlays_values(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test", amazon_price=48.87)])
        self.seed_snapshot(asin, [], gaps=["Easyparser request timed out."])
        row = self.row_for(asin)
        self.assertEqual(row["amazon_price"], 48.87)
        self.assertEqual(row["snapshot_status"], "failed")
        self.assertIn("timed out", "; ".join(row["snapshot_data_gaps"] or []))

    def test_merge_never_forces_or_upgrades_costco_match(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test")])
        self.seed_snapshot(asin, [_offer(56.66, fba=True, buybox=True)], offer_count=1)
        data = self._get(costco={})
        row = next(p for p in data["products"] if p.get("asin") == asin)
        self.assertIsNone(row["costco_cost"])
        self.assertNotEqual(row.get("pack_match"), "exact")
        self.assertEqual(row["amazon_price"], 56.66)

    def test_merge_is_read_only_on_store(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test")])
        self.seed_snapshot(asin, [_offer(56.66, fba=True, buybox=True)], offer_count=1)
        before = _sha256(self.store_path)
        self.row_for(asin)
        self.assertEqual(_sha256(self.store_path), before)

    def test_missing_snapshot_values_stay_unknown(self):
        asin = "B0CS6Z9SRX"
        self.write_cache([fake_candidate(asin, "Kirkland Test", amazon_price=48.87)])
        self.seed_snapshot(asin, [_offer(56.66, fba=True)], offer_count=1)
        row = self.row_for(asin)
        self.assertEqual(row["amazon_price"], 48.87)
        self.assertIsNone(row.get("monthly_sales_estimate"))
        self.assertFalse(row.get("monthly_sales_estimated", False))
        self.assertEqual(row["snapshot_buy_box_available"], False)
        self.assertIsNone(row.get("snapshot_buy_box_price"))
        self.assertEqual(row["snapshot_buy_box_fulfillment"], "Unknown")


class Phase3MergeIntegrationTests(unittest.TestCase):
    """Phase 3: merged rows carry demand / competition / portfolio
    intelligence, and the zero-proof honesty rule holds at merge level."""

    cache_path = os.path.join(_TMP, "p3-cache.json")
    store_path = os.path.join(_TMP, "p3-store.json")

    def setUp(self):
        for path in (self.cache_path, self.store_path):
            if os.path.exists(path):
                os.remove(path)
        self.env = patch.dict(
            os.environ,
            {
                "SCANNER_SEARCH_CACHE_PATH": self.cache_path,
                "SCANNER_MARKET_SNAPSHOT_PATH": self.store_path,
                "SCANNER_OFFER_ENRICHMENT": "OFF",
                "SCANNER_LOCAL_SNAPSHOT_MERGE": "1",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def write_cache(self, products):
        payload = {
            "schema_version": 1,
            "fetched_at": "2026-08-15T12:00:00+00:00",
            "source": "brightdata",
            "search_terms": ["kirkland"],
            "candidate_count": len(products),
            "products": products,
        }
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def seed_snapshot(self, asin, offers, offer_count=None, gaps=None):
        result = _easyparser_result(asin, offer_count if offer_count is not None else len(offers), offers, gaps)
        snap = store.build_snapshot(asin, result)
        ok, err = store.save_snapshot(asin, snap)
        self.assertTrue(ok, err)
        return snap

    def _get(self):
        with patch.object(requests.api, "get", side_effect=_provider_called), \
             patch.object(requests.api, "post", side_effect=_provider_called), \
             patch.object(product_analysis, "get_costco_price", return_value=fake_costco()), \
             patch.object(product_analysis, "calculate_unit_economics",
                          side_effect=lambda product, costco: fake_economics()), \
             patch.object(product_analysis, "MIN_ROI_PERCENT", -100.0), \
             patch.object(product_analysis, "MIN_PROFIT_MARGIN_PERCENT", -100.0), \
             patch.object(product_analysis, "estimate_financial_profile",
                          return_value=fake_profile()), \
             patch.object(costco_client, "catalog_state", return_value="ready"), \
             patch.object(costco_api_client, "last_run_status", return_value=FAKE_DISCOVERY):
            return main.get_kirkland_scanner()

    def row_for(self, asin):
        data = self._get()
        for p in data["products"]:
            if p.get("asin") == asin:
                return p
        self.fail("row %s not found in scanner output" % asin)

    def test_merged_row_carries_full_intelligence_set(self):
        asin = "B0CS6Z9SRX"
        candidate = fake_candidate(asin, "Kirkland Test", amazon_price=48.87)
        candidate["monthly_sales_estimate"] = 500
        self.write_cache([candidate])
        self.seed_snapshot(
            asin,
            [_offer(56.66, fba=True, buybox=True), _offer(49.99, fbm=True)],
            offer_count=2,
        )
        row = self.row_for(asin)
        # Demand: estimated from the provider monthly-sales signal.
        self.assertEqual(row["estimated_monthly_sales"], 500)
        self.assertEqual(row["sales_estimation_source"], "provider_estimate")
        # Competition: observed counts, not claimed.
        self.assertEqual(row["observed_total_sellers"], 2)
        self.assertEqual(row["observed_fba_sellers"], 1)
        self.assertEqual(row["observed_fbm_sellers"], 1)
        self.assertEqual(row["offers_complete"], True)
        self.assertIsNone(row.get("offer_roster_reason"))
        # Portfolio: readiness + revenue basis from the Buy Box price.
        self.assertIn("portfolio_readiness", row)
        self.assertIn("portfolio_category", row)
        self.assertIn("risk_flags", row)
        self.assertIn("total_completeness_score", row)

    def test_bsr_without_category_stays_unknown(self):
        # Honesty: a BSR alone cannot estimate demand (no category
        # curve), so the row keeps Unknown rather than inventing a curve.
        asin = "B0CS6Z9SRX"
        candidate = fake_candidate(asin, "Kirkland Test", amazon_price=48.87)
        candidate["sales_rank"] = 2000
        self.write_cache([candidate])
        self.seed_snapshot(asin, [_offer(56.66, fba=True)], offer_count=1)
        row = self.row_for(asin)
        self.assertIsNone(row["estimated_monthly_sales"])
        self.assertFalse(row["monthly_sales_estimated"])

    def test_partial_zero_returned_is_unknown_at_merge_level(self):
        asin = "B0CS6Z9SRX"
        candidate = fake_candidate(asin, "Kirkland Test", amazon_price=48.87)
        candidate["sales_rank"] = 2000
        candidate["amazon_category"] = "Home & Kitchen"
        self.write_cache([candidate])
        self.seed_snapshot(asin, [], offer_count=12)
        row = self.row_for(asin)
        self.assertEqual(row["snapshot_status"], "unavailable")
        self.assertIsNone(row["total_sellers"])
        self.assertIsNone(row["observed_total_sellers"])
        self.assertEqual(row["offer_roster_reason"], "offer_roster_unavailable")

    def test_explicit_zero_proof_shows_zero_at_merge_level(self):
        asin = "B0CS6Z9SRX"
        candidate = fake_candidate(asin, "Kirkland Test", amazon_price=48.87)
        candidate["sales_rank"] = 2000
        candidate["amazon_category"] = "Home & Kitchen"
        self.write_cache([candidate])
        self.seed_snapshot(asin, [], offer_count=0)
        row = self.row_for(asin)
        self.assertEqual(row["snapshot_status"], "available")
        self.assertEqual(row["snapshot_offers_complete"], True)
        self.assertEqual(row["total_sellers"], 0)
        self.assertEqual(row["observed_total_sellers"], 0)
        self.assertIsNone(row.get("offer_roster_reason"))


if __name__ == "__main__":
    unittest.main(verbosity=2)