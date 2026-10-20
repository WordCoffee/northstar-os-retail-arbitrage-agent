"""Execute an approved creative plan — the money path.

The invariants that matter:
  * a job that fails to generate costs NOTHING (the hold is released);
  * a job that succeeds is committed exactly once;
  * no credits means no generator call at all (no free work);
  * a replay with the same idempotency key never double-charges.
"""
from __future__ import annotations

import pytest

import creative_execute as ce
import creative_pricing as cp
import credit_ledger as cl


@pytest.fixture()
def ledger(tmp_path):
    return cl.CreditLedger(str(tmp_path / "ledger.jsonl"))


@pytest.fixture()
def plan():
    return ce.creative_plan.build_plan(
        "design a 6 oz stand-up pouch for mushroom powder", subscription="mover")


def ok_generate(_instruction):
    return {"ok": True, "summary": "rendered", "assets": [{"id": "asset-1"}],
            "data": {"model": "test"}}


def failing_generate(_instruction):
    return {"ok": False, "error": "ComfyUI not armed", "assets": []}


def balance(ledger, account="acct"):
    return ledger.balance(account, cl.CREATIVE)


# ── the happy path ──────────────────────────────────────────────────────────

def test_a_successful_job_reserves_then_commits(ledger, plan):
    ledger.grant("acct", 500, class_=cl.CREATIVE)
    out = ce.execute(ledger, plan, "draft", generate=ok_generate, account_id="acct")
    assert out["ok"] is True
    assert out["credits_charged"] == plan["options"]["draft"]["credits"]
    assert out["asset_ids"] == ["asset-1"]
    assert out["real_cost_usd"] > 0
    assert out["balance"] == 500 - out["credits_charged"]
    kinds = [e["kind"] for e in ledger.entries()]
    assert "reserve" in kinds and "commit" in kinds and "release" not in kinds


def test_final_charges_more_than_draft(ledger, plan):
    ledger.grant("acct", 500, class_=cl.CREATIVE)
    d = ce.execute(ledger, plan, "draft", generate=ok_generate, account_id="acct")
    f = ce.execute(ledger, plan, "final", generate=ok_generate, account_id="acct")
    assert f["credits_charged"] > d["credits_charged"]


# ── a failed job costs nothing ─────────────────────────────────────────────

def test_a_failed_generation_releases_the_hold(ledger, plan):
    ledger.grant("acct", 500, class_=cl.CREATIVE)
    out = ce.execute(ledger, plan, "draft", generate=failing_generate, account_id="acct")
    assert out["ok"] is False
    assert out["stage"] == "generate" and out["released"] is True
    assert "ComfyUI not armed" in out["error"]
    assert balance(ledger) == 500                     # nothing charged


def test_a_raising_generator_releases_the_hold(ledger, plan):
    def boom(_i):
        raise RuntimeError("renderer died")

    ledger.grant("acct", 500, class_=cl.CREATIVE)
    out = ce.execute(ledger, plan, "draft", generate=boom, account_id="acct")
    assert out["ok"] is False and out["released"] is True
    assert "renderer died" in out["error"]
    assert balance(ledger) == 500


# ── no credits, no work ────────────────────────────────────────────────────

def test_insufficient_credits_refuses_before_generating(ledger, plan):
    called = {"n": 0}

    def generate(_i):
        called["n"] += 1
        return {"ok": True, "assets": []}

    out = ce.execute(ledger, plan, "draft", generate=generate, account_id="acct")
    assert out["ok"] is False and out["stage"] == "reserve"
    assert "insufficient credits" in out["error"]
    assert called["n"] == 0, "the generator must never run without a held reservation"


def test_a_tier_denied_job_never_touches_the_ledger(ledger):
    entry = ce.creative_plan.build_plan("design a pouch", subscription="foundation")
    called = {"n": 0}

    def generate(_i):
        called["n"] += 1
        return {"ok": True}

    out = ce.execute(ledger, entry, "final", generate=generate, account_id="acct")
    assert out["ok"] is False and out["stage"] == "confirm"
    assert called["n"] == 0
    assert ledger.entries() == []


