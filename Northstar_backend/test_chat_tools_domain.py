"""Bojo can actually call the four domain tools the gap loop added.

The scorecard's `complete` dimension only means something if the tool is reachable from the
chat surface, so these tests go through `chat_tools.run_tool` — the same path a Bojo call
takes — rather than importing the module directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import chat_tools  # noqa: E402


DOMAIN = ("catalog_pull", "golden_goose_scan", "offer_recommendation", "hub_status")


def test_every_domain_tool_is_on_the_chat_surface():
    for name in DOMAIN:
        assert name in chat_tools.TOOLS, name
        assert callable(chat_tools.TOOLS[name]["handler"])
        assert chat_tools.TOOLS[name]["parameters"]["type"] == "object"


def test_offer_recommendation_answers_through_run_tool():
    result = chat_tools.run_tool("offer_recommendation", json.dumps({
        "cost": 6.40, "target_margin_pct": 25,
        "competitor_prices": [24.99, 26.50],
        "fees": {"fulfilment": 4.10}}))
    assert result["ok"] is True
    assert isinstance(result["data"], dict)
    assert "arithmetic" in result["data"]
    assert result["assets"] == []


def test_hub_status_answers_through_run_tool():
    result = chat_tools.run_tool("hub_status", "{}")
    assert "ok" in result
    assert result["assets"] == []


def test_golden_goose_scan_refuses_an_empty_candidate_list_honestly():
    result = chat_tools.run_tool("golden_goose_scan", json.dumps({"candidates": []}))
    assert result["ok"] is False
    assert result["error"]


def test_catalog_pull_returns_a_shape_or_an_honest_failure():
    result = chat_tools.run_tool("catalog_pull", json.dumps({"query": "supplement pouch",
                                                             "limit": 3}))
    assert "ok" in result and "summary" in result


def test_an_unknown_tool_still_lists_the_known_ones():
    result = chat_tools.run_tool("nope", "{}")
    assert result["ok"] is False
    assert "known tools" in result["error"]
