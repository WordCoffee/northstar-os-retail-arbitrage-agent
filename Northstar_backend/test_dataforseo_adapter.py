"""Zero-network fixture tests for the DataForSEO secondary-validation adapter.

These tests assert dataforseo_adapter.py is OFFLINE-VERIFIED: every gate
fails closed, no network is created, no secrets are accessed or logged, the
feature flag is disabled by default, and normal GET/page loads remain
provider-call-free. All tests run without credentials and without network
access (the global network guard blocks any real request).

Contract: DataForSEO Merchant Standard families products / asin / sellers
(task_post -> task_get). product_info / seller_info / search / reviews /
/live are rejected. Create acceptance requires task-level 20100
"Task Created." + cost > 0 + path match; retrieval requires 20000 + id/family
match + parseable result.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import dataforseo_adapter as df
from dataforseo_adapter import (
    GuardError,
    AmbiguousTransportError,
)

from proof_batch_contracts import (
    evaluate_dataforseo_task_post,
    evaluate_dataforseo_task_get,
    evaluate_dataforseo_labs_live,
)


def block_network(test_case):
    """Patch real HTTP clients so any unmocked call fails the test."""
    patcher = mock.patch.object(
        __import__("requests"), "get", side_effect=AssertionError("network!"))
    patcher2 = mock.patch.object(
        __import__("requests"), "post", side_effect=AssertionError("network!"))
    patcher3 = mock.patch.object(
        __import__("requests").sessions.Session, "request",
        side_effect=AssertionError("network!"))
    patcher.start()
    patcher2.start()
    patcher3.start()
    test_case.addCleanup(patcher.stop)
    test_case.addCleanup(patcher2.stop)
    test_case.addCleanup(patcher3.stop)


class FakeResponse:
    """Minimal requests.Response stand-in for armed transport tests."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if not isinstance(self._payload, dict):
            raise json.JSONDecodeError("not json", "", 0)
        return self._payload


class _RefusingTransport(df.DataForSEOStandardTransport):
    """Subclass of the REAL transport that refuses in submit (route test)."""

    def submit(self, url, payload):
        df.classify_endpoint(url, "POST")
        raise df.GuardError("transport disabled")


def _ledger_records():
    path = df.ledger_path()
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# A single ASIN selected from the existing internal shortlist (it carries an
# estimated economics tier in the offline product-analysis pipeline).
SHORTLIST_ASIN = "B0CS6Z9SRX"
MARKETPLACE = "amazon.com"
BD_REF = "snapshot-2026-08-19T060000Z-rec-0001"


def shortlist_pass(asin, bd_ref):
    return {"found": True, "economics_confidence": "estimated", "profit_tier": 11,
            "name": "Kirkland Organic K-Cups", "verdict": "Pass", "net_profit": 20.0}


def shortlist_fail(asin, bd_ref):
    return {"found": False, "economics_confidence": None, "profit_tier": None}


# ---- Contract fixtures ---------------------------------------------------
# Valid Merchant Standard CREATE (task_post) acceptance envelope:
# task-level 20100 "Task Created." + cost > 0 + path matches family route.
VALID_CREATE = {
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks_error": 0,
    "cost": 0.05,
    "tasks": [{
        "id": "task-created-1",
        "status_code": 20100,
        "status_message": "Task Created.",
        "cost": 0.05,
        "path": ["v3", "merchant", "amazon", "products", "task_post"],
        "data": {"keyword": "kirkland"},
        "result": None,
    }],
}


# The exact task-level rejection observed on data-validation-20asin-live-001.
ENVELOPE_40402 = {
    "version": "0.1.20260806",
    "status_code": 20000,
    "status_message": "Ok.",
    "time": "0.0276 sec.",
    "cost": 0,
    "tasks_count": 1,
    "tasks_error": 1,
    "tasks": [{
        "id": "08200307-2329-0455-0000-fc0cd5bb47ee",
        "status_code": 40402,
        "status_message": "Invalid Path.",
        "time": "0.0000 sec.",
        "cost": 0,
        "result_count": 0,
        "path": ["v3", "merchant", "amazon", "product_info", "task_post"],
        "data": None,
        "result": None,
    }],
}

# Valid retrieval (task_get) completion envelope for the 'products' family.
VALID_GET = {
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks_error": 0,
    "tasks": [{
        "id": "task-created-1",
        "status_code": 20000,
        "status_message": "Ok.",
        "path": ["v3", "merchant", "amazon", "products", "task_get", "advanced"],
        "result": [{
            "asin": SHORTLIST_ASIN,
            "title": "Kirkland K-Cups",
            "brand": "Kirkland Signature",
            "price": {"value": 12.5},
            "sellers": {"offer_count": 3},
            "timestamp": "2026-08-19T00:00:00Z",
        }],
    }],
}


