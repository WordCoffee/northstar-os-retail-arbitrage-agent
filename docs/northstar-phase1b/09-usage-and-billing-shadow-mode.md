# 09 — Usage and Billing (Shadow Mode)

## Shadow mode (owner decision 6)

`foundation/usage.py:UsageLedger`. Shadow mode means:

- Record metered usage and local execution.
- Record provider-reported cost (when available) and estimated cost (when delayed).
- Compute **hypothetical** credits under a versioned pricing policy.
- **Never debit** a customer's spendable balance.
- **Never block** activity based on shadow charges.
- Label all derived values `SHADOW ESTIMATE`.

## Usage event (append-only)

`UsageEvent` carries: usage_event_id, organization, user, service, workflow_run_id,
provider, model_or_endpoint, input/output units, provider_reported_cost, estimated_cost,
credits_debited_shadow, cost_kind, status (`pending|finalized|reversed|adjusted`),
**idempotency_key**, reversal_ref, environment, occurred_at, provenance.

- `record()` is idempotent on `idempotency_key`.
- `record_local_free()` records local Ollama execution at zero cost.
- `reverse()` appends a negative **ADJUSTED** entry referencing the original (originals
  are never mutated — append-only preserved).

## Pricing policy (configurable, versioned)

`PricingPolicy`: version, platform_markup, minimum_charge, service_multipliers,
free_local_execution, failed_run_charge. **Credit→USD conversion is NOT finalized**
(owner decision 6); the policy layer exists and is versioned.

## Derived balance (never a mutable field)

`derived_balance()` computes:

```
balance = granted − consumed(FINALIZED) − adjustments(ADJUSTED)
```

Returns `label: "SHADOW ESTIMATE"` and `debits_applied: false`. The API exposes this at
`GET /api/v1/foundation/usage/summary` (verified live: `debits_applied:false`).

## Evidence

- `foundation/usage.py`
- `foundation/tests/test_usage_shadow.py` (6 tests)