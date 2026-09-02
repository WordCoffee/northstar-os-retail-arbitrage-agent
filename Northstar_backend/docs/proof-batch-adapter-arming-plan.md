# Proof Batch Adapter Arming Plan

Plan for the ADAPTER-ARMING BUILD of the fixed 20-ASIN Proof Batch workflow
(T2 Holdings LLC, `Northstar_backend`). Written BEFORE any implementation
edit. This build makes the production-ready Easyparser adapter
**armed-capable** — able to be explicitly armed ONLY inside the existing
guarded Proof Batch execution path — while keeping it **disabled by
default**. It is NOT authorization for a live pull, credits, secrets, env
gates, servers, routes, or the 20-ASIN run.

- Preflight: `data/batch/proof-batch-preflight-20260818T060549Z.json`
- References: `docs/proof-batch-final-readiness-audit.md`,
  `docs/proof-batch-guarded-execution-design.md`,
  `docs/proof-batch-easyparser-live-adapter-plan.md`,
  `docs/proof-batch-live-validation-approval.md`.
- Zero network / zero live execution: this plan and the entire build are
  offline. No provider call, no credits, no `.env`, no secrets, no server.

## 0. Shared contract module rationale

`ProviderAdapter`, `GuardError`, `BindingError`, and `RunAbort` were originally
defined inside `proof_batch_run.py` and the live adapter reached them via
`import proof_batch_run as pbr`. That works only while the runner and the
adapter resolve to the *same* `proof_batch_run` module object. It breaks the
moment the class identity is not guaranteed to be unique across import paths:

- Running the runner as a script (`python proof_batch_run.py`) loads it as
  `__main__`; the adapter's `import proof_batch_run` can then import a
  *second* copy of the module (a distinct `ProviderAdapter` class object),
  so `isinstance(adapter, ProviderAdapter)` in the runner checks against a
  different class than the one `EasyparserLiveAdapter` actually subclasses.
- `importlib.reload()`, `runpy`, subprocess probes, and test-fixture module
  reloads each reproduce the double-identity failure because the alias
  protection (`sys.modules.setdefault("proof_batch_run", __main__)`) only
  fires once, on direct-script entry, and is not re-applied across reloads.

Moving these shared definitions into a new, dependency-light
`proof_batch_contracts.py` (stdlib only; never imports `proof_batch_run`,
the adapter, or any provider client) makes them a *single* set of class
objects no matter how the modules are imported or executed. Both
`proof_batch_run.py` and `proof_batch_easyparser_adapter.py` import the same
`proof_batch_contracts.ProviderAdapter` / `.GuardError` / `.BindingError` /
`.RunAbort`, so the strict `isinstance(adapter, ProviderAdapter)` guard is now
checked against the one shared base — the `__main__`/module alias is kept only
as harmless belt-and-suspenders, never as the sole identity solution. This
eliminates the duplicate class identities without weakening execution
containment (the runner still imports no provider client; the adapter still
imports no `proof_batch_run` merely to inherit or raise).

## 1. Exact current `allow_live=False` guard

`proof_batch_easyparser_adapter.py` — `EasyparserLiveAdapter.__init__`:

```python
if not self.allow_live:
    raise pbr.GuardError(
        "easyparser-live adapter is not enabled in this build (allow_live=False). "
        "No live execution is possible until a separately human-approved build "
        "enables it; no provider call was made."
    )
if not callable(self.client):
    raise pbr.GuardError(... "explicitly injected client ... never defaults to ...")
```

Construction requires BOTH `allow_live=True` AND an explicitly injected
callable `client`; the adapter never defaults to
`easyparser_client.get_easyparser_offers`. Every test injects a `FakeClient`.

`proof_batch_run.py` `_run_run` currently hardcodes the disarm:

```python
adapter = adapter_mod.EasyparserLiveAdapter(adapter_config={
    "run_id": ..., "preflight_fingerprint": ...,
    "request_budget_remaining": allowed, "credit_budget_remaining": max_credits,
    "allow_live": False,          # <-- always False in this build
})
```