class DataForSEOContractTests(unittest.TestCase):
    """Unit tests for the shared acceptance predicates in proof_batch_contracts."""

    def test_valid_create_accepted(self):
        v = evaluate_dataforseo_task_post(VALID_CREATE, endpoint_family="products")
        self.assertTrue(v["accepted"])
        self.assertEqual(v["classification"], "submitted")
        self.assertEqual(v["task_id"], "task-created-1")
        # provider_cost_cents holds the raw provider cost in USD (float),
        # never integer cents (see proof_batch_contracts._cost_cents contract).
        self.assertEqual(v["provider_cost_cents"], 0.05)
        self.assertTrue(v["path_match"])
        self.assertEqual(v["request_state"], "submitted")

    def test_40402_envelope_rejected_invalid_path(self):
        v = evaluate_dataforseo_task_post(ENVELOPE_40402, endpoint_family="products")
        self.assertFalse(v["accepted"])
        self.assertEqual(v["classification"], "provider_rejected_invalid_path")
        self.assertIsNone(v["task_id"])
        self.assertIn("Invalid Path", v["reason"])

    def test_20000_zero_cost_rejected(self):
        env = {"status_code": 20000, "tasks_error": 0, "tasks": [{
            "id": "t", "status_code": 20000, "status_message": "Ok.",
            "cost": 0, "path": ["v3", "merchant", "amazon", "products", "task_post"]}]}
        v = evaluate_dataforseo_task_post(env, endpoint_family="products")
        self.assertFalse(v["accepted"])
        self.assertEqual(v["classification"], "provider_rejected_unknown")

    def test_20100_zero_cost_rejected(self):
        env = {"status_code": 20000, "tasks_error": 0, "tasks": [{
            "id": "t", "status_code": 20100, "status_message": "Task Created.",
            "cost": 0, "path": ["v3", "merchant", "amazon", "products", "task_post"]}]}
        v = evaluate_dataforseo_task_post(env, endpoint_family="products")
        self.assertFalse(v["accepted"])
        self.assertIn("greater than zero", v["reason"])

    def test_path_mismatch_rejected_invalid_path(self):
        env = {"status_code": 20000, "tasks_error": 0, "tasks": [{
            "id": "t", "status_code": 20100, "status_message": "Task Created.",
            "cost": 0.05, "path": ["v3", "merchant", "amazon", "product_info", "task_post"]}]}
        v = evaluate_dataforseo_task_post(env, endpoint_family="products")
        self.assertFalse(v["accepted"])
        self.assertEqual(v["classification"], "provider_rejected_invalid_path")

    def test_valid_get_retrieved(self):
        v = evaluate_dataforseo_task_get(VALID_GET, "products", "task-created-1")
        self.assertTrue(v["accepted"])
        self.assertEqual(v["classification"], "retrieved")
        self.assertEqual(v["task_id"], "task-created-1")
        self.assertTrue(v["path_match"])
        self.assertEqual(v["result_item"]["asin"], SHORTLIST_ASIN)

    def test_get_id_mismatch_rejected(self):
        v = evaluate_dataforseo_task_get(VALID_GET, "products", "OTHER-ID")
        self.assertFalse(v["accepted"])
        self.assertEqual(v["classification"], "provider_rejected_validation")
        self.assertIsNone(v.get("result_item"))

    def test_labs_live_accepted(self):
        payload = {
            "status_code": 20000, "tasks_error": 0, "cost": 0.05,
            "tasks": [{
                "id": "labs-1", "status_code": 20000, "status_message": "Ok.",
                "path": ["v3", "dataforseo_labs", "amazon", "related_keywords", "live"],
                "result": [{"keyword": "x"}],
            }],
        }
        v = evaluate_dataforseo_labs_live(payload, "related_keywords")
        self.assertTrue(v["accepted"])
        self.assertEqual(v["classification"], "retrieved")
        # provider_cost_cents holds the raw provider cost in USD (float).
        self.assertEqual(v["provider_cost_cents"], 0.05)

    def test_labs_zero_cost_rejected(self):
        payload = {
            "status_code": 20000, "tasks_error": 0, "cost": 0,
            "tasks": [{
                "id": "labs-1", "status_code": 20000, "status_message": "Ok.",
                "path": ["v3", "dataforseo_labs", "amazon", "related_keywords", "live"],
                "result": [{"keyword": "x"}],
            }],
        }
        v = evaluate_dataforseo_labs_live(payload, "related_keywords")
        self.assertFalse(v["accepted"])


