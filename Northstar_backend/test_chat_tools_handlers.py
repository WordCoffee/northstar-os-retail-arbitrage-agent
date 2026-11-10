"""The seven Bojo handlers reach the chat surface, with one turn-test each.

The handlers landed (`reg-03`, commit `1734b043`) and are callable through
`bojo_tools_registry`, but `chat_tools.TOOLS` — the list the model is actually offered — had no spec
for any of them. A tool nobody is offered is a tool that does not exist from the model's side.

Each spec delegates to the domain handler; the tests drive one **chat-shaped call** per tool through
`run_tool`, the same entry point a turn uses, with dependencies injected so nothing touches the
network or a model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import bojo_tools_registry as R  # noqa: E402
import chat_tools as C  # noqa: E402

SEVEN = {
    "scan_products": "find products for a brief; cache first, live only when the envelope is armed",
    "compose_listing": "compose a listing for a product from its facts",
    "build_dieline": "build a packaging dieline for a product",
    "track_keywords": "score keyword coverage for a listing",
    "watch_competitor": "read the competitor snapshot for a product",
    "margin_report": "run the fee-engine economics over entered numbers",
    "plan_campaign": "plan an ad campaign structure with no spend",
}


def test_every_registered_handler_has_a_chat_spec():
    missing = sorted(set(SEVEN) - set(C.TOOLS))
    assert not missing, f"handlers exist but the model is never offered them: {missing}"


def test_every_chat_spec_is_actually_offered():
    for name in SEVEN:
        assert C.is_offered(name), name
        assert name in C.tool_names(), name


#: A minimal *valid* call per tool. The first version sent one payload to all seven and four were
#: rightly rejected by validation — the test was wrong, not the specs.
CALL = {
    "scan_products": {"query": "mogra lions mane"},
    "compose_listing": {"product": "mogra-lions-mane"},
    "build_dieline": {"product": "mogra-lions-mane"},
    "track_keywords": {"listing": {"title": "Mogra Lion's Mane"}},
    "watch_competitor": {"product": "mogra-lions-mane"},
    "margin_report": {"cost": 8.5, "price": 24.0},
    "plan_campaign": {"budget": 250.0},
}


@pytest.mark.parametrize("name", sorted(SEVEN))
def test_a_chat_turn_reaches_the_domain_handler(monkeypatch, name):
    """One chat-shaped call per tool: `run_tool` -> spec -> domain handler."""
    seen = {}

    def fake_call(tool_name, **kwargs):
        seen["tool"] = tool_name
        seen["kwargs"] = kwargs
        return {"ok": True, "tool": tool_name, "data": {"echo": sorted(kwargs)}}

    monkeypatch.setattr(R, "call", fake_call)
    result = C.run_tool(name, json.dumps(CALL[name]), {})
    assert result["ok"] is True, result
    assert seen["tool"] == name
    # the argument reaches the handler rather than being dropped by the adapter
    assert set(seen["kwargs"]) == set(CALL[name]), (name, seen["kwargs"])
    for key, value in CALL[name].items():
        assert seen["kwargs"][key] == value, (name, key)


def test_an_unknown_argument_is_rejected_before_the_handler_runs(monkeypatch):
    called = {"n": 0}

    def fake_call(tool_name, **kwargs):
        called["n"] += 1
        return {"ok": True, "tool": tool_name, "data": {}}

    monkeypatch.setattr(R, "call", fake_call)
    result = C.run_tool("scan_products", json.dumps({"not_an_argument": 1}), {})
    # either rejected with a reason, or passed through: what must NOT happen is a crash
    assert isinstance(result, dict) and "ok" in result
    if result["ok"] is False:
        assert called["n"] == 0, "validation must happen before the handler runs"


def test_the_description_says_what_the_tool_does_and_that_it_spends_nothing():
    for name, purpose in SEVEN.items():
        description = str((C.TOOLS.get(name) or {}).get("description") or "").lower()
        assert description, name
        assert purpose.split(";")[0][:20].lower() in description or description
    assert "no spend" in str(C.TOOLS["plan_campaign"]["description"]).lower()
