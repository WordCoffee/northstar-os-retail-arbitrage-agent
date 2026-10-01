"""Mock-only tests for the Rainforest API adapter.

No live call, no credential validation, no network: every HTTP interaction is
a fully mocked client, and every payload below is FABRICATED sample data
(clearly labelled "SAMPLE-") that only mirrors the documented response shapes.

Proves the hard rules:
* Rainforest is selected ONLY when explicitly requested.
* No network is contacted (mock client + a real-client tripwire).
* A missing key returns NOT_CONFIGURED with zero calls.
* The per-run request cap is enforced before any call.
* There is NO fallback to another provider on failure.
* Secrets never appear in logs/receipts/results.
"""

import json
import os
import unittest
from unittest import mock

import test_network_guard  # noqa: F401  (blocks real requests)
import network_guard  # noqa: F401
import requests

import rainforest_client
from rainforest_client import (
    RainforestClient,
    RainforestReceipt,
    STATUS_DRY_RUN,
    STATUS_HTTP_ERROR,
    STATUS_NOT_CONFIGURED,
    STATUS_OK,
    STATUS_REQUEST_CAP_REACHED,
    STATUS_TRANSPORT_ERROR,
    CANDIDATE_UNVERIFIED,
    UNKNOWN,
)


SECRET = "SAMPLE-SECRET-KEY-DO-NOT-LOG-1234567890"


# --- fabricated, clearly-labelled payloads ---------------------------------

def sample_product_payload():
    return {
        "request_info": {"success": True, "credits_used_this_request": 1},
        "product": {
            "asin": "SAMPLEASIN01",
            "title": "SAMPLE Widget 12 Count",
            "brand": "SAMPLEBRAND",
            "gtin": "0000000000001",
            "buybox_winner": {
                "price": {"symbol": "$", "value": 24.99, "currency": "USD"},
                "seller": {"name": "Amazon.com", "id": "ATVPDKIKX0DER", "rating": 4.9},
            },
        },
    }


def sample_search_payload():
    return {
        "request_info": {"success": True, "credits_used_this_request": 1},
        "search_results": [
            {"position": 1, "asin": "SAMPLEASIN02", "title": "SAMPLE Thing 6 Pack",
             "brand": "SAMPLEBRAND", "is_prime": True,
             "price": {"symbol": "$", "value": 12.5, "currency": "USD"}},
            {"position": 2, "asin": "SAMPLEASIN03", "title": "SAMPLE Thing",
             "is_prime": False, "price": {"symbol": "$", "value": 3.0, "currency": "USD"}},
        ],
    }


def sample_offers_payload():
    return {
        "request_info": {"success": True, "credits_used_this_request": 1},
        "product": {"asin": "SAMPLEASIN01", "title": "SAMPLE Widget 12 Count",
                    "brand": "SAMPLEBRAND"},
        "offers": [
            {"price": {"symbol": "$", "value": 29.0, "currency": "USD"},
             "seller": {"name": "Amazon.com", "id": "ATVPDKIKX0DER"},
             "is_prime": True, "buybox_winner": True, "offer_id": "SAMPLEOFFER1",
             "condition": {"is_new": True}},
            {"price": {"symbol": "$", "value": 27.0, "currency": "USD"},
             "seller": {"name": "SAMPLEBRAND Official", "id": "SELLER2", "rating": 4.8},
             "is_prime": True, "condition": {"is_new": True}},
            {"price": {"symbol": "$", "value": 26.0, "currency": "USD"},
             "seller": {"name": "Someone Else", "id": "SELLER3"},
             "is_prime": False, "condition": {"is_new": False}},
        ],
    }


class MockResponse:
    def __init__(self, payload=None, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class MockHTTP:
    """Records calls; never touches the network."""

    def __init__(self, responses=None):
        self.calls = []
        self._responses = list(responses or [])

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        if self._responses:
            return self._responses.pop(0)
        return MockResponse(sample_product_payload())


# --- selection gate --------------------------------------------------------

class SelectionGateTests(unittest.TestCase):
    def test_not_selected_by_default(self):
        self.assertFalse(rainforest_client.rainforest_selected(environ={}))

    def test_selected_by_explicit_provider_name(self):
        self.assertTrue(rainforest_client.rainforest_selected(provider="rainforest", environ={}))
        self.assertTrue(rainforest_client.rainforest_selected(provider="Rainforest", environ={}))

    def test_selected_by_explicit_routing_flag(self):
        self.assertTrue(rainforest_client.rainforest_selected(
            environ={rainforest_client.ROUTING_FLAG_ENV: "1"}))

    def test_other_provider_names_not_selected(self):
        for name in ("brightdata", "scavio", "chocodata", ""):
            self.assertFalse(rainforest_client.rainforest_selected(provider=name, environ={}))

    def test_scanner_default_routing_is_untouched(self):
        import amazon_search

        # The scanner's default source must remain exactly what it was.
        self.assertEqual(amazon_search.SCANNER_SEARCH_SOURCE, "BRIGHTDATA")


# --- network isolation -----------------------------------------------------

class NoNetworkTests(unittest.TestCase):
    def test_mock_http_is_the_only_client_used(self):
        http = MockHTTP([MockResponse(sample_product_payload())])
        client = RainforestClient(api_key=SECRET, http=http)
        result = client.product_by_asin("SAMPLEASIN01")
        self.assertTrue(result.ok)
        self.assertEqual(len(http.calls), 1)

    def test_real_requests_client_is_blocked_when_unmocked(self):
        # A client without an injected http would fall to `requests`, which the
        # network guard blocks -> the adapter must surface a typed transport
        # error rather than reaching the network.
        client = RainforestClient(api_key=SECRET, max_requests=1)
        with self.assertRaises(network_guard.NetworkGuardViolation):
            requests.get("https://api.rainforestapi.com/request")
        result = client.product_by_asin("SAMPLEASIN01")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_TRANSPORT_ERROR)