class DataForSEOAdapterTests(unittest.TestCase):
    def setUp(self):
        block_network(self)
        self.tmp = tempfile.mkdtemp(prefix="ns-df-test-")
        self._orig = {}
        for k in ("DATAFORSEO_ENABLED", "DATAFORSEO_MODE",
                  "DATAFORSEO_ESTIMATED_COST_CENTS", "DATAFORSEO_BUDGET_CENTS",
                  "DATAFORSEO_FIRST_RUN_BUDGET_CENTS", "DATAFORSEO_CACHE_TTL_HOURS",
                  "DATAFORSEO_ADAPTER_ROOT", "DATAFORSEO_LEDGER_PATH",
                  "DATAFORSEO_CACHE_DIR", "DATAFORSEO_RAW_DIR",
                  "DATAFORSEO_APPROVAL_STATE_PATH", "DATAFORSEO_LOGIN",
                  "DATAFORSEO_PASSWORD", "DATAFORSEO_TRANSPORT_ENABLED",
                  "DATAFORSEO_LABS_AUTO_SUBMIT"):
            self._orig[k] = os.environ.pop(k, None)
        os.environ["DATAFORSEO_ADAPTER_ROOT"] = self.tmp
        os.environ["DATAFORSEO_LEDGER_PATH"] = os.path.join(self.tmp, "ledger.jsonl")
        os.environ["DATAFORSEO_CACHE_DIR"] = os.path.join(self.tmp, "cache")
        os.environ["DATAFORSEO_RAW_DIR"] = os.path.join(self.tmp, "raw")
        os.environ["DATAFORSEO_APPROVAL_STATE_PATH"] = os.path.join(self.tmp, "approval.json")
        os.environ["DATAFORSEO_ESTIMATED_COST_CENTS"] = "1"
        os.environ["DATAFORSEO_ENABLED"] = "1"

    def tearDown(self):
        for k, v in self._orig.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # --- Section 1: feature flag ------------------------------------------
    def test_feature_disabled_by_default(self):
        self.assertFalse(df.feature_enabled({}))
        cfg = df.load_config({})
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["mode"], "standard_queue")

    def test_non_standard_mode_blocked(self):
        cfg = df.load_config({"DATAFORSEO_ENABLED": "1"})
        cfg["mode"] = "priority_queue"
        with self.assertRaises(GuardError):
            df.validate_config(cfg)

    def test_invalid_estimated_cost_blocked(self):
        with self.assertRaises(GuardError):
            df.load_config({"DATAFORSEO_ENABLED": "1",
                            "DATAFORSEO_ESTIMATED_COST_CENTS": "abc"})

    # --- Section 2: endpoint allowlist -----------------------------------
    def test_allowlist_permit_products_task_post(self):
        cls = df.classify_endpoint(
            "https://api.dataforseo.com/v3/merchant/amazon/products/task_post", "POST")
        self.assertEqual(cls, "task_post")

    def test_allowlist_permit_sellers_and_asin(self):
        self.assertEqual(df.classify_endpoint(
            "https://api.dataforseo.com/v3/merchant/amazon/sellers/task_get/t-1", "GET"),
            "task_get")
        self.assertEqual(df.classify_endpoint(
            "https://api.dataforseo.com/v3/merchant/amazon/asin/task_post", "POST"),
            "task_post")

    def test_allowlist_reject_seller_info(self):
        with self.assertRaises(GuardError):
            df.classify_endpoint(
                "https://api.dataforseo.com/v3/merchant/amazon/seller_info/task_post", "POST")

    def test_live_endpoint_refused(self):
        with self.assertRaises(GuardError):
            df.classify_endpoint(
                "https://api.dataforseo.com/v3/merchant/amazon/products/live/task_post", "POST")

    def test_keyword_endpoint_refused(self):
        with self.assertRaises(GuardError):
            df.classify_endpoint(
                "https://api.dataforseo.com/v3/merchant/amazon/search/task_post", "POST")

    def test_bulk_tasks_ready_refused(self):
        with self.assertRaises(GuardError):
            df.classify_endpoint(
                "https://api.dataforseo.com/v3/merchant/amazon/products/tasks_ready", "GET")

    def test_unknown_endpoint_refused(self):
        with self.assertRaises(GuardError):
            df.classify_endpoint(
                "https://api.dataforseo.com/v3/merchant/amazon/reviews/task_post", "POST")

    def test_task_get_without_id_refused(self):
        with self.assertRaises(GuardError):
            df.classify_endpoint(
                "https://api.dataforseo.com/v3/merchant/amazon/products/task_get", "GET")

    # --- Section 3: bounded contract -------------------------------------
    def test_contract_accepts_single_candidate(self):
        c = df.validate_contract({
            "asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
            "bd_snapshot_ref": BD_REF, "approval_run_id": "run-1"})
        self.assertEqual(c["asin"], SHORTLIST_ASIN)
        self.assertEqual(c["task_types"], ["product"])

    def test_contract_accepts_sellers_task_type(self):
        c = df.validate_contract({
            "asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
            "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
            "task_types": ["sellers"]})
        self.assertEqual(c["task_types"], ["sellers"])

    def test_explicit_unknown_task_type_rejected(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                                   "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
                                   "task_types": ["seller_offer"]})

    def test_labs_task_rejected_without_env_gate(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                                   "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
                                   "task_types": ["bulk_search_volume"]})

    def test_labs_task_allowed_with_env_gate(self):
        os.environ["DATAFORSEO_LABS_AUTO_SUBMIT"] = "true"
        c = df.validate_contract({"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
                                  "task_types": ["bulk_search_volume"]})
        self.assertIn("bulk_search_volume", c["task_types"])

    def test_blank_asin_rejected(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": "", "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r"})

    def test_list_asin_rejected(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": [SHORTLIST_ASIN, "B0AAAAAAAAA"],
                                  "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r"})

    def test_wildcard_asin_rejected(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": "B0*", "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r"})

    def test_keyword_search_rejected(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
                                  "keyword": "kirkland"})

    def test_more_than_two_task_types_rejected(self):
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
                                  "task_types": ["product", "sellers", "asin"]})

    def test_shortlist_gate_blocks_unpassed(self):
        with self.assertRaises(GuardError):
            df.execute_validation(
                {"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                 "bd_snapshot_ref": BD_REF, "approval_run_id": "r"},
                operator_token="r", lookup=shortlist_fail)
        df.create_approval("r", "r")
        with self.assertRaises(GuardError):
            df.execute_validation(
                {"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                 "bd_snapshot_ref": BD_REF, "approval_run_id": "r"},
                operator_token="r", lookup=shortlist_fail)

    # --- Section 4/5: budget ledger + idempotency ------------------------
    def test_max_tasks_per_asin_guard(self):
        ledger = df.Ledger()
        orig = df.MAX_TASKS_PER_ASIN
        df.MAX_TASKS_PER_ASIN = 1
        try:
            df.ledger_plan_task(ledger, "r", SHORTLIST_ASIN, MARKETPLACE, "product",
                                "amazon_merchant_products", BD_REF, 1, 100)
            with self.assertRaises(GuardError):
                df.ledger_plan_task(ledger, "r", SHORTLIST_ASIN, MARKETPLACE, "product",
                                    "amazon_merchant_products", BD_REF, 1, 100)
        finally:
            df.MAX_TASKS_PER_ASIN = orig

    def test_first_run_budget_one_cent_blocks_second_asin(self):
        df.create_approval("first", "first")
        self.assertTrue(df.is_first_approved_run("first"))
        self.assertEqual(df.effective_budget_cents("first"), 1)
        ledger = df.Ledger()
        df.ledger_plan_task(ledger, "first", SHORTLIST_ASIN, MARKETPLACE, "product",
                            "amazon_merchant_products", BD_REF, 1, 1)
        with self.assertRaises(GuardError):
            df.ledger_plan_task(ledger, "first", "B0AAAAAAAAA", MARKETPLACE, "product",
                                "amazon_merchant_products", BD_REF, 1, 1)
        self.assertLessEqual(ledger.reserved_plus_completed(), 1)
        self.assertTrue(ledger.records(request_state="budget_rejected"))

    def test_second_run_gets_default_budget(self):
        df.create_approval("first", "first")
        df.create_approval("second", "second")
        self.assertFalse(df.is_first_approved_run("second"))
        self.assertEqual(df.effective_budget_cents("second"), 100)

    def test_duplicate_idempotency_no_second_row(self):
        ledger = df.Ledger()
        rec = df.ledger_plan_task(ledger, "r", SHORTLIST_ASIN, MARKETPLACE, "product",
                                  "amazon_merchant_products", BD_REF, 1, 100)
        same = df.ledger_plan_task(ledger, "r", SHORTLIST_ASIN, MARKETPLACE, "product",
                                   "amazon_merchant_products", BD_REF, 1, 100)
        self.assertEqual(same["idempotency_key"], rec["idempotency_key"])
        self.assertEqual(ledger.count_tasks(SHORTLIST_ASIN), 1)

    def test_approval_token_must_equal_run_id(self):
        with self.assertRaises(GuardError):
            df.create_approval("run-x", "wrong-token")
        rec = df.create_approval("run-x", "run-x")
        self.assertEqual(rec["run_status"], "authorized")

    def test_execute_requires_approval_token(self):
        df.create_approval("run-x", "run-x")
        with self.assertRaises(GuardError):
            df.execute_validation(
                {"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                 "bd_snapshot_ref": BD_REF, "approval_run_id": "run-x"},
                operator_token="nope", lookup=shortlist_pass)

    # --- Section 6: cache-first ------------------------------------------
    def test_cache_hit_returns_without_paid_call(self):
        norm = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water",
                "provider": "dataforseo", "task_type": "product"}
        df.cache_put(SHORTLIST_ASIN, MARKETPLACE, "product", norm)
        df.create_approval("run-x", "run-x")
        result = df.execute_validation(
            {"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
             "bd_snapshot_ref": BD_REF, "approval_run_id": "run-x"},
            operator_token="run-x", lookup=shortlist_pass)
        self.assertEqual(result["LIVE_CALLS_MADE"], 0)
        prod = [r for r in result["results"] if r["task_type"] == "product"][0]
        self.assertEqual(prod["source"], "cache")

    def test_cache_put_preserves_raw_separately(self):
        df.raw_put("run-x", SHORTLIST_ASIN, "product", {"foo": "bar"})
        df.cache_put(SHORTLIST_ASIN, MARKETPLACE, "product",
                     {"asin": SHORTLIST_ASIN, "title": "X"})
        self.assertTrue(os.path.isdir(df.raw_dir()))
        self.assertTrue(os.path.isdir(df.cache_dir()))
        self.assertNotEqual(df.raw_dir(), df.cache_dir())

    # --- Section 7: normalization + comparison ---------------------------
    def test_normalize_only_supported_fields(self):
        raw = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water", "brand": "Kirkland",
               "observed_price": 19.99, "condition": "New",
               "fulfillment_signal": "FBA",
               "secret_field": "must-be-dropped", "buy_box_owner": "amazon"}
        norm = df.normalize_provider_record(raw, SHORTLIST_ASIN, MARKETPLACE, "product")
        self.assertEqual(norm["title"], "Kirkland Water")
        self.assertEqual(norm["observed_price"], 19.99)
        self.assertIsNone(norm.get("secret_field"))
        self.assertIsNone(norm["sales_estimate"])
        self.assertIsNone(norm["buy_box_owner"])
        self.assertIsNone(norm["fba_fee"])
        self.assertFalse(norm["purchase_authorized"])
        self.assertEqual(norm["endpoint_family"], "products")

    def test_sellers_family_sets_offer_count(self):
        raw = {"asin": SHORTLIST_ASIN, "price": {"value": 9.99},
               "sellers": {"offer_count": 5}}
        norm = df.normalize_provider_record(raw, SHORTLIST_ASIN, MARKETPLACE, "sellers")
        self.assertEqual(norm["seller_offer_count"], 5)

    def test_compare_matched(self):
        bd = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water", "brand": "Kirkland",
              "observed_price": 19.99}
        df_norm = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water", "brand": "Kirkland",
                   "observed_price": 19.99}
        res = df.compare_with_bright_data(bd, df_norm)
        self.assertEqual(res["classification"], "matched")
        self.assertEqual(res["review_flags"], [])
        self.assertFalse(res["purchase_authorized"])

    def test_compare_mismatch_preserves_both_values(self):
        bd = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water", "brand": "Kirkland",
              "observed_price": 19.99}
        df_norm = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water 120ct", "brand": "Kirkland",
                   "observed_price": 21.99}
        res = df.compare_with_bright_data(bd, df_norm)
        self.assertEqual(res["classification"], "mismatch")
        self.assertIn("mismatch_title", res["review_flags"])
        self.assertIn("mismatch_observed_price", res["review_flags"])
        self.assertEqual(res["bright_data_observed_value"]["title"], "Kirkland Water")
        self.assertEqual(res["dataforseo_observed_value"]["title"], "Kirkland Water 120ct")

    def test_compare_incomplete(self):
        bd = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water"}
        df_norm = {"asin": SHORTLIST_ASIN}  # no title/brand/price
        res = df.compare_with_bright_data(bd, df_norm)
        self.assertEqual(res["classification"], "incomplete")

    def test_compare_provider_error(self):
        bd = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water"}
        df_norm = {"asin": SHORTLIST_ASIN, "request_state": "provider_error"}
        res = df.compare_with_bright_data(bd, df_norm)
        self.assertEqual(res["classification"], "provider_error")

    def test_bright_data_never_mutated(self):
        bd = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water", "brand": "Kirkland"}
        bd_copy = json.loads(json.dumps(bd))
        df_norm = {"asin": SHORTLIST_ASIN, "title": "Different", "brand": "Other"}
        df.compare_with_bright_data(bd, df_norm)
        self.assertEqual(bd, bd_copy)

    # --- Section 5: ambiguous POST timeout, no auto-retry ---------------
    def test_ambiguous_post_marks_reconciliation_no_repost(self):
        class AmbiguousTransport(df.DataForSEOStandardTransport):
            def submit(self, url, payload):
                df.classify_endpoint(url, "POST")
                raise AmbiguousTransportError("POST timeout, outcome unknown")

        df.create_approval("prior", "prior")
        df.create_approval("run-x", "run-x")
        result = df.execute_validation(
            {"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
             "bd_snapshot_ref": BD_REF, "approval_run_id": "run-x"},
            operator_token="run-x", lookup=shortlist_pass,
            transport=AmbiguousTransport(allow_live=True))
        prod = [r for r in result["results"] if r["task_type"] == "product"][0]
        self.assertEqual(prod["source"], "needs_manual_reconciliation")
        key = df.idempotency_key("run-x", SHORTLIST_ASIN, MARKETPLACE, "product", BD_REF)
        self.assertEqual(df.Ledger().get(key)["request_state"],
                         "needs_manual_reconciliation")

    def test_transport_refused_makes_zero_calls(self):
        df.create_approval("prior", "prior")
        df.create_approval("run-x", "run-x")
        result = df.execute_validation(
            {"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
             "bd_snapshot_ref": BD_REF, "approval_run_id": "run-x"},
            operator_token="run-x", lookup=shortlist_pass)
        self.assertEqual(result["LIVE_CALLS_MADE"], 0)
        for r in result["results"]:
            self.assertEqual(r["source"], "transport_refused")

    # --- Section 9: preflight --------------------------------------------
    def test_preflight_reports_zero_live_calls(self):
        plan = df.preflight(SHORTLIST_ASIN, MARKETPLACE, BD_REF,
                            approval_run_id="run-x", lookup=shortlist_pass)
        self.assertEqual(plan["LIVE_CALLS_MADE"], 0)
        self.assertIsInstance(plan["feature_flag"]["enabled"], bool)
        self.assertTrue(plan["explicit_live_approval_required"])
        self.assertIn("task_post", plan["allowed_endpoint_classes"])
        self.assertIn("task_get", plan["allowed_endpoint_classes"])
        self.assertGreaterEqual(plan["budget"]["effective_ceiling_cents"], 0)
        for ik in plan["idempotency_keys"]:
            self.assertNotIn(SHORTLIST_ASIN, ik["key_prefix"])

    def test_preflight_disabled_reports_disabled(self):
        os.environ.pop("DATAFORSEO_ENABLED", None)
        plan = df.preflight(SHORTLIST_ASIN, MARKETPLACE, BD_REF, lookup=shortlist_pass)
        self.assertFalse(plan["feature_flag"]["enabled"])
        self.assertTrue(plan["explicit_live_approval_required"])
        self.assertEqual(plan["LIVE_CALLS_MADE"], 0)

    def test_preflight_shortlist_failure_flagged(self):
        plan = df.preflight(SHORTLIST_ASIN, MARKETPLACE, BD_REF, lookup=shortlist_fail)
        self.assertFalse(plan["candidate"]["shortlist_passed"])

    def test_preflight_labs_not_proposed_by_default(self):
        plan = df.preflight(SHORTLIST_ASIN, MARKETPLACE, BD_REF,
                            approval_run_id="run-x", lookup=shortlist_pass,
                            task_types=["bulk_search_volume"])
        self.assertFalse(plan["candidate"]["contract_valid"])


