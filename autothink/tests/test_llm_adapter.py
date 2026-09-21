"""Offline tests for the UnifiedLLMAdapter.

requests is fully mocked — no live Ollama or cloud calls are executed.
Credential presence is toggled via env var without ever reading a value.
"""

import os
import json
import unittest
from unittest import mock

import requests

import backend.llm_adapter as la
from backend.llm_adapter import UnifiedLLMAdapter


class _FakeStreamResponse:
    """Minimal requests.Response stand-in for a streamed Ollama chat."""

    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self, decode_unicode=True):
        for item in self._lines:
            if isinstance(item, dict):
                yield json.dumps(item)
            else:
                yield item


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = UnifiedLLMAdapter(local_model="qwen3:14b", timeout_s=5)

    @mock.patch("backend.llm_adapter.requests.post")
    def test_local_generate_success(self, mock_post):
        mock_post.return_value = _FakeStreamResponse([
            {"message": {"content": "Hello "}},
            {"message": {"content": "from Ollama"}},
            {"done": True, "prompt_eval_count": 12, "eval_count": 8,
             "total_duration": 1_250_000},
        ])
        result = self.adapter.generate("Hi there", provider="local")
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "local")
        self.assertEqual(result["content"], "Hello from Ollama")
        self.assertEqual(result["prompt_tokens"], 12)
        self.assertEqual(result["completion_tokens"], 8)
        mocked_call = mock_post.call_args
        self.assertEqual(mocked_call.kwargs["json"]["model"], "qwen3:14b")
        self.assertTrue(mocked_call.kwargs["json"]["stream"])
        self.assertEqual(mocked_call.kwargs["json"]["options"]["num_predict"], la.NUM_PREDICT)
        self.assertEqual(mocked_call.kwargs["json"]["options"]["num_ctx"], la.NUM_CTX)
        self.assertTrue(mocked_call.kwargs["stream"])

    @mock.patch("backend.llm_adapter.requests.post")
    def test_local_generate_http_error_fallback(self, mock_post):
        mock_post.return_value.status_code = 503
        result = self.adapter.generate("hi", provider="local")
        self.assertFalse(result["ok"])
        self.assertIn("[LOCAL FALLBACK]", result["content"])

    @mock.patch("backend.llm_adapter.requests.post")
    def test_local_generate_network_error_fallback(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("connection refused")
        result = self.adapter.generate("hi", provider="local")
        self.assertFalse(result["ok"])
        self.assertIn("[LOCAL FALLBACK]", result["content"])

    @mock.patch("backend.llm_adapter.requests.get")
    def test_local_available_probes_ollama(self, mock_get):
        mock_get.return_value.status_code = 200
        self.assertTrue(self.adapter.local_available())

    @mock.patch("backend.llm_adapter.requests.get")
    def test_local_unavailable_on_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("refused")
        self.assertFalse(self.adapter.local_available())

    @mock.patch("backend.llm_adapter.requests.get")
    def test_list_local_models_parses_tags(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "qwen3:14b"}, {"name": "qwen3:4b"}, {"name": ""}]
        }
        models = self.adapter.list_local_models()
        self.assertEqual(models, ["qwen3:14b", "qwen3:4b"])

    def test_cloud_without_key_is_gated(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
                if k in os.environ:
                    os.environ.pop(k)
            self.assertFalse(self.adapter.cloud_available())
            result = self.adapter.generate("hi", provider="cloud")
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "no_api_key")
            self.assertIn("[CLOUD FALLBACK]", result["content"])

    def test_cloud_availability_reflects_presence_only(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "set"}, clear=False):
            os.environ.pop("OPENROUTER_API_KEY", None)
            self.assertTrue(self.adapter.cloud_available())
        # never leaks the value

    def test_cloud_requires_live_flag_even_with_key(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "set"}, clear=False):
            os.environ.pop("CLOUD_MODEL_LIVE", None)
            self.assertTrue(self.adapter.cloud_available())
            self.assertFalse(self.adapter.cloud_live_armed())
            result = self.adapter.generate("hi", provider="cloud")
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "not_approved")

    @mock.patch("backend.llm_adapter.requests.post")
    def test_openrouter_armed_call_parses_response(self, mock_post):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "set", "CLOUD_MODEL_LIVE": "1"}, clear=False):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "model": "deepseek/deepseek-v4-flash-0731",
                "choices": [{"message": {"content": "Cloud says hi"}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 4},
            }
            result = self.adapter.generate("hi", provider="cloud",
                                           model="deepseek/deepseek-v4-flash-0731")
            self.assertTrue(result["ok"])
            self.assertEqual(result["content"], "Cloud says hi")
            self.assertEqual(result["prompt_tokens"], 9)
            self.assertEqual(mock_post.call_args.kwargs["json"]["model"],
                             "deepseek/deepseek-v4-flash-0731")

    @mock.patch("backend.llm_adapter.requests.post")
    def test_openrouter_armed_http_error_is_fallback(self, mock_post):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "set", "CLOUD_MODEL_LIVE": "1"}, clear=False):
            mock_post.return_value.status_code = 429
            result = self.adapter.generate("hi", provider="cloud")
            self.assertFalse(result["ok"])
            self.assertIn("[CLOUD FALLBACK]", result["content"])


if __name__ == "__main__":
    unittest.main()