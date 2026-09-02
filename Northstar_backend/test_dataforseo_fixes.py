"""Regression tests for the two DataForSEO adapter fixes (offline, mocked).

Bug #1 (polling): a task_get that returns status 40602 ("Task In Queue") must be
treated as a *pending* (retryable) verdict, not a terminal rejection, so
_get_task keeps polling until the result is ready.

Bug #2 (cost): provider `cost` is fractional USD (e.g. 0.0015). Coercing to
integer cents truncated it to 0; it must be accumulated as a raw float USD in
result['cost_usd']. DataForSEO reports no separate credit field, so
result['credits_used'] stays None (never conflated with cost).

These tests mock requests.post/get only; no network is touched.
"""

import os
import re
import unittest
from unittest import mock

import proof_batch_contracts as pbc
import dataforseo_adapter as dfa


def _post_body(family, task_id, cost=0.0015):
    return {
        "status_code": 20000,
        "tasks_error": 0,
        "tasks": [{
            "status_code": 20100,
            "status_message": "Task Created.",
            "id": task_id,
            "path": ["v3", "merchant", "amazon", family, "task_post"],
            "cost": cost,
        }],
    }


def _get_pending_body(family, task_id):
    return {
        "status_code": 20000,
        "tasks_error": 1,  # DataForSEO reports tasks_error=1 while in queue
        "tasks": [{
            "status_code": 40602,
            "status_message": "Task In Queue.",
            "id": task_id,
            "path": ["v3", "merchant", "amazon", family, "task_get", "advanced"],
        }],
    }


def _get_ready_asin_body(task_id):
    return {
        "status_code": 20000,
        "tasks_error": 0,
        "tasks": [{
            "status_code": 20000,
            "status_message": "ok.",
            "id": task_id,
            "path": ["v3", "merchant", "amazon", "asin", "task_get", "advanced"],
            "result": [{
                "items": [{
                    "data_asin": "B00AQ0LMTC",
                    "title": "Kirkland Signature Vitamin B12",
                    "price_from": 12.34,
                    "product_information": [
                        {"body": {"Best Sellers Rank":
                                  "#292,264 in Health & Household "
                                  "(#810 in Vitamin B12 Supplements)"}}
                    ],
                }]
            }]
        }]
    }


def _get_ready_sellers_body(task_id):
    return {
        "status_code": 20000,
        "tasks_error": 0,
        "tasks": [{
            "status_code": 20000,
            "status_message": "ok.",
            "id": task_id,
            "path": ["v3", "merchant", "amazon", "sellers", "task_get", "advanced"],
            "result": [{
                "items": [
                    {"seller_name": "Amazon",
                     "seller_url": "https://www.amazon.com/sp?seller=A&isAmazonFulfilled=1",
                     "price": {"current": 12.34}, "buybox_winner": True},
                    # all-None header/aggregate row DataForSEO sometimes emits
                    {"seller_name": None, "seller_url": None, "price": None},
                    {"seller_name": "ThirdParty",
                     "seller_url": "https://www.amazon.com/sp?seller=TP&isAmazonFulfilled=0",
                     "price": 11.99},
                ]
            }]
        }]
    }


class TestCostFix(unittest.TestCase):
    def test_subcent_cost_not_truncated(self):
        self.assertIsInstance(pbc._cost_cents({"cost": 0.0015}), float)
        self.assertEqual(pbc._cost_cents({"cost": 0.0015}), 0.0015)
        self.assertEqual(pbc._cost_cents({"cost": 0.05}), 0.05)
        self.assertEqual(pbc._cost_cents(None), 0.0)
        self.assertEqual(pbc._cost_cents({"cost": "nope"}), 0.0)
        self.assertEqual(pbc._cost_cents({}), 0.0)

    def test_post_verdict_carries_float_cost(self):
        v = pbc.evaluate_dataforseo_task_post(_post_body("asin", "t1"), "asin")
        self.assertTrue(v["accepted"])
        self.assertIsInstance(v["provider_cost_cents"], float)
        self.assertEqual(v["provider_cost_cents"], 0.0015)


