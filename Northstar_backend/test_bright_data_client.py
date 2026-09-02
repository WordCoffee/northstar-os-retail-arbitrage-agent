"""Mocked unit tests for the Bright Data Web Unlocker client.

Never makes live calls: every Web Unlocker POST is mocked. Covers
search_products, get_product_detail, normalization (None never 0),
missing-key contract, non-2xx handling, the 15-minute cache, and the
dispatcher routing/fallback for SCANNER_SEARCH_SOURCE / 
SCANNER_OFFER_ENRICHMENT = BRIGHTDATA.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import os
import unittest
from unittest import mock
from unittest.mock import patch

import amazon_search
import bright_data_client
import offer_enrichment


def setUpModule():
    """Live-path tests: explicitly opt into SCANNER_LIVE_ALLOWED (the
    default-off gate). tearDownModule restores it for later modules."""
    os.environ["SCANNER_LIVE_ALLOWED"] = "1"


def tearDownModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)


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


def brightdata_page(cards, prefix='<div data-asin="" data-index="0"></div>'):
    return prefix + "".join(cards)


def _breadcrumb_html(crumbs):
    """Amazon wayfinding breadcrumbs div. Each (text, node) emits a
    category link carrying a real numeric node= id; node None emits a
    link with no node (skipped by the parser)."""
    items = []
    for i, (text, node) in enumerate(crumbs, 1):
        if node is None:
            items.append(
                f'<li><span class="a-list-item"><a class="a-link-normal a-color-tertiary" '
                f'href="/b/ref=dp_bc_{i}?ie=UTF8">{text}</a></span></li>'
            )
        else:
            items.append(
                f'<li><span class="a-list-item"><a class="a-link-normal a-color-tertiary" '
                f'href="/b/ref=dp_bc_{i}?ie=UTF8&amp;node={node}">{text}</a></span></li>'
            )
    return (
        '<div id="wayfinding-breadcrumbs_feature_div">'
        '<ul class="a-unordered-list a-horizontal a-size-small">'
        + "".join(items) +
        "</ul></div>"
    )


def product_page_html(asin="B000000001", title="Kirkland Signature K-Cups (120ct)", price="48.87",
                      brand="Visit the KIRKLAND SIGNATURE Store", image="https://m.media-amazon.com/images/I/1.jpg",
                      offers="New (4) from $45.87", weight="11.2 ounces", package_dimensions=None,
                      rank="#3,042 in Grocery", rating="4.6", reviews="1,200",
                      bought="5K+ bought in past month", breadcrumbs=None):
    details_rows = [
        f'<li><span class="a-text-bold">Item Weight : </span><span>{weight}</span></li>',
    ]
    if package_dimensions is not None:
        details_rows.append(
            f'<li><span class="a-text-bold">Package Dimensions : </span><span>{package_dimensions}</span></li>'
        )
    details_html = "".join(details_rows)
    breadcrumb_html = _breadcrumb_html(breadcrumbs) if breadcrumbs else ""
    parts = [
        breadcrumb_html,
        f'<span id="productTitle" class="a-size-large">{title}</span>',
        f'<div id="corePrice_feature_div"><span class="a-offscreen">${price}</span></div>',
        f'<a id="bylineInfo">{brand}</a>',
        f'<img id="landingImage" src="{image}" />',
        f'<span id="olp-upd-new-used">{offers}</span>',
        f'<div id="productDetails_techSpec_section_1"><ul>{details_html}</ul></div>',
        f'<div id="productDetails_detailBullets_sections1">Best Sellers Rank {rank}</div>',
        f'<div id="acrPopover" title="{rating} out of 5 stars"></div>',
        f'<span id="acrCustomerReviewText">{reviews} ratings</span>',
        f'<span>{bought}</span>',
    ]
    return "".join(parts)


class _CacheIsolated(unittest.TestCase):
    def setUp(self):
        bright_data_client._CACHE.clear()
        bright_data_client.LAST_ERROR = None


class SearchProductsTests(_CacheIsolated):
    def _run(self, side_effect, key="bd_live_test"):
        patches = [
            patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", key),
            patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=side_effect))),
        ]
        for p in patches:
            p.start()
        try:
            return bright_data_client.search_products("kirkland", 1)
        finally:
            for p in reversed(patches):
                p.stop()

    def _response(self, text, status_code=200):
        return mock.Mock(status_code=status_code, text=text)

    def test_search_returns_normalized_kirkland_candidates(self):
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
        self.assertEqual(card["product_url"], "https://www.amazon.com/dp/B000000001")
        self.assertEqual(card["rating"], 4.6)
        self.assertEqual(card["reviews_count"], 1200)
        self.assertEqual(card["monthly_sales_estimate"], 5000)
        self.assertIs(card["monthly_sales_estimated"], True)

    def test_missing_or_zero_price_is_none_not_zero(self):
        html = brightdata_page([brightdata_card("B000000001", "Kirkland Signature Item")])
        result = self._run([self._response(html)])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["amazon_price"])

    def test_used_items_dropped_by_shared_filter(self):
        html = brightdata_page([
            brightdata_card("B000000003", "Kirkland Signature Item Used", 10.0),
            brightdata_card("B000000006", "Kirkland Signature Fresh Item", 15.0),
        ])
        result = self._run([self._response(html)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asin"], "B000000006")

    def test_missing_api_key_raises_value_error(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", ""):
            with self.assertRaises(ValueError):
                bright_data_client.search_products("kirkland", 1)

    def test_non_200_returns_empty_with_error(self):
        result = self._run([self._response("blocked", status_code=403)])
        self.assertEqual(result, [])
        self.assertEqual(bright_data_client.LAST_ERROR, "auth_error: HTTP 403")

    def test_network_exception_returns_empty_with_error(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=RuntimeError("boom")))):
            result = bright_data_client.search_products("kirkland", 1)
        self.assertEqual(result, [])
        self.assertEqual(bright_data_client.LAST_ERROR, "transport_error: boom")

    def test_empty_card_page_stops_paging(self):
        page1 = brightdata_page([brightdata_card("B000000001", "Kirkland Signature K-Cups (120ct)", 48.87)])
        page2 = brightdata_page([])
        result = self._run([self._response(page1), self._response(page2)])
        self.assertEqual(len(result), 1)
        self.assertIsNone(bright_data_client.LAST_ERROR)

    def test_empty_keyword_returns_empty(self):
        result = bright_data_client.search_products("", 1)
        self.assertEqual(result, [])


class ProductDetailTests(_CacheIsolated):
    def _run(self, side_effect, key="bd_live_test"):
        patches = [
            patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", key),
            patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=side_effect))),
        ]
        for p in patches:
            p.start()
        try:
            return bright_data_client.get_product_detail("B000000001")
        finally:
            for p in reversed(patches):
                p.stop()

    def _response(self, text, status_code=200):
        return mock.Mock(status_code=status_code, text=text)

    def test_detail_normalized_with_contract_fields(self):
        result = self._run([self._response(product_page_html())])
        self.assertEqual(result["asin"], "B000000001")
        self.assertEqual(result["name"], "Kirkland Signature K-Cups (120ct)")
        self.assertEqual(result["amazon_price"], 48.87)
        self.assertEqual(result["buy_box_price"], 48.87)
        self.assertEqual(result["total_sellers"], 4)
        self.assertEqual(result["lowest_price"], 45.87)
        self.assertEqual(result["fba_sellers"], None)
        self.assertIs(result["fba_sellers_estimated"], False)
        self.assertEqual(result["brand"], "KIRKLAND SIGNATURE")
        self.assertEqual(result["image_url"], "https://m.media-amazon.com/images/I/1.jpg")
        self.assertAlmostEqual(result["weight_lbs"], 11.2 / 16.0, places=5)
        self.assertEqual(result["fba_fee"], 5.25)
        self.assertEqual(result["sales_rank"], 3042)
        self.assertEqual(result["rating"], 4.6)
        self.assertEqual(result["reviews_count"], 1200)
        self.assertEqual(result["monthly_sales_estimate"], 5000)
        self.assertEqual(result["product_url"], "https://www.amazon.com/dp/B000000001")

    def test_detail_missing_price_is_none_not_zero(self):
        html = product_page_html().replace('<span class="a-offscreen">$48.87</span>', "")
        result = self._run([self._response(html)])
        self.assertIsNone(result["amazon_price"])
        self.assertIsNone(result["buy_box_price"])

    def test_detail_missing_offers_keeps_price_as_lowest(self):
        html = product_page_html(offers="")
        result = self._run([self._response(html)])
        self.assertIsNone(result["total_sellers"])
        self.assertEqual(result["lowest_price"], 48.87)

    def test_detail_weight_from_package_dimensions_row(self):
        html = product_page_html(
            weight="",
            package_dimensions="8.7 x 8.62 x 5.08 inches; 5.25 pounds",
        )
        result = self._run([self._response(html)])
        self.assertAlmostEqual(result["weight_lbs"], 5.25, places=5)
        self.assertEqual(result["fba_fee"], 9.90)

    def test_detail_empty_item_weight_row_falls_through_to_package_dimensions(self):
        html = product_page_html(
            weight="",
            package_dimensions="4.7 x 3.9 x 1.8 inches; 1.32 ounces",
        )
        result = self._run([self._response(html)])
        self.assertAlmostEqual(result["weight_lbs"], 1.32 / 16.0, places=5)

    def test_detail_package_dimensions_preferred_over_item_weight(self):
        html = product_page_html(
            weight="16.9 ounces",
            package_dimensions="8.7 x 8.62 x 5.08 inches; 5.25 pounds",
        )
        result = self._run([self._response(html)])
        self.assertAlmostEqual(result["weight_lbs"], 5.25, places=5)
        self.assertEqual(result["fba_fee"], 9.90)

    def test_detail_missing_weight_fee_stays_none(self):
        html = product_page_html(weight="")
        result = self._run([self._response(html)])
        self.assertIsNone(result["weight_lbs"])
        self.assertIsNone(result["fba_fee"])

    def test_detail_brand_prefix_stripped(self):
        html = product_page_html(brand="Brand: Costco")
        result = self._run([self._response(html)])
        self.assertEqual(result["brand"], "Costco")

    def test_detail_parses_breadcrumb_category_and_browse_node(self):
        html = product_page_html(
            breadcrumbs=[("Grocery &amp; Gourmet Food", 16310101), ("Snack Foods", 16310071)]
        )
        result = self._run([self._response(html)])
        self.assertEqual(result["amazon_category"], "Grocery & Gourmet Food")
        self.assertEqual(result["browse_node_id"], 16310101)
        self.assertIsInstance(result["browse_node_id"], int)
        self.assertEqual(result["breadcrumb"], ["Grocery & Gourmet Food", "Snack Foods"])
        self.assertEqual(result["category_source_hint"], "breadcrumb")

    def test_detail_missing_breadcrumb_all_nulls(self):
        result = self._run([self._response(product_page_html())])
        self.assertIsNone(result["amazon_category"])
        self.assertIsNone(result["browse_node_id"])
        self.assertIsNone(result["breadcrumb"])
        self.assertIsNone(result["category_source_hint"])

    def test_detail_breadcrumb_link_without_node_is_skipped(self):
        """A category link with no numeric node= id is not trusted: both
        fields stay null rather than guessing."""
        html = product_page_html(breadcrumbs=[("Pet Supplies", None)])
        result = self._run([self._response(html)])
        self.assertIsNone(result["amazon_category"])
        self.assertIsNone(result["browse_node_id"])
        self.assertIsNone(result["breadcrumb"])

    def test_detail_breadcrumb_div_absent_but_node_links_elsewhere_ignored(self):
        """node= ids outside the wayfinding div (widgets, related searches)
        must not leak into the browse node."""
        html = product_page_html() + '<a href="/b?ie=UTF8&amp;node=11055981">Beauty</a>'
        result = self._run([self._response(html)])
        self.assertIsNone(result["browse_node_id"])

    def test_detail_accepts_url_identifier(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests") as mock_requests:
            mock_requests.post.return_value = self._response(product_page_html())
            result = bright_data_client.get_product_detail("https://www.amazon.com/dp/B000000001")
        self.assertEqual(result["asin"], "B000000001")

    def test_detail_invalid_identifier_returns_empty(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"):
            result = bright_data_client.get_product_detail("not-an-asin")
        self.assertEqual(result, {})

    def test_detail_missing_api_key_raises_value_error(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", ""):
            with self.assertRaises(ValueError):
                bright_data_client.get_product_detail("B000000001")

    def test_detail_non_200_returns_empty_with_error(self):
        result = self._run([self._response("blocked", status_code=403)])
        self.assertEqual(result, {})
        self.assertEqual(bright_data_client.LAST_ERROR, "auth_error: HTTP 403")

    def test_detail_network_exception_returns_empty(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=RuntimeError("boom")))):
            result = bright_data_client.get_product_detail("B000000001")
        self.assertEqual(result, {})

    def test_request_uses_zone_url_and_bearer(self):
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests") as mock_requests:
            mock_requests.post.return_value = self._response(product_page_html())
            bright_data_client.get_product_detail("B000000001")
        args, kwargs = mock_requests.post.call_args
        self.assertEqual(kwargs["json"]["zone"], "northstaros")
        self.assertIn("/dp/B000000001", kwargs["json"]["url"])
        self.assertEqual(kwargs["json"]["format"], "raw")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer bd_live_test")

    def test_cache_serves_second_call_without_second_request(self):
        html = product_page_html()
        post_mock = mock.Mock(return_value=self._response(html))
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=post_mock)):
            bright_data_client.get_product_detail("B000000001")
            bright_data_client.get_product_detail("B000000001")
        self.assertEqual(post_mock.call_count, 1)


class DispatcherRoutingTests(_CacheIsolated):
    def test_search_dispatcher_routes_to_brightdata(self):
        html = brightdata_page([brightdata_card("B000000001", "Kirkland Signature K-Cups (120ct)", 48.87)])
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"), \
             patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(return_value=mock.Mock(status_code=200, text=html)))):
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asin"], "B000000001")
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)

    def test_enrichment_dispatcher_routes_to_brightdata(self):
        with patch.object(offer_enrichment, "get_product_detail", return_value={
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
        }):
            with patch.dict("os.environ", {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["offer_data_provider"], "brightdata")
        self.assertEqual(result["enrichment_status"], "complete")

    def test_brightdata_mapper_does_not_drop_category_metadata(self):
        """The mapper choke point must pass the parsed category / browse
        node through, or the fee engine keeps falling back to Default 15%."""
        with patch.object(offer_enrichment, "get_product_detail", return_value={
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
            "amazon_category": "Grocery & Gourmet Food",
            "browse_node_id": 16310101,
            "breadcrumb": ["Grocery & Gourmet Food", "Snack Foods"],
            "category_source_hint": "breadcrumb",
            "sellers": [],
        }):
            with patch.dict("os.environ", {"SCANNER_OFFER_ENRICHMENT": "BRIGHTDATA"}, clear=False):
                result = offer_enrichment.get_scanner_offer("B000000001")
        self.assertEqual(result["amazon_category"], "Grocery & Gourmet Food")
        self.assertEqual(result["browse_node_id"], 16310101)
        self.assertEqual(result["breadcrumb"], ["Grocery & Gourmet Food", "Snack Foods"])
        self.assertEqual(result["category_source_hint"], "breadcrumb")

    def test_fallback_to_scavio_when_configured(self):
        import scavio_client
        candidates = [{"asin": "B000000001", "name": "Kirkland Item", "amazon_price": 10.0}]
        with patch.object(amazon_search, "SCANNER_SEARCH_SOURCE", "BRIGHTDATA"), \
             patch.object(amazon_search, "SCANNER_SEARCH_FALLBACK", "SCAVIO"), \
             patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(side_effect=RuntimeError("boom")))), \
             patch.object(scavio_client, "search_kirkland_products", return_value=candidates) as search_mock:
            result = amazon_search.search_kirkland_products(keywords=["kirkland"], pages=1)
        search_mock.assert_called_once()
        self.assertEqual(result, candidates)
        self.assertIsNone(amazon_search.LAST_SEARCH_ERROR)


class CreditsTrackingTests(_CacheIsolated):
    def test_request_count_tracks_session(self):
        html = brightdata_page([brightdata_card("B000000001", "Kirkland Signature K-Cups (120ct)", 48.87)])
        with patch.object(bright_data_client, "BRIGHTDATA_UNLOCKER_API_KEY", "bd_live_test"), \
             patch.object(bright_data_client, "requests", mock.Mock(post=mock.Mock(return_value=mock.Mock(status_code=200, text=html)))):
            before = bright_data_client.get_bright_data_request_count()
            bright_data_client.search_products("kirkland", 1)
            after = bright_data_client.get_bright_data_request_count()
        self.assertEqual(after, before + 1)

    def test_credits_remaining_none_no_rest_endpoint_for_free_tier(self):
        self.assertIsNone(bright_data_client.get_bright_data_credits_remaining())


if __name__ == "__main__":
    unittest.main(verbosity=2)