"""Offline unit tests for offer_enrichment provider selection and mapping.

Never touches Easyparser, Bright Data, or any network: the provider
functions are mocked; only the mapping/flag logic runs for real.
"""

import json
import os
import tempfile
import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import offer_enrichment

# Hermetic cache: every test reads/writes the per-ASIN enrichment cache in a
# temp dir so the real data/enriched-offer-cache.json is never touched. The
# cache is DISABLED globally (TTL 0) so mapping tests can never cross-pollute
# each other; EnrichmentCacheTests re-enables it per-test with a clean file.
_TEST_CACHE_PATH = os.path.join(tempfile.mkdtemp(prefix="offer-cache-test-"), "cache.json")
os.environ.setdefault("SCANNER_OFFER_CACHE_PATH", _TEST_CACHE_PATH)
os.environ.setdefault("SCANNER_OFFER_CACHE_TTL_HOURS", "0")


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)


@contextmanager
def enrichment_mode(mode):
    with patch.dict(os.environ, {"SCANNER_OFFER_ENRICHMENT": mode}):
        yield


def easyparser_payload(offer_count=5, fba_count=2, buy_box_price=48.87):
    return {
        "source": "easyparser",
        "asin": "B000000001",
        "title": "Kirkland Test Item",
        "offer_count": offer_count,
        "buy_box_price": buy_box_price,
        "observed_fba_offer_count": fba_count,
        "observed_fbm_offer_count": offer_count - fba_count,
        "offers": [
            {
                "position": 1,
                "buybox_winner": True,
                "price": {"value": buy_box_price},
                "is_fba": True,
                "is_fbm": False,
                "seller_name": "Amazon.com",
            },
            {
                "position": 2,
                "buybox_winner": False,
                "price": {"value": buy_box_price + 5.0},
                "is_fba": True,
                "is_fbm": False,
                "seller_name": "Seller Two",
            },
            {
                "position": 3,
                "buybox_winner": False,
                "price": {"value": buy_box_price - 3.0},
                "is_fba": False,
                "is_fbm": True,
                "seller_name": "Seller Three",
            },
        ],
    }


def brightdata_payload():
    return {
        "asin": "B000000001",
        "title": "Kirkland Test Item",
        "amazon_price": 48.87,
        "buy_box_price": 48.87,
        "lowest_price": 45.87,
        "highest_price": 53.87,
        "seller_count": 5,
        "fba_sellers": 2,
        "fba_fee": 9.25,
        "monthly_sales_estimate": 1200,
        "monthly_sales_estimated": True,
        "sellers": [],
    }


def failed_easyparser_payload():
    """Real provider-failure shape: everything the ranking needs is null."""
    payload = dict(easyparser_payload())
    payload["offers"] = []
    payload["offer_count"] = None
    payload["observed_fba_offer_count"] = None
    payload["observed_fbm_offer_count"] = None
    payload["buy_box_price"] = None
    payload["title"] = None
    return payload


def offline_shape(status="no_provider_configured"):
    return {
        "amazon_price": 0,
        "buy_box_price": None,
        "lowest_price": None,
        "highest_price": None,
        "total_sellers": None,
        "fba_sellers": None,
        "fba_sellers_estimated": False,
        "lowest_price_seller_type": "unknown",
        "highest_price_seller_type": "unknown",
        "monthly_sales_estimate": None,
        "monthly_sales_estimated": False,
        "fba_fee": None,
        "offer_data_provider": "offline",
        "enrichment_status": status,
        "enriched_at": None,
    }


