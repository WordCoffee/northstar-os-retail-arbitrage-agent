"""What Bojo offers is derived, and a spec must match the handler it forwards to.

Two directions are asserted, because either alone is easy to fake:

* a tool **declared** in `ty/bojo_tool_list.json` with no handler is absent from every offer
  (`tool_names()`, `ollama_tool_schemas()`, `bojo_tools_registry.offered()`);
* a tool **with** a handler is present — and, for the seven `reg-03` tools whose chat spec
  forwards straight into `bojo_tools_registry.call(name, **args)`, the spec's parameter names
  must be the handler's parameter names.

The second rule is new on 2026-11-11: six of the seven specs used a friendlier shape
(`product`, `facts`, `budget`, `asin`) than their handlers accept (`sku`, `inputs`,
`daily_budget`, `asins`), so Bojo was offered six tools that could only answer "bad
arguments". Offered-and-impossible is worse than not offered, so it is asserted mechanically
rather than by a hand-maintained list of names.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import bojo_tools_registry  # noqa: E402
import chat_tools  # noqa: E402


def _schema_names() -> list:
    return [schema["function"]["name"] for schema in chat_tools.ollama_tool_schemas()]


def _declared_tools() -> set:
    listed = json.loads((ROOT / "ty" / "bojo_tool_list.json").read_text(encoding="utf-8"))
    return {tool["name"] for tool in listed["tools"] if tool["status"] == "declared"}


def _forwarded_tools() -> list:
    """Chat specs that forward into the domain registry: name -> handler."""
    out = []
    for name in chat_tools._BOJO_SPECS:
        if not chat_tools.is_offered(name):
            continue
        try:
            handler = bojo_tools_registry.get(name)
        except KeyError:
            continue
        out.append((name, handler))
    return out


# --- declared-but-unhandled tools are never offered --------------------------

def test_a_declared_tool_without_a_handler_is_not_offered():
    for name in sorted(_declared_tools()):
        assert name not in chat_tools.tool_names(), name
        assert name not in _schema_names(), name
        assert chat_tools.is_offered(name) is False, name


def test_the_registry_record_still_names_every_declared_tool():
    """Absent from the offer, present in the record — the gap is visible, not dropped."""
    listed = json.loads((ROOT / "ty" / "bojo_tool_list.json").read_text(encoding="utf-8"))
    declared = _declared_tools()
    recorded = {tool["name"] for tool in listed["tools"]}
    assert declared <= recorded


# --- an offered tool's spec must be callable by its handler ------------------

@pytest.mark.parametrize("name,handler", _forwarded_tools(),
                         ids=[name for name, _ in _forwarded_tools()])
def test_a_forwarded_spec_uses_the_handlers_own_parameter_names(name, handler):
    signature = inspect.signature(handler)
    accepted = {param for param, value in signature.parameters.items()
                if value.kind in (value.KEYWORD_ONLY, value.POSITIONAL_OR_KEYWORD)}
    required = {param for param, value in signature.parameters.items()
                if value.default is value.empty
                and value.kind in (value.KEYWORD_ONLY, value.POSITIONAL_OR_KEYWORD)}
    spec = (chat_tools.TOOLS.get(name) or {}).get("parameters") or {}
    declared = set((spec.get("properties") or {}).keys())
    spec_required = set(spec.get("required") or [])

    invented = sorted(declared - accepted)
    assert invented == [], (
        f"{name}: the spec offers parameter(s) {invented} that {handler.__name__} does not "
        f"accept, so every call answers 'bad arguments'")
    unfillable = sorted(required - declared)
    assert unfillable == [], (
        f"{name}: {handler.__name__} requires {unfillable}, which the spec never offers")


def test_every_forwarded_tool_returns_the_registry_contract():
    """A call through the adapter answers {ok, summary, ...} — never a raise, and never the
    one error that means the spec and the handler disagree about a name.

    A *missing required* argument is a validation answer, not a mismatch: it says the caller
    left something out, which is the caller's problem. `unexpected keyword argument` is the
    signature of a spec that offers a parameter the handler has never heard of.
    """
    for name, _handler in _forwarded_tools():
        spec = chat_tools.TOOLS.get(name) or {}
        result = spec["handler"]({})
        assert isinstance(result, dict), name
        assert "ok" in result, name
        assert "unexpected keyword argument" not in str(result.get("summary") or ""), name


# --- retirement is the other half of the same gate ---------------------------

def test_a_retired_tool_is_kept_but_not_offered():
    retired = [name for name, spec in chat_tools.TOOLS.items()
               if str((spec or {}).get("status") or "") == "retired"]
    for name in retired:
        assert not chat_tools.is_offered(name), name
        assert name in chat_tools.TOOLS, "retired means kept, never deleted"
