"""Route-level tests for the hosted reasoning API.

All provider calls are mocked; no live OpenCode Go traffic is generated.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient


class ReasoningRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import main lazily so environment can be patched first.
        os.environ.setdefault("OPENCODE_GO_ENABLED", "1")
        os.environ.setdefault("OPENCODE_GO_API_KEY", "test-key")
        import main
        cls.app = main.app
        cls.client = TestClient(cls.app)
        cls._import_reasoning_tasks = __import__("reasoning_tasks")

    def _patch_provider(self, response_text):
        from adapters.reasoning_provider import MockReasoningProvider
        patcher = mock.patch.object(self._import_reasoning_tasks, "get_reasoning_provider", return_value=MockReasoningProvider(response_text=response_text))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reasoning_models_returns_catalog(self):
        r = self.client.get("/api/v1/reasoning/models")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("models", data)
        self.assertIn("default_model", data)
        self.assertEqual(data["default_model"], "step-5-preview-free")
        self.assertEqual(data["verified_model"], "step-5-preview-free")
        self.assertEqual(data["runtime_default_model"], "step-5-preview-free")
        self.assertTrue(data["verified_usability"])
        self.assertEqual(data["provider"], "opencode-go")
        self.assertEqual(data["chat_endpoint"], "https://opencode.ai/zen/go/v1/chat/completions")
        self.assertEqual(data["base_url"], "https://opencode.ai/zen/go/v1")
        self.assertTrue(data["configured"])
        self.assertTrue(data["enabled"])
        self.assertTrue(data["armed"])
        self.assertIn("One model has a verified completion", data["note"])
        self.assertFalse(data["hosted_reasoning_is_creative_renderer"])
        self.assertTrue(all(not m.get("is_runtime_default") for m in data["escalation_models"]))

    def test_reasoning_models_report_per_model_state(self):
        r = self.client.get("/api/v1/reasoning/models")
        self.assertEqual(r.status_code, 200)
        models = r.json()["models"]
        self.assertTrue(len(models) >= 4)
        for m in models:
            for field in ("provider", "base_url", "endpoint", "configured",
                          "enabled", "verified_usability", "intended_role",
                          "allowed_for_creative"):
                self.assertIn(field, m)
            self.assertEqual(m["provider"], "opencode-go")
            self.assertEqual(m["base_url"], "https://opencode.ai/zen/go/v1")
            self.assertEqual(m["endpoint"], "https://opencode.ai/zen/go/v1/chat/completions")
            self.assertFalse(m["allowed_for_creative"])

        by_id = {m["id"]: m for m in models}
        # Intended roles per the hardening policy.
        self.assertEqual(by_id["step-5-preview-free"]["intended_role"], "default")
        self.assertEqual(by_id["deepseek-v4.1-flash"]["intended_role"], "fallback")
        self.assertEqual(by_id["kimi-k2.7-code"]["intended_role"], "escalation")
        self.assertEqual(by_id["glm-5.3-flash"]["intended_role"], "experimental")

        # Configured vs verified vs active default are three distinct states.
        for m in models:
            self.assertTrue(m["configured"])
        self.assertTrue(by_id["step-5-preview-free"]["verified_usability"])
        self.assertFalse(by_id["deepseek-v4.1-flash"]["verified_usability"])
        self.assertTrue(by_id["step-5-preview-free"]["is_runtime_default"])
        self.assertFalse(by_id["deepseek-v4.1-flash"]["is_runtime_default"])
        self.assertTrue(by_id["step-5-preview-free"]["usable"])
        self.assertFalse(by_id["deepseek-v4.1-flash"]["usable"])

    def test_listing_proposal_endpoint(self):
        self._patch_provider(json.dumps({
            "sku": "SKU-123",
            "proposed": {
                "title": "Better title",
                "bullets": ["b1", "b2", "b3", "b4", "b5"],
                "description": "Better desc",
                "attributes": {},
            },
            "reasons": ["improved clarity"],
            "missing_evidence": [],
            "warnings": [],
        }))
        r = self.client.post("/api/v1/reasoning/listing-proposal", json={
            "sku": "SKU-123",
            "title": "Old title",
            "bullets": ["b1", "b2", "b3", "b4", "b5"],
            "description": "Old desc",
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["proposal"]["ok"])
        self.assertEqual(data["proposal"]["proposed"]["title"], "Better title")

    def test_ad_copy_proposal_endpoint(self):
        self._patch_provider(json.dumps({
            "headlines": ["H1"],
            "body": "Body",
            "cta": "Shop",
            "brand_tone": "professional",
            "unsupported_claims": [],
            "warnings": [],
        }))
        r = self.client.post("/api/v1/reasoning/ad-copy-proposal", json={
            "product_facts": {"name": "Widget"},
            "brand_tone": "professional",
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["proposal"]["ok"])
        self.assertEqual(data["proposal"]["cta"], "Shop")

    def test_spreadsheet_analysis_endpoint(self):
        self._patch_provider(json.dumps({
            "row_count": 1,
            "columns": ["sku"],
            "summary": "One row",
            "anomalies": [],
            "inferred_formulas": [],
            "suggested_exports": [],
            "warnings": [],
        }))
        r = self.client.post("/api/v1/reasoning/spreadsheet-analysis", json={
            "rows": [{"sku": "A"}],
            "columns": ["sku"],
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["analysis"]["ok"])
        self.assertEqual(data["analysis"]["row_count"], 1)

    def test_reasoning_run_endpoint(self):
        self._patch_provider("hello")
        r = self.client.post("/api/v1/reasoning/run", json={"query": "say hi"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["content"], "hello")

    def test_reasoning_run_rejects_empty_query(self):
        r = self.client.post("/api/v1/reasoning/run", json={"query": "   "})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