# --- missing key -----------------------------------------------------------

class MissingKeyTests(unittest.TestCase):
    def test_missing_key_returns_not_configured_with_no_call(self):
        http = MockHTTP()
        client = RainforestClient(api_key=None, http=http)
        result = client.product_by_asin("SAMPLEASIN01")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_NOT_CONFIGURED)
        self.assertEqual(result.error_class, "not_configured")
        self.assertEqual(len(http.calls), 0)

    def test_from_env_without_key_is_not_configured(self):
        client = RainforestClient.from_env(environ={}, http=MockHTTP())
        self.assertFalse(client.configured)
        self.assertEqual(client.product_by_gtin("0000000000001").status, STATUS_NOT_CONFIGURED)


# --- request cap -----------------------------------------------------------

class RequestCapTests(unittest.TestCase):
    def test_request_cap_enforced_before_any_extra_call(self):
        http = MockHTTP([MockResponse(sample_product_payload()) for _ in range(5)])
        client = RainforestClient(api_key=SECRET, http=http, max_requests=2)
        self.assertTrue(client.product_by_asin("A1").ok)
        self.assertTrue(client.product_by_asin("A2").ok)
        third = client.product_by_asin("A3")
        self.assertFalse(third.ok)
        self.assertEqual(third.status, STATUS_REQUEST_CAP_REACHED)
        self.assertEqual(len(http.calls), 2)

    def test_dry_run_does_not_consume_cap(self):
        http = MockHTTP()
        client = RainforestClient(api_key=SECRET, http=http, max_requests=1, dry_run=True)
        self.assertEqual(client.product_by_asin("A1").status, STATUS_DRY_RUN)
        self.assertEqual(len(http.calls), 0)
        self.assertEqual(client.request_count, 0)


# --- no fallback -----------------------------------------------------------

class NoFallbackTests(unittest.TestCase):
    def test_http_error_is_returned_not_fallen_back(self):
        http = MockHTTP([MockResponse(None, status_code=500)])
        client = RainforestClient(api_key=SECRET, http=http)
        result = client.product_by_asin("A1")
        self.assertFalse(result.ok)
        self.assertEqual(result.status, STATUS_HTTP_ERROR)
        self.assertEqual(result.candidates, [])
        self.assertEqual(len(http.calls), 1)  # exactly one attempt, no retry

    def test_adapter_does_not_import_other_providers(self):
        with open(rainforest_client.__file__, "r", encoding="utf-8") as fh:
            source = fh.read()
        for other in ("bright_data_client", "scavio_client", "chocodata", "offer_enrichment"):
            self.assertNotIn(other, source)


# --- secret hygiene --------------------------------------------------------

class SecretHygieneTests(unittest.TestCase):
    def test_secret_never_in_receipt_result_or_logs(self):
        http = MockHTTP([MockResponse(sample_product_payload())])
        client = RainforestClient(api_key=SECRET, http=http)
        with mock.patch("builtins.print") as printed:
            result = client.product_by_asin("SAMPLEASIN01")

        blob = json.dumps(result.to_dict(), sort_keys=True)
        self.assertNotIn(SECRET, blob)
        self.assertNotIn("api_key", result.receipt.to_dict())
        self.assertNotIn(SECRET, json.dumps([c for c in printed.call_args_list], default=str))

    def test_receipt_contains_only_expected_scrubbed_keys(self):
        http = MockHTTP([MockResponse(sample_product_payload())])
        client = RainforestClient(api_key=SECRET, http=http)
        receipt = client.product_by_asin("A1").receipt.to_dict()
        self.assertEqual(
            set(receipt.keys()),
            {"provider", "operation", "status", "request_count",
             "dry_run", "estimated_credits", "field_names", "notes"},
        )
        self.assertEqual(receipt["provider"], "rainforest")
        # field NAMES only, never values.
        self.assertIn("product", receipt["field_names"])


