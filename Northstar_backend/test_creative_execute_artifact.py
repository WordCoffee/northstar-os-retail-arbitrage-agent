"""The creative_plan DRAFT lane must hand back a retrievable artifact.

Operator-visible failure (2026-10-23, live UI): approving a plan's draft charged
34 credits, rendered a real 1024x1024 image, and returned NO asset id or URL -
so the chat could not show it, and `apply_label` could not composite onto it
because there was no plate. Root cause: `default_generate` called the
generate_image tool with `{"account_id": None}` and no db, and that handler only
persists a studio asset when it has both.
"""
from __future__ import annotations

import creative_execute


class _FakeLedger:
    def reserve(self, *a, **k):
        return {"reservation_id": "res-1", "id": "r", "idempotency_key": "k"}

    def commit(self, *a, **k):
        return None

    def release(self, *a, **k):
        return None

    def balance(self, *a, **k):
        return 100


def test_default_generate_persists_through_the_chat_context(monkeypatch):
    seen = {}

    def fake_run_tool(name, args, ctx):
        seen["name"] = name
        seen["args"] = args
        seen["ctx"] = ctx
        return {"ok": True, "assets": [{"id": "asset-1", "kind": "image"}]}

    import chat_tools
    monkeypatch.setattr(chat_tools, "run_tool", fake_run_tool)
    db = object()
    out = creative_execute.default_generate(
        {"job": "product_shot", "quality": "draft", "request": "a pouch"},
        ctx={"db": db, "account_id": "acct-1"})
    assert out["assets"][0]["id"] == "asset-1"
    assert seen["ctx"]["db"] is db
    assert seen["ctx"]["account_id"] == "acct-1", (
        "without an account the render is never persisted as a studio asset")


def test_a_packaging_plan_renders_portrait_not_a_square(monkeypatch):
    def fake_run_tool(name, args, ctx):
        return {"ok": True, "assets": [], "args": args}

    import chat_tools
    monkeypatch.setattr(chat_tools, "run_tool", fake_run_tool)
    out = creative_execute.default_generate(
        {"job": "package_design", "quality": "draft", "request": "6 oz pouch"},
        ctx={"db": object(), "account_id": "acct-1"})
    assert out["args"]["width"] == 832 and out["args"]["height"] == 1216


def test_a_non_packaging_plan_stays_square(monkeypatch):
    def fake_run_tool(name, args, ctx):
        return {"ok": True, "assets": [], "args": args}

    import chat_tools
    monkeypatch.setattr(chat_tools, "run_tool", fake_run_tool)
    out = creative_execute.default_generate(
        {"job": "social_post", "quality": "draft", "request": "a flat lay"},
        ctx={"db": object(), "account_id": "acct-1"})
    assert out["args"]["width"] == 1024 and out["args"]["height"] == 1024


def test_the_plan_handler_passes_its_context_to_the_generator(monkeypatch):
    """The seam that made the bug: execute() got the account, the generator did not."""
    import chat_tools
    captured = {}

    def fake_execute(ledger, plan, action, *, generate, account_id, subscription=None):
        generate({"job": "product_shot", "quality": "draft", "request": "x"})
        return {"ok": True, "quality": action, "credits_charged": 0,
                "real_cost_usd": 0.0, "balance": 0, "assets": [{"id": "a1"}]}

    monkeypatch.setattr(creative_execute, "execute", fake_execute)
    monkeypatch.setattr(creative_execute, "default_ledger", lambda: _FakeLedger())
    monkeypatch.setattr(chat_tools, "_CREATIVE_GENERATOR", None)
    monkeypatch.setattr(chat_tools, "run_tool",
                        lambda n, a, c: captured.update(ctx=c) or {"ok": True, "assets": []})

    import creative_plan
    monkeypatch.setattr(creative_plan, "get", lambda pid: {"plan_id": pid, "job": "product_shot"})
    monkeypatch.setattr(creative_plan, "confirm", lambda p, a: {"ok": True, "message": "ok"})
    monkeypatch.setattr(creative_plan, "forget", lambda pid: None)

    db = object()
    chat_tools.run_tool("creative_plan",
                        {"action": "draft", "plan_id": "plan_x"},
                        {"db": db, "account_id": "acct-1"})
    assert captured["ctx"]["account_id"] == "acct-1"
    assert captured["ctx"]["db"] is db