class DataForSEORouteTests(unittest.TestCase):
    def setUp(self):
        block_network(self)
        self.tmp = tempfile.mkdtemp(prefix="ns-df-route-")
        for k in ("DATAFORSEO_ENABLED", "DATAFORSEO_ADAPTER_ROOT",
                  "DATAFORSEO_LEDGER_PATH", "DATAFORSEO_CACHE_DIR",
                  "DATAFORSEO_RAW_DIR", "DATAFORSEO_APPROVAL_STATE_PATH",
                  "DATAFORSEO_TRANSPORT_ENABLED", "DATAFORSEO_LOGIN",
                  "DATAFORSEO_PASSWORD", "DATAFORSEO_LABS_AUTO_SUBMIT"):
            os.environ.pop(k, None)
        os.environ["DATAFORSEO_ADAPTER_ROOT"] = self.tmp
        os.environ["DATAFORSEO_LEDGER_PATH"] = os.path.join(self.tmp, "ledger.jsonl")
        os.environ["DATAFORSEO_CACHE_DIR"] = os.path.join(self.tmp, "cache")
        os.environ["DATAFORSEO_RAW_DIR"] = os.path.join(self.tmp, "raw")
        os.environ["DATAFORSEO_APPROVAL_STATE_PATH"] = os.path.join(self.tmp, "approval.json")
        os.environ["DATAFORSEO_ESTIMATED_COST_CENTS"] = "1"
        os.environ.pop("DATAFORSEO_ENABLED", None)
        import main
        self.main = main
        # ``import main`` transitively imports modules (amazon_search,
        # bright_data_client, ...) that each call ``load_dotenv()`` at import
        # time, which re-populates DataForSEO env vars from the repo .env and
        # would leak into this isolated route context. Re-isolate by popping
        # them AFTER the import so the tests see a clean, disabled default
        # (assertions below are unchanged and still enforced).
        _df_env_keys = ("DATAFORSEO_ENABLED", "DATAFORSEO_TRANSPORT_ENABLED",
                        "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD",
                        "DATAFORSEO_LABS_AUTO_SUBMIT")
        for _k in _df_env_keys:
            os.environ.pop(_k, None)

    def _post_request(self, **body):
        from pydantic import BaseModel
        req = self.main.DataForSEOValidateRequest(**body)
        return self.main.post_dataforseo_validate(req)

    def test_disabled_post_returns_403(self):
        with self.assertRaises(self.main.HTTPException) as ctx:
            self._post_request(asin=SHORTLIST_ASIN, marketplace=MARKETPLACE,
                               bd_snapshot_ref=BD_REF, approval_run_id="r",
                               approval_token="r")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_authorized_post_makes_zero_live_calls(self):
        os.environ["DATAFORSEO_ENABLED"] = "1"
        df.create_approval("run-x", "run-x")
        with mock.patch.object(self.main._df, "candidate_passed_shortlist",
                               return_value=(True, {})):
            with mock.patch.object(self.main._df,
                                   "DataForSEOStandardTransport") as Tr:
                Tr.return_value = _RefusingTransport(allow_live=True)
                body = self._post_request(asin=SHORTLIST_ASIN, marketplace=MARKETPLACE,
                                          bd_snapshot_ref=BD_REF, approval_run_id="run-x",
                                          approval_token="run-x")
        self.assertEqual(body["LIVE_CALLS_MADE"], 0)
        for r in body["results"]:
            self.assertEqual(r["live_calls_made"], 0)

    def test_get_scanner_makes_no_dataforseo_call(self):
        self.assertFalse(df.feature_enabled())
        resp = self.main.get_kirkland_scanner()
        self.assertIn("products", resp)
        self.assertNotIn("dataforseo", resp.get("summary", {}))