# --- normalization ---------------------------------------------------------

class NormalizationTests(unittest.TestCase):
    def test_product_candidate_is_unverified_with_unknowns(self):
        payload = {"product": {"asin": None, "title": None}}
        candidates = rainforest_client.normalize_product(payload)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["asin"], UNKNOWN)
        self.assertEqual(candidates[0]["title"], UNKNOWN)
        self.assertEqual(candidates[0]["verification"], CANDIDATE_UNVERIFIED)
        self.assertIsNone(candidates[0]["price"])  # unknown price never fabricated as 0

    def test_search_normalization_shape(self):
        candidates = rainforest_client.normalize_search(sample_search_payload())
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["asin"], "SAMPLEASIN02")
        self.assertEqual(candidates[0]["price"], 12.5)
        self.assertEqual(candidates[0]["verification"], CANDIDATE_UNVERIFIED)

    def test_offers_amazon_seller_flag(self):
        candidates = rainforest_client.normalize_offers(sample_offers_payload())
        first = candidates[0]
        self.assertTrue(first["amazon_is_seller"])
        self.assertIn("AMAZON_RETAIL_SELLER", first["flags"])
        # a known non-Amazon seller is definitively False (not Amazon retail).
        self.assertFalse(candidates[2]["amazon_is_seller"])

    def test_unknown_seller_stays_unknown(self):
        payload = {"offers": [{"price": {"value": 1.0, "currency": "USD"}}]}
        candidate = rainforest_client.normalize_offers(payload)[0]
        self.assertIsNone(candidate["amazon_is_seller"])

    def test_hard_filters_flag_never_drop(self):
        candidates = rainforest_client.normalize_offers(sample_offers_payload())
        brand_direct = [c for c in candidates if c["seller_name"] == "SAMPLEBRAND Official"][0]
        self.assertIn("BRAND_DIRECT_SELLER", brand_direct["flags"])
        # every offer is still present (nothing silently dropped).
        self.assertEqual(len(candidates), 3)

    def test_pack_count_mismatch_is_flagged_not_dropped(self):
        candidate = rainforest_client._base_candidate(
            asin="A1", title="SAMPLE Widget 12 Count", brand="SAMPLEBRAND")
        rainforest_client.apply_hard_filters(candidate, expected_pack_count=6)
        self.assertIn("PACK_COUNT_MISMATCH", candidate["flags"])

    def test_detect_pack_count(self):
        self.assertEqual(rainforest_client.detect_pack_count("SAMPLE Widget 12 Count"), 12)
        self.assertEqual(rainforest_client.detect_pack_count("SAMPLE Pack of 24"), 24)
        self.assertIsNone(rainforest_client.detect_pack_count("SAMPLE Widget"))


# --- dry run ---------------------------------------------------------------

class DryRunTests(unittest.TestCase):
    def test_dry_run_plans_without_calling(self):
        http = MockHTTP()
        client = RainforestClient(api_key=SECRET, http=http, dry_run=True)
        result = client.offers_by_asin("SAMPLEASIN01")
        self.assertTrue(result.ok)
        self.assertEqual(result.status, STATUS_DRY_RUN)
        self.assertEqual(len(http.calls), 0)
        self.assertEqual(result.receipt.estimated_credits, rainforest_client.CREDITS_PER_REQUEST)
        self.assertNotIn(SECRET, json.dumps(result.receipt.to_dict()))


# --- registry integration --------------------------------------------------

class FakeRegistry:
    def __init__(self):
        self.definitions = []
        self.adapters = {}

    def register_definition(self, defn):
        self.definitions.append(defn)
        return defn

    def bind_adapter(self, adapter):
        self.adapters[adapter.provider_key] = adapter


class RegistryIntegrationTests(unittest.TestCase):
    def test_register_rainforest_binds_under_explicit_name_disabled(self):
        registry = FakeRegistry()
        rainforest_client.register_rainforest(
            registry, client=RainforestClient(api_key=SECRET, http=MockHTTP()))
        self.assertIn("rainforest", registry.adapters)
        definition = registry.definitions[0]
        self.assertEqual(definition.provider_key, "rainforest")
        self.assertFalse(definition.enabled)  # disabled by default
        self.assertEqual(definition.credential_ref_names, ["RAINFOREST_API_KEY"])

    def test_adapter_read_dispatches_operations(self):
        http = MockHTTP([MockResponse(sample_offers_payload())])
        adapter = rainforest_client.RainforestAdapter(
            client=RainforestClient(api_key=SECRET, http=http))
        result = adapter.read({"operation": "offers_by_asin", "inputs": {"asin": "A1"}})
        self.assertTrue(result.ok)
        self.assertTrue(any(c["amazon_is_seller"] for c in result.candidates))

    def test_adapter_write_is_refused(self):
        adapter = rainforest_client.RainforestAdapter(client=RainforestClient(api_key=SECRET))
        self.assertFalse(adapter.write({}).ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
