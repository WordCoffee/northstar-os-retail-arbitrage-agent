"""Usage events + shadow pricing + derived balance projection.

SHADOW MODE (owner decision 6): record usage, compute hypothetical credits, but
NEVER debit a customer's spendable balance and NEVER block activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import UsageEventStatus, CostKind, Environment
from .models import UsageEvent, PricingPolicy, utcnow
from .repositories import Repositories

_SHADOW_LABEL = "SHADOW ESTIMATE"


@dataclass
class ShadowChargeResult:
    usage_event_id: str
    credits_debited_shadow: Optional[float]
    label: str = _SHADOW_LABEL


class UsageLedger:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def record(self, event: UsageEvent) -> dict:
        # Idempotency on idempotency_key.
        if event.idempotency_key:
            found = self.repos.usage.find({"idempotency_key": event.idempotency_key})
            if found:
                return found
        return self.repos.usage.add(event)

    def record_local_free(self, *, organization_id: str, service: str,
                          workflow_run_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          provider: str = "ollama",
                          model_or_endpoint: Optional[str] = None,
                          environment: str = Environment.PRODUCTION.value) -> dict:
        ev = UsageEvent(
            organization_id=organization_id, user_id=user_id, service=service,
            workflow_run_id=workflow_run_id, provider=provider,
            model_or_endpoint=model_or_endpoint,
            provider_reported_cost=0.0, estimated_cost=0.0,
            credits_debited_shadow=0.0, cost_kind=CostKind.LOCAL_FREE.value,
            status=UsageEventStatus.FINALIZED.value, environment=environment,
            provenance={"note": "local execution; free by policy"},
        )
        return self.record(ev)

    # -- shadow pricing --------------------------------------------------------

    def effective_policy(self) -> PricingPolicy:
        row = self.repos.pricing.latest()
        if not row:
            policy = PricingPolicy()
            self.repos.pricing.add(policy)
            return policy
        mults = row.get("service_multipliers")
        if isinstance(mults, str):
            import json
            try:
                mults = json.loads(mults) if mults else {}
            except (ValueError, TypeError):
                mults = {}
        return PricingPolicy(
            version=row["version"],
            platform_markup=row.get("platform_markup") or 0.0,
            minimum_charge=row.get("minimum_charge") or 0.0,
            service_multipliers=mults or {},
            free_local_execution=bool(row.get("free_local_execution")),
            failed_run_charge=bool(row.get("failed_run_charge")),
        )

    def shadow_charge(self, *, service: str, cost_kind: str,
                      provider_cost: Optional[float]) -> Optional[float]:
        """Compute hypothetical credits. Never debits. Returns None when unknown."""
        policy = self.effective_policy()
        if cost_kind == CostKind.LOCAL_FREE.value and policy.free_local_execution:
            return 0.0
        if provider_cost is None:
            return None  # unknown, not zero
        base = provider_cost * (1.0 + policy.platform_markup)
        mult = float(policy.service_multipliers.get(service, 1.0))
        charge = base * mult
        return max(charge, policy.minimum_charge)

    def derived_balance(self, organization_id: str, *,
                        granted: float = 0.0) -> dict:
        """Balance = granted - consumed - adjustments (all SHADOW).

        consumed  = sum of FINALIZED event debits
        adjustments = signed corrections (negative offsets a reversal)
        Reversals are represented as ADJUSTED entries with a negative value and a
        `reversal_ref` to the original event (append-only; originals are never
        mutated). Explicitly a shadow projection; never a spendable balance."""
        events = self.repos.usage.for_org(organization_id)
        consumed = 0.0
        adjustments = 0.0
        for e in events:
            val = e.get("credits_debited_shadow") or 0.0
            if e["status"] == UsageEventStatus.FINALIZED.value:
                consumed += val
            elif e["status"] == UsageEventStatus.ADJUSTED.value:
                adjustments += val
        return {
            "organization_id": organization_id,
            "granted": granted,
            "consumed_shadow": round(consumed, 6),
            "adjustments_shadow": round(adjustments, 6),
            "balance_shadow": round(granted - consumed - adjustments, 6),
            "label": _SHADOW_LABEL,
            "debits_applied": False,
        }

    def reverse(self, usage_event_id: str, reason: str) -> dict:
        ev = self.repos.usage.get(usage_event_id)
        if ev is None:
            raise ValueError(f"unknown usage event {usage_event_id}")
        reversal = UsageEvent(
            organization_id=ev["organization_id"], user_id=ev.get("user_id"),
            service=ev["service"], provider=ev.get("provider"),
            model_or_endpoint=ev.get("model_or_endpoint"),
            credits_debited_shadow=-(ev.get("credits_debited_shadow") or 0.0),
            cost_kind=ev.get("cost_kind") or CostKind.UNKNOWN.value,
            status=UsageEventStatus.ADJUSTED.value,
            reversal_ref=usage_event_id,
            environment=ev.get("environment"),
            provenance={"reason": reason, "reverses": usage_event_id},
        )
        return self.repos.usage.add(reversal)