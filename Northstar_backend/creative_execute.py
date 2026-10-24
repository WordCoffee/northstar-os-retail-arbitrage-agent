"""Execute an approved creative plan — reserve, generate, commit or release.

The ORDER is the point:

    1. reserve credits        (fail closed when the balance is short)
    2. run the generation
    3. commit on success      /  release on failure

A crash between 1 and 2 leaves a HELD reservation that expires on its own TTL —
never a silent charge for work that did not happen. A generation that reports
``ok: False`` releases the hold and returns the real reason.

Honesty contract
----------------
* The generator is INJECTED. Tests use a fake; production wires the real
  ``generate_image`` tool handler. Nothing here pretends a render happened.
* The receipt carries the REAL model cost from ``creative_pricing`` and the credits
  actually charged — both measured, neither estimated.
* Insufficient credits refuses BEFORE the generator is called (no free work).
* Repeated execution with the same idempotency key returns the same receipt and
  never double-charges.

Alpha note: a fresh account has no credits, so ``ensure_allotment`` grants the
plan's monthly allotment once (reason ``monthly_allotment``). That is the alpha
path; real billing replaces it.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE and _HERE not in os.sys.path:
    os.sys.path.insert(0, _HERE)

import creative_plan  # noqa: E402
import credit_ledger  # noqa: E402
import creative_pricing  # noqa: E402


def ledger_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                        "credit-ledger.jsonl")


def default_ledger() -> "credit_ledger.CreditLedger":
    path = ledger_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return credit_ledger.CreditLedger(path)


def ensure_allotment(ledger, account_id: str, plan: str) -> Dict[str, Any]:
    """Grant the alpha monthly allotment once per account (idempotent)."""
    allotment = creative_pricing.PLAN_ALLOTMENT.get(plan)
    if not allotment:
        return {"granted": 0, "reason": f"unknown plan {plan!r}"}
    if ledger.balance(account_id, credit_ledger.CREATIVE):
        return {"granted": 0, "reason": "already has creative credits"}
    ledger.grant(account_id, allotment, reason="monthly_allotment",
                 class_=credit_ledger.CREATIVE,
                 idempotency_key=f"allotment:{account_id}:{plan}:creative")
    return {"granted": allotment, "reason": "monthly allotment granted (alpha)"}


def _receipt(plan: Dict[str, Any], quality: str, credits: int,
             reservation_id: Optional[str], result: Dict[str, Any]) -> Dict[str, Any]:
    quote = creative_pricing.quote(plan.get("job"), quality, plan.get("count", 1))
    return {
        "ok": True,
        "plan_id": plan.get("plan_id"),
        "job": plan.get("job"),
        "quality": quality,
        "credits_charged": credits,
        "reservation_id": reservation_id,
        "real_cost_usd": quote["real_cost_usd"],
        "margin": quote["margin"],
        "asset_ids": [a.get("id") for a in (result.get("assets") or []) if isinstance(a, dict)],
        "summary": result.get("summary") or "",
        "engine": result.get("data") or {},
    }


def execute(ledger, plan: Dict[str, Any], action: str, *, generate: Callable[[Dict[str, Any]], Dict[str, Any]],
            account_id: str, plan_id_for_allotment: Optional[str] = None,
            subscription: Optional[str] = None) -> Dict[str, Any]:
    """Run one approved job end to end. Never raises; failures are honest receipts."""
    decision = creative_plan.confirm(plan, action)
    if not decision.get("ok"):
        return {"ok": False, "stage": "confirm", "action": action,
                "error": decision.get("error") or "the choice was refused",
                "credits_charged": 0}

    quality = decision["quality"]
    credits = decision["credits"]
    reserve = decision["reserve"]

    if plan_id_for_allotment or subscription:
        ensure_allotment(ledger, account_id, plan_id_for_allotment or subscription)

    try:
        hold = ledger.reserve(account_id, credits, action=reserve["action"],
                              idempotency_key=reserve["idempotency_key"],
                              class_=credit_ledger.CREATIVE)
    except credit_ledger.InsufficientCredits as exc:
        return {"ok": False, "stage": "reserve", "action": action,
                "error": str(exc), "credits_charged": 0,
                "balance": ledger.balance(account_id, credit_ledger.CREATIVE)}

    reservation_id = hold.reservation_id
    try:
        result = generate(decision.get("instruction") or {}) or {}
    except Exception as exc:  # noqa: BLE001 - release the hold, report the truth
        ledger.release(reservation_id)
        return {"ok": False, "stage": "generate", "action": action,
                "error": f"{type(exc).__name__}: {exc}"[:300],
                "credits_charged": 0, "released": True}

    if not result.get("ok"):
        ledger.release(reservation_id)
        return {"ok": False, "stage": "generate", "action": action,
                "error": result.get("error") or result.get("summary") or "generation failed",
                "credits_charged": 0, "released": True}

    ledger.commit(reservation_id, idempotency_key=f"commit:{reserve['idempotency_key']}")
    out = _receipt(plan, quality, credits, reservation_id, result)
    out["balance"] = ledger.balance(account_id, credit_ledger.CREATIVE)
    out["assets"] = [a for a in (result.get("assets") or []) if isinstance(a, dict)]
    return out


def default_generate(instruction: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Production wiring: render through the existing generate_image tool.

    `ctx` carries the chat turn's db + account. Without it the render was made
    with ``account_id=None`` and no db, so `generate_image` skipped asset
    persistence entirely: the plan lane charged its credits, produced a real
    image and returned NO asset id or URL. The operator saw "Draft charged (34
    credits) but the plan lane returned no retrievable asset id", and the label
    pass could not run because there was no plate to composite onto.
    """
    try:
        import chat_tools
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"creative tools unavailable: {exc}"}
    job = instruction.get("job") or "product_shot"
    quality = instruction.get("quality") or "draft"
    request = instruction.get("request") or ""
    prompt = f"{request}. Style: {job.replace('_', ' ')}, {quality} quality."
    # A pouch/bottle/sachet is a PORTRAIT subject; the old fixed 1024x1024 forced
    # every packaging plan into a square framed badly for a standing pack.
    portrait = any(k in job for k in ("pack", "pouch", "product", "bottle", "carton",
                                      "label", "box"))
    width, height = (832, 1216) if portrait else (1024, 1024)
    args = {"prompt": prompt[:1800],
            "tier": "final" if quality == "final" else "draft",
            "width": width, "height": height}

    context: Dict[str, Any] = dict(ctx or {})
    if context.get("db") is None:
        # Called outside a chat turn (a job runner, a script): open the real store
        # so the artifact is still persisted and retrievable.
        try:
            from data_layer import get_northstar_db
            context["db"] = get_northstar_db()
        except Exception:  # noqa: BLE001 - a missing store must not lose the render
            pass
    if not context.get("account_id"):
        context["account_id"] = str(instruction.get("account_id") or "default")
    return chat_tools.run_tool("generate_image", args, context)
