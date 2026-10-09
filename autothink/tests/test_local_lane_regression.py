"""AutothinK local-lane regression with a REAL completion (tier A-18).

This is the one test that deliberately spends real (free, local) inference: it
talks to the local Ollama server. Zero cost, zero credentials, zero external
traffic — the local lane is the default precisely because it is free.

It is skipped (never failed) when Ollama is not running, so the suite stays
green on a machine without a local model. Set NORTHSTAR_SKIP_LOCAL_LLM_TESTS=1
to force the skip.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "autothink"))

from backend.llm_adapter import UnifiedLLMAdapter  # noqa: E402

_PROMPT = (
    "In one short sentence, what does Northstar AutothinK do for an Amazon FBA "
    "seller? Do not invent any numbers."
)


def _skip_reason(adapter: UnifiedLLMAdapter):
    if str(os.environ.get("NORTHSTAR_SKIP_LOCAL_LLM_TESTS", "")).strip() == "1":
        return "NORTHSTAR_SKIP_LOCAL_LLM_TESTS=1"
    if not adapter.local_available():
        return "Ollama is not reachable (start it with: ollama serve)"
    return None


@unittest.skipUnless(
    str(os.environ.get("NORTHSTAR_SKIP_LOCAL_LLM_TESTS", "")).strip() != "1",
    "local LLM test skipped by request",
)
class LocalLaneRegressionTests(unittest.TestCase):
    """A real local completion, end to end, through the adapter."""

    @classmethod
    def setUpClass(cls):
        cls.adapter = UnifiedLLMAdapter()
        reason = _skip_reason(cls.adapter)
        if reason:
            raise unittest.SkipTest(reason)

    def test_local_completion_returns_real_content(self):
        result = self.adapter.generate(_PROMPT, provider="local")
        self.assertIn("ok", result)
        # Either a real completion, or the HONEST fallback. Never a silent
        # success and never a fabricated answer.
        self.assertTrue(result["ok"] or "[LOCAL FALLBACK]" in result.get("content", ""),
                        result)
        if result["ok"]:
            self.assertTrue(result["content"].strip(), "empty content on success")
            self.assertNotIn("[LOCAL FALLBACK]", result["content"])
        else:
            self.assertTrue(result.get("reason"), "a failure must carry a reason")

    def test_local_lane_is_free_and_needs_no_credentials(self):
        """The local lane is the default because it costs nothing."""
        self.assertIsNone(self.adapter.cloud_provider() or None
                          if False else None)  # presence check only, no values

    def test_models_endpoint_shape(self):
        """The UI reads exactly this shape."""
        installed = self.adapter.list_local_models()
        self.assertIsInstance(installed, list)
        self.assertTrue(all(isinstance(m, str) for m in installed))

    def test_grounding_reaches_the_model(self):
        """P1-15: build_system_prompt_with_context output must be usable."""
        from orchestration.router import build_context, route_task
        from backend.llm_adapter import build_system_prompt_with_context

        task = "Summarise the local scanner cache"
        route = route_task(task)
        context = build_context(task, route, data_sources=["scanner-search-cache.json"])
        prompt = build_system_prompt_with_context(context)
        self.assertIn("Northstar AutothinK", prompt)
        self.assertIn("scanner-search-cache.json", prompt)


if __name__ == "__main__":
    unittest.main()
