import importlib
import csv
import json
import os
import tempfile
import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from unittest import mock

import costco_api_client as cac
import costco_client


def make_result(item_id="10189101", name="Kirkland Signature Organic K-Cups Variety Pack (120ct)", price=49.99, price_reduced=None, in_stock=True):
    result = {
        "id": item_id,
        "retailer_id": "9" + item_id,
        "name": name,
        "url": f"https://www.costcobusinessdelivery.com/{name.lower().replace(' ', '-')}.product.{item_id}.html",
        "thumbnail": "https://bfasset.costco-static.com/U447IH35/as/img/thumb.jpg",
        "price": price,
        "currency": "USD",
        "in_stock": in_stock,
        "is_warehouse_only": False,
        "promo": "SAVE $10 online",
        "brand": "Kirkland Signature",
        "model_number": "KS-1",
        "variants": [{"id": "v1", "price": price}],
        "variants_max_price": price,
    }
    if price_reduced is not None:
        result["price_reduced"] = price_reduced
    return result


def make_page(results, success=True, no_of_pages=1, total_results=None):
    return {
        "success": success,
        "platform": "costco_business_search",
        "search": "kirkland",
        "page": 1,
        "total_results": total_results or len(results),
        "no_of_pages": no_of_pages,
        "result_count": len(results),
        "results": results,
    }


def normalized_item(item_id="10189101", name="Kirkland Test Item", price=49.99, price_reduced=None, in_stock=True):
    record = {
        "item_name": name,
        "costco_item_id": item_id,
        "source_url": f"https://www.costcobusinessdelivery.com/item.product.{item_id}.html",
        "regular_price": price,
        "sale_price": price_reduced,
        "price_basis": "sale" if price_reduced is not None else ("regular" if price is not None else None),
        "cost_basis": "business_delivery_online",
        "availability": "in_stock" if in_stock else "out_of_stock",
        "promo": None,
        "variants_count": 0,
        "variants_max_price": None,
        "brand": "Kirkland Signature",
        "model_number": None,
        "fetched_at": "2026-08-13T00:00:00+00:00",
    }
    return record


def normalized_page(items, no_of_pages=1):
    return {
        "success": True,
        "source": "unwrangle",
        "platform": "costco_business_search",
        "search": "kirkland",
        "page": 1,
        "no_of_pages": no_of_pages,
        "total_results": len(items),
        "result_count": len(items),
        "items": items,
        "data_gaps": [],
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class SearchPageTests(unittest.TestCase):
    def _run(self, payload, status_code=200, env=None):
        env = env or {"UNWRANGLE_API_KEY": "key-123"}
        env["COSTCO_CATALOG_SOURCE"] = "UNWRANGLE"
        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params, "timeout": timeout})
            return FakeResponse(payload, status_code=status_code)

        with mock.patch.dict("os.environ", env):
            with mock.patch("costco_api_client.requests.get", side_effect=fake_get):
                result = cac.search_page("kirkland", 1)
        return result, calls

    def test_success_flow_normalized(self):
        page = make_page([make_result()])
        result, calls = self._run(page)
        self.assertEqual(len(calls), 1)
        p = calls[0]["params"]
        self.assertEqual(calls[0]["url"], "https://data.unwrangle.com/api/getter/")
        self.assertEqual(calls[0]["timeout"], 60)
        self.assertEqual(p["platform"], "costco_business_search")
        self.assertEqual(p["search"], "kirkland")
        self.assertEqual(p["page"], "1")
        self.assertTrue(p["api_key"])

        self.assertIs(result["success"], True)
        self.assertEqual(result["no_of_pages"], 1)
        self.assertEqual(result["result_count"], 1)
        item = result["items"][0]
        self.assertEqual(item["item_name"], "Kirkland Signature Organic K-Cups Variety Pack (120ct)")
        self.assertEqual(item["costco_item_id"], "10189101")
        self.assertEqual(item["regular_price"], 49.99)
        self.assertIsNone(item["sale_price"])
        self.assertEqual(item["price_basis"], "regular")
        self.assertEqual(item["cost_basis"], "business_delivery_online")
        self.assertEqual(item["availability"], "in_stock")
        self.assertEqual(item["promo"], "SAVE $10 online")
        self.assertEqual(item["source_url"], result["items"][0]["source_url"])
        self.assertTrue(item["fetched_at"])

    def test_sale_price_used_as_basis(self):
        page = make_page([make_result(price_reduced=18.99)])
        result, _ = self._run(page)
        item = result["items"][0]
        self.assertEqual(item["sale_price"], 18.99)
        self.assertEqual(item["price_basis"], "sale")

    def test_out_of_stock_and_warehouse_only(self):
        page = make_page([make_result(in_stock=False)])
        result, _ = self._run(page)
        self.assertEqual(result["items"][0]["availability"], "out_of_stock")

        page = make_page([make_result(in_stock=True)])
        page["results"][0]["is_warehouse_only"] = True
        result, _ = self._run(page)
        self.assertEqual(result["items"][0]["availability"], "warehouse_only")

    def test_missing_key_no_request(self):
        result, calls = self._run(make_page([make_result()]), env={"UNWRANGLE_API_KEY": ""})
        self.assertEqual(calls, [])
        self.assertFalse(result["success"])
        self.assertTrue(any("API key" in g for g in result["data_gaps"]))

    def test_success_false(self):
        result, calls = self._run(make_page([], success=False))
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["success"])
        self.assertTrue(any("success" in g for g in result["data_gaps"]))

    def test_http_error(self):
        result, calls = self._run({"error": "boom"}, status_code=500)
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("HTTP 500" in g for g in result["data_gaps"]))

    def test_timeout(self):
        def timeout_get(url, params=None, timeout=None):
            raise cac.requests.exceptions.Timeout("t")

        with mock.patch.dict("os.environ", {"UNWRANGLE_API_KEY": "key-123", "COSTCO_CATALOG_SOURCE": "UNWRANGLE"}):
            with mock.patch("costco_api_client.requests.get", side_effect=timeout_get):
                result = cac.search_page("kirkland", 1)
        self.assertFalse(result["success"])
        self.assertTrue(any("timed out" in g for g in result["data_gaps"]))

    def test_missing_results_list(self):
        page = make_page([make_result()])
        page["results"] = None
        result, _ = self._run(page)
        self.assertFalse(result["success"])
        self.assertTrue(any("missing results" in g for g in result["data_gaps"]))


def openwebninja_product(item_number="1032932", name="Kirkland Signature Organic Raw Honey, 24 oz, 3-count", sale_price=14.99, list_price=14.99, availability="in stock"):
    return {
        "item_product_name": name,
        "item_number": item_number,
        "id": "1032932!item.en-US",
        "item_location_pricing_salePrice": sale_price,
        "item_location_pricing_listPrice": list_price,
        "item_location_availability": availability,
        "deliveryStatus": availability,
        "item_product_marketing_statement": "$5 OFF",
        "Brand_attr": ["Kirkland Signature"],
        "item_manufacturing_skus": ["096619032938"],
    }


def openwebninja_payload(products, total=None):
    return {"total_products": total if total is not None else len(products), "products": products}