class ModeSelectionTests(unittest.TestCase):
    def test_off_mode_returns_offline_placeholder(self):
        with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()) as mock_get:
            with enrichment_mode("OFF"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        mock_get.assert_called_once()
        self.assertEqual(result, offline_shape())

    def test_unset_mode_is_offline_cache_only(self):
        """Unset must mean cache-only: zero provider calls (the approved
        contract change from the old unset=>BRIGHTDATA default)."""
        with patch.dict(os.environ, {"SCANNER_OFFER_CACHE_PATH": _TEST_CACHE_PATH, "SCANNER_OFFER_CACHE_TTL_HOURS": "0"}, clear=True):
            with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()) as mock_get:
                result = offer_enrichment.get_scanner_offer("B000000001")
        mock_get.assert_called_once()
        self.assertEqual(result["offer_data_provider"], "offline")

    def test_invalid_mode_returns_offline_placeholder(self):
        with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()) as mock_get:
            with enrichment_mode("SOMETHING_ELSE"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        mock_get.assert_called_once()
        self.assertEqual(result, offline_shape())


class EasyparserMappingTests(unittest.TestCase):
    def test_maps_offer_counts_buybox_and_range(self):
        with patch.object(offer_enrichment, "get_rapidapi_offers", return_value=easyparser_payload()):
            with enrichment_mode("RAPIDAPI"):
                result = offer_enrichment.get_scanner_offer("B000000001")

        self.assertEqual(result["amazon_price"], 48.87)
        self.assertEqual(result["total_sellers"], 5)
        self.assertEqual(result["fba_sellers"], 2)
        self.assertEqual(result["fba_sellers_estimated"], False)
        self.assertEqual(result["lowest_price"], 45.87)
        self.assertEqual(result["highest_price"], 53.87)
        self.assertEqual(result["lowest_price_seller_type"], "FBM")
        self.assertEqual(result["highest_price_seller_type"], "FBA")
        self.assertIsNone(result["fba_fee"])
        self.assertIsNone(result["monthly_sales_estimate"])
        self.assertEqual(result["title"], "Kirkland Test Item")
        self.assertEqual(result["offer_data_provider"], "easyparser")
        self.assertEqual(result["enrichment_status"], "complete")
        self.assertIsNotNone(result["enriched_at"])

    def test_extracts_asin_from_url(self):
        mock_get = patch.object(offer_enrichment, "get_rapidapi_offers", return_value=easyparser_payload()).start()
        try:
            with enrichment_mode("RAPIDAPI"):
                offer_enrichment.get_scanner_offer("https://www.amazon.com/dp/B000000001")
        finally:
            mock_get.stop()
        mock_get.assert_called_once_with("B000000001")

    def test_invalid_asin_falls_back_to_placeholder(self):
        mock_get = patch.object(offer_enrichment, "get_rapidapi_offers").start()
        try:
            with enrichment_mode("RAPIDAPI"):
                with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()) as mock_offline:
                    result = offer_enrichment.get_scanner_offer("not-an-asin")
        finally:
            mock_get.stop()
        mock_get.assert_not_called()
        self.assertEqual(result, offline_shape("invalid_asin"))

    def test_provider_failure_returns_null_shape_without_raising(self):
        with patch.object(offer_enrichment, "get_rapidapi_offers", return_value=failed_easyparser_payload()):
            with enrichment_mode("RAPIDAPI"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertIsNone(result["amazon_price"], "no Buy Box price stays None, never 0")
        self.assertIsNone(result["total_sellers"])
        self.assertIsNone(result["lowest_price"])
        self.assertIsNone(result["highest_price"])
        self.assertEqual(result["offer_data_provider"], "easyparser")
        self.assertEqual(result["enrichment_status"], "provider_rejected")


class AutoModeTests(unittest.TestCase):
    def test_auto_uses_rapidapi_when_complete(self):
        mock_bd = patch.object(offer_enrichment, "enrich_product").start()
        try:
            with patch.object(offer_enrichment, "get_rapidapi_offers", return_value=easyparser_payload()):
                with enrichment_mode("AUTO"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        finally:
            mock_bd.stop()
        mock_bd.assert_not_called()
        self.assertEqual(result["offer_data_provider"], "easyparser")
        self.assertEqual(result["enrichment_status"], "complete")

    def test_auto_falls_back_to_brightdata_when_rapidapi_incomplete(self):
        payload = dict(easyparser_payload())
        payload["offer_count"] = None
        payload["observed_fba_offer_count"] = None
        payload["observed_fbm_offer_count"] = None
        payload["buy_box_price"] = None
        with patch.object(offer_enrichment, "get_rapidapi_offers", return_value=payload):
            with patch.object(offer_enrichment, "enrich_product", return_value=brightdata_payload()):
                with enrichment_mode("AUTO"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["offer_data_provider"], "brightdata")
        self.assertEqual(result["enrichment_status"], "complete")
        self.assertEqual(result["total_sellers"], 5)
        self.assertEqual(result["fba_fee"], 9.25)

    def test_auto_brightdata_partial_still_wins_over_broken_rapidapi(self):
        bd = dict(brightdata_payload())
        bd["seller_count"] = None
        with patch.object(offer_enrichment, "get_rapidapi_offers", return_value=failed_easyparser_payload()):
            with patch.object(offer_enrichment, "enrich_product", return_value=bd):
                with enrichment_mode("AUTO"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["offer_data_provider"], "brightdata")
        self.assertEqual(result["enrichment_status"], "partial")
        self.assertEqual(result["amazon_price"], 48.87)

    def test_auto_both_fail_returns_best_effort_without_raising(self):
        with patch.object(offer_enrichment, "get_rapidapi_offers", return_value=failed_easyparser_payload()):
            with patch.object(offer_enrichment, "enrich_product", return_value=None):
                with enrichment_mode("AUTO"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["offer_data_provider"], "easyparser")
        self.assertEqual(result["enrichment_status"], "provider_rejected")
        self.assertIsNone(result["total_sellers"])

    def test_auto_invalid_asin_goes_offline(self):
        with patch.object(offer_enrichment, "get_rapidapi_offers") as mock_ep:
            with patch.object(offer_enrichment, "enrich_product") as mock_bd:
                with enrichment_mode("AUTO"):
                    result = offer_enrichment.get_scanner_offer("not-an-asin")
        mock_ep.assert_not_called()
        mock_bd.assert_not_called()
        self.assertEqual(result["offer_data_provider"], "offline")
        self.assertEqual(result["enrichment_status"], "invalid_asin")


class BrightdataMappingTests(unittest.TestCase):
    def test_maps_brightdata_fields_including_fee_and_demand(self):
        with patch.object(offer_enrichment, "get_product_detail", return_value=brightdata_payload()):
            with enrichment_mode("BRIGHTDATA"):
                result = offer_enrichment.get_scanner_offer("B000000001")

        self.assertEqual(result["amazon_price"], 48.87)
        self.assertEqual(result["total_sellers"], 5)
        self.assertEqual(result["fba_sellers"], 2)
        self.assertEqual(result["lowest_price"], 45.87)
        self.assertEqual(result["highest_price"], 53.87)
        self.assertEqual(result["fba_fee"], 9.25)
        self.assertEqual(result["monthly_sales_estimate"], 1200)
        self.assertIs(result["monthly_sales_estimated"], True)
        self.assertEqual(result["offer_data_provider"], "brightdata")
        self.assertEqual(result["enrichment_status"], "complete")
        self.assertIsNotNone(result["enriched_at"])

    def test_missing_price_is_none_not_zero(self):
        payload = dict(brightdata_payload())
        payload["amazon_price"] = None
        payload["buy_box_price"] = None
        with patch.object(offer_enrichment, "get_product_detail", return_value=payload):
            with enrichment_mode("BRIGHTDATA"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertIsNone(result["amazon_price"])

    def test_provider_failure_returns_placeholder_without_raising(self):
        with patch.object(offer_enrichment, "get_product_detail", return_value={}):
            with enrichment_mode("BRIGHTDATA"):
                with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result, offline_shape())

    def test_missing_api_key_returns_placeholder_without_raising(self):
        with patch.object(offer_enrichment, "get_product_detail", side_effect=ValueError("BRIGHTDATA_UNLOCKER_API_KEY not set")):
            with enrichment_mode("BRIGHTDATA"):
                with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result, offline_shape())

    def test_invalid_asin_goes_offline(self):
        with patch.object(offer_enrichment, "get_product_detail") as mock_bd:
            with enrichment_mode("BRIGHTDATA"):
                result = offer_enrichment.get_scanner_offer("not-an-asin")
        mock_bd.assert_not_called()
        self.assertEqual(result["offer_data_provider"], "offline")
        self.assertEqual(result["enrichment_status"], "invalid_asin")


def chocodata_product_payload():
    return {
        "asin": "B000000001",
        "title": "KIRKLAND Signature Women's Travel Pant",
        "product_name": "KIRKLAND Signature Women's Travel Pant",
        "brand": "KIRKLAND",
        "price": 38.99,
        "price_buybox": 38.99,
        "highest_price": 38.99,
        "pricing_count": 1,
        "pricing_str": "New (4) from $28.99$28.99 FREE Shipping on orders over $35.00 shipped by Amazon.",
        "other_sellers": "New (4) from $28.99$28.99 FREE Shipping on orders over $35.00 shipped by Amazon.",
        "sales_rank": {"ladder": [{"name": "Women's Hiking Pants", "url": None}], "rank": 263},
        "rating": 4.8,
        "reviews_count": 13,
        "product_details": {"item_weight": "11.2 ounces", "brand_name": "KIRKLAND"},
    }


class ChocodataMappingTests(unittest.TestCase):
    def test_maps_buybox_weight_fee_and_rank(self):
        with patch.object(offer_enrichment, "_fetch_chocodata_product", return_value=chocodata_product_payload()):
            with enrichment_mode("CHOCODATA"):
                result = offer_enrichment.get_scanner_offer("B000000001")

        self.assertEqual(result["amazon_price"], 38.99)
        self.assertEqual(result["buy_box_price"], 38.99)
        self.assertEqual(result["total_sellers"], 4)
        self.assertEqual(result["lowest_price"], 28.99)
        self.assertEqual(result["highest_price"], 38.99)
        self.assertAlmostEqual(result["weight_lbs"], 11.2 / 16.0, places=5)
        self.assertEqual(result["fba_fee"], 5.25)
        self.assertEqual(result["sales_rank"], 263)
        self.assertEqual(result["rating"], 4.8)
        self.assertEqual(result["reviews_count"], 13)
        self.assertEqual(result["title"], "KIRKLAND Signature Women's Travel Pant")
        self.assertEqual(result["offer_data_provider"], "chocodata")
        self.assertEqual(result["enrichment_status"], "partial")

    def test_maps_heavier_weight_to_higher_fee(self):
        payload = chocodata_product_payload()
        payload["product_details"] = {"item_weight": "2.8 pounds"}
        with patch.object(offer_enrichment, "_fetch_chocodata_product", return_value=payload):
            with enrichment_mode("CHOCODATA"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["weight_lbs"], 2.8)
        self.assertEqual(result["fba_fee"], 7.10)

    def test_fetch_failure_returns_offline_placeholder(self):
        with patch.object(offer_enrichment, "_fetch_chocodata_product", return_value={}):
            with enrichment_mode("CHOCODATA"):
                with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result, offline_shape())

    def test_missing_api_key_returns_empty_without_raising(self):
        with patch.object(offer_enrichment, "CHOCODATA_API_KEY", ""):
            with patch.object(offer_enrichment, "requests") as mock_requests:
                data = offer_enrichment._fetch_chocodata_product("B000000001")
        mock_requests.get.assert_not_called()
        self.assertIs(data.get("ok"), False)
        self.assertEqual(data["failure_class"], "not_configured")
        self.assertEqual(data["failure_detail"], "CHOCODATA_API_KEY not set")

    def test_non_200_fetch_returns_empty(self):
        response = unittest.mock.Mock(status_code=402, text="{}", json=lambda: {})
        with patch.object(offer_enrichment, "requests") as mock_requests:
            mock_requests.get.return_value = response
            data = offer_enrichment._fetch_chocodata_product("B000000001")
        self.assertIs(data.get("ok"), False)
        self.assertEqual(data["failure_class"], "transport_error")
        self.assertEqual(data["status_code"], 402)

    def test_parse_weight_units(self):
        self.assertAlmostEqual(offer_enrichment._parse_weight_lbs("11.2 ounces"), 0.7, places=5)
        self.assertAlmostEqual(offer_enrichment._parse_weight_lbs("2.8 pounds"), 2.8, places=5)
        self.assertAlmostEqual(offer_enrichment._parse_weight_lbs("1.5 kg"), 3.30693, places=4)
        self.assertAlmostEqual(offer_enrichment._parse_weight_lbs("500 g"), 1.10231, places=4)
        self.assertIsNone(offer_enrichment._parse_weight_lbs(None))
        self.assertIsNone(offer_enrichment._parse_weight_lbs("no weight here"))

    def test_seller_count_and_price_from_pricing_str(self):
        pricing = "New (7) from $12.34$12.34 FREE delivery"
        self.assertEqual(offer_enrichment._extract_seller_count(pricing), 7)
        self.assertEqual(offer_enrichment._extract_price_from(pricing), 12.34)
        self.assertIsNone(offer_enrichment._extract_seller_count("no offers listed"))
        self.assertIsNone(offer_enrichment._extract_price_from("no offers listed"))