# ── replay safety ─────────────────────────────────────────────────────────

def test_a_replay_with_the_same_plan_does_not_double_charge(ledger, plan):
    ledger.grant("acct", 500, class_=cl.CREATIVE)
    first = ce.execute(ledger, plan, "draft", generate=ok_generate, account_id="acct")
    after_first = balance(ledger)
    second = ce.execute(ledger, plan, "draft", generate=ok_generate, account_id="acct")
    assert second["ok"] is True
    assert balance(ledger) == after_first, "the same plan/quality must not charge twice"
    assert first["credits_charged"] == second["credits_charged"]


# ── alpha allotment ───────────────────────────────────────────────────────

def test_allotment_is_granted_once_and_is_idempotent(ledger):
    a = ce.ensure_allotment(ledger, "acct", "foundation")
    assert a["granted"] == cp.PLAN_ALLOTMENT["foundation"]
    b = ce.ensure_allotment(ledger, "acct", "foundation")
    assert b["granted"] == 0
    assert balance(ledger) == cp.PLAN_ALLOTMENT["foundation"]


def test_unknown_plan_grants_nothing(ledger):
    out = ce.ensure_allotment(ledger, "acct", "platinum")
    assert out["granted"] == 0
    assert balance(ledger) == 0


# ── the chat tool runs the paid job end to end ────────────────────────────

def test_chat_tool_executes_a_confirmed_job_and_charges(monkeypatch, tmp_path):
    import chat_tools

    ledger = cl.CreditLedger(str(tmp_path / "tool-ledger.jsonl"))
    monkeypatch.setattr(ce, "default_ledger", lambda: ledger)
    monkeypatch.setattr(chat_tools, "_CREATIVE_GENERATOR", ok_generate)
    monkeypatch.setattr(ce.creative_plan, "_PLANS", {})         # isolate the registry

    made = chat_tools.run_tool("creative_plan", {
        "request": "design a 6 oz stand-up pouch", "subscription": "mover"},
        {"account_id": "acct"})
    assert made["ok"] is True
    plan = made["data"]["plan"]

    out = chat_tools.run_tool("creative_plan",
                              {"plan_id": plan["plan_id"], "action": "draft"},
                              {"account_id": "acct"})
    assert out["ok"] is True, out
    receipt = out["data"]["receipt"]
    assert receipt["credits_charged"] == plan["options"]["draft"]["credits"]
    assert receipt["asset_ids"] == ["asset-1"]
    assert out["assets"] == [{"id": "asset-1"}]
    assert "credits charged" in out["summary"]
    assert balance(ledger) == cp.PLAN_ALLOTMENT["mover"] - receipt["credits_charged"]


def test_chat_tool_reports_a_failed_render_and_charges_nothing(monkeypatch, tmp_path):
    import chat_tools

    ledger = cl.CreditLedger(str(tmp_path / "tool-ledger2.jsonl"))
    monkeypatch.setattr(ce, "default_ledger", lambda: ledger)
    monkeypatch.setattr(chat_tools, "_CREATIVE_GENERATOR", failing_generate)
    monkeypatch.setattr(ce.creative_plan, "_PLANS", {})

    made = chat_tools.run_tool("creative_plan", {
        "request": "design a pouch", "subscription": "mover"}, {"account_id": "acct"})
    plan = made["data"]["plan"]
    out = chat_tools.run_tool("creative_plan",
                              {"plan_id": plan["plan_id"], "action": "final"},
                              {"account_id": "acct"})
    assert out["ok"] is False
    assert "No credits were charged" in out["summary"]
    assert balance(ledger) == cp.PLAN_ALLOTMENT["mover"]      # untouched
