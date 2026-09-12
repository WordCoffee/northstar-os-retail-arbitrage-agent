import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException

import main
import offer_enrichment


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)

_TEST_SELLER_CACHE_PATH = os.path.join(
    tempfile.gettempdir(), "northstar-seller-cache-route-test.json"
)


def _fake_offers():
    return {
        "source": "easyparser",
        "asin": "B00GYZWNY6",
        "title": "Fake Offer Product",
        "offer_count": 12,
        "offers_returned_count": 2,
        "buy_box_price": 56.66,
        "buy_box_price_raw": {"value": 56.66, "raw": "$56.66", "currency": "USD"},
        "buy_box_seller": "Amazon.com",
        "buy_box_seller_id": "A1",
        "buy_box_is_fba": True,
        "buy_box_is_fbm": False,
        "buy_box_is_prime": True,
        "buy_box_condition": {"is_new": True, "title": "New"},
        "observed_fba_offer_count": 1,
        "observed_fbm_offer_count": 1,
        "observed_amazon_offer_count": 1,
        "offers": [
            {
                "position": 1,
                "buybox_winner": True,
                "price": {"value": 56.66, "currency": "USD"},
                "condition": {"is_new": True, "title": "New"},
                "seller_id": "A1",
                "seller_name": "Amazon.com",
                "seller_rating": 4.9,
                "seller_ratings_total": 1000,
                "is_prime": True,
                "is_fba": True,
                "is_fbm": False,
                "shipping_is_free": True,
                "shipping_text": "FREE Shipping",
            },
            {
                "position": 2,
                "buybox_winner": False,
                "price": 55.0,
                "seller_id": "A2",
                "seller_name": "Some Seller",
                "is_fba": False,
                "is_fbm": True,
            },
        ],
        "request_zip_code": "19805",
        "observed_at": "2026-01-01T00:00:01Z",
        "credits_used": 1,
        "credits_remaining": 999,
        "data_gaps": [],
    }


def _clear_seller_cache():
    path = offer_enrichment._seller_cache_path()
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


class TestOffersRoute(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(
            os.environ,
            {
                "SCANNER_SELLER_CACHE_PATH": _TEST_SELLER_CACHE_PATH,
                "SCANNER_SELLER_CACHE_TTL_HOURS": "24",
                "EASYPARSER_API_KEY": "test-key",
            },
            clear=False,
        )
        self._env.start()
        _clear_seller_cache()

    def tearDown(self):
        _clear_seller_cache()
        self._env.stop()

    def test_valid_asin_calls_client_exactly_once(self):
        with patch.object(
            offer_enrichment, "get_easyparser_offers", return_value=_fake_offers()
        ) as mocked:
            result = main.get_product_offers("B00GYZWNY6")

        mocked.assert_called_once_with("B00GYZWNY6")
        self.assertEqual(result["enrichment_source"], "easyparser")
        self.assertEqual(result["enrichment_scope"], "one_explicit_asin")
        self.assertEqual(result["buy_box_price"], 56.66)
        self.assertEqual(result["request_zip_code"], "19805")
        self.assertEqual(result["offer_data_status"], "partial")
        self.assertEqual(result["offers_complete"], False)
        self.assertEqual(len(result["offers"]), 2)

    def test_roster_contract_fields_present(self):
        with patch.object(
            offer_enrichment, "get_easyparser_offers", return_value=_fake_offers()
        ):
            result = main.get_product_offers("B00GYZWNY6")

        self.assertEqual(result["total_sellers"], 12)
        self.assertEqual(result["fba_sellers"], 1)
        self.assertEqual(result["fbm_sellers"], 1)
        self.assertEqual(result["amazon_sellers"], 1)
        self.assertEqual(result["buy_box"]["seller_name"], "Amazon.com")
        self.assertEqual(result["buy_box"]["fulfillment"], "Amazon")
        self.assertTrue(result["buy_box"]["available"])
        winner = result["offers"][0]
        self.assertTrue(winner["is_buy_box_winner"])
        self.assertEqual(winner["fulfillment"], "Amazon")
        self.assertEqual(winner["price"], 56.66)
        self.assertIsNone(winner["shipping"])
        self.assertIsNone(winner["landed_price"])
        self.assertEqual(result["offers"][1]["fulfillment"], "FBM")

    def test_invalid_asin_returns_400_and_zero_calls(self):
        with patch.object(offer_enrichment, "get_easyparser_offers") as mocked:
            try:
                main.get_product_offers("bad")
            except HTTPException as e:
                self.assertEqual(e.status_code, 400)
                self.assertEqual(
                    e.detail,
                    "Invalid ASIN. Expected a 10-character alphanumeric Amazon ASIN.",
                )
            else:
                raise AssertionError("expected HTTPException for invalid ASIN")

        mocked.assert_not_called()

    def test_metadata_fields_returned(self):
        with patch.object(
            offer_enrichment, "get_easyparser_offers", return_value=_fake_offers()
        ):
            result = main.get_product_offers("B00GYZWNY6")
        self.assertIn("enrichment_source", result)
        self.assertIn("enrichment_scope", result)
        self.assertEqual(result["enrichment_source"], "easyparser")
        self.assertEqual(result["enrichment_scope"], "one_explicit_asin")

    def test_cache_hit_serves_without_provider_call(self):
        with patch.object(
            offer_enrichment, "get_easyparser_offers", return_value=_fake_offers()
        ):
            first = main.get_product_offers("B00GYZWNY6")
        self.assertEqual(first["offer_data_cached"], False)
        with patch.object(offer_enrichment, "get_easyparser_offers") as mocked:
            second = main.get_product_offers("B00GYZWNY6")
        mocked.assert_not_called()
        self.assertTrue(second["offer_data_cached"])

    def test_provider_error_has_no_fake_counts(self):
        fake = _fake_offers()
        fake["offers"] = []
        fake["offer_count"] = None
        fake["observed_fba_offer_count"] = None
        fake["buy_box_price"] = None
        fake["buy_box_seller"] = None
        fake["data_gaps"] = ["Easyparser request failed at the network level."]
        with patch.object(
            offer_enrichment, "get_easyparser_offers", return_value=fake
        ):
            result = main.get_product_offers("B00GYZWNY6")

        self.assertEqual(result["offer_data_status"], "provider_error")
        self.assertIsNone(result["total_sellers"])
        self.assertEqual(result["offers"], [])
        self.assertFalse(result["buy_box"]["available"])

    def test_provider_error_is_not_cached(self):
        fake = _fake_offers()
        fake["offers"] = []
        fake["offer_count"] = None
        fake["data_gaps"] = ["Easyparser request failed at the network level."]
        with patch.object(
            offer_enrichment, "get_easyparser_offers", return_value=fake
        ) as mocked:
            first = main.get_product_offers("B00GYZWNY6")
        self.assertEqual(first["offer_data_status"], "provider_error")
        with patch.object(offer_enrichment, "get_easyparser_offers") as mocked:
            main.get_product_offers("B00GYZWNY6")
        mocked.assert_called_once()  # not cached -> provider called again


if __name__ == "__main__":
    unittest.main(verbosity=2)