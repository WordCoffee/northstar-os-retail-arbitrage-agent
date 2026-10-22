"""Bojo's skill warehouse — every service is reachable through a real tool.

These tests pin:
  * the five service tools are registered with valid JSON schemas;
  * every focus gets the core services even when its curated list omits them;
  * each handler does real work (a rule lookup returns sourced rules, an audit
    finds a promotional phrase, the ads maths names a loss);
  * failures are honest — an unknown domain or bad arguments never raise.
"""

from __future__ import annotations

import json

import pytest

import chat_tools
import shell_focus

SERVICE_TOOLS = ["knowledge_lookup", "listing_audit", "ads_math",
                 "improvement_status", "service_catalog"]


# ── registration ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", SERVICE_TOOLS)
def test_service_tool_is_registered_with_a_valid_schema(name):
    spec = chat_tools.TOOLS[name]
    assert spec["description"].strip()
    schema = spec["parameters"]
    assert schema["type"] == "object"
    assert isinstance(schema.get("properties"), dict)
    assert isinstance(schema.get("required"), list)
    assert callable(spec["handler"])
    # the schema must survive a JSON round-trip (Ollama receives plain JSON)
    json.dumps(schema)


def test_every_focus_offers_the_core_services():
    for focus in shell_focus.FOCUS_PROMPTS:
        tools = shell_focus.tools_for_focus(focus)
        if tools is None:  # "all tools" focus
            continue
        for name in SERVICE_TOOLS:
            assert name in tools, f"{focus} is missing {name}"


# ── knowledge lookup ────────────────────────────────────────────────────────

def test_knowledge_lookup_returns_sourced_rules():
    out = chat_tools.run_tool("knowledge_lookup",
                              {"query": "maximum title length characters"})
    assert out["ok"] is True
    assert out["rules"], out
    top = out["rules"][0]
    assert top["id"].startswith("listing.title")
    assert top["do"] and top["dont"] and top["source"]


def test_knowledge_lookup_rejects_an_unknown_domain_honestly():
    out = chat_tools.run_tool("knowledge_lookup",
                              {"query": "anything", "domain": "lunar"})
    assert out["ok"] is False
    # The schema enum rejects it before the handler runs; either message is honest.
    assert "domain" in out["error"]


def test_knowledge_lookup_says_when_it_has_nothing():
    # Nonsense tokens share nothing with any atom, so the honest answer is
    # "no verified rule" rather than a spurious match.
    out = chat_tools.run_tool("knowledge_lookup", {"query": "zzqx plimflor wug"})
    assert out["ok"] is True
    assert out["rules"] == []
    assert "verified rule" in out["note"]


# ── listing audit ───────────────────────────────────────────────────────────

def test_listing_audit_flags_promotional_language_and_caps():
    out = chat_tools.run_tool("listing_audit", {
        "title": "BEST SELLER FREE SHIPPING Organic Mushroom Powder 8oz!!!",
        "bullets": ["FDA approved and cures everything.", "Great taste."],
    })
    assert out["ok"] is True
    assert out["title"]["failures"], out
    assert any("forbidden" in f for f in out["title"]["failures"])
    assert out["bullets"]["failures"], out


def test_listing_audit_passes_a_clean_listing():
    out = chat_tools.run_tool("listing_audit", {
        "title": "Mogra Organics Organic Lion's Mane Mushroom Powder, 6 oz",
        "bullets": ["Supports daily focus with a clean two-ingredient blend."],
    })
    assert out["ok"] is True
    assert out["title"]["failures"] == []
    assert out["bullets"]["failures"] == []
    assert out["summary"] == "No deterministic problems found."


def test_listing_audit_needs_something_to_audit():
    out = chat_tools.run_tool("listing_audit", {})
    assert out["ok"] is False
    assert "title" in out["error"]


# ── ads maths ───────────────────────────────────────────────────────────────

def test_ads_math_names_a_loss():
    out = chat_tools.run_tool("ads_math", {
        "price": 100, "cogs": 62, "ad_spend": 420, "ad_sales": 1000})
    assert out["ok"] is True
    assert out["unit_margin_pct"] == 38.0
    assert out["acos_pct"] == 42.0
    assert out["break_even_acos_pct"] == 38.0
    assert out["verdict"] == "losing money"
    assert out["profit_per_ad_dollar"] < 0


def test_ads_math_reports_tacos_when_revenue_is_given():
    out = chat_tools.run_tool("ads_math", {
        "price": 30, "cogs": 9, "ad_spend": 100, "ad_sales": 500,
        "total_revenue": 2000})
    assert out["tacos_pct"] == 5.0
    assert out["verdict"] == "profitable"


def test_ads_math_requires_a_price():
    out = chat_tools.run_tool("ads_math", {"cogs": 5})
    assert out["ok"] is False


# ── improvement status + catalogue ──────────────────────────────────────────

def test_improvement_status_reports_coverage_and_packs():
    out = chat_tools.run_tool("improvement_status", {})
    assert out["ok"] is True
    assert 0.0 <= out["coverage"] <= 1.0
    assert out["atoms"] >= 90
    assert out["packs"], out
    assert "Coverage" in out["summary"]


def test_service_catalog_covers_every_domain_and_tool():
    out = chat_tools.run_tool("service_catalog", {})
    assert out["ok"] is True
    ids = {s["id"] for s in out["services"]}
    assert {"listing", "ads", "aplus", "creator-connections", "brand-store",
            "reseller", "creative", "research", "system"} <= ids
    # every tool named by a service must actually exist
    for service in out["services"]:
        for tool in service["tools"]:
            assert tool in chat_tools.TOOLS, f"{service['id']} names missing {tool}"


# ── failure honesty ─────────────────────────────────────────────────────────

def test_unknown_tool_is_an_honest_result_not_an_exception():
    out = chat_tools.run_tool("does_not_exist", {})
    assert out["ok"] is False
    assert "known tools" in out["error"]


def test_bad_arguments_are_rejected_by_the_schema():
    out = chat_tools.run_tool("knowledge_lookup", {"query": ""})
    assert out["ok"] is False
    assert "rejected" in out["summary"].lower()