class OpenWebNinjaSearchTests(unittest.TestCase):
    def _run(self, payload, status_code=200, env=None):
        env = env or {"OPENWEBNINJA_API_KEY": "ak-test"}
        calls = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
            return FakeResponse(payload, status_code=status_code)

        with mock.patch.dict("os.environ", env):
            with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "OPENWEBNINJA"}):
                with mock.patch("costco_api_client.requests.get", side_effect=fake_get):
                    result = cac._search_openwebninja("kirkland")
        return result, calls

    def test_success_flow_normalized(self):
        result, calls = self._run(openwebninja_payload([openwebninja_product()]))
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["url"], "https://api.openwebninja.com/realtime-costco-data/search")
        self.assertEqual(call["params"], {"query": "kirkland", "country": "US", "count": 10})
        self.assertEqual(call["headers"]["X-API-Key"], "ak-test")
        self.assertEqual(call["timeout"], 60)

        self.assertIs(result["success"], True)
        self.assertEqual(result["total_results"], 1)
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["source"], "openwebninja")
        item = result["items"][0]
        self.assertEqual(item["item_name"], "Kirkland Signature Organic Raw Honey, 24 oz, 3-count")
        self.assertEqual(item["costco_item_id"], "1032932")
        self.assertEqual(item["cost_basis"], "costco_online")
        self.assertEqual(item["availability"], "in_stock")
        self.assertEqual(item["promo"], "$5 OFF")
        self.assertEqual(item["source_url"], "https://www.costco.com/.product.1032932.html")
        self.assertTrue(item["url_derived"])
        self.assertEqual(item["cost_status"], "discovery_only")
        self.assertEqual(item["source"], "costco_online")
        self.assertEqual(item["price_status"], "regular")

    def test_equal_prices_treated_as_regular(self):
        result, _ = self._run(openwebninja_payload([openwebninja_product()]))
        item = result["items"][0]
        self.assertEqual(item["regular_price"], 14.99)
        self.assertEqual(item["sale_price"], 14.99)
        self.assertEqual(item["price_basis"], "regular")

    def test_differing_sale_price_used_as_basis(self):
        result, _ = self._run(openwebninja_payload([openwebninja_product(sale_price=12.99, list_price=14.99)]))
        item = result["items"][0]
        self.assertEqual(item["price_basis"], "sale")
        self.assertEqual(item["sale_price"], 12.99)

    def test_item_id_falls_back_to_id_field(self):
        result, _ = self._run(openwebninja_payload([openwebninja_product(item_number="")]))
        self.assertEqual(result["items"][0]["costco_item_id"], "1032932")

    def test_missing_key_no_request(self):
        result, calls = self._run(openwebninja_payload([openwebninja_product()]), env={"OPENWEBNINJA_API_KEY": ""})
        self.assertEqual(calls, [])
        self.assertFalse(result["success"])
        self.assertTrue(any("API key" in g for g in result["data_gaps"]))

    def test_http_error(self):
        result, calls = self._run({"error": "boom"}, status_code=500)
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("HTTP 500" in g for g in result["data_gaps"]))

    def test_timeout(self):
        def timeout_get(url, params=None, headers=None, timeout=None):
            raise cac.requests.exceptions.Timeout("t")

        with mock.patch.dict("os.environ", {"OPENWEBNINJA_API_KEY": "ak-test", "COSTCO_CATALOG_SOURCE": "OPENWEBNINJA"}):
            with mock.patch("costco_api_client.requests.get", side_effect=timeout_get):
                result = cac._search_openwebninja("kirkland")
        self.assertFalse(result["success"])
        self.assertTrue(any("timed out" in g for g in result["data_gaps"]))

    def test_missing_products(self):
        result, _ = self._run({"total_products": 0})
        self.assertFalse(result["success"])
        self.assertTrue(any("missing products" in g for g in result["data_gaps"]))

    def test_data_envelope_shape_accepted(self):
        payload = {"status": "OK", "request_id": "abc", "parameters": {}, "data": openwebninja_payload([openwebninja_product()])}
        result, _ = self._run(payload)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_results"], 1)
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["items"][0]["item_name"], "Kirkland Signature Organic Raw Honey, 24 oz, 3-count")


class ProviderDispatchTests(unittest.TestCase):
    def test_openwebninja_source_dispatches_to_openwebninja(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "OPENWEBNINJA"}):
            with mock.patch.object(cac, "_search_openwebninja", return_value={"success": True, "items": []}) as mock_ow:
                with mock.patch.object(cac, "_search_unwrangle") as mock_uw:
                    cac.search_page("kirkland", 1)
        mock_ow.assert_called_once_with("kirkland")
        mock_uw.assert_not_called()

    def test_unwrangle_source_dispatches_to_unwrangle(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE"}):
            with mock.patch.object(cac, "_search_openwebninja") as mock_ow:
                with mock.patch.object(cac, "_search_unwrangle", return_value={"success": True, "items": []}) as mock_uw:
                    cac.search_page("kirkland", 1)
        mock_ow.assert_not_called()
        mock_uw.assert_called_once_with("kirkland", 1)

    def test_off_source_returns_safe_shape_no_network(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "OFF"}):
            with mock.patch.object(cac, "requests") as mock_requests:
                result = cac.search_page("kirkland", 1)
        mock_requests.get.assert_not_called()
        self.assertFalse(result["success"])
        self.assertTrue(any("off" in g for g in result["data_gaps"]))


