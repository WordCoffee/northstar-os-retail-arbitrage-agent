"""Offline test for the RapidAPI / DataForSEO provider switch (Easyparser disabled).

Zero network: RapidAPI requests are mocked at requests.get; DataForSEO tasks
are mocked at the adapter's _post_task/_get_task; the network guard blocks
any real call as a backstop. No live calls are made and no provider secrets
are read — module-level provider config is patched per test so a future .env
change can never arm a real transport during discovery.
"""

import os
import tempfile
import unittest
from typing import Any, Dict, List
from unittest import mock

import test_network_guard  # noqa: F401  (blocks real network calls)

import rapidapi_client
import dataforseo_adapter
import market_snapshot_store
import offer_enrichment

# Hermetic cache: keep the per-ASIN enrichment cache out of the real data file
# and disabled (TTL 0) so every test exercises the provider path deterministically.
_TEST_CACHE_PATH = os.path.join(tempfile.mkdtemp(prefix="provider-switch-test-"), "cache.json")
os.environ.setdefault("SCANNER_OFFER_CACHE_PATH", _TEST_CACHE_PATH)
os.environ.setdefault("SCANNER_OFFER_CACHE_TTL_HOURS", "0")


def _fake_response(status_code: int, payload: Dict[str, Any]):
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


class RapidApiAdapterTests(unittest.TestCase):
    def _enable_key(self):
        """Patch the module-level config so the test is hermetic: the module
        resolved RAPIDAPI_KEY from the environment at import time, so setting
        os.environ here would not change it — and relying on the real .env
        could arm a live, billed call."""
        for patcher in (
            mock.patch.object(rapidapi_client, "RAPIDAPI_KEY", "test-key"),
            mock.patch.object(rapidapi_client, "RAPIDAPI_HOST",
                              "amazon-product-data4.p.rapidapi.com"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_offers_normalizes_shape(self):
        self._enable_key()
        payload = {
            "product": {
                "asin": "B0TESTASIN",
                "title": "Test Product",
                "offers": [
                    {
                        "price": 19.99,
                        "is_buybox_winner": True,
                        "seller_name": "SellerA",
                        "seller_id": "A1",
                        "is_fba": True,
                        "condition": "New",
                    },
                    {
                        "price": 21.50,
                        "seller_name": "SellerB",
                        "is_fbm": True,
                    },
                ],
            },
            "cost": 1.0,
        }
        with mock.patch("requests.get", return_value=_fake_response(200, payload)):
            result = rapidapi_client.get_rapidapi_offers("B0TESTASIN")

        self.assertEqual(result["source"], "rapidapi")
        self.assertEqual(result["title"], "Test Product")
        self.assertEqual(result["offers_returned_count"], 2)
        self.assertEqual(result["buy_box_price"], 19.99)
        self.assertEqual(result["buy_box_seller"], "SellerA")
        self.assertEqual(result["observed_fba_offer_count"], 1)
        self.assertEqual(result["observed_fbm_offer_count"], 1)
        # cost 1.0 -> 100 cents
        self.assertEqual(result["credits_used"], 100)
        self.assertIn("offers", result)

    def test_missing_key_returns_gap_not_raises(self):
        with mock.patch.object(rapidapi_client, "RAPIDAPI_KEY", None):
            result = rapidapi_client.get_rapidapi_offers("B0TESTASIN")
        self.assertEqual(result["source"], "rapidapi")
        self.assertTrue(any("API key" in g for g in result["data_gaps"]))
        self.assertEqual(result["offers_returned_count"], 0)

    def test_parse_bsr_variants(self):
        gaps: List[str] = []
        none_bsr = rapidapi_client._parse_bsr({}, gaps)
        self.assertEqual(none_bsr["bsr_capture_status"], "unavailable")
        self.assertTrue(any("BSR not returned" in g for g in gaps))

        ok_bsr = rapidapi_client._parse_bsr(
            {"salesRank": "#1,291 in Video Games"}, []
        )
        self.assertEqual(ok_bsr["bsr_primary_rank"], 1291)
        self.assertEqual(ok_bsr["bsr_primary_category"], "Video Games")
        self.assertIn(ok_bsr["bsr_capture_status"], ("verified", "primary", "available"))


class DataForSeoAdapterTests(unittest.TestCase):
    def setUp(self):
        # Hermetic module config: patch what the adapter actually reads at
        # call time. Without this, the .env DATAFORSEO_* values resolved at
        # import can arm a real (billed) transport during discovery.
        self._config = mock.patch.multiple(
            dataforseo_adapter,
            DATAFORSEO_ENABLED=True,
            DATAFORSEO_TRANSPORT_ENABLED=True,
            DATAFORSEO_LOGIN="offline-test-user",
            DATAFORSEO_PASSWORD="offline-test-pass",
        )
        self._config.start()
        self.addCleanup(self._config.stop)

    def _mock_tasks(self):
        asin_post = {"accepted": True, "task_id": "a1", "provider_cost_cents": 25.0}
        asin_get = {
            "accepted": True,
            "task_id": "a1",
            "result_item": {
                "items": [
                    {
                        "data_asin": "B0TESTASIN",
                        "title": "DF Product",
                        "price_from": 9.99,
                    }
                ]
            },
        }
        sellers_post = {"accepted": True, "task_id": "s1", "provider_cost_cents": 50.0}
        sellers_get = {
            "accepted": True,
            "task_id": "s1",
            "result_item": {
                "items": [
                    {
                        "seller_name": "S1",
                        "seller_url": "https://www.amazon.com/sp?seller=A1&isAmazonFulfilled=1",
                        "price": {"current": 9.99},
                        "buybox_winner": True,
                    },
                    {
                        "seller_name": "S2",
                        "seller_url": "https://www.amazon.com/sp?seller=A2&isAmazonFulfilled=0",
                        "price": {"current": 10.50},
                    },
                ]
            },
        }
        return asin_post, asin_get, sellers_post, sellers_get

    def test_offers_honest_gaps(self):
        """Nothing DataForSEO omits is invented: no price_from -> null Buy
        Box price + explicit gap; no BSR -> explicit gap; no flagged Buy Box
        winner -> null winner + explicit gap. FBA/FBM derived ONLY from
        isAmazonFulfilled in seller_url (never guessed)."""
        asin_post, asin_get, sellers_post, sellers_get = self._mock_tasks()
        # Purge the fields providers may genuinely omit so every gap path fires.
        asin_get["result_item"]["items"][0].pop("price_from", None)
        sellers_get["result_item"]["items"][0].pop("buybox_winner", None)
        with mock.patch.object(dataforseo_adapter, "_post_task",
                               side_effect=[asin_post, sellers_post]) as mp, \
                mock.patch.object(dataforseo_adapter, "_get_task",
                                  side_effect=[asin_get, sellers_get]) as mg:
            result = dataforseo_adapter.get_dataforseo_offers("B0TESTASIN")

        self.assertEqual(result["source"], "dataforseo")
        # asin task has no price_from -> null, never invented
        self.assertIsNone(result["buy_box_price"])
        self.assertTrue(any("missing current price (price_from)" in g
                            for g in result["data_gaps"]))
        # BSR not supplied -> honest gap
        self.assertTrue(any("BSR not present" in g for g in result["data_gaps"]))
        # sellers task flags no Buy Box winner -> null + explicit gap
        self.assertIsNone(result["buy_box_seller"])
        self.assertTrue(any("does not flag a Buy Box winner" in g
                            for g in result["data_gaps"]))
        # offers still map; FBA/FBM derived only from isAmazonFulfilled
        self.assertEqual(result["offers_returned_count"], 2)
        self.assertEqual(result["offer_count"], 2)
        self.assertEqual(result["observed_fba_offer_count"], 1)
        self.assertEqual(result["observed_fbm_offer_count"], 1)
        # observed Amazon count comes only from an explicit "Amazon" seller
        self.assertEqual(result["observed_amazon_offer_count"], 0)

    def test_disabled_returns_gap(self):
        with mock.patch.object(dataforseo_adapter, "DATAFORSEO_ENABLED", False):
            result = dataforseo_adapter.get_dataforseo_offers("B0TESTASIN")
        self.assertEqual(result["source"], "dataforseo")
        self.assertTrue(any("not enabled" in g for g in result["data_gaps"]))
        self.assertEqual(result["offers_returned_count"], 0)


class BuildSnapshotTests(unittest.TestCase):
    def test_source_propagated(self):
        result = rapidapi_client._empty_result("B0TESTASIN")
        result["title"] = "X"
        result["offers_returned_count"] = 1
        snap = market_snapshot_store.build_snapshot("B0TESTASIN", result, prior_attempts=0)
        self.assertEqual(snap.get("source"), "rapidapi")

        df = dataforseo_adapter._empty_result("B0DF000000")
        df["title"] = "Y"
        snap2 = market_snapshot_store.build_snapshot("B0DF000000", df, prior_attempts=0)
        self.assertEqual(snap2.get("source"), "dataforseo")


class OfferEnrichmentSwitchTests(unittest.TestCase):
    def test_easyparser_mode_degrades(self):
        with mock.patch.dict(os.environ, {
            "SCANNER_LIVE_ALLOWED": "1",
            "SCANNER_OFFER_ENRICHMENT": "EASYPARSER",
        }, clear=False):
            shape = offer_enrichment.get_scanner_offer("B0TESTASIN")
        # Easyparser is a disabled/deprecated token: _enrichment_mode maps it
        # to OFF, so the result is the offline placeholder with an explicit
        # no_provider_configured status — never a live provider call.
        self.assertEqual(shape.get("offer_data_provider"), "offline")
        self.assertEqual(shape.get("enrichment_status"), "no_provider_configured")

    def test_rapidapi_mode_maps(self):
        # Hermetic RapidAPI config (module constants, not os.environ).
        for patcher in (
            mock.patch.object(rapidapi_client, "RAPIDAPI_KEY", "test-key"),
            mock.patch.object(rapidapi_client, "RAPIDAPI_HOST",
                              "amazon-product-data4.p.rapidapi.com"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        payload = {
            "product": {
                "asin": "B0TESTASIN",
                "title": "Test Product",
                "offers": [{"price": 12.0, "is_buybox_winner": True,
                            "seller_name": "SA"}],
            },
            "cost": 1.0,
        }
        with mock.patch.dict(os.environ, {
            "SCANNER_LIVE_ALLOWED": "1",
            "SCANNER_OFFER_ENRICHMENT": "RAPIDAPI",
        }, clear=False), \
                mock.patch("requests.get",
                           return_value=_fake_response(200, payload)):
            shape = offer_enrichment.get_scanner_offer("B0TESTASIN")
        # RAPIDAPI dispatches through the shared Easyparser-shaped mapper, so
        # the mapping provenance label is "easyparser" while enrichment_status
        # uses the complete/partial vocabulary.
        self.assertEqual(shape.get("offer_data_provider"), "easyparser")
        self.assertEqual(shape.get("buy_box_price"), 12.0)
        self.assertIn(shape.get("enrichment_status"), ("complete", "partial"))


if __name__ == "__main__":
    unittest.main()