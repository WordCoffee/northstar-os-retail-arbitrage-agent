import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from unittest.mock import patch

import easyparser_client as ep

EXPECTED_OFFER_KEYS = {
    "position", "buybox_winner", "price", "condition", "seller_id", "seller_name",
    "seller_rating", "seller_positive_percentage", "seller_ratings_total",
    "is_prime", "is_fba", "is_fbm", "is_sba", "fulfilled_by_amazon",
    "shipping_text", "shipping_is_free", "ships_from",
    "minimum_order_quantity", "maximum_order_quantity",
}


def make_payload(zip_code="19805", success=True):
    return {
        "request_info": {
            "success": success,
            "credits_used": 1,
            "credits_remaining": 999,
            "address": {"zipCode": zip_code},
        },
        "request_metadata": {
            "created_at": "2026-01-01T00:00:00Z",
            "processed_at": "2026-01-01T00:00:01Z",
        },
        "result": {
            "product": {"asin": "B00GYZWNY6", "title": "Test Product", "offer_count": 12},
            "offer": {
                "offer_results": [
                    {
                        "buybox_winner": True,
                        "condition": {"is_new": True, "title": "New"},
                        "is_prime": True,
                        "position": 1,
                        "price": {"value": 56.66, "raw": "$56.66", "currency": "USD"},
                        "seller": {"id": "A1", "name": "Amazon.com", "rating": 4.9, "ratings_percentage_positive": 95, "ratings_total": 1000},
                        "seller_type": {"fba": True, "fbm": False, "sba": False},
                        "delivery": {"fulfilled_by_amazon": True, "price": {"is_free": True}, "text": "FREE Shipping"},
                        "ships_from": "US",
                        "maximum_order_quantity": 10,
                        "minimum_order_quantity": 1,
                    },
                    {
                        "buybox_winner": False,
                        "condition": {"is_new": True, "title": "New"},
                        "is_prime": True,
                        "position": 2,
                        "price": {"value": 49.99, "raw": "$49.99", "currency": "USD"},
                        "seller": {"id": "S2", "name": "Third Party LLC", "rating": 4.5, "ratings_percentage_positive": 90, "ratings_total": 200},
                        "seller_type": {"fba": False, "fbm": True, "sba": False},
                        "delivery": {"fulfilled_by_amazon": False, "price": {"is_free": False}, "text": "Shipping"},
                        "ships_from": "US",
                        "maximum_order_quantity": 5,
                        "minimum_order_quantity": 1,
                    },
                ]
            },
        },
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class TestEasyparserClient(unittest.TestCase):
    def _run(self, payload, asin="B00GYZWNY6", status_code=200):
        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params, "timeout": timeout})
            return FakeResponse(payload, status_code=status_code)

        with patch("easyparser_client.requests.get", side_effect=fake_get):
            result = ep.get_easyparser_offers(asin)
        return result, calls

    def test_success_flow_normalized(self):
        result, calls = self._run(make_payload(zip_code=["19805"]))
        self.assertEqual(len(calls), 1)
        p = calls[0]["params"]
        self.assertEqual(calls[0]["url"], "https://realtime.easyparser.com/v1/request")
        self.assertEqual(calls[0]["timeout"], 60)
        self.assertEqual(p["platform"], "AMZ")
        self.assertEqual(p["operation"], "OFFER")
        self.assertEqual(p["domain"], ".com")
        self.assertEqual(p["asin"], "B00GYZWNY6")
        self.assertTrue(p["api_key"])

        self.assertEqual(result["source"], "easyparser")
        self.assertEqual(result["asin"], "B00GYZWNY6")
        self.assertEqual(result["offer_count"], 12)
        self.assertEqual(result["offers_returned_count"], 2)
        self.assertNotEqual(result["offer_count"], result["offers_returned_count"])
        self.assertEqual(result["observed_fba_offer_count"], 1)
        self.assertEqual(result["observed_fbm_offer_count"], 1)
        self.assertEqual(result["observed_amazon_offer_count"], 1)
        self.assertEqual(result["request_zip_code"], "19805")
        self.assertIsInstance(result["request_zip_code"], str)

        self.assertEqual(result["buy_box_price"], 56.66)
        self.assertIsInstance(result["buy_box_price"], float)
        self.assertEqual(result["buy_box_price_raw"], {"value": 56.66, "raw": "$56.66", "currency": "USD"})
        self.assertEqual(result["buy_box_seller"], "Amazon.com")
        self.assertEqual(result["buy_box_is_fba"], True)

        self.assertEqual(len(result["offers"]), 2)
        self.assertEqual(set(result["offers"][0].keys()), EXPECTED_OFFER_KEYS)
        self.assertEqual(set(result["offers"][1].keys()), EXPECTED_OFFER_KEYS)

    def test_zip_code_string_passthrough(self):
        result, _ = self._run(make_payload(zip_code="75201"))
        self.assertEqual(result["request_zip_code"], "75201")

    def test_zip_code_missing(self):
        result, _ = self._run(make_payload(zip_code=None))
        self.assertIsNone(result["request_zip_code"])

    def test_prime_does_not_imply_fba(self):
        """Offer 2 has is_prime True but seller_type.fbm True - counts by seller_type only."""
        result, _ = self._run(make_payload())
        self.assertEqual(result["observed_fba_offer_count"], 1)
        self.assertEqual(result["observed_fbm_offer_count"], 1)
        offer2 = result["offers"][1]
        self.assertTrue(offer2["is_prime"])
        self.assertIs(offer2["is_fba"], False)
        self.assertIs(offer2["is_fbm"], True)

    def test_invalid_asin_no_request(self):
        result, calls = self._run(make_payload(), asin="bad")
        self.assertEqual(calls, [])
        self.assertEqual(result["offers_returned_count"], 0)
        self.assertTrue(any("Invalid ASIN" in g for g in result["data_gaps"]))

    def test_success_false(self):
        result, calls = self._run(make_payload(success=False))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["offers"], [])
        self.assertTrue(any("success" in g.lower() for g in result["data_gaps"]))

    def test_http_error(self):
        result, calls = self._run({"error": "boom"}, status_code=500)
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("HTTP 500" in g for g in result["data_gaps"]))

    def test_timeout(self):
        def timeout_get(url, params=None, timeout=None):
            raise ep.requests.exceptions.Timeout("t")

        with patch("easyparser_client.requests.get", side_effect=timeout_get):
            result = ep.get_easyparser_offers("B00GYZWNY6")
        self.assertTrue(any("timed out" in g for g in result["data_gaps"]))

    def test_missing_offer_results(self):
        payload = make_payload()
        payload["result"]["offer"] = {}
        result, _ = self._run(payload)
        self.assertEqual(result["offers"], [])
        self.assertTrue(any("offer_results" in g for g in result["data_gaps"]))

    def test_buy_box_price_null_when_no_winner(self):
        payload = make_payload()
        payload["result"]["offer"]["offer_results"][0]["buybox_winner"] = False
        payload["result"]["offer"]["offer_results"][1]["buybox_winner"] = False
        result, _ = self._run(payload)
        self.assertIsNone(result["buy_box_price"])
        self.assertIsNone(result["buy_box_seller"])


if __name__ == "__main__":
    unittest.main(verbosity=2)