# 08 — Provider and Job Foundation (implemented)

## Provider registry (owner decision D)

`foundation/providers.py`:

- `ProviderDefinition`: provider_key, name, category, adapter_module, read/write
  capability, sandbox support, **credential reference NAMES only**, rate limit, timeout,
  cost model, health, `enabled` (default **False**).
- `ProviderAdapter` protocol: `capabilities()`, `read()`, `write()`.
- `FixtureAdapter`: deterministic fixture observations; **never touches a network**.
- `ProviderRegistry.execute_read(key, req)`: refuses when the provider is disabled →
  `ProviderResult(ok=False, error_class="provider_disabled")`.
- `ProviderRegistry.execute_write(...)`: always returns
  `error_class="write_not_permitted"` — **no external write executes in Phase 1B**.

Reference seed registers `ollama` (local) and `fixture_price` (dev), both disabled.

## Job foundation (owner decision 4)

`foundation/jobs.py`:

- `JobRequest`: organization, user, service, scope, data_types, provider policy,
  **max_estimated_cost ceiling**, environment, **idempotency_key**, requires_approval,
  reason, priority.
- `JobRun` state machine: `requested → queued → running → succeeded | failed |
  retry_scheduled → dead_letter | cancelled`. Illegal transitions raise.
- Idempotency: `request_job` returns the existing request for a duplicate key.
- `enforce_ceiling` raises `BudgetExceeded`; `execute_fixture` runs the **local/fixture
  path only** and classifies failures (budget_exceeded / provider_error / unknown).
- Cancellation supported.

## Refresh ownership (owner decision 4)

- The job orchestrator owns refresh execution; services request a refresh via a command.
- **No normal GET route or page load initiates** provider calls, paid activity,
  background enrichment, credit consumption, or external writes (enforced by the absence
  of any such code path in GET handlers; verified by API tests).

## Evidence

- `foundation/providers.py`, `foundation/jobs.py`
- `foundation/tests/test_repositories.py` (provider tests),
  `foundation/tests/test_jobs.py` (8 tests)