class TransportGuardTests(unittest.TestCase):
    """Strict runtime transport kill-switch parsing (no network)."""

    PRODUCTS_POST_URL = "https://api.dataforseo.com/v3/merchant/amazon/products/task_post"

    def setUp(self):
        block_network(self)
        self._prev = os.environ.pop("DATAFORSEO_TRANSPORT_ENABLED", None)
        self._prev_login = os.environ.pop("DATAFORSEO_LOGIN", None)
        self._prev_password = os.environ.pop("DATAFORSEO_PASSWORD", None)

    def tearDown(self):
        os.environ.pop("DATAFORSEO_TRANSPORT_ENABLED", None)
        if self._prev is not None:
            os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = self._prev
        os.environ.pop("DATAFORSEO_LOGIN", None)
        if self._prev_login is not None:
            os.environ["DATAFORSEO_LOGIN"] = self._prev_login
        os.environ.pop("DATAFORSEO_PASSWORD", None)
        if self._prev_password is not None:
            os.environ["DATAFORSEO_PASSWORD"] = self._prev_password

    def _call_submit(self, transport_enabled_value=None):
        if transport_enabled_value is not None:
            os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = transport_enabled_value
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(tr, "_credentials",
                               return_value={"login": "", "password": ""}) as creds:
            raised = False
            try:
                tr.submit(self.PRODUCTS_POST_URL, {"data": {}})
            except df.GuardError:
                raised = True
            return raised, creds

    def test_unset_disables_transport(self):
        os.environ.pop("DATAFORSEO_TRANSPORT_ENABLED", None)
        self.assertFalse(df._transport_enabled())
        raised, creds = self._call_submit(None)
        self.assertTrue(raised)
        creds.assert_not_called()  # gate blocks before any credential access

    def test_true_enables_transport(self):
        raised, creds = self._call_submit("true")
        self.assertTrue(raised)
        creds.assert_called_once()

    def test_armed_transport_posts_with_credentials(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        posted = {}

        def fake_post(url, **kwargs):
            posted["url"] = url
            posted["auth"] = kwargs.get("auth")
            posted["json"] = kwargs.get("json")
            return FakeResponse(200, VALID_CREATE)
        with mock.patch.object(__import__("requests"), "post",
                               side_effect=fake_post):
            out = tr.submit(self.PRODUCTS_POST_URL,
                            [{"asin": SHORTLIST_ASIN, "language_code": "en_US"}])
        self.assertEqual(out["tasks"][0]["id"], "task-created-1")
        self.assertEqual(posted["auth"], ("login@example.com", "pw"))
        self.assertIn("/task_post", posted["url"])

    def test_armed_transport_retrieves_with_credentials(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(
                __import__("requests"), "get",
                return_value=FakeResponse(200, VALID_GET)):
            out = tr.retrieve(
                "https://api.dataforseo.com/v3/merchant/amazon/products/task_get/task-0001")
        self.assertEqual(out["tasks"][0]["id"], "task-created-1")

    def test_armed_transport_http_error_is_guarderror(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(__import__("requests"), "post",
                               return_value=FakeResponse(500, {})):
            with self.assertRaises(df.GuardError):
                tr.submit(self.PRODUCTS_POST_URL, [{}])

    def test_armed_transport_timeout_is_ambiguous(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(__import__("requests"), "post",
                               side_effect=__import__("requests").exceptions.Timeout()):
            with self.assertRaises(df.AmbiguousTransportError):
                tr.submit(self.PRODUCTS_POST_URL, [{}])

    def test_armed_transport_invalid_json_is_guarderror(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(__import__("requests"), "post",
                               return_value=FakeResponse(200, None)):
            with self.assertRaises(df.GuardError):
                tr.submit(self.PRODUCTS_POST_URL, [{}])

    def test_armed_transport_missing_credentials_never_calls_http(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with self.assertRaises(df.GuardError):
            tr.submit(self.PRODUCTS_POST_URL, [{"asin": SHORTLIST_ASIN}])

    def test_unenabled_transport_never_calls_http(self):
        os.environ.pop("DATAFORSEO_TRANSPORT_ENABLED", None)
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with self.assertRaises(df.GuardError):
            tr.submit(self.PRODUCTS_POST_URL, [{"asin": SHORTLIST_ASIN}])

    def test_non_true_values_disable_transport(self):
        for bad in ("", "false", "FALSE", "False", "1", "yes", "YES", "on",
                    "truee", " malformed", "0", "off"):
            os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = bad
            self.assertFalse(df._transport_enabled(), msg=f"value={bad!r}")
            raised, creds = self._call_submit(bad)
            self.assertTrue(raised, msg=f"value={bad!r} should refuse")
            creds.assert_not_called()

    def test_uppercase_true_normalized_to_enabled(self):
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "TRUE"
        self.assertTrue(df._transport_enabled())
        raised, creds = self._call_submit("TRUE")
        self.assertTrue(raised)
        creds.assert_called_once()


class DataForSEOLivePathTests(unittest.TestCase):
    """Armed transport paths: real submission/retrieval wiring with mocked
    HTTP and injected transports (never any live provider call)."""

    def setUp(self):
        block_network(self)
        self.tmp = tempfile.mkdtemp(prefix="ns-df-live-")
        self._orig = {}
        for k in ("DATAFORSEO_ENABLED", "DATAFORSEO_MODE",
                  "DATAFORSEO_ESTIMATED_COST_CENTS", "DATAFORSEO_BUDGET_CENTS",
                  "DATAFORSEO_FIRST_RUN_BUDGET_CENTS", "DATAFORSEO_CACHE_TTL_HOURS",
                  "DATAFORSEO_ADAPTER_ROOT", "DATAFORSEO_LEDGER_PATH",
                  "DATAFORSEO_CACHE_DIR", "DATAFORSEO_RAW_DIR",
                  "DATAFORSEO_APPROVAL_STATE_PATH", "DATAFORSEO_LOGIN",
                  "DATAFORSEO_PASSWORD", "DATAFORSEO_TRANSPORT_ENABLED"):
            self._orig[k] = os.environ.pop(k, None)
        os.environ["DATAFORSEO_ADAPTER_ROOT"] = self.tmp
        os.environ["DATAFORSEO_LEDGER_PATH"] = os.path.join(self.tmp, "ledger.jsonl")
        os.environ["DATAFORSEO_CACHE_DIR"] = os.path.join(self.tmp, "cache")
        os.environ["DATAFORSEO_RAW_DIR"] = os.path.join(self.tmp, "raw")
        os.environ["DATAFORSEO_APPROVAL_STATE_PATH"] = os.path.join(self.tmp, "approval.json")
        os.environ["DATAFORSEO_ESTIMATED_COST_CENTS"] = "1"
        os.environ["DATAFORSEO_ENABLED"] = "1"
        os.environ["DATAFORSEO_TRANSPORT_ENABLED"] = "true"
        os.environ["DATAFORSEO_LOGIN"] = "login@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "pw"
        df.create_approval("prior", "prior")
        df.create_approval("run-live", "run-live")

    def tearDown(self):
        for k, v in self._orig.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _req(self, run_id="run-live"):
        return {
            "asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
            "bd_snapshot_ref": BD_REF, "bd_record_id": "rec-1",
            "approval_run_id": run_id,
        }

    def _ledger(self, idempotency_key):
        for rec in _ledger_records():
            if rec.get("idempotency_key") == idempotency_key:
                return rec
        return None

    def test_execute_live_submit_success(self):
        # True submission case: task-level 20100 "Task Created." + cost > 0
        # + path matches products family.
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(df, "candidate_passed_shortlist",
                               return_value=(True, {"name": "Kirkland K-Cups"})):
            with mock.patch.object(
                    tr, "submit",
                    return_value=json.loads(json.dumps(VALID_CREATE))):
                body = df.execute_validation(self._req(),
                                             operator_token="run-live", transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        self.assertEqual(body["results"][0]["source"], "live")
        self.assertEqual(body["results"][0]["provider_task_id"], "task-created-1")
        rec = self._ledger(body["results"][0]["idempotency_key"])
        self.assertEqual(rec["request_state"], "submitted")
        self.assertEqual(rec["provider_task_id"], "task-created-1")
        self.assertEqual(rec["actual_cost_cents"], 5)
        self.assertEqual(rec["endpoint_family"], "products")

    def test_execute_live_submit_40402_envelope_rejected(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(df, "candidate_passed_shortlist",
                               return_value=(True, {"name": "Kirkland K-Cups"})):
            with mock.patch.object(tr, "submit",
                                   return_value=json.loads(json.dumps(ENVELOPE_40402))):
                body = df.execute_validation(self._req(),
                                             operator_token="run-live", transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        r = body["results"][0]
        self.assertEqual(r["source"], "provider_rejected")
        self.assertEqual(r["classification"], "provider_rejected_invalid_path")
        self.assertEqual(r["provider_cost_cents"], 0)
        rec = self._ledger(r["idempotency_key"])
        self.assertEqual(rec["request_state"], "provider_rejected_invalid_path")
        self.assertIsNone(rec["provider_task_id"])
        self.assertEqual(rec["actual_cost_cents"], 0)
        self.assertIn("Invalid Path", rec["failure_reason"] or "")
        self.assertFalse(df.Ledger().records(request_state="submitted"))

    def test_execute_live_submit_20100_zero_cost_rejected(self):
        env = {"status_code": 20000, "tasks_error": 0, "tasks": [{
            "id": "t0", "status_code": 20100, "status_message": "Task Created.",
            "cost": 0,
            "path": ["v3", "merchant", "amazon", "products", "task_post"]}]}
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(df, "candidate_passed_shortlist",
                               return_value=(True, {"name": "Kirkland K-Cups"})):
            with mock.patch.object(tr, "submit", return_value=env):
                body = df.execute_validation(self._req(),
                                             operator_token="run-live", transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        r = body["results"][0]
        self.assertEqual(r["source"], "provider_rejected")
        self.assertIn("greater than zero", r["reason"])
        rec = self._ledger(r["idempotency_key"])
        self.assertEqual(rec["request_state"], "provider_rejected_unknown")

    def test_execute_live_submit_missing_task_id_is_refused(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(df, "candidate_passed_shortlist",
                               return_value=(True, {"name": "Kirkland K-Cups"})):
            with mock.patch.object(tr, "submit", return_value={"tasks": []}):
                body = df.execute_validation(self._req(),
                                             operator_token="run-live", transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        r = body["results"][0]
        self.assertEqual(r["source"], "provider_rejected")
        self.assertIsNone(self._ledger(r["idempotency_key"])["provider_task_id"])

    def test_execute_live_submit_ambiguous_marks_reconciliation(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(df, "candidate_passed_shortlist",
                               return_value=(True, {"name": "Kirkland K-Cups"})):
            with mock.patch.object(tr, "submit",
                                   side_effect=df.AmbiguousTransportError("timeout")):
                body = df.execute_validation(self._req(),
                                             operator_token="run-live", transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        r = body["results"][0]
        self.assertEqual(r["source"], "needs_manual_reconciliation")
        rec = self._ledger(r["idempotency_key"])
        self.assertEqual(rec["request_state"], "needs_manual_reconciliation")

    def test_retrieve_live_success_normalizes_and_caches(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(tr, "retrieve", return_value=json.loads(json.dumps(VALID_GET))):
            body = df.retrieve_validation(
                "run-live", SHORTLIST_ASIN, "product", "task-created-1",
                transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        self.assertEqual(body["status"], "retrieved")
        norm = body["normalized"]
        self.assertEqual(norm["asin"], SHORTLIST_ASIN)
        self.assertEqual(norm["title"], "Kirkland K-Cups")
        self.assertEqual(norm["observed_price"], 12.5)
        self.assertEqual(norm["seller_offer_count"], 3)
        self.assertEqual(norm["endpoint_family"], "products")
        cached = df.cache_get(SHORTLIST_ASIN, MARKETPLACE, "product")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["observed_price"], 12.5)

    def test_retrieve_live_ambiguous_reports_reconciliation(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(tr, "retrieve",
                               side_effect=df.AmbiguousTransportError("timeout")):
            body = df.retrieve_validation(
                "run-live", SHORTLIST_ASIN, "product", "task-created-1",
                transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        self.assertEqual(body["status"], "needs_manual_reconciliation")

    def test_retrieve_live_provider_error_no_result_item(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        payload = {"tasks": [{"id": "task-live-1", "status_code": 40400, "result": []}]}
        with mock.patch.object(tr, "retrieve", return_value=payload):
            body = df.retrieve_validation(
                "run-live", SHORTLIST_ASIN, "product", "task-live-1",
                transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 1)
        self.assertEqual(body["status"], "provider_error")

    def test_retrieve_live_refused_when_transport_disabled(self):
        tr = df.DataForSEOStandardTransport(allow_live=True)
        with mock.patch.object(tr, "retrieve",
                               side_effect=df.GuardError("not enabled")):
            body = df.retrieve_validation(
                "run-live", SHORTLIST_ASIN, "product", "task-live-1",
                transport=tr)
        self.assertEqual(body["LIVE_CALLS_MADE"], 0)
        self.assertIn("error", body)


class EndpointAllowlistSelfCheckTests(unittest.TestCase):
    def test_verify_endpoint_allowlist_all_pass(self):
        res = df.verify_endpoint_allowlist()
        self.assertTrue(res["all_pass"])
        self.assertTrue(res["products_task_post_allowed"])
        self.assertTrue(res["products_task_get_allowed"])
        self.assertTrue(res["asin_task_post_allowed"])
        self.assertTrue(res["sellers_task_post_allowed"])
        self.assertTrue(res["product_info_rejected"])
        self.assertTrue(res["seller_info_rejected"])
        self.assertTrue(res["search_rejected"])
        self.assertTrue(res["reviews_rejected"])
        self.assertTrue(res["tasks_ready_rejected"])

    def test_no_loop_variable_leakage_between_cases(self):
        for _ in range(5):
            res = df.verify_endpoint_allowlist()
            self.assertTrue(res["all_pass"])

    def test_labs_inspection_allowed_but_not_auto_submitted(self):
        # Labs paths ARE accepted by classify_endpoint for read-only inspection;
        # auto-submission is blocked at the task-type layer (env gate).
        cls = df.classify_endpoint(
            "https://api.dataforseo.com/v3/dataforseo_labs/amazon/related_keywords/live",
            "POST")
        self.assertEqual(cls, "labs_live")
        # Without the env gate, a Labs task type is rejected by validate_contract.
        with self.assertRaises(GuardError):
            df.validate_contract({"asin": SHORTLIST_ASIN, "marketplace": MARKETPLACE,
                                  "bd_snapshot_ref": BD_REF, "approval_run_id": "r",
                                  "task_types": ["related_keywords"]})


class LocalDotenvLoaderTests(unittest.TestCase):
    def setUp(self):
        block_network(self)
        self._prev_root = os.environ.pop("NORTHSTAR_ENV_PATH", None)

    def tearDown(self):
        os.environ.pop("NORTHSTAR_ENV_PATH", None)
        if self._prev_root is not None:
            os.environ["NORTHSTAR_ENV_PATH"] = self._prev_root

    def test_loads_existing_local_env_secret_free(self):
        tmpdir = tempfile.mkdtemp(prefix="ns-df-env-")
        env_path = os.path.join(tmpdir, ".env")
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.write("# comment line\n")
            fh.write("DATAFORSEO_ENABLED=false\n")
            fh.write("DATAFORSEO_TRANSPORT_ENABLED=false\n")
            fh.write("DATAFORSEO_ESTIMATED_COST_CENTS=1\n")
        os.environ["NORTHSTAR_ENV_PATH"] = env_path
        os.environ["DATAFORSEO_ESTIMATED_COST_CENTS"] = "999"
        loaded = df.load_local_env()
        self.assertTrue(loaded)
        self.assertEqual(os.environ.get("DATAFORSEO_ESTIMATED_COST_CENTS"), "999")
        os.environ.pop("DATAFORSEO_TRANSPORT_ENABLED", None)
        df.load_local_env()
        self.assertEqual(os.environ.get("DATAFORSEO_TRANSPORT_ENABLED"), "false")

    def test_missing_env_is_noop_and_returns_false(self):
        os.environ["NORTHSTAR_ENV_PATH"] = os.path.join(
            tempfile.mkdtemp(prefix="ns-df-nofile-"), ".env")
        self.assertFalse(df.load_local_env())

    def test_loader_never_raises_on_malformed(self):
        tmpdir = tempfile.mkdtemp(prefix="ns-df-malf-")
        env_path = os.path.join(tmpdir, ".env")
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.write("this line has no equals\n")
            fh.write("KEY_ONLY=\n")
            fh.write("\n")
        os.environ["NORTHSTAR_ENV_PATH"] = env_path
        loaded = df.load_local_env()
        self.assertTrue(loaded)


if __name__ == "__main__":
    unittest.main(verbosity=2)
