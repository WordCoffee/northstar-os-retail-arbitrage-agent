"""What Bojo offers is derived: offered means a callable handler exists.

Two directions are asserted, because either alone is easy to fake:

* a tool declared on a service with **no handler** is absent from every offer
  (`tool_names()`, `ollama_tool_schemas()`, `bojo_tools_registry.offered()`), and
* a tool **with** a handler is present, including one whose handler lands later.

The rule is not a skip list: it reads the specs, so implementing one of the seven
declared tools makes it appear without anybody editing a catalogue. Retired tools
are the other half of the same gate — kept in `TOOLS` (handler and tests stay),
never offered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import bojo_tools_registry  # noqa: E402
import chat_tools  # noqa: E402

#: Declared on a service in ty/services.json but carrying no handler today.
DECLARED_WITHOUT_HANDLER = (
    "build_dieline",
    "compose_listing",
    "margin_report",
    "plan_campaign",
    "scan_products",
    "track_keywords",
    "watch_competitor",
)


def _schema_names() -> list:
    return [schema["function"]["name"] for schema in chat_tools.ollama_tool_schemas()]


# ── the seven declared-but-unhandled tools are never offered ────────────────


@pytest.mark.parametrize("name", DECLARED_WITHOUT_HANDLER)
def test_declared_tool_without_a_handler_is_not_offered(name):
    assert name not in chat_tools.tool_names()
    assert name not in _schema_names()
    assert chat_tools.is_offered(name) is False


def test_declared_tools_are_named_by_the_services_that_own_them():
    """They are absent from the offer, not from the registry record."""
    listed = json.loads((ROOT / "ty" / "bojo_tool_list.json").read_text(encoding="utf-8"))
    declared = {tool["name"] for tool in listed["tools"] if tool["status"] == "declared"}
    assert declared == set(DECLARED_WITHOUT_HANDLER)


# ── a spec without a handler is dropped even when a caller names it ─────────


def test_a_declared_spec_added_to_tools_is_not_offered(monkeypatch):
    monkeypatch.setitem(chat_tools.TOOLS, "build_dieline", {
        "description": "declared, unimplemented",
        "parameters": {"type": "object", "properties": {}, "required": []},
        # no "handler" key at all: the offer gate must refuse it
    })
    assert chat_tools.is_offered("build_dieline") is False
    assert "build_dieline" not in chat_tools.tool_names()
    assert "build_dieline" not in _schema_names()
    # Even an explicit request for the name is filtered, so a stale focus list
    # cannot smuggle an unimplemented tool into the model's tool array.
    requested = chat_tools.ollama_tool_schemas(["build_dieline", "listing_audit"])
    assert [schema["function"]["name"] for schema in requested] == ["listing_audit"]


def test_a_spec_whose_handler_is_not_callable_is_not_offered(monkeypatch):
    monkeypatch.setitem(chat_tools.TOOLS, "compose_listing", {
        "description": "declared, handler is a string",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": "not a function",
    })
    assert chat_tools.is_offered("compose_listing") is False
    assert "compose_listing" not in _schema_names()


# ── a tool with a handler is present ───────────────────────────────────────


def test_every_offered_tool_has_a_callable_handler():
    offered = chat_tools.tool_names()
    assert offered, "the offer list cannot be empty"
    for name in offered:
        assert callable(chat_tools.TOOLS[name]["handler"]), name


def test_a_tool_with_a_handler_is_offered():
    assert chat_tools.is_offered("listing_audit") is True
    assert "listing_audit" in chat_tools.tool_names()
    assert "listing_audit" in _schema_names()


def test_a_handler_landing_later_makes_its_tool_appear(monkeypatch):
    """Implementing a declared tool offers it with no list to edit."""

    def handler(args, ctx):  # pragma: no cover - never invoked here
        return {"ok": True}

    monkeypatch.setitem(chat_tools.TOOLS, "scan_products", {
        "description": "now implemented",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": handler,
    })
    assert chat_tools.is_offered("scan_products") is True
    assert "scan_products" in chat_tools.tool_names()
    assert "scan_products" in _schema_names()


def test_run_tool_refuses_an_unimplemented_spec_honestly(monkeypatch):
    monkeypatch.setitem(chat_tools.TOOLS, "margin_report", {
        "description": "declared, unimplemented",
        "parameters": {"type": "object", "properties": {}, "required": []},
    })
    result = chat_tools.run_tool("margin_report", {})
    assert result["ok"] is False
    assert "no handler" in result["summary"].lower()


# ── retirement is "not offered", not deletion ──────────────────────────────


def test_retired_tools_keep_their_handler_but_leave_the_offer():
    assert chat_tools.RETIRED, "the retirement record must not be empty"
    for name, reason in chat_tools.RETIRED.items():
        assert name in chat_tools.TOOLS, f"{name} was deleted, not retired"
        assert callable(chat_tools.TOOLS[name]["handler"]), name
        assert chat_tools.TOOLS[name]["status"] == "retired"
        assert len(reason) >= 20, f"{name} needs a one-line reason"
        assert name not in chat_tools.tool_names()
        assert name not in _schema_names()


# ── the generated tool list agrees with the offer ──────────────────────────


def test_generated_tool_list_names_only_offered_wired_tools():
    listed = json.loads((ROOT / "ty" / "bojo_tool_list.json").read_text(encoding="utf-8"))
    wired = {tool["name"] for tool in listed["tools"] if tool["status"] == "wired"}
    declared = {tool["name"] for tool in listed["tools"] if tool["status"] == "declared"}
    offered = set(chat_tools.tool_names())

    assert wired <= offered, f"wired but not offered: {sorted(wired - offered)}"
    assert not (declared & offered), f"declared but offered: {sorted(declared & offered)}"
    # Unclaimed names are the ones no service owns — today, the retired four.
    assert set(listed["unclaimed"]) == set(chat_tools.RETIRED)


# ── the Bojo domain registry uses the same derived gate ────────────────────


def test_bojo_registry_offers_only_callable_handlers(monkeypatch):
    monkeypatch.setattr(bojo_tools_registry, "_load", lambda name: {
        "real_tool": lambda **kwargs: {"ok": True},
        "broken_tool": "not a function",
    })
    assert bojo_tools_registry.offered() == ["real_tool"]
    assert bojo_tools_registry.names() == bojo_tools_registry.offered()
    assert bojo_tools_registry.has_handler("real_tool") is True
    assert bojo_tools_registry.has_handler("broken_tool") is False


def test_bojo_registry_retirement_leaves_the_offer_but_keeps_the_handler(monkeypatch):
    monkeypatch.setattr(bojo_tools_registry, "_load", lambda name: {
        "real_tool": lambda **kwargs: {"ok": True},
    })
    monkeypatch.setitem(bojo_tools_registry.RETIRED, "real_tool", "no service owns it any more")
    assert bojo_tools_registry.offered() == []
    assert "real_tool" in bojo_tools_registry.tools()
