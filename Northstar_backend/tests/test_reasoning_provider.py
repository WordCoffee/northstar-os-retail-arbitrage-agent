"""Mocked tests for the hosted-reasoning adapter.

No live provider calls are made. All credential values are synthetic and never
read beyond presence checks.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from adapters.base import ProviderStatus
from adapters.reasoning_provider import (
    DEFAULT_MODEL_ID,
    HOSTED_MODEL_IDS,
    HOSTED_MODELS,
    MockReasoningProvider,
    OpenCodeGoProvider,
    ReasoningRequest,
    ReasoningUsage,
    get_reasoning_provider,
)


class CatalogTests(unittest.TestCase):
    def test_expected_model_ids_present(self):
        expected = {
            "opencode-go/deepseek-v4.1-flash",
            "opencode-go/glm-5.3-flash",
            "opencode-go/mimo-v2.6-flash",
        }
        self.assertTrue(expected.issubset(HOSTED_MODEL_IDS))

    def test_default_is_deepseek_v41_flash(self):
        self.assertEqual(DEFAULT_MODEL_ID, "opencode-go/deepseek-v4.1-flash")

    def test_pricing_metadata_includes_source_and_timestamp(self):
        for m in HOSTED_MODELS:
            self.assertIn("pricing_source", m)
            self.assertIn("pricing_observed_at", m)
            self.assertGreater(m["cost_per_1m_input"], 0)
            self.assertGreater(m["cost_per_1m_output"], 0)

    def test_resolve_model_defaults(self):
        p = OpenCodeGoProvider()
        self.assertEqual(p.resolve_model(None), DEFAULT_MODEL_ID)

    def test_resolve_model_accepts_full_id(self):
        p = OpenCodeGoProvider()
        self.assertEqual(
            p.resolve_model("opencode-go/glm-5.3-flash"),
            "opencode-go/glm-5.3-flash",
        )

    def test_resolve_model_accepts_short_id(self):
        p = OpenCodeGoProvider()
        self.assertEqual(p.resolve_model("mimo-v2.6-flash"), "opencode-go/mimo-v2.6-flash")

    def test_resolve_model_rejects_unknown(self):
        p = OpenCodeGoProvider()
        with self.assertRaises(ValueError):
            p.resolve_model("openai/gpt-5")


class AvailabilityTests(unittest.TestCase):
    def test_not_available_without_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for k in list(os.environ.keys()):
                if k.startswith("OPENCODE_GO"):
                    del os.environ[k]
            p = OpenCodeGoProvider()
            self.assertFalse(p.available())
            self.assertFalse(p.armed())

    def test_available_requires_enabled_flag(self):
        with mock.patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "set"}, clear=False):
            os.environ.pop("OPENCODE_GO_ENABLED", None)
            p = OpenCodeGoProvider()
            # Key present but not enabled -> available() requires explicit enable
            self.assertFalse(p.available())
            self.assertFalse(p.armed())

    def test_armed_only_with_enabled_one(self):
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "set", "OPENCODE_GO_ENABLED": "1"},
            clear=False,
        ):
            p = OpenCodeGoProvider()
            self.assertTrue(p.available())
            self.assertTrue(p.armed())


class CompleteTests(unittest.TestCase):
    def test_complete_blocked_when_not_configured(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for k in list(os.environ.keys()):
                if k.startswith("OPENCODE_GO"):
                    del os.environ[k]
            p = OpenCodeGoProvider()
            req = ReasoningRequest(messages=[{"role": "user", "content": "hi"}])
            resp = p.complete(req)
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.AUTH_ERROR)
            self.assertIn("not configured", resp.error.lower())

    def test_complete_blocked_when_not_armed(self):
        with mock.patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "set"}, clear=False):
            os.environ.pop("OPENCODE_GO_ENABLED", None)
            p = OpenCodeGoProvider()
            req = ReasoningRequest(messages=[{"role": "user", "content": "hi"}])
            resp = p.complete(req)
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.BLOCKED)

    @mock.patch("adapters.reasoning_provider.BaseAdapter._timed_request")
    def test_complete_success_parses_response(self, mock_timed):
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "set", "OPENCODE_GO_ENABLED": "1"},
            clear=False,
        ):
            from adapters.base import ProviderResponse as BaseProviderResponse

            mock_timed.return_value = BaseProviderResponse(
                success=True,
                status=ProviderStatus.OK,
                provider="opencode_go",
                data={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "opencode-go/deepseek-v4.1-flash",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
                latency_ms=123.0,
                http_status=200,
            )
            p = OpenCodeGoProvider()
            req = ReasoningRequest(messages=[{"role": "user", "content": "hi"}])
            resp = p.complete(req)
            self.assertTrue(resp.success)
            self.assertEqual(resp.data["content"], "hello")
            self.assertEqual(resp.data["model"], "opencode-go/deepseek-v4.1-flash")
            self.assertEqual(resp.data["usage"]["prompt_tokens"], 10)
            self.assertEqual(resp.data["usage"]["completion_tokens"], 5)
            self.assertAlmostEqual(
                resp.data["estimated_cost_usd"],
                10 * 0.15 / 1_000_000 + 5 * 0.60 / 1_000_000,
                delta=1e-6,
            )
            self.assertEqual(resp.latency_ms, 123.0)

            call_kwargs = mock_timed.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["model"], DEFAULT_MODEL_ID)
            self.assertEqual(
                call_kwargs["headers"]["User-Agent"],
                "NorthstarOS/2.0.0 private-testing (non-creative-reasoning)",
            )
            self.assertIn("x-opencode-session", call_kwargs["headers"])
            # Session id should be a valid UUID.
            self.assertEqual(len(call_kwargs["headers"]["x-opencode-session"].split("-")), 5)
            # When a conversation id is supplied, the session id must be deterministic.
            self.assertEqual(
                p.make_session_id("conversation-abc"),
                p.make_session_id("conversation-abc"),
            )

    @mock.patch("adapters.reasoning_provider.BaseAdapter._timed_request")
    def test_complete_malformed_response_is_error(self, mock_timed):
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "set", "OPENCODE_GO_ENABLED": "1"},
            clear=False,
        ):
            from adapters.base import ProviderResponse as BaseProviderResponse

            mock_timed.return_value = BaseProviderResponse(
                success=True,
                status=ProviderStatus.OK,
                provider="opencode_go",
                data={"choices": []},
                latency_ms=10.0,
                http_status=200,
            )
            p = OpenCodeGoProvider()
            resp = p.complete(ReasoningRequest(messages=[{"role": "user", "content": "hi"}]))
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.ERROR)
            self.assertIn("Malformed", resp.error)

    @mock.patch("adapters.reasoning_provider.BaseAdapter._timed_request")
    def test_complete_rate_limited(self, mock_timed):
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "set", "OPENCODE_GO_ENABLED": "1"},
            clear=False,
        ):
            from adapters.base import ProviderResponse as BaseProviderResponse

            mock_timed.return_value = BaseProviderResponse(
                success=False,
                status=ProviderStatus.RATE_LIMITED,
                provider="opencode_go",
                error="Rate limited after retries",
                http_status=429,
            )
            p = OpenCodeGoProvider()
            resp = p.complete(ReasoningRequest(messages=[{"role": "user", "content": "hi"}]))
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.RATE_LIMITED)


class UsageTests(unittest.TestCase):
    def test_estimated_cost_usd(self):
        u = ReasoningUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        # DeepSeek V4.1 Flash: $0.15 in, $0.60 out
        self.assertAlmostEqual(
            u.estimated_cost_usd("opencode-go/deepseek-v4.1-flash"),
            0.75,
            places=4,
        )


class StreamTests(unittest.TestCase):
    @mock.patch("adapters.reasoning_provider.OpenCodeGoProvider._get_client")
    def test_stream_yields_partial_and_final(self, mock_get_client):
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "set", "OPENCODE_GO_ENABLED": "1"},
            clear=False,
        ):
            class FakeStream:
                status_code = 200
                def iter_lines(self):
                    yield 'data: {"choices":[{"delta":{"content":"Hello "}}]}'
                    yield 'data: {"choices":[{"delta":{"content":"world"}}]}'
                    yield 'data: [DONE]'
                def __enter__(self): return self
                def __exit__(self, *a): pass

            class FakeClient:
                def stream(self, *a, **k):
                    return FakeStream()
                def is_closed(self): return False
                def close(self): pass

            mock_get_client.return_value = FakeClient()
            p = OpenCodeGoProvider()
            chunks = list(p.complete_stream(ReasoningRequest(messages=[{"role": "user", "content": "hi"}])))
            self.assertEqual(len(chunks), 3)
            self.assertTrue(all(c.success for c in chunks))
            self.assertEqual(chunks[0].data["content"], "Hello ")
            self.assertTrue(chunks[0].data["partial"])
            self.assertEqual(chunks[1].data["content"], "world")
            self.assertEqual(chunks[2].data["content"], "Hello world")
            self.assertFalse(chunks[2].data["partial"])


class MockProviderTests(unittest.TestCase):
    def test_mock_records_calls_and_returns_content(self):
        p = MockReasoningProvider(response_text="mocked listing proposal")
        req = ReasoningRequest(messages=[{"role": "user", "content": "x"}], task_type="listing")
        resp = p.complete(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.data["content"], "mocked listing proposal")
        self.assertEqual(len(p.calls), 1)
        self.assertEqual(p.calls[0].task_type, "listing")


class FactoryTests(unittest.TestCase):
    def test_factory_returns_opencode_go_by_default(self):
        p = get_reasoning_provider()
        self.assertIsInstance(p, OpenCodeGoProvider)

    def test_factory_returns_mock_when_env_set(self):
        with mock.patch.dict(os.environ, {"REASONING_PROVIDER": "mock"}, clear=False):
            p = get_reasoning_provider()
            self.assertIsInstance(p, MockReasoningProvider)


if __name__ == "__main__":
    unittest.main()