So `run --live` always refuses at the adapter gate after the outer guards
pass (exit 2, "easyparser-live adapter is not enabled in this build … no
provider call was made").

## 2. Exact files and behavior being changed

| File | Change |
|---|---|
| `proof_batch_easyparser_adapter.py` | Add module constant `ADAPTER_ARMED = False` (the single explicit arming switch). When `allow_live=True` but `ADAPTER_ARMED` is falsy → `GuardError` with the SAME message substrings ("easyparser-live adapter is not enabled in this build", "no provider call was made"). `allow_live=False` path unchanged. Docstring updated. **(Later revised — see note below: the source constant was replaced by the external read-only gate `PROOF_BATCH_LIVE_ARMED=1`; the refusal message is now "easyparser-live adapter is not armed … no provider call was made".)** |
| `proof_batch_run.py` | Replace the hardcoded `allow_live: False` construction with `_arm_live_adapter(preflight, allowed, max_credits)` — called ONLY after every runner guard passes (`--live`, `SCANNER_LIVE_ALLOWED`, binding/fingerprint, finite caps, plan consistency, arbitrary-ASIN-option rejection). It passes `allow_live=True` and injects the real client (`easyparser_client.get_easyparser_offers`, lazily imported). Test-only injection hook `LIVE_CLIENT_FACTORY` (default `None`; only tests set it) supplies a fake client for offline tests. Docstring updated. |
| `test_proof_batch_easyparser_adapter.py` | `setUpModule` arms the flag (`adapter_mod.ADAPTER_ARMED = True`) so all offline fake-client tests exercise the armed capability; `tearDownModule` restores `False`. New tests: disabled-default refusal, guards-before-factory (factory never called on any missing guard), armed-CLI full offline run via `main()` with fake client + temp `RUN_OUTPUT_ROOT`, gate-off no-factory, arbitrary-ASIN rejection still precedes arming. Identity probe sets `ADAPTER_ARMED = True` (fake client injected). **(Later revised — the arming control is now the `PROOF_BATCH_LIVE_ARMED` env gate; `setUpModule` sets that env var, and identity probes set it in the subprocess env.)** |
| Docs | `docs/proof-batch-adapter-arming-plan.md` (this file), `docs/proof-batch-live-validation-approval.md`, `README.md` (command docs only). |

No other files change. No protected artifact, no `easyparser_client.py`
behavior, no `intel_schema`, `benchmark_validation`, `market_snapshot_store`,
`proof_batch.py` changes.

## 3. How the production client is constructed only after all runner guards pass

`_run_run` order (unchanged until the final construction step):

1. `_require_caps(argv)` — finite `--max-requests >= 1`, `--max-credits >= 1`
   (missing → exit 2, no construction).
2. `load_preflight(path)` — path required, exists, valid JSON, no
   secret-like keys.
3. `validate_preflight_binding(preflight)` — kind, purpose
   `provider_data_contract_validation`, run_id, exactly 20 unique valid
   ASINs, verbatim human-confirmation line, Easyparser-only plan
   (`market_offers` sole field contract, 1 request/ASIN, total 20, hard
   caps 20/20) → any error = exit 2.
4. `--live` in argv → else exit 2.
5. `live_gate.live_enabled()` (`SCANNER_LIVE_ALLOWED=1` strict opt-in) →
   else exit 2.
6. Arbitrary ASIN options (`--asin/--asins/--input-file/--discover`) →
   rejected, exit 2.
7. ONLY THEN: `_arm_live_adapter(...)` — lazy-imports
   `proof_batch_easyparser_adapter` + `easyparser_client`, builds config
   with `allow_live=True`, injects the client (real function, or the
   test-only `LIVE_CLIENT_FACTORY()` result), computes the preflight
   fingerprint, passes remaining budgets. The adapter itself refuses unless
   `ADAPTER_ARMED` is on (OFF in this build).
8. `run_guarded(...)` re-validates the full guard set (adapter isinstance +
   NAME checks, budget/plan consistency) before any fetch; every request is
   stop-before budget-checked and re-guarded by the adapter.

The real client is therefore referenced only inside step 7, which is
unreachable unless steps 1-6 all pass. No other code path in the project
constructs the adapter.

## 4. How test client injection remains mandatory for tests

- The adapter's constructor still REQUIRES an injected client; a test that
  forgets its fake fails closed at construction (unchanged).
- All offline tests construct via `_adapter(client)` with `FakeClient`
  (unchanged); transports (`requests.*`, `easyparser_client.
  get_easyparser_offers`) remain module-level patched to raise.
- New CLI-level tests arm the adapter (`ADAPTER_ARMED=True`) but route
  client construction through `proof_batch_run.LIVE_CLIENT_FACTORY`, which
  tests set to a `FakeClient` — the real `easyparser_client` function is
  never constructed/called in-process or in subprocesses.
- The identity-probe subprocess sets `ADAPTER_ARMED=True` and injects a
  fake client (probe is test-only, offline by construction).
- Production subprocess regression tests (direct script / `-m`) run with
  the production default (`ADAPTER_ARMED=False`) and keep asserting the
  clean adapter-gate refusal.

## 5. Why no provider/client construction occurs during dry-run

- `_run_dry_run` calls only: `_require_caps`, `load_preflight`,
  `validate_preflight_binding`, `preflight_fingerprint`,
  `canonical_preflight_asins`. It prints the contract and returns 0.
- It never imports `proof_batch_easyparser_adapter` or
  `easyparser_client` and never calls `_arm_live_adapter` or
  `EasyparserLiveAdapter` (test-patched to raise if touched).
- `report`/`fixture-run` paths are equally client-free (fixture uses
  `FixtureAdapter` only).
- Importing the adapter module or `easyparser_client` makes no network call
  and constructs no client (functions only).

## 6. How real credentials remain solely in the user's local runtime environment

- The adapter's injected client is the project's existing
  `easyparser_client.get_easyparser_offers`; credentials/API keys live in
  the user's local environment (`.env`/process env) and are consumed by
  that module at call time — and the adapter never calls it in this build
  (`ADAPTER_ARMED=False`).
- This task does NOT access, print, inspect, request, create, or modify
  `.env`, tokens, keys, cookies, headers, or secrets. `contains_secret_like`
  scans remain in place for every result/meta/envelope.
- No credentials are embedded in any code, config, doc, or test.

## 7. Exact future command (NOT EXECUTED)

```powershell
python proof_batch_run.py run --live --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100
```

NOT EXECUTED in this build. Before it may ever run: (a) the human sets
`SCANNER_LIVE_ALLOWED=1` in the execution environment; (b) a separately
human-approved build flips `ADAPTER_ARMED` to `True` (a visible, reviewed
code change — never an env toggle, never CLI input); (c) a finite
`max_credits` is approved (100 only if ~100 estimated credits is accepted);
(d) the run output under
`data/batch/live-validation-runs/<run_id>/` is reviewed.

## 8. Rollback behavior

- This build is additive and default-off: flipping `ADAPTER_ARMED` back to
  `False` (or reverting the two file edits) restores the exact previous
  behavior — `run --live` refuses at the adapter gate with the same
  message substrings.
- No migration, no data files, no protected artifacts, no schema changes.
- `LIVE_CLIENT_FACTORY` is test-only; production never sets it.
- All guards are re-checked on every run; a future armed run still fails
  closed on any missing/inconsistent condition.

## Shared contract module rationale

The class-identity diagnosis (narrow, no provider calls) showed that the
production guard `isinstance(adapter, ProviderAdapter)` is stable when
`proof_batch_run` is imported once — but the containment contract
(`ContainmentTests.test_module_imports_no_provider_client`) forbids the
provider-client import token in `proof_batch_run.py` source. The arming plan
therefore resolves the real client through the adapter module (which already
imports `proof_batch_run` as `pbr` for its base class) via
`adapter_mod.real_easyparser_client()`, keeping `proof_batch_run.py` free of
the `easyparser_client` import token entirely (it appears only as the lazy,
non-invoked module reference `proof_batch_easyparser_adapter`).

This deliberately does NOT introduce a separate shared-contracts module: the
existing single-sourcing of `ProviderAdapter`/`GuardError` through
`proof_batch_run` (with the `__main__` alias guard at the module bottom so
direct-script and `-m` execution share the same class identity) is proven
stable by the identity-probe regression tests, and a new module would widen
the import surface for no containment benefit. The arming change stays
additive: the only new source token is `import
proof_batch_easyparser_adapter as adapter_mod`, which is not a forbidden
provider-client token.

---

## Implementation outcome (after the build)

- `ADAPTER_ARMED = False` added to the adapter; `allow_live=True` construction
  now also requires the arming switch; refusal message substrings preserved.
- `real_easyparser_client()` added to the adapter module (lazy resolver); the
  runner never imports the provider client directly.
- `_arm_live_adapter` + `LIVE_CLIENT_FACTORY` (test-only, `None` in production)
  added to the runner; `_run_run` arms only after all guards pass; CLI behavior
  with production defaults is the same clean refusal (exit 2, no traceback,
  no provider call).
- Tests: `test_proof_batch_easyparser_adapter` + `test_proof_batch_run` +
  `test_proof_batch` = **139 OK**; full suite = **959 OK (skipped=3)**.
  Dry-run exit 0 with the full contract; production defaults verified
  (`ADAPTER_ARMED=False`, `LIVE_CLIENT_FACTORY=None`,
  `SCANNER_LIVE_ALLOWED` unset).
- Diagnostics (single import): `id(proof_batch_run.ProviderAdapter)` ==
  `id(proof_batch_contracts.ProviderAdapter)` ==
  `id(adapter_mod.ProviderAdapter)`; `isinstance(adapter, ProviderAdapter)`
  == True; and `TestSharedContractIdentity` proves the shared identity is
  stable under ordinary import AND after `importlib.reload` of both modules.
- Protected hashes before == after (12 files; absent files still absent).
- This build is armed-capable but DISABLED BY DEFAULT; a separately
  human-approved live run is still required; a passing live comparison does
  not authorize sourcing or purchases.