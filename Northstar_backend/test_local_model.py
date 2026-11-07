"""Tests for the local llama.cpp model callable used by the coding agent loop."""
import json

import pytest

from agent_kernel import local_model


class _Resp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _chat(content, reasoning=""):
    return {"choices": [{"message": {"content": content,
                                     "reasoning_content": reasoning}}]}


def test_call_returns_content_and_disables_thinking(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(_chat('{"tool":"finish","args":{}}'))

    monkeypatch.setattr(local_model.urllib.request, "urlopen", fake_urlopen)
    model = local_model.LlamaCppModel(base_url="http://127.0.0.1:8080", model="m")
    out = model("prompt")
    assert out.startswith('{"tool"')
    assert seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert seen["body"]["messages"][0]["content"] == "prompt"


def test_empty_content_retries_then_raises(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        return _Resp(_chat("", reasoning="thinking..."))

    monkeypatch.setattr(local_model.urllib.request, "urlopen", fake_urlopen)
    model = local_model.LlamaCppModel(retries=1)
    with pytest.raises(local_model.ModelError):
        model("prompt")
    assert len(calls) == 2  # first try + one retry


def test_health_false_when_unreachable(monkeypatch):
    def boom(*a, **k):
        raise OSError("no server")

    monkeypatch.setattr(local_model.urllib.request, "urlopen", boom)
    assert local_model.health("http://127.0.0.1:9") is False


def test_make_local_model_reads_env(monkeypatch):
    monkeypatch.setenv("TYS_CODING_URL", "http://10.0.0.5:9000")
    monkeypatch.setenv("TYS_CODING_MODEL", "alias-x")
    m = local_model.make_local_model()
    assert m.base_url == "http://10.0.0.5:9000"
    assert m.model == "alias-x"


def test_schema_is_sent_as_response_format(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(_chat('{"tool":"finish","args":{}}'))

    monkeypatch.setattr(local_model.urllib.request, "urlopen", fake_urlopen)
    local_model.LlamaCppModel(schema=local_model.TOOL_CALL_SCHEMA)("prompt")
    fmt = seen["body"]["response_format"]
    assert fmt["type"] == "json_schema"
    assert "tool" in fmt["json_schema"]["schema"]["properties"]


def test_default_model_is_schema_constrained(monkeypatch):
    monkeypatch.delenv("TYS_CODING_SCHEMA", raising=False)
    m = local_model.make_local_model()
    assert m.schema == local_model.TOOL_CALL_SCHEMA