class TestPendingVerdict(unittest.TestCase):
    def test_40602_is_pending(self):
        v = pbc.evaluate_dataforseo_task_get(
            _get_pending_body("asin", "t1"), "asin", "t1")
        self.assertFalse(v["accepted"])
        self.assertTrue(v["pending"])
        self.assertEqual(v["classification"], "pending")

    def test_20100_is_pending(self):
        body = _get_pending_body("sellers", "t2")
        body["tasks"][0]["status_code"] = 20100
        v = pbc.evaluate_dataforseo_task_get(body, "sellers", "t2")
        self.assertTrue(v["pending"])

    def test_tasks_error_1_queued_is_pending(self):
        # Faithful queued payload: status 40602 + tasks_error=1 must NOT be a
        # terminal reject (that was the live bug).
        v = pbc.evaluate_dataforseo_task_get(
            _get_pending_body("asin", "t1"), "asin", "t1")
        self.assertFalse(v["accepted"])
        self.assertTrue(v["pending"])
        self.assertNotEqual(v["classification"], "provider_error")

    def test_terminal_error_status_rejected(self):
        # A real failure (e.g. 40501 Task Not Found) with tasks_error=1 must
        # reject, not pend forever.
        body = {
            "status_code": 20000,
            "tasks_error": 1,
            "tasks": [{
                "status_code": 40501,
                "status_message": "Task Not Found.",
                "id": "t1",
                "path": ["v3", "merchant", "amazon", "asin", "task_get", "advanced"],
            }],
        }
        v = pbc.evaluate_dataforseo_task_get(body, "asin", "t1")
        self.assertFalse(v["accepted"])
        self.assertFalse(v["pending"])

    def test_20000_is_accepted(self):
        v = pbc.evaluate_dataforseo_task_get(
            _get_ready_asin_body("t1"), "asin", "t1")
        self.assertTrue(v["accepted"])
        self.assertFalse(v["pending"])
        self.assertIsNotNone(v["result_item"])

    def test_task_id_mismatch_rejected(self):
        v = pbc.evaluate_dataforseo_task_get(
            _get_ready_asin_body("t1"), "asin", "WRONG")
        self.assertFalse(v["accepted"])
        self.assertFalse(v.get("pending", False))


class TestEnrichmentPolling(unittest.TestCase):
    def _arm(self):
        dfa.DATAFORSEO_ENABLED = True
        dfa.DATAFORSEO_TRANSPORT_ENABLED = True
        dfa.DATAFORSEO_LOGIN = "u"
        dfa.DATAFORSEO_PASSWORD = "p"
        dfa.POLL_INTERVAL_SECONDS = 0  # keep the unit test fast

    def test_40602_then_20000_populates(self):
        self._arm()
        counters = {}

        def fake_post(url, **kwargs):
            if "/amazon/asin/task_post" in url:
                family, tid = "asin", "task-asin-1"
            else:
                family, tid = "sellers", "task-sellers-1"
            return mock.Mock(status_code=200, json=lambda: _post_body(family, tid))

        def fake_get(url, **kwargs):
            m = re.search(r"task_get/advanced/([^/?]+)", url)
            tid = m.group(1) if m else "unknown"
            family = "sellers" if "/amazon/sellers/" in url else "asin"
            counters[tid] = counters.get(tid, 0) + 1
            if counters[tid] == 1:
                return mock.Mock(status_code=200,
                                 json=lambda: _get_pending_body(family, tid))
            if family == "asin":
                return mock.Mock(status_code=200,
                                 json=lambda: _get_ready_asin_body(tid))
            return mock.Mock(status_code=200,
                             json=lambda: _get_ready_sellers_body(tid))

        with mock.patch.object(dfa.requests, "post", side_effect=fake_post), \
                mock.patch.object(dfa.requests, "get", side_effect=fake_get):
            result = dfa.get_dataforseo_offers("B00AQ0LMTC")

        self.assertEqual(result["source"], "dataforseo")
        self.assertEqual(result["buy_box_price"], 12.34)
        # all-None header row is dropped -> 2 real offers
        self.assertEqual(result["offers_returned_count"], 2)
        self.assertEqual(result["observed_fba_offer_count"], 1)  # Amazon
        self.assertEqual(result["observed_fbm_offer_count"], 1)  # ThirdParty
        self.assertEqual(result["buy_box_seller"], "Amazon")
        # cost = 0.0015 (asin post) + 0.0015 (sellers post) = 0.003
        self.assertAlmostEqual(result["cost_usd"], 0.003, places=6)
        self.assertIsNone(result["credits_used"])
        self.assertNotIn("merchant_asin", result["data_gaps"])
        self.assertNotIn("merchant_sellers", result["data_gaps"])

    def test_disabled_adapter_makes_no_network_call(self):
        dfa.DATAFORSEO_ENABLED = False
        with mock.patch.object(dfa.requests, "post") as post, \
                mock.patch.object(dfa.requests, "get") as get:
            result = dfa.get_dataforseo_offers("B00AQ0LMTC")
        post.assert_not_called()
        get.assert_not_called()
        self.assertIn("not enabled", " ".join(result["data_gaps"]))


if __name__ == "__main__":
    unittest.main()