def unwrangle_amazon_detail_payload():
    return {
        "name": "KIRKLAND Signature Women's Travel Pant",
        "brand": "KIRKLAND",
        "asin": "B000000001",
        "price": 391.95,
        "price_reduced": 377.0,
        "currency": "USD",
        "buying_offers": [
            {"offer_type": "Refurbished - Excellent", "price": 377.0, "seller": "Seller A"},
            {"offer_type": "Refurbished - Good", "price": 323.36, "seller": "Seller B"},
        ],
        "other_sellers": {"text": "New (4) from", "link": "https://example.invalid/offers"},
        "rating": 4.1,
        "total_ratings": 13214,
        "past_month_sales": "1K+ boughtin past month",
        "details_table": [
            {"name": "Item Weight", "value": "11.2 ounces"},
            {"name": "ASIN", "value": "B000000001"},
        ],
        "bestseller_ranks": [
            {"name": "See Top 100 in Amazon Renewed", "rank": 7},
            {"name": "Renewed Smartphones", "rank": 3},
        ],
    }


class UnwrangleMappingTests(unittest.TestCase):
    def test_maps_sale_price_weight_fee_rank_and_sales(self):
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value=unwrangle_amazon_detail_payload()):
            with enrichment_mode("UNWRANGLE"):
                result = offer_enrichment.get_scanner_offer("B000000001")

        self.assertEqual(result["amazon_price"], 377.0)
        self.assertEqual(result["buy_box_price"], 377.0)
        self.assertEqual(result["lowest_price"], 323.36)
        self.assertEqual(result["highest_price"], 391.95)
        self.assertEqual(result["total_sellers"], 2)
        self.assertAlmostEqual(result["weight_lbs"], 11.2 / 16.0, places=5)
        self.assertEqual(result["fba_fee"], 5.25)
        self.assertEqual(result["sales_rank"], 3)
        self.assertEqual(result["monthly_sales_estimate"], 1000)
        self.assertIs(result["monthly_sales_estimated"], True)
        self.assertEqual(result["rating"], 4.1)
        self.assertEqual(result["reviews_count"], 13214)
        self.assertEqual(result["title"], "KIRKLAND Signature Women's Travel Pant")
        self.assertEqual(result["offer_data_provider"], "unwrangle")
        self.assertEqual(result["enrichment_status"], "partial")

    def test_buybox_prefers_price_when_no_sale_price(self):
        payload = unwrangle_amazon_detail_payload()
        payload["price_reduced"] = None
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value=payload):
            with enrichment_mode("UNWRANGLE"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["amazon_price"], 391.95)
        self.assertEqual(result["highest_price"], 391.95)

    def test_maps_heavier_weight_to_higher_fee(self):
        payload = unwrangle_amazon_detail_payload()
        payload["details_table"] = [{"name": "Item Weight", "value": "2.8 pounds"}]
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value=payload):
            with enrichment_mode("UNWRANGLE"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["weight_lbs"], 2.8)
        self.assertEqual(result["fba_fee"], 7.10)

    def test_missing_weight_leaves_fee_none(self):
        payload = unwrangle_amazon_detail_payload()
        payload["details_table"] = []
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value=payload):
            with enrichment_mode("UNWRANGLE"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertIsNone(result["weight_lbs"])
        self.assertIsNone(result["fba_fee"])

    def test_weight_parsed_from_package_dimensions_row(self):
        payload = unwrangle_amazon_detail_payload()
        payload["details_table"] = [
            {"name": "PackageDimensions", "value": "8.7x8.62x5.08inches;5.25pounds"},
            {"name": "Itemmodelnumber", "value": "1472215"},
        ]
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value=payload):
            with enrichment_mode("UNWRANGLE"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["weight_lbs"], 5.25)
        self.assertEqual(result["fba_fee"], 9.90)

    def test_no_offers_falls_back_to_other_sellers_text(self):
        payload = unwrangle_amazon_detail_payload()
        payload["buying_offers"] = []
        payload["other_sellers"] = {"text": "New (7) from $12.34", "link": None}
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value=payload):
            with enrichment_mode("UNWRANGLE"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["total_sellers"], 7)
        self.assertEqual(result["lowest_price"], 12.34)

    def test_fetch_failure_returns_offline_placeholder(self):
        with patch.object(offer_enrichment, "_fetch_unwrangle_amazon_detail", return_value={}):
            with enrichment_mode("UNWRANGLE"):
                with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result, offline_shape())

    def test_missing_api_key_returns_empty_without_raising(self):
        with patch.object(offer_enrichment, "UNWRANGLE_API_KEY", ""):
            with patch.object(offer_enrichment, "requests") as mock_requests:
                data = offer_enrichment._fetch_unwrangle_amazon_detail("B000000001")
        mock_requests.get.assert_not_called()
        self.assertIs(data.get("ok"), False)
        self.assertEqual(data["failure_class"], "not_configured")
        self.assertEqual(data["failure_detail"], "UNWRANGLE_API_KEY not set")

    def test_non_200_fetch_returns_empty(self):
        response = unittest.mock.Mock(status_code=402, text="{}", json=lambda: {})
        with patch.object(offer_enrichment, "requests") as mock_requests:
            mock_requests.get.return_value = response
            data = offer_enrichment._fetch_unwrangle_amazon_detail("B000000001")
        self.assertIs(data.get("ok"), False)
        self.assertEqual(data["failure_class"], "transport_error")
        self.assertEqual(data["status_code"], 402)

    def test_detail_requests_use_asin_and_us_country(self):
        response = unittest.mock.Mock(status_code=200, json=lambda: {"success": True, "detail": {}})
        with patch.object(offer_enrichment, "requests") as mock_requests:
            mock_requests.get.return_value = response
            data = offer_enrichment._fetch_unwrangle_amazon_detail("B000000001")
        args, kwargs = mock_requests.get.call_args
        self.assertEqual(kwargs["params"]["platform"], "amazon_detail")
        self.assertEqual(kwargs["params"]["asin"], "B000000001")
        self.assertEqual(kwargs["params"]["country_code"], "us")
        self.assertEqual(data, {})

    def test_parse_monthly_sales_strings(self):
        self.assertEqual(offer_enrichment._parse_monthly_sales("1K+ bought in past month"), 1000)
        self.assertAlmostEqual(
            offer_enrichment._parse_monthly_sales("200+ bought in past week"), 200 * 4.33, places=4
        )
        self.assertAlmostEqual(
            offer_enrichment._parse_monthly_sales("50+ bought in past day"), 50 * 30.4, places=4
        )
        self.assertIsNone(offer_enrichment._parse_monthly_sales(None))
        self.assertIsNone(offer_enrichment._parse_monthly_sales("no sales data"))


