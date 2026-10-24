"""The single entry point for every model/data call (blueprint §11A).

Agents call `complete(role, prompt, ctx)`. This module owns:

  • role -> provider chain resolution          (config only, never code)
  • retries with exponential backoff           (bounded, per provider)
  • fallback down the chain                    (a failure is never user-visible
                                                if a later provider answers)
  • idempotency                                (a retry never double-charges)
  • the usage ledger row for every attempt     (cost, charge, margin)

Nothing else in the codebase may call a provider directly.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from gateway import adapters, ledger, roles

MAX_ATTEMPTS_PER_PROVIDER = 2
BACKOFF_BASE_S = 0.05  # tests must not sleep for seconds

#: completed idempotency keys -> result, so a retry is free.
_RESULTS: Dict[str, Dict[str, Any]] = {}


def _key(role: str, prompt: str, ctx: Dict[str, Any]) -> str:
    seed = "|".join([role, prompt[:400], str(ctx.get("user_id")),
                     str(ctx.get("tenant_id")), str(ctx.get("job_id"))])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def estimate(role: str, prompt: str, *, plan: str = "", service: str = "") -> Dict[str, Any]:
    """Cost estimate shown BEFORE an expensive job (no provider call)."""
    tokens_in = max(1, len(prompt) // 4)
    tokens_out = max(1, tokens_in // 2)
    usage = {"tokens_in": tokens_in, "tokens_out": tokens_out, "gpu_seconds": 0.0}
    chain = roles.chain(role)
    first = chain[0]
    cost = ledger.raw_cost(first, usage)
    margin = ledger.margin_for(plan, service)
    return {"role": role, "provider": first, "chain": chain,
            "estimated_tokens_in": tokens_in, "estimated_tokens_out": tokens_out,
            "estimated_cost_usd": cost,
            "estimated_charge_usd": ledger.charge_for(cost, margin),
            "margin": margin}


def complete(role: str, prompt: str, *, ctx: Optional[Dict[str, Any]] = None,
             payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run one call through the chain. Never raises for a provider failure."""
    ctx = dict(ctx or {})
    body: Dict[str, Any] = dict(payload or {})
    body.setdefault("prompt", prompt)
    body["__role"] = role

    user_id = str(ctx.get("user_id") or "anonymous")
    tenant_id = str(ctx.get("tenant_id") or "default")
    plan = str(ctx.get("plan") or "")
    service = str(ctx.get("service") or "")
    agent = str(ctx.get("agent") or "")
    job_id = str(ctx.get("job_id") or "")

    key = _key(role, prompt, ctx)
    if key in _RESULTS:
        cached = dict(_RESULTS[key])
        cached["idempotent_replay"] = True
        return cached

    chain = roles.chain(role)
    attempts: List[Dict[str, Any]] = []
    last_error = "no provider answered"

    for provider_name in chain:
        adapter = adapters.get(provider_name)
        if adapter is None:
            attempts.append({"provider": provider_name, "error": "adapter_not_registered"})
            continue
        for attempt in range(1, MAX_ATTEMPTS_PER_PROVIDER + 1):
            out = adapter.complete(role, body)
            usage = out.get("usage") or {}
            cost = ledger.raw_cost(provider_name, usage)
            margin = ledger.margin_for(plan, service)
            projected = ledger.charge_for(cost, margin)
            cap = ledger.cap_check(user_id, projected)
            if not cap.get("ok"):
                ledger.record(user_id=user_id, tenant_id=tenant_id, role=role,
                              provider=provider_name, model=out.get("model"),
                              usage=usage, agent=agent, job_id=job_id,
                              service=service, plan=plan, ok=False,
                              idempotency_key=key, detail=f"cap:{cap.get('reason')}")
                return {"ok": False, "error": "spending_cap", "detail": cap.get("detail"),
                        "attempts": attempts, "user_visible": True}

            row = ledger.record(user_id=user_id, tenant_id=tenant_id, role=role,
                                provider=provider_name, model=out.get("model"),
                                usage=usage, agent=agent, job_id=job_id,
                                service=service, plan=plan, ok=bool(out.get("ok")),
                                idempotency_key=key, detail=out.get("error") or "")
            attempts.append({"provider": provider_name, "attempt": attempt,
                             "ok": bool(out.get("ok")), "error": out.get("error"),
                             "cost_usd": row["raw_cost_usd"],
                             "charge_usd": row["charge_usd"]})

            if out.get("ok"):
                result = {
                    "ok": True, "role": role, "provider": provider_name,
                    "model": out.get("model"), "text": out.get("text"),
                    "bytes": out.get("bytes"), "usage": usage,
                    "cost_usd": row["raw_cost_usd"], "charge_usd": row["charge_usd"],
                    "margin": row["margin"], "attempts": attempts,
                    "fell_back": provider_name != chain[0],
                }
                _RESULTS[key] = result
                return result
            last_error = str(out.get("error") or "provider failed")
            if attempt < MAX_ATTEMPTS_PER_PROVIDER:
                time.sleep(BACKOFF_BASE_S * (2 ** (attempt - 1)))

    # Every provider in the chain failed: this IS user-visible, and it is honest.
    return {"ok": False, "error": "all_providers_failed", "detail": last_error,
            "attempts": attempts, "user_visible": True}


def health() -> Dict[str, Any]:
    return {
        "roles": roles.describe(),
        "providers": adapters.registered(),
        "ledger_rows": len(ledger.read_rows()),
        "margin_default": ledger.margin_rules().get("default_margin"),
        "caps": ledger.margin_rules().get("user_caps"),
    }


def reset_idempotency() -> None:
    """Test seam: forget completed keys."""
    _RESULTS.clear()