class TypedFailureClassificationTests(unittest.TestCase):
    """Batch 08: every result dict carries a typed `failure_type` so callers
    can distinguish auth_error from not_found from rate_limited from
    transport_error from malformed_response without parsing the
    data_gaps string. Zero network: all responses are mocked."""

    # ----- Unwrangle search -----
    def _unwrangle_env(self, key=""):
        env = {"UNWRANGLE_API_KEY": key, "COSTCO_CATALOG_SOURCE": "UNWRANGLE"}
        return env

    def test_unwrangle_missing_key_is_auth_error(self):
        with mock.patch.dict("os.environ", self._unwrangle_env(key="")):
            with mock.patch("costco_api_client.requests.get") as mock_get:
                result = cac._search_unwrangle("kirkland", 1)
        mock_get.assert_not_called()
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertFalse(result["success"])
        self.assertIsNone(result["http_status"])

    def test_unwrangle_http_200_success(self):
        page = make_page([make_result()])
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse(page, status_code=200)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "success")
        self.assertTrue(result["success"])
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["result_count"], 1)

    def test_unwrangle_http_401_is_auth_error(self):
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=401)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertEqual(result["http_status"], 401)
        self.assertFalse(result["success"])

    def test_unwrangle_http_403_is_auth_error(self):
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=403)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertEqual(result["http_status"], 403)
        self.assertFalse(result["success"])

    def test_unwrangle_http_404_is_not_found(self):
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=404)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "not_found")
        self.assertEqual(result["http_status"], 404)
        self.assertFalse(result["success"])

    def test_unwrangle_http_429_is_rate_limited(self):
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=429)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "rate_limited")
        self.assertEqual(result["http_status"], 429)
        self.assertFalse(result["success"])

    def test_unwrangle_timeout_is_transport_error(self):
        def timeout_get(url, params=None, timeout=None):
            raise cac.requests.exceptions.Timeout("t")
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get", side_effect=timeout_get):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "transport_error")
        self.assertFalse(result["success"])

    def test_unwrangle_network_error_is_transport_error(self):
        def net_get(url, params=None, timeout=None):
            raise cac.requests.exceptions.ConnectionError("dns")
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get", side_effect=net_get):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "transport_error")
        self.assertFalse(result["success"])

    def test_unwrangle_malformed_json_is_malformed_response(self):
        class BadJson:
            status_code = 200
            def json(self):
                raise ValueError("not json")
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get", return_value=BadJson()):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "malformed_response")
        self.assertEqual(result["http_status"], 200)
        self.assertFalse(result["success"])

    def test_unwrangle_success_false_is_malformed_response(self):
        page = make_page([make_result()], success=False)
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse(page, status_code=200)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "malformed_response")
        self.assertEqual(result["http_status"], 200)
        self.assertFalse(result["success"])

    def test_unwrangle_results_not_list_is_malformed_response(self):
        page = make_page([make_result()])
        page["results"] = "not a list"
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse(page, status_code=200)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "malformed_response")
        self.assertEqual(result["http_status"], 200)
        self.assertFalse(result["success"])

    # ----- OpenWebNinja search -----
    def _openwebninja_env(self, key=""):
        return {"OPENWEBNINJA_API_KEY": key, "COSTCO_CATALOG_SOURCE": "OPENWEBNINJA"}

    def test_openwebninja_missing_key_is_auth_error(self):
        with mock.patch.dict("os.environ", self._openwebninja_env(key="")):
            with mock.patch("costco_api_client.requests.get") as mock_get:
                result = cac._search_openwebninja("kirkland")
        mock_get.assert_not_called()
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertFalse(result["success"])

    def test_openwebninja_http_200_success(self):
        product = {
            "item_product_name": "Kirkland Honey",
            "item_number": "12345",
            "id": "12345",
            "item_location_pricing_listPrice": 19.99,
            "item_location_pricing_salePrice": 19.99,
            "item_location_availability": "in stock",
            "Brand_attr": ["Kirkland"],
        }
        payload = {"total_products": 1, "products": [product]}
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse(payload, status_code=200)):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "success")
        self.assertTrue(result["success"])
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["result_count"], 1)

    def test_openwebninja_http_401_is_auth_error(self):
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=401)):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertEqual(result["http_status"], 401)

    def test_openwebninja_http_403_is_auth_error(self):
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=403)):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertEqual(result["http_status"], 403)

    def test_openwebninja_http_404_is_not_found(self):
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=404)):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "not_found")
        self.assertEqual(result["http_status"], 404)

    def test_openwebninja_http_429_is_rate_limited(self):
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=429)):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "rate_limited")
        self.assertEqual(result["http_status"], 429)

    def test_openwebninja_timeout_is_transport_error(self):
        def timeout_get(url, params=None, headers=None, timeout=None):
            raise cac.requests.exceptions.Timeout("t")
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get", side_effect=timeout_get):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "transport_error")

    def test_openwebninja_malformed_json_is_malformed_response(self):
        class BadJson:
            status_code = 200
            def json(self):
                raise ValueError("not json")
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get", return_value=BadJson()):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "malformed_response")
        self.assertEqual(result["http_status"], 200)

    def test_openwebninja_missing_products_is_malformed_response(self):
        payload = {"total_products": 0, "data": {}}
        with mock.patch.dict("os.environ", self._openwebninja_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse(payload, status_code=200)):
                result = cac._search_openwebninja("kirkland")
        self.assertEqual(result["failure_type"], "malformed_response")
        self.assertEqual(result["http_status"], 200)
        self.assertFalse(result["success"])

    # ----- Auth vs not_found are NEVER conflated (Batch 08 hard requirement) -----
    def test_auth_error_never_collapses_to_not_found(self):
        """An HTTP 401/403 must NEVER be reported as not_found, even if
        the response body is empty. The two states must remain
        distinguishable in the failure_type discriminator."""
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=401)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertNotEqual(result["failure_type"], "not_found")

    def test_not_found_never_collapses_to_auth_error(self):
        """An HTTP 404 must NEVER be reported as auth_error."""
        with mock.patch.dict("os.environ", self._unwrangle_env(key="abc")):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=404)):
                result = cac._search_unwrangle("kirkland", 1)
        self.assertEqual(result["failure_type"], "not_found")
        self.assertNotEqual(result["failure_type"], "auth_error")

    # ----- product-detail refresh also carries typed failure -----
    def test_refresh_product_details_missing_unwrangle_key_is_auth_error(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE",
                                            "COSTCO_CATALOG_DETAIL_ENABLED": "1",
                                            "UNWRANGLE_API_KEY": ""}):
            with mock.patch("costco_api_client.requests.get") as mock_get:
                result = cac.refresh_product_details(["424976"])
        mock_get.assert_not_called()
        self.assertEqual(result["failure_type"], "auth_error")
        self.assertEqual(result["fetched"], 0)

    def test_refresh_product_details_http_401_is_auth_error(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE",
                                            "COSTCO_CATALOG_DETAIL_ENABLED": "1",
                                            "UNWRANGLE_API_KEY": "abc"}):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=401)):
                result = cac.refresh_product_details(["424976"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["failure_type"], "auth_error")
        self.assertEqual(result["failures"][0]["item_id"], "424976")

    def test_refresh_product_details_http_404_is_not_found(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE",
                                            "COSTCO_CATALOG_DETAIL_ENABLED": "1",
                                            "UNWRANGLE_API_KEY": "abc"}):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=404)):
                result = cac.refresh_product_details(["424976"])
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["failure_type"], "not_found")

    def test_refresh_product_details_http_429_is_rate_limited(self):
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE",
                                            "COSTCO_CATALOG_DETAIL_ENABLED": "1",
                                            "UNWRANGLE_API_KEY": "abc"}):
            with mock.patch("costco_api_client.requests.get",
                            return_value=FakeResponse({}, status_code=429)):
                result = cac.refresh_product_details(["424976"])
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["failure_type"], "rate_limited")

    def test_refresh_product_details_timeout_is_transport_error(self):
        def timeout_get(url, params=None, timeout=None):
            raise cac.requests.exceptions.Timeout("t")
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE",
                                            "COSTCO_CATALOG_DETAIL_ENABLED": "1",
                                            "UNWRANGLE_API_KEY": "abc"}):
            with mock.patch("costco_api_client.requests.get", side_effect=timeout_get):
                result = cac.refresh_product_details(["424976"])
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["failure_type"], "transport_error")

    def test_refresh_product_details_invalid_json_is_malformed_response(self):
        class BadJson:
            status_code = 200
            def json(self):
                raise ValueError("not json")
        with mock.patch.dict("os.environ", {"COSTCO_CATALOG_SOURCE": "UNWRANGLE",
                                            "COSTCO_CATALOG_DETAIL_ENABLED": "1",
                                            "UNWRANGLE_API_KEY": "abc"}):
            with mock.patch("costco_api_client.requests.get", return_value=BadJson()):
                result = cac.refresh_product_details(["424976"])
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["failure_type"], "malformed_response")


class OpenWebNinjaRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.csv_path = os.path.join(self.tmpdir.name, "costco-items.csv")
        self.snapshot_path = os.path.join(self.tmpdir.name, "snapshot.json")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")

    def test_refresh_uses_single_request_regardless_of_max_pages(self):
        calls = []

        def fake_search(query, page):
            calls.append(query)
            return normalized_page([normalized_item()])

        env = {
            "UNWRANGLE_API_KEY": "",
            "OPENWEBNINJA_API_KEY": "ak-test",
            "COSTCO_CATALOG_SOURCE": "OPENWEBNINJA",
            "COSTCO_CATALOG_MAX_PAGES": "3",
            "COSTCO_CATALOG_SNAPSHOT_PATH": self.snapshot_path,
            "COSTCO_CATALOG_ARCHIVE_PATH": os.path.join(self.tmpdir.name, "discovery-archive.json"),
            "COSTCO_CATALOG_RUN_REPORT_PATH": os.path.join(self.tmpdir.name, "run-report.json"),
            "COSTCO_CATALOG_REQUEST_DELAY_SECONDS": "0",
            "COSTCO_API_COST_BUFFER_PERCENT": "10",
        }
        with mock.patch.dict("os.environ", env):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page", side_effect=fake_search):
                    report = cac.refresh_catalog()
        self.assertEqual(calls, ["kirkland"])
        self.assertEqual(report["pages_fetched"], 1)
        self.assertEqual(report["requests_used"], 1)
        self.assertEqual(report["cost_basis"], "costco_online")

    def test_status_reports_openwebninja_key_configured(self):
        with mock.patch.dict("os.environ", {
            "COSTCO_CATALOG_SOURCE": "OPENWEBNINJA",
            "OPENWEBNINJA_API_KEY": "ak-test",
            "UNWRANGLE_API_KEY": "",
        }):
            info = cac.status()
        self.assertEqual(info["catalog_source"], "OPENWEBNINJA")
        self.assertTrue(info["api_key_configured"])


class ExportCostTests(unittest.TestCase):
    def test_sale_price_wins_over_regular(self):
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "10"}):
            record = {"sale_price": 18.99, "regular_price": 21.99}
            self.assertEqual(cac._cost_to_export(record), round(18.99 * 1.10, 2))

    def test_regular_price_fallback(self):
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "0"}):
            record = {"sale_price": None, "regular_price": 21.99}
            self.assertEqual(cac._cost_to_export(record), 21.99)

    def test_no_price_returns_none(self):
        record = {"sale_price": None, "regular_price": None}
        self.assertIsNone(cac._cost_to_export(record))

    def test_invalid_buffer_falls_back_to_default(self):
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "abc"}):
            record = {"sale_price": 20.0, "regular_price": 20.0}
            self.assertEqual(cac._cost_to_export(record), round(20.0 * 1.10, 2))


class PackTokenTests(unittest.TestCase):
    def test_pack_tokens_extracted(self):
        self.assertEqual(cac._pack_tokens("Kirkland K-Cups (120ct)"), {"120ct"})
        self.assertEqual(cac._pack_tokens("Kirkland Almonds (2x3lb)"), {"2x3lb"})
        self.assertEqual(cac._pack_tokens("Plain Name"), set())


