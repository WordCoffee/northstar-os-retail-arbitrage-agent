"""Mocked unit tests for the amazon_search provider dispatcher.

Never touches Scavio, CHOCODATA.com, or any external API: every
provider call is mocked. Covers the CHOCODATA normalizer, the
SCAVIO passthrough + error mirroring, and the SCANNER_SEARCH_SOURCE
dispatch.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import unittest
from unittest import mock
from unittest.mock import patch

import amazon_search
import bright_data_client
import scavio_client


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)


def make_search_response(products=None, page=1, no_results=False, status_code=200):
    payload = {
        "page": page,
        "products": products if products is not None else [],
        "html": "",
    }
    if no_results:
        payload["no_results"] = True
        payload["total_results"] = 0
        payload["html"] = None
    return mock.Mock(status_code=status_code, text="", json=lambda: payload)


def fake_product(asin="B000000001", title="Kirkland Signature K-Cups (120ct)", price=48.87):
    return {
        "asin": asin,
        "title": title,
        "url": f"https://www.amazon.com/dp/{asin}",
        "price": price,
        "currency": "USD",
        "rating": 4.6,
        "reviews_count": 1200,
        "organic_position": 1,
        "is_sponsored": False,
    }


class ChocodataSearchTests(unittest.TestCase):
    def _run(self, side_effect, env_patches=None):
        patches = [
            patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"),
            patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"),
            patch.object(amazon_search, "requests", mock.Mock(get=mock.Mock(side_effect=side_effect))),
        ]
        if env_patches:
            patches += env_patches
        for p in patches:
            p.start()
        try:
            return amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_success_flow_normalized(self):
        response = make_search_response(products=[
            fake_product(),
            fake_product(asin="B000000002", title="Kirkland Signature Bath Tissue (180ct)", price=34.99),
        ])
        result = self._run([response])
        self.assertEqual(len(result), 2)
        first = result[0]
        self.assertEqual(first["asin"], "B000000001")
        self.assertEqual(first["name"], "Kirkland Signature K-Cups (120ct)")
        self.assertEqual(first["amazon_price"], 48.87)
        self.assertEqual(first["product_url"], "https://www.amazon.com/dp/B000000001")
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_empty_products_is_not_an_error(self):
        response = make_search_response(no_results=True)
        result = self._run([response])
        self.assertEqual(result, [])
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_requests_start_page_params(self):
        response = make_search_response(products=[fake_product()])
        get_mock = mock.Mock(side_effect=[response])
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
             patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"), \
             patch.object(amazon_search, "requests", mock.Mock(get=get_mock)):
            amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        params = get_mock.call_args.kwargs["params"]
        self.assertEqual(params["query"], "kirkland")
        self.assertEqual(params["start_page"], 1)
        self.assertEqual(params["domain"], "com")
        self.assertEqual(params["sort_by"], "best_match")

    def test_pages_loop_fetches_each_page(self):
        responses = [
            make_search_response(products=[fake_product(asin="B000000001")], page=1),
            make_search_response(products=[fake_product(asin="B000000002")], page=2),
        ]
        get_mock = mock.Mock(side_effect=responses)
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
             patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"), \
             patch.object(amazon_search, "requests", mock.Mock(get=get_mock)):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=2)
        self.assertEqual(get_mock.call_count, 2)
        start_pages = [call.kwargs["params"]["start_page"] for call in get_mock.call_args_list]
        self.assertEqual(start_pages, [1, 2])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["asin"], "B000000001")
        self.assertEqual(result[1]["asin"], "B000000002")

    def test_paging_stops_on_empty_page(self):
        responses = [
            make_search_response(products=[fake_product(asin="B000000001")], page=1),
            make_search_response(products=[], page=2),
        ]
        get_mock = mock.Mock(side_effect=responses)
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
             patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"), \
             patch.object(amazon_search, "requests", mock.Mock(get=get_mock)):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=10)
        self.assertEqual(get_mock.call_count, 2)
        self.assertEqual(len(result), 1)

    def test_brand_field_matches_kirkland_when_title_omits_it(self):
        product = fake_product(title="Minoxidil for Men Liquid, Extra Strength 5% (6 Months Supply)")
        product["brand"] = "Kirkland Signature"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asin"], "B000000001")

    def test_non_kirkland_brand_and_title_dropped(self):
        product = fake_product(title="Generic Minoxidil 5% (6 Months Supply)")
        product["brand"] = "SomeOtherBrand"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(result, [])

    def test_extra_offer_fields_carried_through(self):
        product = fake_product()
        product["brand"] = "Kirkland Signature"
        product["sales_volume"] = "5K+ bought in past month"
        product["rating"] = 4.6
        product["reviews_count"] = 2500
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(result[0]["brand"], "Kirkland Signature")
        self.assertEqual(result[0]["sales_volume"], "5K+ bought in past month")
        self.assertEqual(result[0]["rating"], 4.6)
        self.assertEqual(result[0]["reviews_count"], 2500)

    def test_used_token_in_title_still_excluded_even_with_kirkland_brand(self):
        product = fake_product(title="Kirkland Signature 13 Gallon Trash Bag, 400 Count, New")
        product["brand"] = "Kirkland Signature"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(len(result), 1)
        product = fake_product(title="Used Kirkland Signature 13 Gallon Trash Bag")
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(result, [])

    def test_missing_api_key_sets_error(self):
        result = self._run([make_search_response(products=[fake_product()])],
                           env_patches=[patch.object(amazon_search, "CHOCODATA_API_KEY", "")])
        self.assertEqual(result, [])
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "CHOCODATA_API_KEY not set")

    def test_http_error_sets_error(self):
        response = make_search_response(status_code=500)
        result = self._run([response])
        self.assertEqual(result, [])
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "HTTP 500")

    def test_retryable_502_retries_once_then_succeeds(self):
        blocked = mock.Mock(
            status_code=502,
            text='{"error":"target_unreachable","retryable":true}',
            json=lambda: {"error": "target_unreachable", "retryable": True},
        )
        ok = make_search_response(products=[fake_product()])
        get_mock = mock.Mock(side_effect=[blocked, ok])
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
             patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"), \
             patch.object(amazon_search.time, "sleep") as sleep_mock, \
             patch.object(amazon_search, "requests", mock.Mock(get=get_mock)):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(get_mock.call_count, 2)
        sleep_mock.assert_called_once_with(amazon_search.RETRY_SLEEP_SECONDS)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asin"], "B000000001")
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_retryable_502_exhausted_sets_error_with_message(self):
        blocked = mock.Mock(
            status_code=502,
            text='{"error":"target_unreachable","message":"Amazon blocked every retry.","retryable":true}',
            json=lambda: {"error": "target_unreachable", "message": "Amazon blocked every retry.", "retryable": True},
        )
        get_mock = mock.Mock(side_effect=[blocked, blocked])
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
             patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"), \
             patch.object(amazon_search.time, "sleep"), \
             patch.object(amazon_search, "requests", mock.Mock(get=get_mock)):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(get_mock.call_count, 2)
        self.assertEqual(result, [])
        self.assertIn("502", amazon_search.LAST_SEARCH_ERROR)
        self.assertIn("Amazon blocked every retry", amazon_search.LAST_SEARCH_ERROR)

    def test_non_retryable_502_sets_error_without_retry(self):
        blocked = mock.Mock(
            status_code=502,
            text='{"error":"target_unreachable","retryable":false}',
            json=lambda: {"error": "target_unreachable", "retryable": False},
        )
        get_mock = mock.Mock(side_effect=[blocked])
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"), \
             patch.object(amazon_search, "CHOCODATA_API_KEY", "cd_live_test"), \
             patch.object(amazon_search.time, "sleep") as sleep_mock, \
             patch.object(amazon_search, "requests", mock.Mock(get=get_mock)):
            amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(get_mock.call_count, 1)
        sleep_mock.assert_not_called()

    def test_insufficient_credits_detected_in_body(self):
        response = mock.Mock(status_code=402, text='{"error":"Insufficient credits","credit_balance":0}', json=lambda: {})
        result = self._run([response])
        self.assertEqual(result, [])
        self.assertIn("402", amazon_search.LAST_SEARCH_ERROR)
        self.assertIn("insufficient credits", amazon_search.LAST_SEARCH_ERROR)

    def test_exception_sets_error_and_continues(self):
        def boom(*args, **kwargs):
            raise TimeoutError("timed out")
        result = self._run(boom)
        self.assertEqual(result, [])
        self.assertIn("timed out", amazon_search.LAST_SEARCH_ERROR)

    def test_null_price_becomes_none_not_zero(self):
        product = fake_product()
        product["price"] = None
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertIsNone(result[0]["amazon_price"])

    def test_zero_price_becomes_none_not_zero(self):
        product = fake_product()
        product["price"] = 0
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertIsNone(result[0]["amazon_price"])

    def test_negative_price_becomes_none(self):
        product = fake_product()
        product["price"] = -5.0
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertIsNone(result[0]["amazon_price"])

    def test_numeric_string_price_is_parsed(self):
        product = fake_product()
        product["price"] = "48.87"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(result[0]["amazon_price"], 48.87)

    def test_non_numeric_string_price_becomes_none(self):
        product = fake_product()
        product["price"] = "N/A"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertIsNone(result[0]["amazon_price"])

    def test_sales_volume_parsed_to_monthly_estimate(self):
        product = fake_product()
        product["sales_volume"] = "5K+ bought in past month"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertEqual(result[0]["monthly_sales_estimate"], 5000.0)
        self.assertIs(result[0]["monthly_sales_estimated"], True)

    def test_sales_volume_week_scale_converted(self):
        product = fake_product()
        product["sales_volume"] = "200+ bought in past week"
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertAlmostEqual(result[0]["monthly_sales_estimate"], 200 * 4.33, places=2)

    def test_missing_sales_volume_stays_none(self):
        product = fake_product()
        product["sales_volume"] = None
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertIsNone(result[0]["monthly_sales_estimate"])

    def test_invalid_price_type_becomes_none(self):
        product = fake_product()
        product["price"] = None
        response = make_search_response(products=[product])
        result = self._run([response])
        self.assertIsNone(result[0]["amazon_price"])

    def test_domain_derived_from_marketplace(self):
        with patch.object(amazon_search, "DEFAULT_MARKETPLACE", "https://www.amazon.co.uk"):
            self.assertEqual(amazon_search._marketplace_domain(), "co.uk")


def brightdata_card(asin, title, price=None, rating=None, reviews=None, bought=None, brand=None):
    brand_html = f'<h2 class="a-size-mini"><span>{brand}</span></h2>' if brand else ""
    price_html = (
        f'<span class="a-offscreen">${price}</span>'
        if price is not None
        else ""
    )
    rating_html = (
        f'<i class="a-icon"><span class="a-icon-alt">{rating} out of 5 stars</span></i>'
        if rating is not None
        else ""
    )
    reviews_html = (
        f'<a aria-label="{reviews} ratings">{reviews}</a>' if reviews is not None else ""
    )
    bought_html = f"<span>{bought}</span>" if bought is not None else ""
    return (
        f'<div data-asin="{asin}" data-component-type="s-search-result">'
        f"{brand_html}"
        f'<h2 class="a-size-mini"><span>{title}</span></h2>'
        f"{price_html}{rating_html}{reviews_html}{bought_html}</div>"
    )


def brightdata_page(cards, prefix="<div data-asin=\"\" data-index=\"0\"></div>"):
    return prefix + "".join(cards)


class BrightDataSearchTests(unittest.TestCase):
    def setUp(self):
        bright_data_client._CACHE.clear()
        bright_data_client.LAST_ERROR = None

    def _run(self, side_effect, key="bd_live_test"):
        patches = [
            patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"),
            patch.object(amazon_search, "SCANNER_SEARCH_FALLBACK", ""),
            patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", key),
            patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_ZONE", "northstaros"),
            patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=side_effect))),
        ]
        for p in patches:
            p.start()
        try:
            return amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        finally:
            for p in reversed(patches):
                p.stop()

    def _response(self, text, status_code=200):
        return mock.Mock(status_code=status_code, text=text)

    def test_parses_cards_with_price_rating_reviews_and_velocity(self):
        html = brightdata_page([
            brightdata_card("B000000001", "Kirkland Signature K-Cups (120ct)", 48.87, 4.6, 1200, "5K+ bought in past month"),
            brightdata_card("B000000002", "Some Other Brand Widget", 12.34),
        ])
        result = self._run([self._response(html)])
        self.assertEqual(len(result), 1)
        card = result[0]
        self.assertEqual(card["asin"], "B000000001")
        self.assertEqual(card["name"], "Kirkland Signature K-Cups (120ct)")
        self.assertEqual(card["amazon_price"], 48.87)
        self.assertEqual(card["rating"], 4.6)
        self.assertEqual(card["reviews_count"], 1200)
        self.assertEqual(card["monthly_sales_estimate"], 5000)
        self.assertIs(card["monthly_sales_estimated"], True)
        self.assertEqual(card["product_url"], "https://www.amazon.com/dp/B000000001")
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_keeps_title_missing_brand_when_brand_row_present(self):
        html = brightdata_page([
            brightdata_card("B000000007", "Minoxidil for Men Liquid, Extra Strength", 12.49, brand="KIRKLAND"),
            brightdata_card("B000000008", "Some Other Brand Widget", 12.34),
        ])
        result = self._run([self._response(html)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asin"], "B000000007")
        self.assertEqual(result[0]["name"], "Minoxidil for Men Liquid, Extra Strength")
        self.assertEqual(result[0]["brand"], "KIRKLAND")

    def test_drops_used_refurbished_and_titleless_cards(self):
        html = brightdata_page([
            brightdata_card("B000000003", "Kirkland Signature Item Used", 10.0),
            brightdata_card("B000000004", "Refurbished Kirkland Widget", 10.0),
            brightdata_card("B000000005", "", 10.0),
            brightdata_card("B000000006", "Kirkland Signature Fresh Item", 15.0),
        ])
        result = self._run([self._response(html)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asin"], "B000000006")

    def test_request_uses_zone_url_and_bearer(self):
        html = brightdata_page([brightdata_card("B000000001", "Kirkland Signature K-Cups (120ct)", 48.87)])
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests") as mock_requests:
            mock_requests.post.return_value = self._response(html)
            bright_data_client.search_products("kirkland", 1)
        args, kwargs = mock_requests.post.call_args
        self.assertEqual(kwargs["json"]["zone"], "northstaros")
        self.assertIn("/s?k=kirkland&page=1", kwargs["json"]["url"])
        self.assertEqual(kwargs["json"]["format"], "raw")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer bd_live_test")

    def test_missing_api_key_returns_empty_with_error(self):
        result = self._run([self._response("")], key="")
        self.assertEqual(result, [])
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "BRIGHTDATA_UNLOCKER_API_KEY not set")

    def test_non_200_records_error(self):
        result = self._run([self._response("blocked", status_code=403)])
        self.assertEqual(result, [])
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "HTTP 403")

    def test_network_exception_records_error(self):
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"), \
             patch.object(amazon_search, "SCANNER_SEARCH_FALLBACK", ""), \
             patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=RuntimeError("boom")))):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(result, [])
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "boom")

    def test_empty_card_page_stops_paging(self):
        page1 = brightdata_page([brightdata_card("B000000001", "Kirkland Signature K-Cups (120ct)", 48.87)])
        page2 = brightdata_page([])
        result = self._run([self._response(page1), self._response(page2)])
        self.assertEqual(len(result), 1)
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, None)


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        bright_data_client._CACHE.clear()
        bright_data_client.LAST_ERROR = None

    def test_default_source_maps_to_brightdata(self):
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"):
            self.assertEqual(amazon_search.active_search_source(), "BRIGHTDATA")

    def test_scavio_fallback_when_configured(self):
        candidates = [{"asin": "B000000001", "name": "Kirkland Item", "amazon_price": 10.0, "product_url": None}]
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"), \
             patch.object(amazon_search, "SCANNER_SEARCH_FALLBACK", "SCAVIO"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=RuntimeError("boom")))), \
             patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(scavio_client, "search_kirkland_products", return_value=candidates) as search_mock, \
             patch.object(scavio_client, "LAST_SEARCH_ERROR", None):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        search_mock.assert_called_once()
        self.assertEqual(result, candidates)
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_no_fallback_keeps_brightdata_error(self):
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"), \
             patch.object(amazon_search, "SCANNER_SEARCH_FALLBACK", ""), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=RuntimeError("boom")))), \
             patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(result, [])
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "boom")

    def test_scavio_passthrough_and_error_mirroring(self):
        candidates = [{"asin": "B000000001", "name": "Kirkland Item", "amazon_price": 10.0, "product_url": None}]
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "SCAVIO"), \
             patch.object(scavio_client, "search_kirkland_products", return_value=candidates) as search_mock, \
             patch.object(scavio_client, "LAST_SEARCH_ERROR", None):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        search_mock.assert_called_once_with(["kirkland"], 1)
        self.assertEqual(result, candidates)
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_scavio_error_is_mirrored(self):
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "SCAVIO"), \
             patch.object(scavio_client, "search_kirkland_products", return_value=[]), \
             patch.object(scavio_client, "LAST_SEARCH_ERROR", "HTTP 500"):
            amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(amazon_search.LAST_SEARCH_ERROR, "HTTP 500")

    def test_label_and_billing_url(self):
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"):
            self.assertEqual(amazon_search.provider_label(), "Bright Data")
            self.assertEqual(amazon_search.provider_billing_url(), "https://www.brightdata.com")
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "CHOCODATA"):
            self.assertEqual(amazon_search.provider_label(), "Chocodata")
            self.assertIn("app.chocodata.com", amazon_search.provider_billing_url())
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "SCAVIO"):
            self.assertEqual(amazon_search.provider_label(), "Scavio")
            self.assertEqual(amazon_search.provider_billing_url(), "https://dashboard.scavio.dev/billing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
