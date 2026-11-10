"""Usage ledger / shadow billing tests (owner decision 6)."""
from __future__ import annotations

from Northstar_backend.foundation.usage import UsageLedger
from Northstar_backend.foundation.models import UsageEvent, PricingPolicy
from Northstar_backend.foundation.enums import CostKind, UsageEventStatus


def test_record_local_free(seeded_state):
    led = UsageLedger(seeded_state.repos)
    row = led.record_local_free(organization_id=seeded_state.ids["org"],
                                service="autothink", provider="ollama")
    assert row["cost_kind"] == CostKind.LOCAL_FREE.value
    assert row["credits_debited_shadow"] == 0.0
    assert row["status"] == UsageEventStatus.FINALIZED.value


def test_shadow_charge_computes_but_never_debits(seeded_state):
    led = UsageLedger(seeded_state.repos)
    charge = led.shadow_charge(service="prospector", cost_kind=CostKind.ESTIMATED.value,
                               provider_cost=1.0)
    assert charge is not None
    # no balance mutation happened
    bal = led.derived_balance(seeded_state.ids["org"], granted=100.0)
    assert bal["consumed_shadow"] == 0.0
    assert bal["debits_applied"] is False
    assert bal["label"] == "SHADOW ESTIMATE"


def test_shadow_charge_unknown_cost_is_none(seeded_state):
    led = UsageLedger(seeded_state.repos)
    assert led.shadow_charge(service="x", cost_kind=CostKind.UNKNOWN.value,
                             provider_cost=None) is None


def test_derived_balance_reflects_finalized_events(seeded_state):
    led = UsageLedger(seeded_state.repos)
    led.record(UsageEvent(organization_id=seeded_state.ids["org"], service="s",
                          credits_debited_shadow=5.0,
                          status=UsageEventStatus.FINALIZED.value))
    led.record(UsageEvent(organization_id=seeded_state.ids["org"], service="s",
                          credits_debited_shadow=3.0,
                          status=UsageEventStatus.FINALIZED.value))
    bal = led.derived_balance(seeded_state.ids["org"], granted=100.0)
    assert bal["consumed_shadow"] == 8.0
    assert bal["balance_shadow"] == 92.0


def test_idempotent_usage_event(seeded_state):
    led = UsageLedger(seeded_state.repos)
    ev = UsageEvent(organization_id=seeded_state.ids["org"], service="s",
                    idempotency_key="k1", credits_debited_shadow=2.0)
    a = led.record(ev)
    b = led.record(UsageEvent(organization_id=seeded_state.ids["org"], service="s",
                              idempotency_key="k1", credits_debited_shadow=2.0))
    assert a["id"] == b["id"]
    assert seeded_state.repos.usage.count() == 1


def test_reversal_offsets_event(seeded_state):
    led = UsageLedger(seeded_state.repos)
    row = led.record(UsageEvent(organization_id=seeded_state.ids["org"], service="s",
                                credits_debited_shadow=10.0,
                                status=UsageEventStatus.FINALIZED.value))
    led.reverse(row["id"], "provider failed")
    bal = led.derived_balance(seeded_state.ids["org"], granted=100.0)
    # original stays FINALIZED (append-only); reversal is a negative adjustment
    assert bal["consumed_shadow"] == 10.0
    assert bal["adjustments_shadow"] == -10.0
    assert bal["balance_shadow"] == 100.0  # net effect is zero
    assert bal["debits_applied"] is False