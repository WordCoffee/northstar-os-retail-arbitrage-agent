"""Offline tests for the cache-only scanner mode and strict flag parsing.

Proves that SCANNER_OFFER_ENRICHMENT=OFF/unset/disabled values make
GET /api/kirkland/scanner complete from the local candidate cache with
ZERO provider or HTTP-client calls, that only 1/true/yes/on enable the
default provider, that documented provider tokens stay valid opt-ins,
and that the candidate cache is written only after a fully successful
live search (never wiped by a failed/disabled run).

Never touches the network, never runs test_scavio.py, and never reads or
writes real data files: the cache path and all Costco/matching inputs are
pointed at temp/mocked locations.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
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
import offer_enrichment
import product_analysis


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules.
    Cache-only assertions below are unaffected: the gate only ever
    forces OFF, never ON."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)

_TMP = tempfile.mkdtemp(prefix="scanner-cache-test-")

DISABLED_VALUES = ("", "0", "false", "no", "off", "OFF", "banana", "FALSE")
ENABLED_BOOLEAN_VALUES = ("1", "true", "yes", "on", "TRUE", "Yes", "ON")
PROVIDER_TOKENS = ("AUTO", "BRIGHTDATA", "EASYPARSER", "CHOCODATA", "UNWRANGLE")

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


def fake_candidate(asin, name, amazon_price=48.87):
    return {
        "name": name,
        "product_url": f"https://www.amazon.com/dp/{asin}",
        "asin": asin,
        "amazon_price": amazon_price,
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


def _provider_called(*args, **kwargs):
    raise AssertionError("provider/HTTP call made in cache-only mode")


class CacheOnlyScannerTests(unittest.TestCase):
    cache_path = os.path.join(_TMP, "cache.json")

    @contextmanager
    def _env(self, mode, extra=None):
        """Control SCANNER_OFFER_ENRICHMENT (None = unset) plus extras."""
        env = {"SCANNER_SEARCH_CACHE_PATH": self.cache_path}
        if extra:
            env.update(extra)
        with patch.dict(os.environ, env, clear=False):
            if mode is None:
                os.environ.pop("SCANNER_OFFER_ENRICHMENT", None)
            else:
                os.environ["SCANNER_OFFER_ENRICHMENT"] = mode
            yield

    def _route_patches(self):
        return [
            patch.object(product_analysis, "search_kirkland_products", side_effect=_provider_called),
            patch.object(requests.api, "get", side_effect=_provider_called),
            patch.object(requests.api, "post", side_effect=_provider_called),
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
        with patches[0]:
            for p in patches[1:]:
                p.start()
            try:
                return main.get_kirkland_scanner()
            finally:
                for p in reversed(patches[1:]):
                    p.stop()

    # --- Phase 3.1 / 3.2: disabled values + unset => zero provider calls ---

    def test_unset_is_cache_only_zero_provider_calls(self):
        products = [fake_candidate("B000000001", "Alpha"), fake_candidate("B000000002", "Beta", 41.0)]
        write_cache(self.cache_path, products)
        with self._env(None):
            body = self._get(self._route_patches())
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")
        self.assertEqual(body["summary"]["enrichment_source"], "OFF")
        self.assertEqual(body["summary"]["cache_status"], "fresh")
        self.assertEqual(body["summary"]["cache_fetched_at"], "2026-08-15T12:00:00+00:00")
        self.assertEqual(body["summary"]["cache_source"], "brightdata")
        self.assertEqual(body["summary"]["candidates_returned"], 2)
        # UTC timestamp contract for generated_at.
        self.assertIn("+00:00", body["generated_at"])

    def test_disabled_values_are_cache_only(self):
        products = [fake_candidate("B000000001", "Alpha")]
        write_cache(self.cache_path, products)
        for value in DISABLED_VALUES:
            with self.subTest(value=value), self._env(value):
                body = self._get(self._route_patches())
            self.assertEqual(body["status"], "ok", value)
            self.assertEqual(body["summary"]["scanner_mode"], "cache_only", value)
            self.assertEqual(body["summary"]["candidates_returned"], 1, value)

    # --- Phase 3.3: only explicit booleans enable the default provider ---

    def test_boolean_values_enable_default_provider(self):
        for value in ENABLED_BOOLEAN_VALUES:
            with self.subTest(value=value), self._env(value):
                self.assertEqual(offer_enrichment._enrichment_mode(), "BRIGHTDATA", value)

    def test_provider_tokens_remain_explicit_optins(self):
        for token in PROVIDER_TOKENS:
            with self.subTest(token=token), self._env(token):
                self.assertEqual(offer_enrichment._enrichment_mode(), token, token)

    # --- Phase 3.4 / 3.5: cache-only route behavior ---

    def test_missing_cache_returns_promptly_no_provider(self):
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
        with self._env(None):
            body = self._get(self._route_patches())
        self.assertEqual(body["status"], "no_candidates")
        self.assertEqual(body["summary"]["scanner_mode"], "cache_only")
        self.assertEqual(body["summary"]["cache_status"], "missing")
        self.assertEqual(body["products"], [])

    def test_corrupt_cache_is_honest_no_provider(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            f.write("{not valid json!!")
        with self._env("OFF"):
            body = self._get(self._route_patches())
        self.assertEqual(body["status"], "no_candidates")
        self.assertEqual(body["summary"]["cache_status"], "corrupt")
        self.assertEqual(body["products"], [])

    def test_stale_cache_reported_only_with_ttl_configured(self):
        products = [fake_candidate("B000000001", "Alpha")]
        write_cache(self.cache_path, products, fetched_at="2020-01-01T00:00:00+00:00")
        with self._env("OFF", extra={"SCANNER_SEARCH_CACHE_TTL_HOURS": "24"}):
            body = self._get(self._route_patches())
        self.assertEqual(body["summary"]["cache_status"], "stale")
        with self._env("OFF"):
            body = self._get(self._route_patches())
        self.assertEqual(body["summary"]["cache_status"], "fresh")

    # --- Phase 3.6: cache write only after a successful live search ---

    def test_cache_written_only_after_successful_live_search(self):
        candidates = [fake_candidate("B000000001", "Alpha"), fake_candidate("B000000002", "Beta", 41.0)]
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
        with self._env("BRIGHTDATA", extra={"SEARCH_KEYWORDS": "kirkland"}), \
             patch.object(product_analysis, "search_kirkland_products", return_value=candidates), \
             patch.object(amazon_search, "LAST_SEARCH_ERROR", None):
            got = product_analysis._candidates_for_mode()
        self.assertEqual(len(got), 2)
        with open(self.cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("+00:00", payload["fetched_at"])
        self.assertEqual(payload["source"], "brightdata")
        self.assertEqual(payload["search_terms"], ["kirkland"])
        self.assertEqual(payload["candidate_count"], 2)
        self.assertEqual(len(payload["products"]), 2)

    def test_failed_live_search_preserves_prior_cache(self):
        products = [fake_candidate("B000000001", "Alpha")]
        write_cache(self.cache_path, products)
        with self._env("BRIGHTDATA"), \
             patch.object(product_analysis, "search_kirkland_products", return_value=[]), \
             patch.object(amazon_search, "LAST_SEARCH_ERROR", "HTTP 500"):
            got = product_analysis._candidates_for_mode()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["asin"], "B000000001")
        with open(self.cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["fetched_at"], "2026-08-15T12:00:00+00:00")
        self.assertEqual(payload["candidate_count"], 1)

    def test_failed_live_search_with_no_cache_writes_nothing(self):
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
        with self._env("BRIGHTDATA"), \
             patch.object(product_analysis, "search_kirkland_products", return_value=[]), \
             patch.object(amazon_search, "LAST_SEARCH_ERROR", "timeout"):
            got = product_analysis._candidates_for_mode()
        self.assertEqual(got, [])
        self.assertFalse(os.path.exists(self.cache_path))

    def test_enabled_mode_uses_prior_cache_when_provider_fails(self):
        """Enabled mode with a provider error falls back to the cache
        instead of returning empty partial results."""
        products = [fake_candidate("B000000001", "Alpha")]
        write_cache(self.cache_path, products)
        with self._env("EASYPARSER"), \
             patch.object(product_analysis, "search_kirkland_products", return_value=[]), \
             patch.object(amazon_search, "LAST_SEARCH_ERROR", "HTTP 502"):
            got = product_analysis._candidates_for_mode()
        self.assertEqual([c["asin"] for c in got], ["B000000001"])


if __name__ == "__main__":
    unittest.main()