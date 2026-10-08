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
    GO_BASE_URL,
    GO_CHAT_ENDPOINT,
    GO_PROVIDER_ID,
    HOSTED_ESCALATION_MODELS,
    HOSTED_MODEL_IDS,
    HOSTED_MODELS,
    POLICY_PREFERRED_MODEL,
    RUNTIME_DEFAULT_MODEL,
    VERIFIED_GO_MODEL,
    MockReasoningProvider,
    OpenCodeGoProvider,
    ReasoningRequest,
    ReasoningUsage,
    get_reasoning_provider,
)


class CatalogTests(unittest.TestCase):
    def test_expected_model_ids_present(self):
        expected = {
            "step-5-preview-free",
            "deepseek-v4.1-flash",
            "glm-5.3-flash",
            "mimo-v2.6-flash-free",
        }
        self.assertTrue(expected.issubset(HOSTED_MODEL_IDS))

    def test_default_is_step5_preview_free(self):
        self.assertEqual(POLICY_PREFERRED_MODEL, "step-5-preview-free")

    def test_runtime_default_requires_verification(self):
        # Guardrail: the runtime default is only ever the verified model.
        self.assertIsNotNone(VERIFIED_GO_MODEL)
        self.assertEqual(RUNTIME_DEFAULT_MODEL, VERIFIED_GO_MODEL)
        self.assertTrue(
            any(m["id"] == VERIFIED_GO_MODEL and m.get("verified_usability")
                for m in HOSTED_MODELS + HOSTED_ESCALATION_MODELS),
        )

    def test_go_endpoint_contract_is_exact(self):
        self.assertEqual(GO_BASE_URL, "https://opencode.ai/zen/go/v1")
        self.assertEqual(GO_CHAT_ENDPOINT, "https://opencode.ai/zen/go/v1/chat/completions")
        p = OpenCodeGoProvider()
        self.assertEqual(p.endpoint, "https://opencode.ai/zen/go/v1/chat/completions")

    def test_provider_identifier_is_opencode_go(self):
        self.assertEqual(GO_PROVIDER_ID, "opencode-go")
        for m in HOSTED_MODELS + HOSTED_ESCALATION_MODELS:
            self.assertEqual(m["provider"], "opencode-go")

    def test_model_ids_are_bare(self):
        for m in HOSTED_MODELS + HOSTED_ESCALATION_MODELS:
            self.assertEqual(m["id"], m["short_id"])
            self.assertNotIn("/", m["id"])

    def test_exactly_one_model_is_verified(self):
        verified = [m for m in HOSTED_MODELS + HOSTED_ESCALATION_MODELS if m.get("verified_usability")]
        self.assertEqual([m["id"] for m in verified], ["step-5-preview-free"])

    def test_verified_model_has_a_verified_at_stamp(self):
        m = next(x for x in HOSTED_MODELS if x["id"] == VERIFIED_GO_MODEL)
        self.assertTrue(m.get("verified_usability"))
        self.assertTrue(m.get("verified_at"))

    def test_runtime_default_is_the_verified_model(self):
        self.assertEqual(VERIFIED_GO_MODEL, "step-5-preview-free")
        self.assertEqual(RUNTIME_DEFAULT_MODEL, VERIFIED_GO_MODEL)
        p = OpenCodeGoProvider()
        self.assertEqual(p.verified_model(), "step-5-preview-free")
        self.assertEqual(p.resolve_model(None), "step-5-preview-free")

    def test_legacy_prefixed_id_is_stripped(self):
        p = OpenCodeGoProvider()
        self.assertEqual(p.resolve_model("opencode-go/step-5-preview-free"), "step-5-preview-free")

    def test_endpoint_override_env(self):
        with mock.patch.dict(os.environ, {"OPENCODE_GO_ENDPOINT": "https://example.invalid/go/v1/chat/completions"}, clear=False):
            self.assertEqual(OpenCodeGoProvider().endpoint, "https://example.invalid/go/v1/chat/completions")

    def test_documented_endpoint_default(self):
        p = OpenCodeGoProvider()
        self.assertEqual(p.endpoint, "https://opencode.ai/zen/go/v1/chat/completions")

    def test_not_found_is_classified_as_not_found(self):
        r = OpenCodeGoProvider._classify_provider_error(404, '{"error":"not found"}')
        self.assertIsNotNone(r)
        self.assertEqual(r.status, ProviderStatus.NOT_FOUND)

    def test_free_tier_error_is_classified_as_blocked(self):
        r = OpenCodeGoProvider._classify_provider_error(
            403, '{"error":{"type":"FreeTierError","message":"OpenCode\'s free tier can only be used from within OpenCode"}}'
        )
        self.assertIsNotNone(r)
        self.assertFalse(r.success)
        self.assertEqual(r.status, ProviderStatus.BLOCKED)
        self.assertIn("free tier", r.error.lower())

    def test_insufficient_funds_is_classified_as_credits_exhausted(self):
        r = OpenCodeGoProvider._classify_provider_error(
            402, '{"error":{"type":"server_error","message":"Upstream request failed: Insufficient account funds"}}'
        )
        self.assertIsNotNone(r)
        self.assertFalse(r.success)
        self.assertEqual(r.status, ProviderStatus.CREDITS_EXHAUSTED)

    def test_unauthorized_is_classified_as_auth_error(self):
        r = OpenCodeGoProvider._classify_provider_error(401, '{"error":"Unauthorized"}')
        self.assertIsNotNone(r)
        self.assertEqual(r.status, ProviderStatus.AUTH_ERROR)

    def test_rate_limit_is_classified(self):
        r = OpenCodeGoProvider._classify_provider_error(429, '{"error":"rate limit exceeded"}')
        self.assertIsNotNone(r)
        self.assertEqual(r.status, ProviderStatus.RATE_LIMITED)

    def test_unknown_error_returns_none(self):
        r = OpenCodeGoProvider._classify_provider_error(500, '{"error":"boom"}')
        self.assertIsNone(r)

    def test_escalation_models_present(self):
        from adapters.reasoning_provider import HOSTED_ESCALATION_MODELS
        ids = {m["id"] for m in HOSTED_ESCALATION_MODELS}
        self.assertIn("kimi-k2.7-code", ids)

    def test_pricing_metadata_includes_source_and_timestamp(self):
        for m in HOSTED_MODELS:
            self.assertIn("pricing_source", m)
            self.assertIn("pricing_observed_at", m)
            self.assertGreaterEqual(m["cost_per_1m_input"], 0)
            self.assertGreaterEqual(m["cost_per_1m_output"], 0)

    def test_step5_is_free_but_others_are_not(self):
        free = [m for m in HOSTED_MODELS if m["cost_per_1m_input"] == 0.0]
        paid = [m for m in HOSTED_MODELS if m["cost_per_1m_input"] > 0]
        self.assertEqual([m["id"] for m in free], ["step-5-preview-free", "mimo-v2.6-flash-free"])
        self.assertEqual(len(paid), 2)

    def test_resolve_model_defaults_to_verified_only(self):
        p = OpenCodeGoProvider()
        # With nothing requested, only the verified model may be used — never a guess.
        self.assertEqual(p.resolve_model(None), VERIFIED_GO_MODEL)
        self.assertEqual(p.resolve_model(""), VERIFIED_GO_MODEL)
        self.assertEqual(p.resolve_model("  "), VERIFIED_GO_MODEL)

    def test_resolve_model_accepts_explicit_id(self):
        p = OpenCodeGoProvider()
        self.assertEqual(p.resolve_model("glm-5.3-flash"), "glm-5.3-flash")

    def test_resolve_model_rejects_dropped_paid_mimo_id(self):
        # OpenCode Go publishes mimo-v2.6-flash-free; the paid id is not in the catalog.
        p = OpenCodeGoProvider()
        with self.assertRaises(ValueError):
            p.resolve_model("mimo-v2.6-flash")

    def test_resolve_model_accepts_free_mimo_id(self):
        p = OpenCodeGoProvider()
        self.assertEqual(p.resolve_model("mimo-v2.6-flash-free"), "mimo-v2.6-flash-free")

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
                provider="opencode-go",
                data={
                    "choices": [{"message": {"content": "hello"}}],
                    "model": "deepseek-v4.1-flash",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
                latency_ms=123.0,
                http_status=200,
            )
            p = OpenCodeGoProvider()
            req = ReasoningRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-v4.1-flash")
            resp = p.complete(req)
            self.assertTrue(resp.success)
            self.assertEqual(resp.data["content"], "hello")
            self.assertEqual(resp.data["model"], "deepseek-v4.1-flash")
            self.assertEqual(resp.data["usage"]["prompt_tokens"], 10)
            self.assertEqual(resp.data["usage"]["completion_tokens"], 5)
            self.assertAlmostEqual(
                resp.data["estimated_cost_usd"],
                10 * 0.30 / 1_000_000 + 5 * 1.20 / 1_000_000,
                delta=1e-6,
            )
            self.assertEqual(resp.latency_ms, 123.0)

            call_kwargs = mock_timed.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["model"], "deepseek-v4.1-flash")
            self.assertEqual(
                call_kwargs["headers"]["Authorization"],
                "Bearer " + os.environ["OPENCODE_GO_API_KEY"],
            )
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
                provider="opencode-go",
                data={"choices": []},
                latency_ms=10.0,
                http_status=200,
            )
            p = OpenCodeGoProvider()
            resp = p.complete(ReasoningRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-v4.1-flash"))
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.ERROR)
            self.assertIn("Malformed", resp.error)

    @mock.patch("adapters.reasoning_provider.BaseAdapter._timed_request")
    def test_complete_without_a_selected_model_fails_closed(self, mock_timed):
        with mock.patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "set", "OPENCODE_GO_ENABLED": "1"},
            clear=False,
        ):
            mock_timed.side_effect = AssertionError("no HTTP call should be made without a model")
            p = OpenCodeGoProvider()
            with mock.patch.object(OpenCodeGoProvider, "verified_model", return_value=None):
                resp = p.complete(ReasoningRequest(messages=[{"role": "user", "content": "hi"}]))
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.BLOCKED)
            self.assertIn("No OpenCode Go model was selected", resp.error)

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
                provider="opencode-go",
                error="Rate limited after retries",
                http_status=429,
            )
            p = OpenCodeGoProvider()
            resp = p.complete(ReasoningRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-v4.1-flash"))
            self.assertFalse(resp.success)
            self.assertEqual(resp.status, ProviderStatus.RATE_LIMITED)


class UsageTests(unittest.TestCase):
    def test_estimated_cost_usd(self):
        u = ReasoningUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        # DeepSeek V4.1 Flash per OpenCode published rates: $0.30 in, $1.20 out
        self.assertAlmostEqual(
            u.estimated_cost_usd("deepseek-v4.1-flash"),
            1.50,
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
            chunks = list(p.complete_stream(ReasoningRequest(messages=[{"role": "user", "content": "hi"}], model="deepseek-v4.1-flash")))
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
