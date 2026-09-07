"""Offline API tests for the AutoThink FastAPI server.

The LLM adapter is monkeypatched so zero live/Ollama/cloud calls occur.
SessionStore is pointed at a temp path so no operator files are touched.
"""

import os
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import backend.server as server
from memory.session_store import SessionStore


class _FakeAdapter:
    def __init__(self):
        self.calls = []

    def generate(self, query, provider="local", model=None):
        self.calls.append((query, provider, model))
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
        return ["qwen2.5-coder:14b"]


class AutoThinkApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._orig_adapter = server.adapter
        cls._orig_store = server.store
        cls._orig_audit_log = server.AUDIT_LOG
        server.adapter = _FakeAdapter()
        server.store = SessionStore(path=os.path.join(cls._tmp.name, "session.json"))
        server.AUDIT_LOG = os.path.join(cls._tmp.name, "audit-runs.jsonl")
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        server.adapter = cls._orig_adapter
        server.store = cls._orig_store
        server.AUDIT_LOG = cls._orig_audit_log
        cls._tmp.cleanup()

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
        self.assertIn("qwen2.5-coder:14b", data["models"])
        self.assertTrue(data["local_available"])
        self.assertFalse(data["cloud_available"])

    def test_run_local_success(self):
        r = self.client.post("/api/autothink/run", json={"query": "Compare Costco catalog", "provider": "local"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["content"], "FAKE RESPONSE for: Compare Costco catalog")
        self.assertIn("task_class", data)
        self.assertTrue(data["plan"])

    def test_run_invalid_provider_rejected(self):
        r = self.client.post("/api/autothink/run", json={"query": "hi", "provider": "carrier_pigeon"})
        self.assertEqual(r.status_code, 422)

    def test_run_empty_query_rejected(self):
        r = self.client.post("/api/autothink/run", json={"query": "   "})
        self.assertEqual(r.status_code, 422)

    def test_run_persists_history(self):
        before = self.client.get("/api/autothink/history").json()["total"]
        self.client.post("/api/autothink/run", json={"query": "Explain BSR", "provider": "local"})
        after = self.client.get("/api/autothink/history").json()
        self.assertEqual(after["total"], before + 1)
        self.assertEqual(after["entries"][-1]["query"], "Explain BSR")


if __name__ == "__main__":
    unittest.main()