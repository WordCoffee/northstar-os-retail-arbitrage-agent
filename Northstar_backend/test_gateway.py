"""Gateway acceptance + the replacement for the old no-egress test (blueprint §11A.5).

Four things must hold:

  1. every role can be swapped to `stub_cloud` by CONFIG ONLY;
  2. all specialist agents still behave identically with that swap;
  3. the ledger records the correct raw cost and customer charge;
  4. a forced provider failure falls back and produces NO user-visible error.

Plus the gateway check itself: nothing outside `gateway/adapters.py` may talk to a
provider, and no URL may point at an unapproved host.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from gateway import adapters, ledger, roles, service  # noqa: E402
from specialists import (content, image_aplus, job_queue, listing_optimizer,  # noqa: E402
                         package_designer, panel_map, ppc_agent, social_graphics,
                         video_ugc)

APPROVED_HOSTS = {"127.0.0.1", "localhost", "api.dataforseo.com",
                  "api.brightdata.com", "api.sellersprite.com"}
_NET_CLIENTS = {"requests", "httpx", "urllib", "urllib3", "socket", "aiohttp",
                "openai", "anthropic"}
_URL = re.compile(r"https?://([A-Za-z0-9._-]+)")


@pytest.fixture(autouse=True)
def _isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "usage.jsonl")
    service.reset_idempotency()
    monkeypatch.delenv("NORTHSTAR_FORCE_PROVIDER", raising=False)
    yield


# ── 1. config-only swap ────────────────────────────────────────────────────

def test_every_role_can_be_swapped_to_the_stub_by_config(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    for role in roles.VALID_ROLES:
        assert roles.chain(role) == ["stub_cloud"], role


def test_one_role_can_be_swapped_without_touching_the_file(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_ROLE_IMAGE", "stub_cloud")
    assert roles.chain("image") == ["stub_cloud"]
    assert "local_ollama" in roles.chain("reasoning")


def test_an_unknown_role_is_refused():
    with pytest.raises(ValueError):
        roles.chain("do_everything")


# ── 2. agents unchanged under the swap ─────────────────────────────────────

def test_all_specialist_agents_behave_identically_on_the_stub(monkeypatch):
    """The agents are deterministic and provider-agnostic; the swap must be invisible."""
    before = {
        "package": package_designer.missing_inputs({"title": ""}),
        "listing": listing_optimizer.optimize(title="x", bullets=["y"], keywords=[])["status"],
        "ppc": ppc_agent.analyze([{"Campaign": "A"}])["status"],
        "aplus": len(image_aplus.plan(spec={"product": "p"})["modules"]),
        "social": len(social_graphics.plan(spec={"product": "p", "content_type": "ad"})["layouts"]),
        "video": video_ugc.plan(spec={"product": "p", "duration_seconds": 5})["frames"],
        "content": len(content.plan(spec={"product": "p", "surface": "ad"})["variants"]),
        "panels": len(panel_map.visible_fractions({"front": [0, 0, 95, 200],
                                                   "gusset": [0, 0, 95, 80]})),
    }
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    after = {
        "package": package_designer.missing_inputs({"title": ""}),
        "listing": listing_optimizer.optimize(title="x", bullets=["y"], keywords=[])["status"],
        "ppc": ppc_agent.analyze([{"Campaign": "A"}])["status"],
        "aplus": len(image_aplus.plan(spec={"product": "p"})["modules"]),
        "social": len(social_graphics.plan(spec={"product": "p", "content_type": "ad"})["layouts"]),
        "video": video_ugc.plan(spec={"product": "p", "duration_seconds": 5})["frames"],
        "content": len(content.plan(spec={"product": "p", "surface": "ad"})["variants"]),
        "panels": len(panel_map.visible_fractions({"front": [0, 0, 95, 200],
                                                   "gusset": [0, 0, 95, 80]})),
    }
    assert before == after
    assert ledger.read_rows() == [], "an agent called a provider directly"


def test_the_job_queue_is_provider_agnostic():
    q = job_queue.JobQueue(vram_guard=lambda: True)
    job = q.submit("image")
    assert q.acquire()["ok"] is True
    q.complete(job["job_id"], ok=True, credits=10, cost_usd=0.0)
    assert q.totals()["jobs"] == 1


# ── 3. ledger correctness ──────────────────────────────────────────────────

def test_the_ledger_records_the_exact_cost_and_charge(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    out = service.complete("reasoning", "hello world, please answer briefly",
                           ctx={"user_id": "u1", "tenant_id": "t1", "plan": "mover",
                                "service": "chat", "agent": "bojo"})
    assert out["ok"] is True
    row = ledger.read_rows()[-1]
    price = ledger.prices()["providers"]["stub_cloud"]
    expected_cost = round((row["usage"]["tokens_in"] / 1000) * price["input"]
                          + (row["usage"]["tokens_out"] / 1000) * price["output"], 8)
    assert row["raw_cost_usd"] == pytest.approx(expected_cost, abs=1e-9)
    expected_charge = round(expected_cost / (1 - row["margin"]), 8)
    assert row["charge_usd"] == pytest.approx(expected_charge, abs=1e-9)
    assert row["margin"] == ledger.margin_for("mover", "chat")
    assert row["user_id"] == "u1" and row["tenant_id"] == "t1"


def test_margin_stays_inside_the_target_band():
    for plan in ("foundation", "scout", "mover", "autothink"):
        m = ledger.margin_for(plan, "package")
        assert ledger.margin_rules()["floor_margin"] <= m <= ledger.margin_rules()["ceiling_margin"]


def test_a_local_call_costs_nothing_and_charges_nothing():
    row = ledger.record(user_id="u", tenant_id="t", role="image", provider="comfyui",
                        model="flux", usage={"gpu_seconds": 90.0})
    assert row["raw_cost_usd"] == 0.0 and row["charge_usd"] == 0.0


def test_the_monthly_report_matches_the_rows(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    service.complete("reasoning", "one", ctx={"user_id": "u1", "tenant_id": "t1"})
    service.complete("reasoning", "two", ctx={"user_id": "u1", "tenant_id": "t1"})
    report = ledger.monthly_report()
    assert report["calls"] == 2
    assert report["charge_usd"] >= report["raw_cost_usd"]
    assert report["by_provider"]["stub_cloud"]["calls"] == 2


def test_an_estimate_is_available_before_a_job_runs(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    est = service.estimate("reasoning", "x" * 400, plan="mover", service="chat")
    assert est["estimated_cost_usd"] > 0
    assert est["estimated_charge_usd"] > est["estimated_cost_usd"]
    assert ledger.read_rows() == [], "an estimate must not call the provider"


def test_a_spending_cap_blocks_before_the_call(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    monkeypatch.setattr(ledger, "margin_rules", lambda: {
        "default_margin": 0.65, "by_plan": {}, "by_service": {},
        "user_caps": {"daily_default": 0.000001, "monthly_default": 1.0}})
    out = service.complete("reasoning", "this should be refused by the cap",
                           ctx={"user_id": "u1", "tenant_id": "t1"})
    assert out["ok"] is False and out["error"] == "spending_cap"
    assert out["user_visible"] is True


# ── 4. fallback on failure ─────────────────────────────────────────────────

def test_a_forced_failure_falls_back_with_no_user_visible_error(monkeypatch):
    # Two DIFFERENT providers: the first fails hard, the second answers. A retry
    # inside one provider is not a fallback, so the chain must change provider.
    monkeypatch.setenv("NORTHSTAR_ROLE_REASONING", "stub_cloud,local_voice")
    monkeypatch.setattr(adapters.StubCloud, "complete",
                        lambda self, role, payload: self._fail("simulated outage"))
    out = service.complete("reasoning", "answer me", ctx={"user_id": "u", "tenant_id": "t"})
    assert out["ok"] is True
    assert out["provider"] == "local_voice"
    assert out["fell_back"] is True
    assert out["attempts"][0]["ok"] is False


def test_when_every_provider_fails_the_error_is_honest(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_ROLE_REASONING", "stub_cloud")
    monkeypatch.setattr(adapters.StubCloud, "complete",
                        lambda self, role, payload: self._fail("hard down"))
    out = service.complete("reasoning", "x", ctx={"user_id": "u", "tenant_id": "t"})
    assert out["ok"] is False
    assert out["error"] == "all_providers_failed"
    assert out["user_visible"] is True


def test_a_retry_does_not_double_charge(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_FORCE_PROVIDER", "stub_cloud")
    ctx = {"user_id": "u1", "tenant_id": "t1"}
    first = service.complete("reasoning", "same request", ctx=ctx)
    rows_after_first = len(ledger.read_rows())
    second = service.complete("reasoning", "same request", ctx=ctx)
    assert second.get("idempotent_replay") is True
    assert len(ledger.read_rows()) == rows_after_first
    assert first["charge_usd"] == second["charge_usd"]


# ── the gateway check (replaces the old no-egress test) ────────────────────

def _py_files():
    files = sorted((BACKEND / "specialists").glob("*.py"))
    files += sorted((BACKEND / "gateway").glob("*.py"))
    return files


def test_only_the_adapter_module_may_import_a_network_client():
    offenders = []
    for path in _py_files():
        if path.name == "adapters.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in _NET_CLIENTS:
                    offenders.append(f"{path.name}:{node.lineno} imports {name}")
    assert not offenders, "a module bypassed the gateway: " + "; ".join(offenders)


def test_no_url_points_at_an_unapproved_host():
    offenders = []
    for path in _py_files():
        for m in _URL.finditer(path.read_text(encoding="utf-8")):
            if m.group(1).lower() not in APPROVED_HOSTS:
                offenders.append(f"{path.name}: {m.group(1)}")
    assert not offenders, "unapproved host: " + "; ".join(offenders)


def test_the_role_map_is_complete_and_fail_closed():
    data = json.loads((BACKEND.parent / "shared" / "model-roles.json")
                      .read_text(encoding="utf-8"))
    for role in roles.VALID_ROLES:
        assert data["roles"][role]["chain"], f"{role} has no chain"


def test_health_reports_roles_and_caps():
    h = service.health()
    assert set(h["roles"]) == set(roles.VALID_ROLES)
    assert "daily_default" in h["caps"]
