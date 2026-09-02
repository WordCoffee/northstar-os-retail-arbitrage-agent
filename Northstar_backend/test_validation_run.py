"""Offline verification tests for the guarded 20-ASIN validation extension.

These tests assert the implementation in validation_run.py is OFFLINE-VERIFIED
and LIVE-READY: every gate fails closed, no network is created during any
offline command, secrets never appear in config objects or reports, the
canonical 20-ASIN source is referenced but never mutated, and the three
manual-review ASINs stay review-only.

No live provider calls are made or simulated here.
"""

import copy
import json
import os
import tempfile
import unittest
from unittest import mock

import validation_run as vr
from proof_batch_contracts import GuardError, RunAbort, BindingError
from dataforseo_adapter import GuardError as DataForSeoGuardError

MANUAL = ("B01H40O42I", "B08R2SRN88", "B00N54AJZE")
TEST_RUN_ID = "data-validation-20asin-testrun"


class ValidationRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ns-validation-test-")
        self._prev_root = os.environ.get("VALIDATION_RUNS_ROOT")
        self._prev_src = os.environ.get("VALIDATION_SOURCE_PREFLIGHT")
        self._prev_enabled = os.environ.pop("DATAFORSEO_ENABLED", None)
        self._prev_mode = os.environ.pop("DATAFORSEO_MODE", None)
        self._prev_cap = os.environ.pop("DATAFORSEO_HARD_CAP_CENTS", None)
        os.environ["VALIDATION_RUNS_ROOT"] = self.tmp
        os.environ["VALIDATION_SOURCE_PREFLIGHT"] = vr.source_preflight_path()
        self.source_path = vr.source_preflight_path()
        self.source = vr.read_json(self.source_path)

    def tearDown(self):
        if self._prev_root is None:
            os.environ.pop("VALIDATION_RUNS_ROOT", None)
        else:
            os.environ["VALIDATION_RUNS_ROOT"] = self._prev_root
        if self._prev_src is None:
            os.environ.pop("VALIDATION_SOURCE_PREFLIGHT", None)
        else:
            os.environ["VALIDATION_SOURCE_PREFLIGHT"] = self._prev_src
        if self._prev_enabled is not None:
            os.environ["DATAFORSEO_ENABLED"] = self._prev_enabled
        if self._prev_mode is not None:
            os.environ["DATAFORSEO_MODE"] = self._prev_mode
        if self._prev_cap is not None:
            os.environ["DATAFORSEO_HARD_CAP_CENTS"] = self._prev_cap

    # --- Phase 1: config boundary (C) -------------------------------------
    def test_dataforseo_disabled_by_default(self):
        cfg = vr.load_dataforseo_config(environ={})
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["mode"], "standard_queue")
        self.assertEqual(cfg["hard_cap_cents"], vr.DEFAULT_HARD_CAP_CENTS)

    def test_non_standard_mode_blocked(self):
        cfg = vr.load_dataforseo_config(environ={"DATAFORSEO_ENABLED": "1"})
        cfg["mode"] = "priority_queue"
        with self.assertRaises(GuardError):
            vr.validate_dataforseo_config(cfg)

    def test_invalid_cap_blocked(self):
        # load is fail-closed too: an unparseable cap is rejected immediately.
        with self.assertRaises(GuardError):
            vr.load_dataforseo_config(environ={"DATAFORSEO_ENABLED": "1",
                                               "DATAFORSEO_HARD_CAP_CENTS": "notanint"})

    def test_config_contains_no_secret_values(self):
        cfg = vr.load_dataforseo_config(environ={"DATAFORSEO_LOGIN": "x",
                                                 "DATAFORSEO_PASSWORD": "y"})
        serialized = json.dumps(cfg)
        self.assertNotIn("x", serialized)
        self.assertNotIn("y", serialized)
        self.assertEqual(cfg["login_env"], "DATAFORSEO_LOGIN")
        self.assertEqual(cfg["password_env"], "DATAFORSEO_PASSWORD")

    def test_credentials_only_inside_transport(self):
        # get_dataforseo_credentials is transport-only; the planner/manifest
        # never read it. Assert it is not invoked by create_validation_manifest.
        with mock.patch.object(vr, "get_dataforseo_credentials") as g:
            vr.create_validation_manifest(run_id=TEST_RUN_ID)
            g.assert_not_called()

    # --- Phase 1: manifest (B) --------------------------------------------
    def test_manifest_references_source_without_mutation(self):
        before = vr.sha256_file(self.source_path)
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        after = vr.sha256_file(self.source_path)
        self.assertEqual(before, after)
        manifest = vr.load_manifest(TEST_RUN_ID)
        ref = manifest["source_reference"]
        self.assertEqual(ref["path"], self.source_path)
        self.assertEqual(ref["sha256"], before)
        self.assertEqual(ref["selected_count"], 20)
        self.assertEqual(len(manifest["asins"]), 20)
        self.assertEqual(manifest["max_asins"], 20)
        self.assertEqual(manifest["hard_cap_cents"], 100)

    def test_manifest_preserves_three_conflict_flags(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        by_asin = {a["asin"]: a for a in manifest["asins"]}
        for asin in MANUAL:
            self.assertTrue(by_asin[asin]["manual_review_only"])
            self.assertTrue(by_asin[asin]["title_conflict"])

    def test_run_dirs_isolated_per_run(self):
        vr.create_validation_manifest(run_id="runA")
        vr.create_validation_manifest(run_id="runB")
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "runA")))
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "runB")))
        # Each run owns its own manifest; run A's manifest lives under A only.
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "runA", "manifest.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "runB", "manifest.json")))
        self.assertNotEqual(vr.run_dir("runA"), vr.run_dir("runB"))

    def test_more_than_20_asins_blocked(self):
        bad = copy.deepcopy(self.source)
        extra = copy.deepcopy(bad["selection"]["asins"][0])
        extra["asin"] = "B0ZZZZZZZZ"
        bad["selection"]["asins"].append(extra)
        path = os.path.join(self.tmp, "bad21.json")
        vr.atomic_write_json(path, bad)
        with self.assertRaises(GuardError):
            vr.create_validation_manifest(run_id="x", source_path=path)

    def test_duplicate_asins_blocked(self):
        bad = copy.deepcopy(self.source)
        bad["selection"]["asins"].append(copy.deepcopy(bad["selection"]["asins"][0]))
        path = os.path.join(self.tmp, "dup.json")
        vr.atomic_write_json(path, bad)
        with self.assertRaises(GuardError):
            vr.create_validation_manifest(run_id="x", source_path=path)

    # --- Phase 1: authorization (D) ---------------------------------------
    def test_create_authorization_requires_exact_confirm(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        with self.assertRaises(GuardError):
            vr.create_authorization(TEST_RUN_ID, manifest, "wrong-confirm")
        with self.assertRaises(GuardError):
            vr.create_authorization(TEST_RUN_ID, manifest, None)
        rec = vr.create_authorization(TEST_RUN_ID, manifest, TEST_RUN_ID)
        self.assertEqual(rec["run_status"], "authorized")
        self.assertEqual(rec["permitted_queue_mode"], "standard_queue")

    def test_verify_authorization_invalid_without_record(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        ledger = vr.Ledger(TEST_RUN_ID)
        ok, reasons = vr.verify_authorization(TEST_RUN_ID, manifest, ledger)
        self.assertFalse(ok)
        self.assertIn("no authorization record for run_id", reasons)

    def test_verify_authorization_detects_manifest_mismatch(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        rec = vr.create_authorization(TEST_RUN_ID, manifest, TEST_RUN_ID)
        vr.atomic_write_json(os.path.join(vr.run_dir(TEST_RUN_ID), "authorization.json"), rec)
        tampered = copy.deepcopy(manifest)
        tampered["asins"].append({"asin": "B0ZZZZZZZZ", "manual_review_only": False,
                                  "title_conflict": False, "source_rank": 99,
                                  "title": "x", "expected_validation_plan": {},
                                  "max_reservation_cents": 0})
        ledger = vr.Ledger(TEST_RUN_ID)
        ok, reasons = vr.verify_authorization(TEST_RUN_ID, tampered, ledger)
        self.assertFalse(ok)
        self.assertIn("manifest fingerprint mismatch", reasons)

    def test_cli_authorize_check_refuses_without_confirm(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        rc = vr.main(["authorize-check", "--run", TEST_RUN_ID])
        self.assertEqual(rc, 0)  # reports invalid, no confirmation => no write
        self.assertIsNone(vr.load_authorization(TEST_RUN_ID))

    # --- Phase 1: ledger / budget (E) -------------------------------------
    def test_max_two_tasks_per_asin(self):
        vr.ledger_add_planned(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, "B0AAAAAAAAA",
                              "product", vr.DATAFORSEO_ESTIMATED_COST_CENTS,
                              vr.DATAFORSEO_SCHEMA_VERSION)
        vr.ledger_add_planned(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, "B0AAAAAAAAA",
                              "seller_offer", vr.DATAFORSEO_ESTIMATED_COST_CENTS,
                              vr.DATAFORSEO_SCHEMA_VERSION)
        with self.assertRaises(RunAbort):
            vr.ledger_add_planned(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, "B0AAAAAAAAA",
                                  "product", vr.DATAFORSEO_ESTIMATED_COST_CENTS,
                                  vr.DATAFORSEO_SCHEMA_VERSION)

    def test_budget_overage_blocked_and_recorded(self):
        ledger = vr.Ledger(TEST_RUN_ID)
        # 20 ASINs * 2 tasks * 5 cents = 200 cents > 100 cap.
        blocked = 0
        for i in range(20):
            asin = f"B0{i:08d}A"
            for vt in vr.VALIDATION_TYPES:
                try:
                    vr.ledger_add_planned(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, asin,
                                          vt, vr.DATAFORSEO_ESTIMATED_COST_CENTS,
                                          vr.DATAFORSEO_SCHEMA_VERSION)
                except RunAbort:
                    blocked += 1
        self.assertGreater(blocked, 0)
        self.assertLessEqual(ledger.total_reserved(), vr.DEFAULT_HARD_CAP_CENTS)
        self.assertTrue(ledger.records(state="budget_rejected"))

    def test_duplicate_idempotency_key_no_second_task(self):
        key = vr.Ledger.idempotency_key(
            vr.PROVIDER_DATAFORSEO, vr.DATAFORSEO_SCHEMA_VERSION, TEST_RUN_ID,
            "B0BBBBBBBB", "product", "standard_queue", "fp")
        rec = {"idempotency_key": key, "asin": "B0BBBBBBBB",
               "provider": vr.PROVIDER_DATAFORSEO, "state": "planned",
               "reserved_cost_cents": 5}
        ledger = vr.Ledger(TEST_RUN_ID)
        first = ledger.add(rec, dedupe_key=key)
        second = ledger.add(copy.deepcopy(rec), dedupe_key=key)
        self.assertEqual(second["idempotency_key"], first["idempotency_key"])
        self.assertEqual(ledger.count_tasks(vr.PROVIDER_DATAFORSEO, "B0BBBBBBBB"), 1)

    def test_integer_cent_accounting(self):
        vr.ledger_add_planned(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, "B0CCCCCCCCC",
                              "product", 5, vr.DATAFORSEO_SCHEMA_VERSION)
        ledger = vr.Ledger(TEST_RUN_ID)
        self.assertIsInstance(ledger.total_reserved(), int)
        self.assertEqual(ledger.total_reserved(), 5)

    # --- Phase 2: planner (F) ---------------------------------------------
    def test_plan_marks_manual_review_asins_review_only(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        plan = vr.plan_run(TEST_RUN_ID, manifest)
        totals = plan["totals"]
        self.assertEqual(totals["manual_review_only"], 3)
        self.assertEqual(totals["asin_count"], 20)
        per = {r["asin"]: r["classification"] for r in plan["per_asin"]}
        for asin in MANUAL:
            self.assertEqual(per[asin], "manual_review_only")
        # manual-review ASINs never appear as eligible_to_submit
        eligible = [r["asin"] for r in plan["per_asin"]
                    if r["classification"] == "eligible_to_submit"]
        for asin in MANUAL:
            self.assertNotIn(asin, eligible)

    def test_plan_reserves_within_budget(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        plan = vr.plan_run(TEST_RUN_ID, manifest)
        self.assertTrue(plan["within_budget"])
        self.assertLessEqual(plan["reserved_max_cost_cents"],
                             manifest["hard_cap_cents"])

    def test_retrieval_classification_without_creating_task(self):
        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        # Seed an existing ledger record that already has a remote task id.
        ledger = vr.Ledger(TEST_RUN_ID)
        asin = manifest["asins"][5]["asin"]
        ledger.add({
            "idempotency_key": "seed", "asin": asin,
            "provider": vr.PROVIDER_DATAFORSEO, "state": "submitted",
            "reserved_cost_cents": 5, "remote_task_id": "task-123",
        })
        plan = vr.plan_run(TEST_RUN_ID, manifest)
        per = {r["asin"]: r["classification"] for r in plan["per_asin"]}
        self.assertEqual(per[asin], "retrieve_existing_task")
        # retrieval must not create a new task row
        self.assertEqual(ledger.count_tasks(vr.PROVIDER_DATAFORSEO, asin), 1)

    # --- Phase 3: evidence + comparison (G) -------------------------------
    def test_raw_immutable(self):
        p1 = vr.store_raw(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, "B0DDDDDDDD",
                         {"asin": "B0DDDDDDDD", "title": "original"})
        # attempt to overwrite with different payload
        p2 = vr.store_raw(TEST_RUN_ID, vr.PROVIDER_DATAFORSEO, "B0DDDDDDDD",
                         {"asin": "B0DDDDDDDD", "title": "tampered"})
        self.assertEqual(p1, p2)
        stored = vr.read_json(p1)
        self.assertEqual(stored["payload"]["title"], "original")

    def test_normalize_missing_fields_null(self):
        norm = vr.normalize_provider_record(
            vr.PROVIDER_DATAFORSEO, {"asin": "B0EEEEEEEE", "title": "X"},
            retrieval_ts="t", schema_version="v", raw_reference="r")
        self.assertIsNone(norm["brand"])
        self.assertIsNone(norm["pack_count"])
        self.assertIn("brand", norm["data_gaps"])
        self.assertIn("pack_count", norm["data_gaps"])
        self.assertIn("asin", norm["coverage"])

    def test_compare_flags_without_overwrite(self):
        bd = {"asin": "B0FFFFFFFF", "title": "Kirkland Water", "pack_count": 12,
              "raw_reference": "rb"}
        df_match = {"asin": "B0FFFFFFFF", "title": "Kirkland Water", "pack_count": 12,
                    "raw_reference": "rd"}
        res = vr.compare_providers(copy.deepcopy(bd), copy.deepcopy(df_match), TEST_RUN_ID)
        self.assertEqual(res["classification"], "identity_match")
        # inputs unchanged
        self.assertEqual(bd["title"], "Kirkland Water")

        df_conflict = {"asin": "B0FFFFFFFF", "title": "Kirkland Water", "pack_count": 24,
                       "raw_reference": "rd"}
        res2 = vr.compare_providers(copy.deepcopy(bd), df_conflict, TEST_RUN_ID)
        self.assertEqual(res2["classification"], "identity_conflict")

    def test_compare_manual_review_asin_forced(self):
        rec = {"asin": "B01H40O42I", "title": "Whatever", "raw_reference": "r"}
        res = vr.compare_providers(rec, rec, TEST_RUN_ID)
        self.assertEqual(res["classification"], "manual_review_required")

    # --- Phase 4: transport fail-closed -----------------------------------
    def test_transport_construction_makes_zero_calls(self):
        with mock.patch("requests.get"), mock.patch("requests.post"):
            t = vr.DataForSEOTransport()
            b = vr.BrightDataValidationInterface()
        self.assertIsInstance(t, vr.DataForSEOTransport)
        self.assertIsInstance(b, vr.BrightDataValidationInterface)

    def test_dataforseo_transport_submit_refuses(self):
        t = vr.DataForSEOTransport(allow_live=True)
        with self.assertRaises(GuardError):
            t.submit("B0GGGGGGGG", "product", "standard_queue")

    def test_dataforseo_transport_delegates_to_wired_client(self):
        calls = []
        class FakeClient:
            def submit(self, asin, validation_type, mode, keyword=None):
                calls.append(("submit", asin, validation_type, mode, keyword))
                return {"tasks": [{"id": "task-1", "status_code": 20000}]}
            def retrieve(self, remote_task_id, validation_type="product"):
                calls.append(("retrieve", remote_task_id, validation_type))
                return {"tasks": [{"id": remote_task_id, "status_code": 20000}]}
        with mock.patch.dict(os.environ, {
            "DATAFORSEO_TRANSPORT_ENABLED": "true",
            "DATAFORSEO_LOGIN": "login@example.com",
            "DATAFORSEO_PASSWORD": "pw",
        }):
            t = vr.DataForSEOTransport(client=FakeClient(), allow_live=True)
            out = t.submit("B0GGGGGGGG", "product", "standard_queue")
            got = t.retrieve("task-1")
        self.assertEqual(out["tasks"][0]["id"], "task-1")
        self.assertEqual(got["tasks"][0]["status_code"], 20000)
        self.assertEqual(calls, [("submit", "B0GGGGGGGG", "product", "standard_queue", None),
                                 ("retrieve", "task-1", "product")])

    def test_dataforseo_transport_refuses_without_credentials(self):
        client = mock.MagicMock()
        with mock.patch.dict(os.environ, {
            "DATAFORSEO_TRANSPORT_ENABLED": "true",
        }, clear=False):
            os.environ.pop("DATAFORSEO_LOGIN", None)
            os.environ.pop("DATAFORSEO_PASSWORD", None)
            t = vr.DataForSEOTransport(client=client, allow_live=True)
            with self.assertRaises(GuardError):
                t.submit("B0GGGGGGGG", "product", "standard_queue")
        client.submit.assert_not_called()

    def test_dataforseo_transport_refuses_without_client(self):
        with mock.patch.dict(os.environ, {
            "DATAFORSEO_TRANSPORT_ENABLED": "true",
            "DATAFORSEO_LOGIN": "login@example.com",
            "DATAFORSEO_PASSWORD": "pw",
        }):
            t = vr.DataForSEOTransport(allow_live=True)
            with self.assertRaises(GuardError):
                t.submit("B0GGGGGGGG", "product", "standard_queue")

    def test_brightdata_interface_submit_refuses(self):
        b = vr.BrightDataValidationInterface(allow_live=True)
        with self.assertRaises(GuardError):
            b.submit("B0GGGGGGGG", "product", "standard_queue")

    def test_brightdata_interface_delegates_to_wired_client(self):
        calls = []
        class FakeClient:
            def submit(self, asin, validation_type, mode):
                calls.append((asin, validation_type, mode))
                return {"ok": True}
        b = vr.BrightDataValidationInterface(client=FakeClient(), allow_live=True)
        out = b.submit("B0GGGGGGGG", "product", "standard_queue")
        self.assertEqual(out, {"ok": True})
        self.assertEqual(calls, [("B0GGGGGGGG", "product", "standard_queue")])

    # --- End-to-end offline flow makes no network -------------------------
    def test_offline_cli_flow_no_network(self):
        import requests
        with mock.patch.object(requests, "get", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "post", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "Session", side_effect=AssertionError("network!")):
            self.assertEqual(vr.main(["preflight", "--run", TEST_RUN_ID]), 0)
            self.assertEqual(vr.main(["authorize-check", "--run", TEST_RUN_ID,
                                      "--confirm", TEST_RUN_ID]), 0)
            self.assertEqual(vr.main(["report", "--run", TEST_RUN_ID]), 0)

    # --- DataForSEO exception-class fix + endpoint pairing ----------------
    def test_retrieve_404_guarderror_handled_per_asin(self):
        # Regression: the transport raises its OWN GuardError class
        # (dataforseo_adapter.GuardError), distinct from proof_batch_contracts.
        # An HTTP 404 on task_get must fail gracefully per ASIN, never crash
        # the CLI, and never mutate the ledger row (no retrieved/completed
        # state, no resubmission).
        import requests
        from contextlib import redirect_stdout
        from io import StringIO

        class Fake404Client:
            def submit(self, asin, validation_type, mode, keyword=None):
                raise AssertionError("no submission in a retrieval test")

            def retrieve(self, remote_task_id, validation_type="product"):
                raise DataForSeoGuardError("DataForSEO returned HTTP 404")

        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        vr.create_authorization(TEST_RUN_ID, manifest, TEST_RUN_ID)
        ledger = vr.Ledger(TEST_RUN_ID)
        asin = "B0AAAAAAABA"
        ledger.add({
            "idempotency_key": "k-404", "run_id": TEST_RUN_ID,
            "provider": vr.PROVIDER_DATAFORSEO, "asin": asin,
            "validation_type": "product", "mode": vr.STANDARD_QUEUE,
            "state": "submitted", "reserved_cost_cents": 5,
            "actual_cost_cents": 5, "remote_task_id": "task-404",
        })
        env = {
            "SCANNER_LIVE_ALLOWED": "1",
            "DATAFORSEO_TRANSPORT_ENABLED": "true",
            "DATAFORSEO_LOGIN": "login@example.com",
            "DATAFORSEO_PASSWORD": "pw",
        }
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(vr, "_dataforseo_standard_client",
                               return_value=Fake404Client()), \
             mock.patch.object(requests, "get", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "post", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "Session", side_effect=AssertionError("network!")):
            buf = StringIO()
            with redirect_stdout(buf):
                code = vr.main(["retrieve-dataforseo", "--run", TEST_RUN_ID])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("retrieval refused", out)
        self.assertIn("retrieve complete", out)
        self.assertIn("failed: 1", out)
        rows = ledger.records(asin=asin)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "submitted")
        self.assertEqual(rows[0]["remote_task_id"], "task-404")
        self.assertIsNone(rows[0].get("raw_response_reference"))
        self.assertIsNone(rows[0].get("normalized_response_reference"))
        self.assertFalse(ledger.records(state="retrieved"))
        self.assertFalse(ledger.records(state="completed"))

    def test_standard_client_exact_post_get_urls(self):
        # Locks the exact standard-queue endpoint pairing used at runtime:
        # POST .../merchant/amazon/products/task_post (keyword-driven body)
        # GET  .../merchant/amazon/products/task_get/<id>  (id exactly once)
        import requests
        calls = []

        class StubTransport:
            def submit(self, url, payload):
                calls.append(("POST", url, payload))
                return {"tasks": [{"id": "task-1", "status_code": 20000}]}

            def retrieve(self, url):
                calls.append(("GET", url))
                return {"tasks": [{"id": "task-1", "status_code": 20000}]}

        with mock.patch.object(requests, "get", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "post", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "Session", side_effect=AssertionError("network!")):
            client = vr._dataforseo_standard_client()
            client._tr = StubTransport()
            client.submit("B0AAAAAAABA", "product", "standard_queue",
                          keyword="kirkland k-cups")
            client.retrieve("task-1", validation_type="product")
        self.assertEqual(len(calls), 2)
        method, url, payload = calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(
            url,
            "https://api.dataforseo.com/v3/merchant/amazon/products/task_post")
        self.assertEqual(payload, [{
            "keyword": "kirkland k-cups",
            "language_code": "en_US",
            "location_code": 2840,
        }])
        method, url = calls[1]
        self.assertEqual(method, "GET")
        # Production task_get URL includes the /advanced/ segment
        # (see proof_batch_contracts.merchant_task_get_url).
        self.assertEqual(
            url,
            "https://api.dataforseo.com/v3/merchant/amazon/products/task_get/advanced/task-1")
        self.assertEqual(url.count("task-1"), 1)
        self.assertNotIn("/live/", url)

    def test_standard_client_rejects_unknown_validation_type(self):
        client = vr._dataforseo_standard_client()
        with mock.patch.object(client, "_tr", StubTransportSimple()):
            with self.assertRaises(vr.GuardError):
                client.submit("B0AAAAAAABA", "seller_offer", "standard_queue",
                              keyword="x")
        client2 = vr._dataforseo_standard_client()
        with mock.patch.object(client2, "_tr", StubTransportSimple()):
            with self.assertRaises(vr.GuardError):
                client2.retrieve("task-1", validation_type="seller_offer")


class StubTransportSimple:
    def submit(self, url, payload):
        return {"tasks": []}

    def retrieve(self, url):
        return {"tasks": []}

    # --- Phase 1: no secrets in reports/logs ------------------------------
    def test_no_secrets_in_reports(self):
        os.environ["DATAFORSEO_LOGIN"] = "secretlogin@example.com"
        os.environ["DATAFORSEO_PASSWORD"] = "supersecretpassword123"
        try:
            vr.create_validation_manifest(run_id=TEST_RUN_ID)
            manifest = vr.load_manifest(TEST_RUN_ID)
            vr.plan_run(TEST_RUN_ID, manifest)
            vr.main(["report-plan", "--run", TEST_RUN_ID])
            run_dir = vr.run_dir(TEST_RUN_ID)
            blobs = []
            for root, _dirs, files in os.walk(run_dir):
                for fn in files:
                    with open(os.path.join(root, fn), encoding="utf-8") as fh:
                        blobs.append(fh.read())
            combined = "\n".join(blobs)
            self.assertNotIn("secretlogin@example.com", combined)
            self.assertNotIn("supersecretpassword123", combined)
        finally:
            os.environ.pop("DATAFORSEO_LOGIN", None)
            os.environ.pop("DATAFORSEO_PASSWORD", None)


# --- DataForSEO task-post acceptance predicate -------------------------
    def _REJECTED_ENVELOPE_40402(self):
        # The exact task-level rejection observed on
        # data-validation-20asin-live-001 (HTTP 200 wrapper, task 40402).
        return {
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

    def test_evaluate_task_post_40402_envelope_rejected(self):
        v = vr.evaluate_dataforseo_task_post(self._REJECTED_ENVELOPE_40402())
        self.assertFalse(v["accepted"])
        self.assertEqual(v["classification"], "provider_rejected_invalid_path")
        self.assertIsNone(v["task_id"])
        self.assertEqual(v["provider_cost_cents"], 0)
        self.assertIn("Invalid Path", v["reason"])
        self.assertTrue(vr.is_dataforseo_rejection_state(v["classification"]))

    def test_evaluate_task_post_20000_zero_cost_rejected(self):
        v = vr.evaluate_dataforseo_task_post({
            "status_code": 20000, "tasks_error": 0,
            "tasks": [{"id": "t-0", "status_code": 20000,
                       "status_message": "Ok.", "cost": 0,
                       "path": ["v3", "merchant", "amazon", "products", "task_post"]}],
        }, endpoint_family="products")
        self.assertFalse(v["accepted"])
        self.assertEqual(v["classification"], "provider_rejected_unknown")
        self.assertIsNone(v["task_id"])
        self.assertEqual(v["provider_cost_cents"], 0)

    def test_evaluate_task_post_valid_positive_cost_accepted(self):
        v = vr.evaluate_dataforseo_task_post({
            "status_code": 20000, "tasks_error": 0,
            "tasks": [{"id": "task-1", "status_code": 20100,
                       "status_message": "Task Created.", "cost": 0.05,
                       "path": ["v3", "merchant", "amazon", "products", "task_post"]}],
        }, endpoint_family="products")
        self.assertTrue(v["accepted"])
        self.assertEqual(v["classification"], vr.DATAFORSEO_ACCEPTED_STATE)
        self.assertEqual(v["task_id"], "task-1")
        self.assertEqual(v["provider_cost_cents"], 5)

    def test_evaluate_task_post_taxonomy(self):
        base_path = ["v3", "merchant", "amazon", "products", "task_post"]
        cases = [
            ({"status_code": 20000, "tasks_error": 0, "tasks": [{
                "id": "x", "status_code": 401, "status_message": "unauthorized",
                "cost": 1, "path": base_path}]},
             "provider_rejected_auth"),
            ({"status_code": 20000, "tasks_error": 0, "tasks": [{
                "id": "x", "status_code": 402,
                "status_message": "insufficient credits", "cost": 0,
                "path": base_path}]},
             "provider_rejected_budget"),
            ({"status_code": 20000, "tasks_error": 0, "tasks": [{
                "id": "x", "status_code": 40400,
                "status_message": "invalid parameter", "cost": 0,
                "path": base_path}]},
             "provider_rejected_validation"),
            ({"status_code": 20000, "tasks_error": 0, "tasks": [{
                "id": "x", "status_code": 59999, "status_message": "weird",
                "cost": 1, "path": base_path}]},
             "provider_rejected_unknown"),
        ]
        for payload, expected in cases:
            v = vr.evaluate_dataforseo_task_post(payload, endpoint_family="products")
            self.assertFalse(v["accepted"])
            self.assertEqual(v["classification"], expected)

    def test_rejected_states_release_reserved_cents(self):
        ledger = vr.Ledger(TEST_RUN_ID)
        ledger.add({
            "idempotency_key": "k-a", "run_id": TEST_RUN_ID,
            "provider": vr.PROVIDER_DATAFORSEO, "asin": "B0AAAAAAAAAA",
            "validation_type": "product", "mode": vr.STANDARD_QUEUE,
            "state": "provider_rejected_invalid_path",
            "reserved_cost_cents": 5, "actual_cost_cents": 0,
        })
        ledger.add({
            "idempotency_key": "k-b", "run_id": TEST_RUN_ID,
            "provider": vr.PROVIDER_DATAFORSEO, "asin": "B0BBBBBBBBBB",
            "validation_type": "product", "mode": vr.STANDARD_QUEUE,
            "state": "submitted", "reserved_cost_cents": 5,
        })
        self.assertEqual(ledger.total_reserved(), 5)

    def test_execute_dataforseo_40402_envelope_rejected_end_to_end(self):
        import requests
        from contextlib import redirect_stdout
        from io import StringIO
        envelope = self._REJECTED_ENVELOPE_40402()

        class Fake40402Client:
            def submit(self, asin, validation_type, mode, keyword=None):
                if validation_type != "product":
                    raise GuardError(
                        "validation_type not supported by the DataForSEO transport")
                return copy.deepcopy(envelope)
            def retrieve(self, remote_task_id, validation_type="product"):
                raise AssertionError("no retrieval in a submission test")

        vr.create_validation_manifest(run_id=TEST_RUN_ID)
        manifest = vr.load_manifest(TEST_RUN_ID)
        vr.create_authorization(TEST_RUN_ID, manifest, TEST_RUN_ID)
        vr.plan_run(TEST_RUN_ID, manifest)
        ledger = vr.Ledger(TEST_RUN_ID)
        self.assertTrue(ledger.records(state="planned"))
        env = {
            "SCANNER_LIVE_ALLOWED": "1",
            "DATAFORSEO_TRANSPORT_ENABLED": "true",
            "DATAFORSEO_LOGIN": "login@example.com",
            "DATAFORSEO_PASSWORD": "pw",
        }
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(vr, "_dataforseo_standard_client",
                               return_value=Fake40402Client()), \
             mock.patch.object(requests, "get", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "post", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "Session", side_effect=AssertionError("network!")):
            buf = StringIO()
            with redirect_stdout(buf):
                code = vr.main(["execute-dataforseo", "--run", TEST_RUN_ID,
                                "--confirm", TEST_RUN_ID])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("provider rejected", out)
        # No submission: no submitted state, no stored task id, no retrieval.
        self.assertFalse(ledger.records(state="submitted"))
        rejected = ledger.records(state="provider_rejected_invalid_path")
        self.assertEqual(len(rejected), 10)
        for rec in rejected:
            self.assertIsNone(rec["remote_task_id"])
            self.assertEqual(rec["actual_cost_cents"], 0)
            self.assertIn("Invalid Path", rec["error_classification"] or "")
            # envelope persisted
            env_path = os.path.join(
                vr.run_dir(TEST_RUN_ID), "raw", "dataforseo",
                f"{rec['asin']}.json")
            self.assertTrue(os.path.isfile(env_path), env_path)
            stored = vr.read_json(env_path)
            self.assertEqual(stored["payload"]["tasks"][0]["status_code"], 40402)
        # Reservation released: only the 10 seller_offer planned rows remain.
        self.assertEqual(ledger.total_reserved(), 10 * 5)

    def test_repair_dataforseo_command_offline(self):
        import requests
        from contextlib import redirect_stdout
        from io import StringIO

        os.environ["VALIDATION_RUNS_ROOT"] = self.tmp
        run_id = "data-validation-20asin-repair"
        ledger = vr.Ledger(run_id)
        asin = "B0CP6LXPLK"
        vr.store_raw(run_id, vr.PROVIDER_DATAFORSEO, asin,
                     self._REJECTED_ENVELOPE_40402())
        ledger.add({
            "idempotency_key": "r-1", "run_id": run_id,
            "provider": vr.PROVIDER_DATAFORSEO, "asin": asin,
            "validation_type": "product", "mode": vr.STANDARD_QUEUE,
            "state": "submitted", "reserved_cost_cents": 5,
            "actual_cost_cents": 5, "remote_task_id": "08200307-2329-0455-0000-fc0cd5bb47ee",
        })
        ledger.add({
            "idempotency_key": "r-2", "run_id": run_id,
            "provider": vr.PROVIDER_DATAFORSEO, "asin": "B00BISGJXA",
            "validation_type": "seller_offer", "mode": vr.STANDARD_QUEUE,
            "state": "planned", "reserved_cost_cents": 5,
        })
        self.assertEqual(ledger.total_reserved(), 10)
        with mock.patch.object(requests, "get", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "post", side_effect=AssertionError("network!")), \
             mock.patch.object(requests, "Session", side_effect=AssertionError("network!")):
            buf = StringIO()
            with redirect_stdout(buf):
                code = vr.main(["repair-dataforseo", "--run", run_id])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("repair complete", out)
        rows = ledger.records(asin=asin)
        self.assertEqual(len(rows), 1)
        rec = rows[0]
        self.assertEqual(rec["state"], "provider_rejected_invalid_path")
        self.assertIsNone(rec["remote_task_id"])
        self.assertEqual(rec["actual_cost_cents"], 0)
        self.assertIsNotNone(rec["raw_response_reference"])
        # Reservation released; planned seller_offer row unaffected.
        self.assertEqual(ledger.total_reserved(), 5)
        # Unrelated rows untouched.
        self.assertEqual(
            ledger.records(asin="B00BISGJXA")[0]["state"], "planned")
        # Manifest written and parseable.
        import glob
        manifests = glob.glob(os.path.join(vr.run_dir(run_id), "reports",
                                           "repair-manifest-*.json"))
        self.assertEqual(len(manifests), 1)
        manifest = vr.read_json(manifests[0])
        self.assertEqual(manifest["rows_repaired"], 1)
        self.assertEqual(manifest["rows_unchanged"], 0)
        self.assertEqual(manifest["provider_calls_made"], 0)
        self.assertEqual(manifest["before"]["submitted"], 1)
        self.assertEqual(manifest["after"]["provider_rejected_invalid_path"], 1)
        self.assertEqual(manifest["actual_cost_cents_before"], 5)
        self.assertEqual(manifest["actual_cost_cents_after"], 0)
        self.assertEqual(manifest["reserved_cents_before"], 10)
        self.assertEqual(manifest["reserved_cents_after"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
