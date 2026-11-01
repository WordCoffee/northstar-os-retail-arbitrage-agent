"""Native tool calling in the Ollama adapter.

The adapter used to force every model through a JSON-text prompt. `bojo` advertises
`tools` and answers with structured `message.tool_calls`; discarding that interface
was a harness defect. Both interfaces now produce the same one-JSON-action string
and the same validator judges it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel import tool_protocol as tp
from agent_kernel import local_model as lm


def test_payload_offers_tools_and_drops_json_mode():
    m = lm.OllamaChatModel(model="bojo", native_tools=True, tool_names=["read", "finish"])
    body = m.payload("x")
    assert "tools" in body and "format" not in body
    names = [t["function"]["name"] for t in body["tools"]]
    assert names == ["read", "finish"]


def test_payload_without_native_tools_keeps_json_mode():
    body = lm.OllamaChatModel(model="bojo").payload("x")
    assert body.get("format") == "json" and "tools" not in body


def test_tool_call_becomes_the_same_action_string(monkeypatch):
    m = lm.OllamaChatModel(model="bojo", native_tools=True)
    monkeypatch.setattr(lm, "_post_json", lambda *a, **k: {"message": {
        "content": "", "tool_calls": [{"function": {"name": "read",
                                                    "arguments": {"path": "a.py"}}}]}})
    action = tp.parse_action(m("prompt"))
    assert action.tool == "read" and action.args == {"path": "a.py"}


def test_string_arguments_are_parsed(monkeypatch):
    m = lm.OllamaChatModel(model="bojo", native_tools=True)
    monkeypatch.setattr(lm, "_post_json", lambda *a, **k: {"message": {
        "content": "", "tool_calls": [{"function": {
            "name": "ast_edit",
            "arguments": '{"path":"a.py","op":"replace_function_body","target":"f","source":"return 2"}'}}]}})
    action = tp.parse_action(m("prompt"))
    assert action.tool == "ast_edit" and action.args["target"] == "f"


def test_content_is_used_when_no_tool_call_is_returned(monkeypatch):
    m = lm.OllamaChatModel(model="bojo", native_tools=True)
    monkeypatch.setattr(lm, "_post_json", lambda *a, **k: {"message": {
        "content": '{"tool":"finish","args":{}}'}})
    assert tp.parse_action(m("prompt")).tool == "finish"


def test_an_unknown_native_tool_is_passed_through_for_refusal(monkeypatch):
    m = lm.OllamaChatModel(model="bojo", native_tools=True)
    monkeypatch.setattr(lm, "_post_json", lambda *a, **k: {"message": {
        "content": "", "tool_calls": [{"function": {"name": "execute_shell",
                                                    "arguments": {"cmd": "x"}}}]}})
    with pytest.raises(tp.ActionError) as exc:
        tp.parse_action(m("prompt"))
    assert exc.value.code == "unknown_tool"


def test_schemas_are_built_from_the_one_table():
    names = [t["function"]["name"] for t in tp.json_schemas()]
    assert names == list(tp.CANONICAL_ACTIONS)
    read = next(t for t in tp.json_schemas(["read"]))["function"]["parameters"]
    assert read["required"] == ["path"] and read["properties"]["path"]["type"] == "string"