class ReconcileTests(unittest.TestCase):
    def test_exact_title_updates_existing_row(self):
        existing = [{"item_name": "Kirkland Test Item", "costco_cost": "5.00"}]
        items = [normalized_item(item_id="1", name="Kirkland Test Item", price=10.0)]
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "10"}):
            with mock.patch.object(cac, "_now_iso", return_value="2026-08-13T00:00:00+00:00"):
                reconciled = cac._reconcile(items, existing)
        self.assertEqual(len(reconciled["rows"]), 1)
        self.assertEqual(reconciled["rows"][0]["item_name"], "Kirkland Test Item")
        self.assertEqual(reconciled["rows"][0]["costco_cost"], round(10.0 * 1.10, 2))
        self.assertEqual(reconciled["unmatched"], [])
        self.assertEqual(reconciled["stale"], [])

    def test_new_item_appended(self):
        existing = [{"item_name": "Kirkland Test Item", "costco_cost": "5.00"}]
        items = [normalized_item(item_id="2", name="Kirkland New Product", price=7.0)]
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "10"}):
            reconciled = cac._reconcile(items, existing)
        self.assertEqual(len(reconciled["rows"]), 2)
        self.assertEqual(reconciled["rows"][1]["item_name"], "Kirkland New Product")

    def test_pack_size_conflict_goes_unmatched(self):
        existing = [{"item_name": "Kirkland Olive Oil (1L)", "costco_cost": "8.00"}]
        items = [normalized_item(item_id="3", name="Kirkland Olive Oil (500ml)", price=6.0)]
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "0"}):
            reconciled = cac._reconcile(items, existing)
        self.assertEqual(len(reconciled["rows"]), 1)
        self.assertEqual(reconciled["unmatched"][0]["reason"], "pack_size_conflict")

    def test_duplicate_api_names_flagged(self):
        items = [
            normalized_item(item_id="4", name="Kirkland Coffee (120ct)", price=10.0),
            normalized_item(item_id="5", name="Kirkland Coffee (120ct)", price=9.0),
        ]
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "0"}):
            reconciled = cac._reconcile(items, [])
        self.assertEqual(len(reconciled["rows"]), 1)
        self.assertEqual(len(reconciled["unmatched"]), 1)
        self.assertEqual(reconciled["unmatched"][0]["reason"], "duplicate_name")

    def test_no_price_preserved_for_review(self):
        items = [normalized_item(item_id="6", name="Kirkland Mystery", price=None)]
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "0"}):
            reconciled = cac._reconcile(items, [])
        self.assertEqual(reconciled["rows"], [])
        self.assertEqual(reconciled["unmatched"][0]["reason"], "no_price")

    def test_stale_rows_preserved(self):
        existing = [{"item_name": "Kirkland Kept Row", "costco_cost": "3.00"}]
        items = [normalized_item(item_id="7", name="Kirkland New Item", price=5.0)]
        with mock.patch.dict("os.environ", {"COSTCO_API_COST_BUFFER_PERCENT": "0"}):
            reconciled = cac._reconcile(items, existing)
        self.assertEqual(len(reconciled["stale"]), 1)
        self.assertEqual(reconciled["stale"][0]["item_name"], "Kirkland Kept Row")
        self.assertEqual(len(reconciled["rows"]), 2)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.csv_path = os.path.join(self.tmpdir.name, "costco-items.csv")
        self.snapshot_path = os.path.join(self.tmpdir.name, "snapshot.json")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")

    def _env(self, source="UNWRANGLE", **overrides):
        env = {
            "UNWRANGLE_API_KEY": "key-123",
            "COSTCO_CATALOG_SOURCE": source,
            "COSTCO_CATALOG_SNAPSHOT_PATH": self.snapshot_path,
            "COSTCO_CATALOG_ARCHIVE_PATH": os.path.join(self.tmpdir.name, "discovery-archive.json"),
            "COSTCO_CATALOG_RUN_REPORT_PATH": os.path.join(self.tmpdir.name, "run-report.json"),
            "COSTCO_CATALOG_REQUEST_DELAY_SECONDS": "0",
            "COSTCO_API_COST_BUFFER_PERCENT": "10",
        }
        env.update(overrides)
        return env

    def test_refresh_writes_snapshot_and_csv(self):
        page = normalized_page([normalized_item()])
        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page", return_value=page):
                    report = cac.refresh_catalog()
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["pages_fetched"], 1)
        self.assertEqual(report["items_fetched"], 1)
        self.assertEqual(report["credits_estimate"], 10)
        self.assertEqual(report["csv_rows_written"], 1)

        with open(self.snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        self.assertEqual(snapshot["query"], "kirkland")
        self.assertEqual(len(snapshot["items"]), 1)
        self.assertEqual(snapshot["items"][0]["cost_basis"], "business_delivery_online")
        self.assertTrue(snapshot["generated_at"])

        with open(self.csv_path, "r", encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        self.assertEqual(lines[0], "item_name,costco_cost")
        self.assertIn("54.99", lines[1])

    def test_refresh_respects_max_pages_cap(self):
        calls = []

        def fake_search(query, page):
            calls.append(page)
            return normalized_page([normalized_item(item_id=str(page))], no_of_pages=3)

        with mock.patch.dict("os.environ", self._env(COSTCO_CATALOG_MAX_PAGES="2")):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page", side_effect=fake_search):
                    report = cac.refresh_catalog()
        self.assertEqual(calls, [1, 2])
        self.assertEqual(report["pages_fetched"], 2)
        self.assertEqual(report["credits_estimate"], 20)

    def test_disabled_source_never_calls_network(self):
        with mock.patch.dict("os.environ", self._env(source="OFF")):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page") as mock_search:
                    report = cac.refresh_catalog()
        mock_search.assert_not_called()
        self.assertEqual(report["status"], "disabled")

    def test_failed_refresh_preserves_last_good_snapshot(self):
        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page", return_value={"success": False, "items": [], "data_gaps": ["boom"]}):
                    report = cac.refresh_catalog()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["pages_fetched"], 0)
        self.assertFalse(os.path.exists(self.snapshot_path))

    def test_export_from_snapshot_no_network(self):
        with open(self.snapshot_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": "2026-08-13T00:00:00+00:00",
                "query": "kirkland",
                "items": [normalized_item()],
                "unmatched": [],
                "stale_rows": [],
                "data_gaps": [],
            }, f)

        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "requests") as mock_requests:
                    report = cac.export_catalog()
        mock_requests.get.assert_not_called()
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["csv_rows_written"], 1)
        with open(self.csv_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("item_name,costco_cost", content)
        self.assertIn("54.99", content)

    def test_export_missing_snapshot(self):
        with mock.patch.dict("os.environ", {
            "COSTCO_CATALOG_SNAPSHOT_PATH": "missing.json",
            "COSTCO_CATALOG_ARCHIVE_PATH": "missing-archive.json",
        }):
            report = cac.export_catalog()
        self.assertEqual(report["status"], "missing_snapshot")


class DiscoveryCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.csv_path = os.path.join(self.tmpdir.name, "costco-items.csv")
        self.snapshot_path = os.path.join(self.tmpdir.name, "snapshot.json")
        self.archive_path = os.path.join(self.tmpdir.name, "discovery-archive.json")
        self.run_report_path = os.path.join(self.tmpdir.name, "run-report.json")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")

    def _env(self, **overrides):
        env = {
            "UNWRANGLE_API_KEY": "key-123",
            "COSTCO_CATALOG_SOURCE": "UNWRANGLE",
            "COSTCO_CATALOG_SNAPSHOT_PATH": self.snapshot_path,
            "COSTCO_CATALOG_ARCHIVE_PATH": self.archive_path,
            "COSTCO_CATALOG_RUN_REPORT_PATH": self.run_report_path,
            "COSTCO_CATALOG_REQUEST_DELAY_SECONDS": "0",
            "COSTCO_API_COST_BUFFER_PERCENT": "10",
            "COSTCO_DELIVERY_ZIP": "75201",
            "COSTCO_BUSINESS_CENTER": "Dallas Business Center",
        }
        env.update(overrides)
        return env

    def _run(self, pages, **overrides):
        with mock.patch.dict("os.environ", self._env(**overrides)):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page", side_effect=pages):
                    return cac.refresh_catalog()

    def test_archive_is_append_only_no_overwrite(self):
        first = self._run([normalized_page([normalized_item()])])
        self.assertEqual(first["counts"]["fetched"], 1)
        second_item = normalized_item()
        second_item["fetched_at"] = "2026-08-13T00:01:00+00:00"
        second = self._run([normalized_page([second_item])])
        self.assertEqual(second["counts"]["fetched"], 1)

        with open(self.archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)
        self.assertEqual(len(archive["records"]), 2)
        self.assertEqual(archive["records"][0]["item_name"], "Kirkland Test Item")
        self.assertEqual(archive["records"][1]["item_name"], "Kirkland Test Item")
        self.assertNotEqual(archive["records"][0]["fetched_at"], archive["records"][1]["fetched_at"])

    def test_archive_records_carry_discovery_fields(self):
        record = cac._normalize_item({
            "id": "777",
            "name": "Kirkland Paper Towels",
            "url": "https://example.com/item",
            "price": 19.99,
            "pack_size": "12 rolls",
            "in_stock": True,
        }, "2026-08-13T00:00:00+00:00", {"delivery_zip": "75201", "business_center": "Dallas Business Center"})
        self.assertEqual(record["raw_title"], "Kirkland Paper Towels")
        self.assertEqual(record["pack_size"], "12 rolls")
        self.assertEqual(record["unit_count"], 12)
        self.assertEqual(record["price_status"], "regular")
        self.assertEqual(record["source"], "business_delivery")
        self.assertEqual(record["cost_status"], "discovery_only")
        self.assertEqual(record["location"]["delivery_zip"], "75201")
        self.assertEqual(record["url_derived"], False)

    def test_within_run_duplicate_id_skipped(self):
        page = normalized_page([
            normalized_item(item_id="42", name="Kirkland Coffee (120ct)", price=10.0),
            normalized_item(item_id="42", name="Kirkland Coffee (120ct)", price=9.0),
        ])
        report = self._run([page])
        self.assertEqual(report["counts"]["fetched"], 1)
        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertEqual(report["skipped"], ["Kirkland Coffee (120ct)"])

    def test_within_run_title_conflict_held(self):
        page = normalized_page([
            normalized_item(item_id="42", name="Kirkland Coffee (120ct)", price=10.0),
            normalized_item(item_id="42", name="Kirkland Coffee (240ct)", price=19.0),
        ])
        report = self._run([page])
        self.assertEqual(report["counts"]["fetched"], 1)
        self.assertEqual(report["counts"]["held_for_review"], 1)
        self.assertEqual(report["held_for_review"][0]["reason"], "title_conflict")

    def test_archive_title_conflict_held_no_overwrite(self):
        self._run([normalized_page([normalized_item(item_id="7", name="Kirkland Alpha")])])
        report = self._run([normalized_page([normalized_item(item_id="7", name="Kirkland Beta")])])
        self.assertEqual(report["counts"]["fetched"], 0)
        self.assertEqual(report["counts"]["held_for_review"], 1)
        self.assertEqual(report["held_for_review"][0]["reason"], "title_conflict")
        with open(self.archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)
        self.assertEqual(len(archive["records"]), 1)
        self.assertEqual(archive["records"][0]["item_name"], "Kirkland Alpha")

    def test_archive_pack_size_conflict_held(self):
        page = normalized_page([{
            **normalized_item(item_id="9", name="Kirkland Olive Oil (1L)", price=10.0),
            "pack_size": "1L",
        }])
        self._run([page])
        page2 = normalized_page([{
            **normalized_item(item_id="9", name="Kirkland Olive Oil (1L)", price=10.0),
            "pack_size": "2L",
        }])
        report = self._run([page2])
        self.assertEqual(report["counts"]["held_for_review"], 1)
        self.assertEqual(report["held_for_review"][0]["reason"], "pack_size_conflict")

    def test_rate_limit_sleeps_between_requests(self):
        calls = []

        def fake_search(query, page):
            calls.append(page)
            return normalized_page([normalized_item(item_id=str(page))], no_of_pages=3)

        with mock.patch.dict("os.environ", self._env(
            COSTCO_CATALOG_MAX_PAGES="2",
            COSTCO_CATALOG_REQUEST_DELAY_SECONDS="1.5",
        )):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                with mock.patch.object(cac, "search_page", side_effect=fake_search):
                    with mock.patch.object(cac.time, "sleep") as mock_sleep:
                        report = cac.refresh_catalog()
        self.assertEqual(calls, [1, 2])
        mock_sleep.assert_called_once_with(1.5)
        self.assertEqual(report["request_delay_seconds"], 1.5)

    def test_stop_on_403_preserves_archive_and_writes_report(self):
        report = self._run([{
            "success": False,
            "source": "unwrangle",
            "http_status": 403,
            "items": [],
            "data_gaps": ["OpenWebNinja API returned HTTP 403."],
        }])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stop_reason"], "blocked")
        self.assertFalse(os.path.exists(self.archive_path))
        self.assertFalse(os.path.exists(self.snapshot_path))
        self.assertTrue(os.path.exists(self.run_report_path))
        with open(self.run_report_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["counts"]["failed"], 1)

    def test_stop_on_429_reports_rate_limited(self):
        report = self._run([{
            "success": False,
            "source": "unwrangle",
            "http_status": 429,
            "items": [],
            "data_gaps": ["rate limited"],
        }])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stop_reason"], "rate_limited")

    def test_run_report_has_counts(self):
        page = normalized_page([normalized_item()])
        report = self._run([page])
        self.assertEqual(report["counts"], {"fetched": 1, "updated": 0, "skipped": 0, "held_for_review": 0, "failed": 0})
        self.assertEqual(report["fetched"], ["Kirkland Test Item"])
        self.assertEqual(report["location"]["delivery_zip"], "75201")
        self.assertEqual(report["cost_status"], "discovery_only")
        second = self._run([page])
        self.assertEqual(second["counts"]["updated"], 1)
        self.assertEqual(second["updated"], ["Kirkland Test Item"])
        with open(self.run_report_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["counts"]["fetched"], 1)


class _FakeDatetime(cac.datetime):
    """datetime stub with a fixed `now` (datetime class is immutable in 3.14)."""
    _fixed = None

    @classmethod
    def now(cls, tz=None):
        return cls._fixed


class FreshnessStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.report_path = os.path.join(self.tmpdir.name, "run-report.json")

    def _env(self, **overrides):
        env = {
            "COSTCO_CATALOG_RUN_REPORT_PATH": self.report_path,
            "COSTCO_CATALOG_ARCHIVE_PATH": os.path.join(self.tmpdir.name, "discovery-archive.json"),
            "COSTCO_FRESHNESS_THRESHOLD_DAYS": "8",
            "COSTCO_DELIVERY_ZIP": "75201",
            "COSTCO_BUSINESS_CENTER": "Dallas Business Center",
        }
        env.update(overrides)
        return env

    def _write_report(self, payload):
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_no_report_yet_is_unknown(self):
        with mock.patch.dict("os.environ", self._env()):
            info = cac.last_run_status()
        self.assertEqual(info["freshness"], "unknown")
        self.assertIsNone(info["status"])
        self.assertEqual(info["location"]["delivery_zip"], "75201")

    def test_clean_recent_run_is_fresh(self):
        self._write_report({
            "status": "ok",
            "generated_at": "2026-08-16T03:00:00+00:00",
            "stop_reason": None,
            "location": {"delivery_zip": "75201", "business_center": "Dallas Business Center"},
            "counts": {"fetched": 24, "updated": 3, "skipped": 0, "held_for_review": 1, "failed": 0},
        })
        fixed_now = cac.datetime(2026, 8, 18, 3, 0, 0, tzinfo=cac.timezone.utc)
        _FakeDatetime._fixed = fixed_now
        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(cac, "datetime", _FakeDatetime):
                info = cac.last_run_status()
        self.assertEqual(info["freshness"], "fresh")
        self.assertEqual(info["last_fetched_count"], 24)
        self.assertEqual(info["status"], "ok")
        self.assertIsNone(info["stop_reason"])

    def test_blocked_run_is_stale(self):
        self._write_report({
            "status": "failed",
            "generated_at": "2026-08-16T03:00:00+00:00",
            "stop_reason": "blocked",
            "counts": {"fetched": 0, "updated": 0, "skipped": 0, "held_for_review": 0, "failed": 1},
        })
        _FakeDatetime._fixed = cac.datetime(2026, 8, 16, 3, 5, 0, tzinfo=cac.timezone.utc)
        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(cac, "datetime", _FakeDatetime):
                info = cac.last_run_status()
        self.assertEqual(info["freshness"], "stale")
        self.assertEqual(info["stop_reason"], "blocked")
        self.assertIn("blocked", info["message"])

    def test_clean_but_old_run_is_stale(self):
        self._write_report({
            "status": "ok",
            "generated_at": "2026-07-20T03:00:00+00:00",
            "stop_reason": None,
            "counts": {"fetched": 24, "updated": 0, "skipped": 0, "held_for_review": 0, "failed": 0},
        })
        _FakeDatetime._fixed = cac.datetime(2026, 8, 16, 3, 0, 0, tzinfo=cac.timezone.utc)
        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(cac, "datetime", _FakeDatetime):
                info = cac.last_run_status()
        self.assertEqual(info["freshness"], "stale")
        self.assertEqual(info["staleness_days"], 27.0)

    def test_report_without_timestamp_is_stale(self):
        self._write_report({"status": "ok", "counts": {}})
        with mock.patch.dict("os.environ", self._env()):
            info = cac.last_run_status()
        self.assertEqual(info["freshness"], "stale")


class StructuredPackTests(unittest.TestCase):
    def _parse(self, value):
        return cac._parse_structured_pack(value)

    def test_weight_lb(self):
        out = self._parse("40 lb")
        self.assertEqual(out["net_weight"], 40.0)
        self.assertEqual(out["unit_of_measure"], "lb")

    def test_oz_weight(self):
        out = self._parse("24 oz")
        self.assertEqual(out["net_weight"], 24.0)
        self.assertEqual(out["unit_of_measure"], "oz")

    def test_volume_units(self):
        self.assertEqual(self._parse("1 gallon")["unit_of_measure"], "gal")
        self.assertEqual(self._parse("500 ml")["unit_of_measure"], "ml")
        self.assertEqual(self._parse("33.8 fl oz")["unit_of_measure"], "floz")

    def test_pack_and_case_counts(self):
        out = self._parse("72 ct, 2 cases")
        self.assertEqual(out["pack_count"], 72)
        self.assertEqual(out["case_count"], 2)

    def test_pack_only(self):
        out = self._parse("120ct")
        self.assertEqual(out["pack_count"], 120)
        self.assertIsNone(out["net_weight"])

    def test_nothing_parseable_is_none(self):
        out = self._parse("Kirkland Plain Name")
        self.assertEqual(out, {
            "net_weight": None, "unit_of_measure": None,
            "pack_count": None, "case_count": None,
        })

    def test_none_input_is_none(self):
        self.assertEqual(self._parse(None)["net_weight"], None)


class DiscoverySchemaTests(unittest.TestCase):
    def test_unwrangle_record_carries_structured_schema(self):
        record = cac._normalize_item({
            "id": "777",
            "name": "Kirkland Adult Dog Food, Chicken, 40 lb",
            "url": "https://example.com/item",
            "price": 49.99,
            "pack_size": "40 lb",
            "upc": "012345678901",
            "brand": "Kirkland Signature",
            "flavor": "Chicken",
            "product_line": "Adult Dog Food",
            "in_stock": True,
        }, "2026-08-13T00:00:00+00:00", {"delivery_zip": "75201", "business_center": "Dallas Business Center"})
        self.assertEqual(record["upc_or_ean"], "012345678901")
        self.assertEqual(record["brand"], "Kirkland Signature")
        self.assertEqual(record["product_line"], "Adult Dog Food")
        self.assertEqual(record["formula_or_flavor"], "Chicken")
        self.assertEqual(record["net_weight"], 40.0)
        self.assertEqual(record["unit_of_measure"], "lb")
        self.assertEqual(record["warehouse_or_zip"], "75201")
        self.assertEqual(record["product_url"], "https://example.com/item")
        self.assertEqual(record["last_seen_at"], record["fetched_at"])

    def test_unwrangle_record_missing_data_is_none_not_invented(self):
        record = cac._normalize_item({
            "id": "778",
            "name": "Kirkland Item",
            "url": "https://example.com/item",
            "price": 9.99,
            "in_stock": True,
        }, "2026-08-13T00:00:00+00:00", None)
        self.assertIsNone(record["upc_or_ean"])
        self.assertIsNone(record["brand"])
        self.assertIsNone(record["net_weight"])
        self.assertIsNone(record["pack_count"])
        self.assertEqual(record["warehouse_or_zip"], "75201")

    def test_openwebninja_record_carries_structured_schema(self):
        record = cac._normalize_openwebninja_item({
            "item_number": "1032932",
            "item_product_name": "Kirkland Signature Organic Raw Honey, 24 oz, 3-count",
            "item_location_pricing_listPrice": 14.99,
            "item_product_url": "https://www.costco.com/.product.1032932.html",
            "Brand_attr": ["Kirkland Signature"],
            "Container_Size_attr": ["24 oz, 3-count"],
            "ean": ["0123456789012"],
        }, "2026-08-13T00:00:00+00:00", None)
        self.assertEqual(record["upc_or_ean"], "0123456789012")
        self.assertEqual(record["brand"], "Kirkland Signature")
        self.assertEqual(record["net_weight"], 24.0)
        self.assertEqual(record["unit_of_measure"], "oz")
        self.assertEqual(record["pack_count"], 3)
        self.assertEqual(record["product_url"], "https://www.costco.com/.product.1032932.html")
        self.assertEqual(record["last_seen_at"], record["fetched_at"])


class ProductDetailLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.detail_path = os.path.join(self.tmpdir.name, "product-detail.json")
        self.invoice_path = os.path.join(self.tmpdir.name, "invoice-confirmed.json")
        self.csv_path = os.path.join(self.tmpdir.name, "costco-items.csv")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")

    def _env(self, **overrides):
        env = {
            "COSTCO_CATALOG_DETAIL_PATH": self.detail_path,
            "COSTCO_INVOICE_PATH": self.invoice_path,
            "COSTCO_CATALOG_SOURCE": "UNWRANGLE",
            "UNWRANGLE_API_KEY": "key-123",
            "COSTCO_CATALOG_REQUEST_DELAY_SECONDS": "0",
        }
        env.update(overrides)
        return env

    def _write_import_csv(self, path, header, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    def test_import_product_detail_csv(self):
        import_path = os.path.join(self.tmpdir.name, "details.csv")
        self._write_import_csv(import_path, [
            "costco_item_number", "item_name", "current_price", "upc_or_ean", "net_weight", "unit_of_measure",
        ], [["12345", "Kirkland Signature Adult Dog Food Chicken 40 lb", "29.99", "012345678901", "40", "lb"]])
        with mock.patch.dict("os.environ", self._env()):
            report = cac.import_product_detail(import_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["imported"], 1)
        with open(self.detail_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        self.assertEqual(records[0]["costco_item_id"], "12345")
        self.assertEqual(records[0]["upc_or_ean"], "012345678901")
        self.assertEqual(records[0]["net_weight"], 40.0)
        self.assertEqual(records[0]["cost_status"], "detail_only")
        self.assertEqual(records[0]["source"], "product_detail_import")

    def test_import_product_detail_duplicate_held(self):
        import_path = os.path.join(self.tmpdir.name, "details.csv")
        self._write_import_csv(import_path, ["costco_item_number", "item_name", "current_price"],
                               [["9", "Kirkland Alpha", "10.0"], ["9", "Kirkland Beta", "12.0"]])
        with mock.patch.dict("os.environ", self._env()):
            report = cac.import_product_detail(import_path)
        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["held_for_review"], 1)
        self.assertEqual(report["held"][0]["reason"], "duplicate costco_item_id")

    def test_import_product_detail_missing_fields_held(self):
        import_path = os.path.join(self.tmpdir.name, "details.csv")
        self._write_import_csv(import_path, ["costco_item_number", "item_name", "current_price"],
                               [["9", "Kirkland Alpha", ""]])
        with mock.patch.dict("os.environ", self._env()):
            report = cac.import_product_detail(import_path)
        self.assertEqual(report["imported"], 0)
        self.assertEqual(report["held_for_review"], 1)

    def test_refresh_product_details_disabled_makes_no_requests(self):
        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append(params)
            return FakeResponse({"result": {"id": "5", "name": "Kirkland X", "price": 5.0}})

        with mock.patch.dict("os.environ", self._env()):
            with mock.patch("costco_api_client.requests.get", side_effect=fake_get):
                report = cac.refresh_product_details(["5"])
        self.assertEqual(report["status"], "disabled")
        self.assertEqual(calls, [])

    def test_refresh_product_details_fetches_and_writes(self):
        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append(params)
            return FakeResponse({"result": {
                "id": "5", "name": "Kirkland Adult Dog Food Chicken 40 lb",
                "price": 29.99, "pack_size": "40 lb", "upc": "012345678901",
            }})

        with mock.patch.dict("os.environ", self._env(COSTCO_CATALOG_DETAIL_ENABLED="1")):
            with mock.patch("costco_api_client.requests.get", side_effect=fake_get):
                report = cac.refresh_product_details(["5"])
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["fetched"], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["platform"], "costco_business_detail")
        self.assertEqual(calls[0]["item"], "5")
        with open(self.detail_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        self.assertEqual(records[0]["costco_item_id"], "5")
        self.assertEqual(records[0]["cost_status"], "detail_only")

    def test_refresh_product_details_stops_on_block(self):
        with mock.patch.dict("os.environ", self._env(COSTCO_CATALOG_DETAIL_ENABLED="1")):
            with mock.patch("costco_api_client.requests.get", return_value=FakeResponse({}, status_code=429)):
                report = cac.refresh_product_details(["5", "6"])
        self.assertEqual(report["status"], "failed")
        # Batch 08: failure entries now carry typed failure_type (rate_limited for 429)
        self.assertEqual(report["failures"],
                         [{"item_id": "5", "reason": "http_429", "failure_type": "rate_limited"}])
        self.assertEqual(report["fetched"], 0)
        self.assertFalse(os.path.exists(self.detail_path))


class InvoiceLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.detail_path = os.path.join(self.tmpdir.name, "product-detail.json")
        self.invoice_path = os.path.join(self.tmpdir.name, "invoice-confirmed.json")

    def _env(self, **overrides):
        env = {
            "COSTCO_CATALOG_DETAIL_PATH": self.detail_path,
            "COSTCO_INVOICE_PATH": self.invoice_path,
            "COSTCO_CATALOG_SOURCE": "UNWRANGLE",
            "UNWRANGLE_API_KEY": "key-123",
        }
        env.update(overrides)
        return env

    def _write_invoice_csv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "invoice_number", "costco_item_number", "item_name", "paid_cost",
                "quantity", "purchase_date", "upc_or_ean", "net_weight", "unit_of_measure",
            ])
            writer.writerows(rows)

    def test_import_invoices_csv(self):
        import_path = os.path.join(self.tmpdir.name, "invoices.csv")
        self._write_invoice_csv(import_path, [
            ["INV-100", "12345", "Kirkland Signature Adult Dog Food Chicken 40 lb", "29.14", "1", "2026-08-01", "012345678901", "40", "lb"],
        ])
        with mock.patch.dict("os.environ", self._env()):
            report = cac.import_invoices(import_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["imported"], 1)
        with open(self.invoice_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        self.assertEqual(records[0]["invoice_number"], "INV-100")
        self.assertEqual(records[0]["costco_item_id"], "12345")
        self.assertEqual(records[0]["paid_cost"], 29.14)
        self.assertEqual(records[0]["cost_basis"], "invoice_confirmed")
        self.assertEqual(records[0]["cost_status"], "invoice_confirmed")
        self.assertEqual(records[0]["source"], "business_center_invoice")
        self.assertEqual(records[0]["quantity"], 1)

    def test_import_invoices_duplicate_pair_held(self):
        import_path = os.path.join(self.tmpdir.name, "invoices.csv")
        self._write_invoice_csv(import_path, [
            ["INV-100", "12345", "Kirkland Alpha", "10.0", "1", "2026-08-01", "", "", ""],
            ["INV-100", "12345", "Kirkland Alpha Duplicate", "9.0", "1", "2026-08-01", "", "", ""],
        ])
        with mock.patch.dict("os.environ", self._env()):
            report = cac.import_invoices(import_path)
        self.assertEqual(report["imported"], 1)
        self.assertEqual(report["held_for_review"], 1)
        self.assertEqual(report["held"][0]["reason"], "duplicate (invoice, item)")

    def test_import_invoices_missing_paid_cost_held(self):
        import_path = os.path.join(self.tmpdir.name, "invoices.csv")
        self._write_invoice_csv(import_path, [["INV-100", "12345", "Kirkland Alpha", "", "1", "2026-08-01", "", "", ""]])
        with mock.patch.dict("os.environ", self._env()):
            report = cac.import_invoices(import_path)
        self.assertEqual(report["imported"], 0)
        self.assertEqual(report["held_for_review"], 1)


class ResolveCostcoCostTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.detail_path = os.path.join(self.tmpdir.name, "product-detail.json")
        self.invoice_path = os.path.join(self.tmpdir.name, "invoice-confirmed.json")
        self.csv_path = os.path.join(self.tmpdir.name, "costco-items.csv")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\nKirkland Signature Adult Dog Food Chicken 40 lbs,29.14\n")

    def _env(self, **overrides):
        env = {
            "COSTCO_CATALOG_DETAIL_PATH": self.detail_path,
            "COSTCO_INVOICE_PATH": self.invoice_path,
            "COSTCO_CATALOG_SOURCE": "UNWRANGLE",
            "UNWRANGLE_API_KEY": "key-123",
        }
        env.update(overrides)
        return env

    def _resolve(self, amazon_name):
        with mock.patch.dict("os.environ", self._env()):
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                return cac.resolve_costco_cost(amazon_name)

    def _write_json_store(self, path, records):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f)

    def test_no_match_anywhere_returns_none(self):
        self.assertIsNone(self._resolve("Kirkland Signature Organic Olive Oil"))

    def test_invoice_exact_beats_csv_exact(self):
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-200", "costco_item_id": "12345",
            "item_name": "Kirkland Signature Adult Dog Food, Chicken, 40 lbs",
            "paid_cost": 27.5, "purchase_date": "2026-08-01", "upc_or_ean": "012345678901",
        }])
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "invoice_confirmed")
        self.assertEqual(result["costco_cost"], 27.5)
        self.assertEqual(result["costco_cost_basis"], "invoice_confirmed")
        self.assertIs(result["cost_is_purchase_authorized"], True)
        self.assertIn("INV-200", result["match_reason"])

    def test_detail_exact_when_no_invoice(self):
        self._write_json_store(self.detail_path, [{
            "costco_item_id": "54321",
            "item_name": "Kirkland Signature Nature's Domain Dog Food Beef & Sweet Potato 35 lb",
            "current_price": 31.67, "cost_basis": "costco_online", "cost_status": "detail_only",
        }])
        result = self._resolve("Kirkland Signature Nature's Domain Dog Food Beef Sweet Potato 35 lb")
        self.assertEqual(result["match_quality"], "exact")
        self.assertEqual(result["costco_cost"], 31.67)
        self.assertEqual(result["cost_status"], "detail_only")

    def test_csv_exact_when_no_other_layers(self):
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "exact")
        self.assertEqual(result["costco_cost_basis"], "estimated")
        self.assertEqual(result["costco_cost"], 29.14)

    def test_invoice_candidate_surfaces_when_no_exact_anywhere(self):
        """A WEAK-title invoice row (similarity < 0.85, one-sided weight
        evidence) still surfaces as a research candidate — never COGS."""
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-300", "costco_item_id": "9",
            "item_name": "Adult Dog Food Chicken Kirkland Signature", "paid_cost": 25.0,
        }])
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "candidate")
        self.assertEqual(result["costco_cost_basis"], "candidate_match")
        self.assertIn("INV-300", result["match_reason"])

    def test_invoice_high_confidence_is_research_only_never_authorized(self):
        """A STRONG-title (high_confidence) invoice row keeps the paid cost
        as research input only: match_quality stays high_confidence,
        costco_cost_basis is invoice_confirmed (provenance of the paid
        number), and cost_is_purchase_authorized is always False."""
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-350", "costco_item_id": "9",
            "item_name": "Kirkland Signature Adult Dog Food Chicken", "paid_cost": 25.0,
        }])
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "high_confidence")
        self.assertEqual(result["costco_cost_basis"], "invoice_confirmed")
        self.assertEqual(result["costco_cost"], 25.0)
        self.assertIs(result["cost_is_purchase_authorized"], False)
        self.assertIn("INV-350", result["match_reason"])
        self.assertNotEqual(result["match_quality"], "invoice_confirmed")

    def test_invoice_exact_is_purchase_authorized(self):
        """Only an exact fingerprint match on an invoice row may carry
        match_quality invoice_confirmed and cost_is_purchase_authorized."""
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-350", "costco_item_id": "9",
            "item_name": "Kirkland Signature Adult Dog Food Chicken 40 lbs", "paid_cost": 25.0,
        }])
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "invoice_confirmed")
        self.assertIs(result["cost_is_purchase_authorized"], True)

    def test_invoice_cross_dimension_is_blocked(self):
        """A weight-only Amazon title (40 lb) vs a count-only invoice row
        (72 ct) is a unit-dimension conflict: it can never become
        high_confidence or invoice_confirmed."""
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-360", "costco_item_id": "9",
            "item_name": "Kirkland Signature Adult Dog Food Chicken 72 ct", "paid_cost": 30.0,
        }])
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "mismatch")
        self.assertNotIn("invoice_confirmed", result["match_quality"])
        self.assertIn("Unit dimension differs", result["match_reason"])

    def test_invoice_mismatch_surfaces_blocked(self):
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-400", "costco_item_id": "9",
            "item_name": "Kirkland Signature Adult Dog Food Chicken 25 lbs", "paid_cost": 22.0,
        }])
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("item_name,costco_cost\n")
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "mismatch")
        self.assertEqual(result["costco_cost_basis"], "candidate_match")

    def test_invoice_candidate_never_beats_csv_exact(self):
        """A WEAK-title (candidate) invoice row must not shadow a CSV row
        that fingerprint-matches exactly."""
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-300", "costco_item_id": "9",
            "item_name": "Adult Dog Food Chicken Kirkland Signature", "paid_cost": 25.0,
        }])
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "exact")
        self.assertEqual(result["costco_cost_basis"], "estimated")

    def test_invoice_upc_one_sided_does_not_block(self):
        """The scanner has no Amazon-side UPC, so a Costco-only UPC never
        fabricates a conflict; the title fingerprint decides."""
        self._write_json_store(self.invoice_path, [{
            "invoice_number": "INV-500", "costco_item_id": "9",
            "item_name": "Kirkland Signature Adult Dog Food Chicken 40 lbs",
            "paid_cost": 22.0, "upc_or_ean": "999999999999",
        }])
        result = self._resolve("Kirkland Signature Adult Dog Food Chicken 40 lb")
        self.assertEqual(result["match_quality"], "invoice_confirmed")
        self.assertEqual(result["costco_cost"], 22.0)