class EnrichmentCacheTests(unittest.TestCase):
    """Cache behavior tests. Each test re-enables the cache (TTL 24h) and
    starts from a clean cache file so results are deterministic."""

    @contextmanager
    def _cache_enabled(self):
        with patch.dict(os.environ, {"SCANNER_OFFER_CACHE_TTL_HOURS": "24"}):
            yield

    def setUp(self):
        self._clear_cache()
        self.addCleanup(self._clear_cache)

    def _clear_cache(self):
        try:
            os.remove(_TEST_CACHE_PATH)
        except OSError:
            pass

    def _cached_shape(self, asin="B000000001", provider="easyparser", status="complete"):
        return {
            "amazon_price": 48.87,
            "buy_box_price": 48.87,
            "lowest_price": 45.87,
            "highest_price": 53.87,
            "total_sellers": 5,
            "fba_sellers": 2,
            "fba_sellers_estimated": False,
            "monthly_sales_estimate": 1200,
            "monthly_sales_estimated": True,
            "fba_fee": None,
            "offer_data_provider": provider,
            "enrichment_status": status,
            "enriched_at": "2026-01-01T00:00:00+00:00",
            "asin": asin,
        }

    def test_fresh_cache_hit_skips_provider_call(self):
        with self._cache_enabled():
            offer_enrichment._cache_offer("B000000001", self._cached_shape())
        mock_provider = patch.object(offer_enrichment, "get_rapidapi_offers").start()
        try:
            with self._cache_enabled():
                with enrichment_mode("RAPIDAPI"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        finally:
            mock_provider.stop()
        mock_provider.assert_not_called()
        self.assertEqual(result["offer_data_provider"], "easyparser")
        self.assertEqual(result["enrichment_status"], "complete")
        self.assertEqual(result["enriched_at"], "2026-01-01T00:00:00+00:00")

    def test_fresh_partial_cache_hit_skips_provider_call(self):
        with self._cache_enabled():
            offer_enrichment._cache_offer(
                "B000000009", self._cached_shape(asin="B000000009", provider="chocodata", status="partial")
            )
        mock_provider = patch.object(offer_enrichment, "_fetch_chocodata_product").start()
        try:
            with self._cache_enabled():
                with enrichment_mode("CHOCODATA"):
                    result = offer_enrichment.get_scanner_offer("B000000009")
        finally:
            mock_provider.stop()
        mock_provider.assert_not_called()
        self.assertEqual(result["offer_data_provider"], "chocodata")
        self.assertEqual(result["enrichment_status"], "partial")
        self.assertEqual(result["enriched_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(result["amazon_price"], 48.87)

    def test_stale_cache_entry_is_ignored_and_refreshed(self):
        stale = self._cached_shape()
        stale["amazon_price"] = 10.0
        with self._cache_enabled():
            offer_enrichment._cache_offer("B000000001", stale)
        with open(_TEST_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        cache["B000000001"]["cached_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with open(_TEST_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        mock_provider = patch.object(offer_enrichment, "get_rapidapi_offers", return_value=easyparser_payload()).start()
        try:
            with self._cache_enabled():
                with enrichment_mode("RAPIDAPI"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        finally:
            mock_provider.stop()
        mock_provider.assert_called_once()
        self.assertEqual(result["amazon_price"], 48.87)

    def test_cache_disabled_when_ttl_is_zero(self):
        offer_enrichment._cache_offer("B000000001", self._cached_shape())
        mock_provider = patch.object(offer_enrichment, "get_rapidapi_offers", return_value=easyparser_payload()).start()
        try:
            with enrichment_mode("RAPIDAPI"):
                result = offer_enrichment.get_scanner_offer("B000000001")
        finally:
            mock_provider.stop()
        mock_provider.assert_called_once()
        self.assertEqual(result["amazon_price"], 48.87)

    def test_failed_fetch_is_never_cached(self):
        mock_provider = patch.object(offer_enrichment, "get_rapidapi_offers", return_value=failed_easyparser_payload()).start()
        try:
            with self._cache_enabled():
                with enrichment_mode("RAPIDAPI"):
                    result = offer_enrichment.get_scanner_offer("B000000001")
        finally:
            mock_provider.stop()
        self.assertEqual(result["enrichment_status"], "provider_rejected")
        self.assertIsNone(offer_enrichment._cached_offer("B000000001"))

    def test_corrupt_cache_file_is_ignored(self):
        with open(_TEST_CACHE_PATH, "w", encoding="utf-8") as f:
            f.write("{not json")
        with self._cache_enabled():
            self.assertIsNone(offer_enrichment._cached_offer("B000000001"))
            offer_enrichment._cache_offer("B000000001", self._cached_shape())
            self.assertIsNotNone(offer_enrichment._cached_offer("B000000001"))

    def test_offline_placeholder_is_never_cached(self):
        with self._cache_enabled():
            with enrichment_mode("OFF"):
                with patch.object(offer_enrichment, "get_offer_data", return_value=offline_shape()):
                    offer_enrichment.get_scanner_offer("B000000001")
            self.assertIsNone(offer_enrichment._cached_offer("B000000001"))


_TEST_SELLER_CACHE_PATH = os.path.join(
    tempfile.mkdtemp(prefix="seller-cache-test-"), "seller-cache.json"
)


def seller_roster_payload():
    """Easyparser OFFER response with a genuine 3-offer roster (2 returned
    of 3 total -> provider itself admits the roster is page-limited)."""
    return {
        "source": "easyparser",
        "asin": "B000000021",
        "title": "Seller Roster Item",
        "offer_count": 3,
        "offers_returned_count": 2,
        "buy_box_price": 25.0,
        "buy_box_seller": "Amazon.com",
        "buy_box_seller_id": "A1",
        "buy_box_is_fba": True,
        "buy_box_is_fbm": False,
        "buy_box_is_prime": True,
        "buy_box_condition": {"is_new": True, "title": "New"},
        "observed_fba_offer_count": 2,
        "observed_fbm_offer_count": 1,
        "observed_amazon_offer_count": 1,
        "offers": [
            {
                "position": 1,
                "buybox_winner": True,
                "price": {"value": 25.0, "currency": "USD"},
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
                "price": 24.0,
                "condition": "New",
                "seller_id": "A2",
                "seller_name": "Some Seller",
                "seller_rating": 4.5,
                "seller_ratings_total": 50,
                "is_prime": False,
                "is_fba": False,
                "is_fbm": True,
                "shipping_is_free": False,
            },
        ],
        "request_zip_code": "75201",
        "observed_at": "2026-08-14T20:19:04Z",
        "credits_used": 1,
        "credits_remaining": 10,
        "data_gaps": [],
    }


class SellerContractTests(unittest.TestCase):
    """On-demand seller/Buy Box contract: normalization, honesty rules,
    cache behavior, in-flight dedup, and invalid-ASIN safety. All offline;
    the Easyparser client is mocked or fed fixtures directly."""

    @contextmanager
    def _seller_cache_enabled(self):
        with patch.dict(
            os.environ,
            {
                "SCANNER_SELLER_CACHE_PATH": _TEST_SELLER_CACHE_PATH,
                "SCANNER_SELLER_CACHE_TTL_HOURS": "24",
                "EASYPARSER_API_KEY": "test-key",
            },
        ):
            yield

    def setUp(self):
        try:
            os.remove(_TEST_SELLER_CACHE_PATH)
        except OSError:
            pass
        self.addCleanup(self._remove_cache)

    def _remove_cache(self):
        try:
            os.remove(_TEST_SELLER_CACHE_PATH)
        except OSError:
            pass

    # ---- normalization ---------------------------------------------------

    def test_roster_normalizes_full_contract(self):
        payload = offer_enrichment.map_seller_offer_contract(seller_roster_payload(), "B000000021")
        self.assertEqual(payload["offer_data_status"], "partial")  # 2 of 3 returned
        self.assertEqual(payload["offer_data_source"], "easyparser")
        self.assertEqual(payload["offer_data_fetched_at"], "2026-08-14T20:19:04Z")
        self.assertEqual(payload["total_sellers"], 3)
        self.assertEqual(payload["fba_sellers"], 2)
        self.assertEqual(payload["fbm_sellers"], 1)
        self.assertEqual(payload["amazon_sellers"], 1)
        self.assertEqual(payload["offers_returned"], 2)
        self.assertEqual(payload["offers_complete"], False)
        bb = payload["buy_box"]
        self.assertTrue(bb["available"])
        self.assertEqual(bb["seller_name"], "Amazon.com")
        self.assertEqual(bb["seller_id"], "A1")
        self.assertEqual(bb["fulfillment"], "Amazon")
        self.assertEqual(bb["price"], 25.0)
        self.assertIsNone(bb["shipping"])
        self.assertIsNone(bb["landed_price"])
        self.assertEqual(bb["condition"], "New")
        self.assertTrue(bb["prime"])
        winner = payload["offers"][0]
        self.assertTrue(winner["is_buy_box_winner"])
        self.assertEqual(winner["seller_name"], "Amazon.com")
        self.assertEqual(winner["seller_id"], "A1")
        self.assertEqual(winner["fulfillment"], "Amazon")
        self.assertEqual(winner["price"], 25.0)
        self.assertIsNone(winner["shipping"])
        self.assertIsNone(winner["landed_price"])
        self.assertEqual(winner["condition"], "New")
        self.assertTrue(winner["prime"])
        self.assertEqual(winner["rating"], 4.9)
        self.assertEqual(winner["feedback_count"], 1000)
        self.assertIsNone(winner["availability"])
        self.assertTrue(winner["shipping_free"])
        second = payload["offers"][1]
        self.assertFalse(second["is_buy_box_winner"])
        self.assertEqual(second["fulfillment"], "FBM")
        self.assertEqual(second["price"], 24.0)

    def test_full_roster_status_available(self):
        data = seller_roster_payload()
        data["offers_returned_count"] = 3
        data["offers"].append(
            {
                "position": 3,
                "buybox_winner": False,
                "price": 26.5,
                "seller_id": "A3",
                "seller_name": "Third Seller",
                "is_fba": None,
                "is_fbm": None,
            }
        )
        payload = offer_enrichment.map_seller_offer_contract(data, "B000000021")
        self.assertEqual(payload["offer_data_status"], "available")
        self.assertTrue(payload["offers_complete"])
        self.assertEqual(payload["offers"][2]["fulfillment"], "Unknown")

    def test_aggregate_only_response_never_synthesizes_rows(self):
        data = seller_roster_payload()
        data["offers"] = []
        data["offers_returned_count"] = 0
        data["data_gaps"] = ["Returned offers may be a subset of the total offer_count."]
        payload = offer_enrichment.map_seller_offer_contract(data, "B000000021")
        self.assertEqual(payload["offers"], [])
        self.assertEqual(payload["total_sellers"], 3)
        self.assertEqual(payload["offer_data_status"], "partial")
        self.assertEqual(payload["offers_complete"], False)
        self.assertIn("aggregate", payload["offer_data_note"])

    def test_buy_box_never_inferred_from_lowest_price(self):
        data = seller_roster_payload()
        data["buy_box_price"] = None
        data["buy_box_seller"] = None
        data["buy_box_seller_id"] = None
        data["buy_box_is_fba"] = None
        payload = offer_enrichment.map_seller_offer_contract(data, "B000000021")
        self.assertFalse(payload["buy_box"]["available"])
        self.assertIn("never inferred", payload["buy_box"]["note"])

    def test_failed_fetch_is_provider_error_with_nulls(self):
        data = {
            "source": "easyparser",
            "asin": "B000000021",
            "data_gaps": ["Easyparser request failed at the network level."],
        }
        payload = offer_enrichment.map_seller_offer_contract(data, "B000000021")
        self.assertEqual(payload["offer_data_status"], "provider_error")
        self.assertIsNone(payload["total_sellers"])
        self.assertEqual(payload["offers"], [])
        self.assertFalse(payload["buy_box"]["available"])

    def test_unconfigured_provider_is_provider_error(self):
        data = {
            "source": "easyparser",
            "asin": "B000000021",
            "data_gaps": ["Easyparser API key is not configured."],
        }
        payload = offer_enrichment.map_seller_offer_contract(data, "B000000021")
        self.assertEqual(payload["offer_data_status"], "provider_error")
        self.assertIn("EASYPARSER_API_KEY", payload["offer_data_note"])

    def test_no_data_at_all_is_provider_error(self):
        payload = offer_enrichment.map_seller_offer_contract(None, "B000000021")
        self.assertEqual(payload["offer_data_status"], "provider_error")
        self.assertIsNone(payload["total_sellers"])

    def test_invalid_asin_rejected_with_zero_provider_calls(self):
        with patch.object(offer_enrichment, "get_easyparser_offers") as mocked:
            payload = offer_enrichment.get_seller_offer_contract("bad")
        mocked.assert_not_called()
        self.assertEqual(payload["offer_data_status"], "provider_error")
        self.assertIsNone(payload["total_sellers"])

    # ---- on-demand fetch + cache -----------------------------------------

    def test_cache_miss_calls_provider_exactly_once_and_caches(self):
        with self._seller_cache_enabled():
            with patch.object(
                offer_enrichment, "get_easyparser_offers", return_value=seller_roster_payload()
            ) as mocked:
                payload = offer_enrichment.get_seller_offer_contract("B000000021")
            mocked.assert_called_once_with("B000000021")
            self.assertEqual(payload["offer_data_cached"], False)
            self.assertEqual(payload["offer_data_status"], "partial")
            self.assertIsNotNone(offer_enrichment._cached_seller_detail("B000000021"))

    def test_cache_hit_serves_without_provider_call(self):
        with self._seller_cache_enabled():
            with patch.object(
                offer_enrichment, "get_easyparser_offers", return_value=seller_roster_payload()
            ):
                offer_enrichment.get_seller_offer_contract("B000000021")
            with patch.object(offer_enrichment, "get_easyparser_offers") as mocked:
                payload = offer_enrichment.get_seller_offer_contract("B000000021")
            mocked.assert_not_called()
            self.assertTrue(payload["offer_data_cached"])
            self.assertEqual(payload["offer_data_status"], "partial")

    def test_stale_cache_makes_one_provider_call(self):
        with self._seller_cache_enabled():
            with patch.object(
                offer_enrichment, "get_easyparser_offers", return_value=seller_roster_payload()
            ):
                offer_enrichment.get_seller_offer_contract("B000000021")
            with open(_TEST_SELLER_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
            cache["B000000021"]["cached_at"] = (
                datetime.now(timezone.utc) - timedelta(hours=25)
            ).isoformat()
            with open(_TEST_SELLER_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(cache, f)
            with patch.object(
                offer_enrichment, "get_easyparser_offers", return_value=seller_roster_payload()
            ) as mocked:
                offer_enrichment.get_seller_offer_contract("B000000021")
            mocked.assert_called_once()

    def test_disabled_cache_still_makes_one_provider_call(self):
        with patch.dict(
            os.environ,
            {
                "SCANNER_SELLER_CACHE_PATH": _TEST_SELLER_CACHE_PATH,
                "SCANNER_SELLER_CACHE_TTL_HOURS": "0",
            },
        ):
            with patch.object(
                offer_enrichment, "get_easyparser_offers", return_value=seller_roster_payload()
            ) as mocked:
                offer_enrichment.get_seller_offer_contract("B000000021")
            mocked.assert_called_once()
            self.assertIsNone(offer_enrichment._cached_seller_detail("B000000021"))

    def test_provider_error_is_never_cached(self):
        failed = {
            "source": "easyparser",
            "asin": "B000000021",
            "data_gaps": ["Easyparser request timed out."],
        }
        with self._seller_cache_enabled():
            with patch.object(
                offer_enrichment, "get_easyparser_offers", return_value=failed
            ):
                payload = offer_enrichment.get_seller_offer_contract("B000000021")
            self.assertEqual(payload["offer_data_status"], "provider_error")
            self.assertIsNone(offer_enrichment._cached_seller_detail("B000000021"))

    def test_unavailable_result_is_never_cached(self):
        empty = {
            "source": "easyparser",
            "asin": "B000000021",
            "data_gaps": ["Easyparser response was missing result data."],
        }
        with self._seller_cache_enabled():
            with patch.object(offer_enrichment, "get_easyparser_offers", return_value=empty):
                payload = offer_enrichment.get_seller_offer_contract("B000000021")
            self.assertEqual(payload["offer_data_status"], "unavailable")
            self.assertIsNone(offer_enrichment._cached_seller_detail("B000000021"))

    def test_concurrent_requests_share_one_fetch(self):
        import threading

        calls = []

        def slow_fetch(asin):
            calls.append(asin)
            return seller_roster_payload()

        with self._seller_cache_enabled():
            with patch.object(offer_enrichment, "get_easyparser_offers", side_effect=slow_fetch):
                results = []
                threads = [
                    threading.Thread(
                        target=lambda: results.append(
                            offer_enrichment.get_seller_offer_contract("B000000021")
                        )
                    )
                    for _ in range(3)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(results), 3)
            for r in results:
                self.assertEqual(r["offer_data_status"], "partial")


if __name__ == "__main__":
    unittest.main(verbosity=2)
