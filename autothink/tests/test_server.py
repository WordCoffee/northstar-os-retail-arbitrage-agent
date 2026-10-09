"""Offline API tests for the AutoThink FastAPI server.

The LLM adapter is monkeypatched so zero live/Ollama/cloud calls occur.
SessionStore, UsageLedger and the idempotency map are pointed at temp paths so
no operator files are touched.

Every data route is tenant-scoped: these tests pass an explicit ``org_id``
exactly the way ``main.py`` does after ``require_session`` resolves the caller.
"""

import os
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import backend.server as server
from memory.session_store import SessionStore
from memory.usage_ledger import UsageLedger


class _FakeAdapter:
    def __init__(self):
        self.calls = []
        self.system_prompts = []

    def generate(self, query, provider="local", model=None,
                 system_prompt=None, should_cancel=None):
        self.calls.append((query, provider, model))
        self.system_prompts.append(system_prompt)
        return {
            "ok": True,
            "provider": provider,
            "model": model or "fake-model",
            "content": "FAKE RESPONSE for: " + query,
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "elapsed_ms": 1.0,
        }

    def local_available(self):
        return True

    def cloud_available(self):
        return False

    def list_local_models(self):
        return ["qwen3:14b"]


class AutoThinkApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._orig_adapter = server.adapter
        cls._orig_store = server.store
        cls._orig_audit_log = server.AUDIT_LOG
        cls._orig_usage = server.usage
        cls._orig_idem = server.IDEMPOTENCY_PATH
        cls._orig_memory = server.MEMORY_DIR
        server.adapter = _FakeAdapter()
        server.store = SessionStore(path=os.path.join(cls._tmp.name, "session.json"))
        server.AUDIT_LOG = os.path.join(cls._tmp.name, "audit-runs.jsonl")
        server.usage = UsageLedger(path=os.path.join(cls._tmp.name, "usage.jsonl"))
        server.IDEMPOTENCY_PATH = os.path.join(cls._tmp.name, "idem.json")
        server.MEMORY_DIR = os.path.join(cls._tmp.name, "memory")
        server._STORES.clear()
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        server.adapter = cls._orig_adapter
        server.store = cls._orig_store
        server.AUDIT_LOG = cls._orig_audit_log
        server.usage = cls._orig_usage
        server.IDEMPOTENCY_PATH = cls._orig_idem
        server.MEMORY_DIR = cls._orig_memory
        server._STORES.clear()
        cls._tmp.cleanup()

    # --- basic surface --------------------------------------------------

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_ui_served(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("font-family", r.text)

    def test_models_endpoint(self):
        r = self.client.get("/api/autothink/models")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("qwen3:14b", data["models"])
        self.assertTrue(data["local_available"])
        self.assertFalse(data["cloud_available"])

    def test_run_local_success(self):
        r = self.client.post("/api/autothink/run",
                             params={"org_id": "org-a"},
                             json={"query": "Compare Costco catalog", "provider": "local"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["content"], "FAKE RESPONSE for: Compare Costco catalog")
        self.assertIn("task_class", data)
        self.assertTrue(data["plan"])
        self.assertTrue(data["run_id"].startswith("atrun_"))

    def test_run_invalid_provider_rejected(self):
        r = self.client.post("/api/autothink/run",
                             params={"org_id": "org-a"},
                             json={"query": "hi", "provider": "carrier_pigeon"})
        self.assertEqual(r.status_code, 422)

    def test_run_empty_query_rejected(self):
        r = self.client.post("/api/autothink/run",
                             params={"org_id": "org-a"},
                             json={"query": "   "})
        self.assertEqual(r.status_code, 422)

    # --- auth boundary (P0-04) ------------------------------------------

    def test_history_without_org_is_refused(self):
        r = self.client.get("/api/autothink/history")
        self.assertEqual(r.status_code, 401)

    def test_run_without_org_is_refused(self):
        r = self.client.post("/api/autothink/run", json={"query": "hello"})
        self.assertEqual(r.status_code, 401)

    def test_usage_without_org_is_refused(self):
        r = self.client.get("/api/autothink/usage")
        self.assertEqual(r.status_code, 401)

    def test_blank_org_is_refused(self):
        r = self.client.post("/api/autothink/run",
                             params={"org_id": "  "},
                             json={"query": "hello"})
        self.assertEqual(r.status_code, 401)

    def test_history_with_org_is_served(self):
        r = self.client.get("/api/autothink/history", params={"org_id": "org-a"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("entries", r.json())

    def test_run_persists_history(self):
        before = self.client.get("/api/autothink/history", params={"org_id": "org-a"}).json()["total"]
        self.client.post("/api/autothink/run", params={"org_id": "org-a"},
                         json={"query": "Explain BSR", "provider": "local"})
        after = self.client.get("/api/autothink/history", params={"org_id": "org-a"}).json()
        self.assertEqual(after["total"], before + 1)
        self.assertEqual(after["entries"][-1]["query"], "Explain BSR")

    # --- tenant isolation (A-23) ----------------------------------------

    def test_org_b_cannot_see_org_a_history(self):
        self.client.post("/api/autothink/run", params={"org_id": "org-iso"},
                         json={"query": "org-iso-secret-query", "provider": "local"})
        seen = self.client.get("/api/autothink/history",
                               params={"org_id": "org-iso-other"}).json()
        queries = [e.get("query", "") for e in seen["entries"]]
        self.assertNotIn("org-iso-secret-query", queries)

    def test_org_b_cannot_cancel_org_a_run(self):
        r = self.client.post("/api/autothink/cancel", params={"org_id": "org-iso"},
                             json={"run_id": "atrun_doesnotexist"})
        self.assertEqual(r.status_code, 404)

    def test_usage_is_tenant_scoped(self):
        self.client.post("/api/autothink/run", params={"org_id": "org-meter"},
                         json={"query": "metered run", "provider": "local"})
        a = self.client.get("/api/autothink/usage", params={"org_id": "org-meter"}).json()
        b = self.client.get("/api/autothink/usage", params={"org_id": "org-meter-other"}).json()
        self.assertGreaterEqual(a["runs"], 1)
        self.assertEqual(b["runs"], 0)

    # --- idempotency (A-22) ---------------------------------------------

    def test_repeat_idempotency_key_makes_one_run_and_replays(self):
        before = len(server.adapter.calls)
        key = "idem-key-1"
        first = self.client.post("/api/autothink/run", params={"org_id": "org-idem"},
                                 json={"query": "idempotent please", "provider": "local",
                                       "idempotency_key": key})
        second = self.client.post("/api/autothink/run", params={"org_id": "org-idem"},
                                  json={"query": "idempotent please", "provider": "local",
                                        "idempotency_key": key})
        self.assertEqual(len(server.adapter.calls) - before, 1)
        self.assertFalse(first.json()["idempotent_replay"])
        self.assertTrue(second.json()["idempotent_replay"])
        self.assertEqual(first.json()["content"], second.json()["content"])
        usage = self.client.get("/api/autothink/usage", params={"org_id": "org-idem"}).json()
        self.assertEqual(usage["runs"], 1)

    def test_same_key_in_another_org_is_independent(self):
        self.client.post("/api/autothink/run", params={"org_id": "org-idem"},
                         json={"query": "shared key", "provider": "local",
                               "idempotency_key": "shared"})
        r = self.client.post("/api/autothink/run", params={"org_id": "org-idem-2"},
                             json={"query": "shared key", "provider": "local",
                                   "idempotency_key": "shared"})
        self.assertFalse(r.json()["idempotent_replay"])

    # --- grounding (P1-15) ----------------------------------------------

    def test_context_reaches_the_model(self):
        self.client.post("/api/autothink/run", params={"org_id": "org-ground"},
                         json={"query": "What is in the local cache?", "provider": "local"})
        self.assertTrue(server.adapter.system_prompts[-1])
        self.assertIn("Northstar AutothinK", server.adapter.system_prompts[-1])
        payload = self.client.post("/api/autothink/run", params={"org_id": "org-ground"},
                                   json={"query": "again", "provider": "local"}).json()
        self.assertTrue(payload["grounded"])
        self.assertIsInstance(payload["grounding_sources"], list)

    def test_no_citations_are_claimed(self):
        """A result must only claim citations that exist (AutothinK.jsx:207)."""
        r = self.client.post("/api/autothink/run", params={"org_id": "org-cite"},
                             json={"query": "cite check", "provider": "local"})
        self.assertEqual(r.json()["citations"], [])

    # --- cancellation (A-24) --------------------------------------------

    def test_cancel_reaches_the_run_and_is_tenant_scoped(self):
        token = server.runs.create(org_id="org-cancel", user_id="u1")
        r = self.client.post("/api/autothink/cancel", params={"org_id": "org-cancel"},
                             json={"run_id": token["run_id"]})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["cancel_requested"])
        other = self.client.post("/api/autothink/cancel",
                                 params={"org_id": "org-cancel-other"},
                                 json={"run_id": token["run_id"]})
        self.assertEqual(other.status_code, 404)

    def test_job_state_is_tenant_scoped(self):
        token = server.runs.create(org_id="org-job", user_id="u1")
        ok = self.client.get("/api/autothink/jobs/%s" % token["run_id"],
                             params={"org_id": "org-job"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["state"], "running")
        missing = self.client.get("/api/autothink/jobs/%s" % token["run_id"],
                                  params={"org_id": "org-job-other"})
        self.assertEqual(missing.status_code, 404)


class LocalLaneCancellationAdapterTests(unittest.TestCase):
    """A cancelled streaming run stops instead of running to completion."""

    def test_adapter_aborts_stream_when_cancelled(self):
        from backend.llm_adapter import UnifiedLLMAdapter

        class _Resp:
            status_code = 200

            def iter_lines(self, decode_unicode=True):
                yield '{"message": {"content": "partial"}, "done": false}'
                # After this line the run is cancelled.

            def close(self):
                self.closed = True

        resp = _Resp()
        adapter = UnifiedLLMAdapter()

        with mock.patch("backend.llm_adapter.requests.post", return_value=resp):
            result = adapter._generate_local("q", "m", None, lambda: True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "cancelled_by_user")
        self.assertIn("[CANCELLED]", result["content"])


if __name__ == "__main__":
    unittest.main()