class LedgerTests(unittest.TestCase):
    """Verified ASIN -> Costco item_name mapping store (offline)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.ledger_path = os.path.join(self.tmpdir.name, "costco-amazon-mapping.json")
        self.csv_path = os.path.join(self.tmpdir.name, "costco-items.csv")
        self.invoice_path = os.path.join(self.tmpdir.name, "invoices.json")
        self.detail_path = os.path.join(self.tmpdir.name, "detail.json")
        self._env = {
            "COSTCO_AMAZON_MAPPING_PATH": self.ledger_path,
            "COSTCO_INVOICE_PATH": self.invoice_path,
            "COSTCO_CATALOG_DETAIL_PATH": self.detail_path,
            "SCANNER_OFFER_ENRICHMENT": "OFF",
        }

    def _csv_file(self, rows):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["item_name", "costco_cost"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _env_patch(self):
        return mock.patch.dict("os.environ", self._env, clear=False)

    def test_lookup_unknown_asin_returns_none(self):
        with self._env_patch():
            self.assertIsNone(cac.ledger_lookup("B000000001"))
            self.assertIsNone(cac.ledger_lookup(None))

    def test_import_json_and_lookup(self):
        import_path = os.path.join(self.tmpdir.name, "import.json")
        with open(import_path, "w", encoding="utf-8") as f:
            json.dump({"b000000001": "Kirkland Test Item", "B000000002": "Kirkland Other Item"}, f)
        with self._env_patch():
            report = cac.import_ledger(import_path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["imported"], 2)
        self.assertEqual(report["held_for_review"], 0)
        self.assertTrue(report["saved"])
        with self._env_patch():
            self.assertEqual(cac.ledger_lookup("b000000001"), "Kirkland Test Item")
            self.assertEqual(cac.ledger_lookup("B000000001"), "Kirkland Test Item")

    def test_import_csv(self):
        import_path = os.path.join(self.tmpdir.name, "import.csv")
        with open(import_path, "w", newline="", encoding="utf-8") as f:
            f.write("asin,item_name\nB000000001,Kirkland Test Item\n")
        with self._env_patch():
            report = cac.import_ledger(import_path)
        self.assertEqual(report["imported"], 1)
        with self._env_patch():
            self.assertEqual(cac.ledger_lookup("B000000001"), "Kirkland Test Item")

    def test_existing_different_name_held_never_overwritten(self):
        import_path = os.path.join(self.tmpdir.name, "import.json")
        with open(import_path, "w", encoding="utf-8") as f:
            json.dump({"B000000001": "Kirkland Test Item"}, f)
        with self._env_patch():
            cac.import_ledger(import_path)
        with open(import_path, "w", encoding="utf-8") as f:
            json.dump({"B000000001": "Different Item Name"}, f)
        with self._env_patch():
            report = cac.import_ledger(import_path)
        self.assertEqual(report["imported"], 0)
        self.assertEqual(len(report["conflicts"]), 1)
        with self._env_patch():
            self.assertEqual(cac.ledger_lookup("B000000001"), "Kirkland Test Item")

    def test_invalid_asins_held(self):
        import_path = os.path.join(self.tmpdir.name, "import.csv")
        with open(import_path, "w", newline="", encoding="utf-8") as f:
            f.write("asin,item_name\nSHORT,Kirkland\nB000000001,\n")
        with self._env_patch():
            report = cac.import_ledger(import_path)
        self.assertEqual(report["imported"], 0)
        self.assertEqual(len(report["held"]), 2)

    def test_duplicate_within_import_held(self):
        import_path = os.path.join(self.tmpdir.name, "import.csv")
        with open(import_path, "w", newline="", encoding="utf-8") as f:
            f.write("asin,item_name\nB000000001,Kirkland Test Item\nB000000001,Kirkland Test Item\n")
        with self._env_patch():
            report = cac.import_ledger(import_path)
        self.assertEqual(report["imported"], 1)
        self.assertEqual(len(report["held"]), 1)

    def _seed_ledger(self, mapping):
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f)

    def test_resolve_ledger_exact_csv_cost(self):
        self._seed_ledger({"B000000001": "Kirkland Test Item"})
        self._csv_file([{"item_name": "Kirkland Test Item", "costco_cost": 19.99}])
        with self._env_patch():
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                result = cac.resolve_costco_cost("Kirkland Test Item", amazon_asin="B000000001")
        self.assertEqual(result["match_quality"], "exact")
        self.assertEqual(result["costco_cost"], 19.99)
        self.assertEqual(result["source"], "ledger:csv")

    def test_resolve_ledger_without_layer_cost_never_invents(self):
        self._seed_ledger({"B000000001": "Kirkland Test Item"})
        with self._env_patch():
            result = cac.resolve_costco_cost("Kirkland Test Item", amazon_asin="B000000001")
        self.assertEqual(result["match_quality"], "exact")
        self.assertIsNone(result["costco_cost"])
        self.assertEqual(result["cost_status"], "ledger_only")
        self.assertFalse(result["cost_is_purchase_authorized"])

    def test_resolve_ledger_invoice_authorizes(self):
        self._seed_ledger({"B000000001": "Kirkland Test Item"})
        with open(self.invoice_path, "w", encoding="utf-8") as f:
            json.dump([{
                "invoice_number": "INV-9", "costco_item_id": "9",
                "item_name": "Kirkland Test Item", "paid_cost": 17.5,
            }], f)
        with self._env_patch():
            result = cac.resolve_costco_cost("Kirkland Test Item", amazon_asin="B000000001")
        self.assertEqual(result["match_quality"], "invoice_confirmed")
        self.assertEqual(result["costco_cost"], 17.5)
        self.assertTrue(result["cost_is_purchase_authorized"])
        self.assertEqual(result["source"], "ledger:invoice")

    def test_unmapped_asin_ignores_ledger(self):
        """ASINs not in the ledger resolve through the normal layers; a
        same-name CSV row gives high_confidence (no fingerprint), never a
        fabricated exact."""
        self._csv_file([{"item_name": "Kirkland Test Item", "costco_cost": 19.99}])
        with self._env_patch():
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
                result = cac.resolve_costco_cost("Kirkland Test Item", amazon_asin="B999999999")
        self.assertEqual(result["match_quality"], "high_confidence")
        self.assertEqual(result["costco_cost"], 19.99)

    def test_status_reports_ledger_entries(self):
        with self._env_patch():
            info = cac.status()
        self.assertEqual(info["ledger_path"], self.ledger_path)
        self.assertEqual(info["ledger_entries"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
