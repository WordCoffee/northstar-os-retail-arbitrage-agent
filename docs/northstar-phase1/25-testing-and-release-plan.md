# 25 — Testing and Release Plan

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Test strategy (from Phase 0 `10` baseline)

| Layer | Tooling | Coverage targets |
|---|---|---|
| Unit (backend) | pytest (existing 2,368+25 fns; extend) | domain modules, fee/economics formulas, identity, normalization, scoring |
| Integration (API) | FastAPI TestClient (existing pattern) | endpoints + auth + modes + gates |
| Contract | OpenAPI schema validation; existing `.cjs` contracts evolve | new `/api/v1/*` + legacy envelope |
| Component (frontend) | Vitest + React Testing Library (ADD — Phase 0 R6 gap) | pages, components, API client |
| E2E | Playwright (add) | canonical flows: login → hub → service → approval |
| Visual regression | Playwright screenshots + design-token drift guard (reuse `test_ui_display.cjs` pattern) | design system |
| Accessibility | axe-core (add) | WCAG AA per route |
| Data quality | migration dry-run reconciliation, provenance completeness | canonical model |
| Formula | golden-parameter tests (fee/ACoS/margin single source) | economics |
| Provider/sandbox | mock harnesses; provider budget guards; never real calls in CI | provider adapters |
| Security | authN/authZ tests, mode/preview guards, credential-hygiene scan | security |

## 2. Test commands (proposed; NOT run — require approval)

- Backend: `cd Northstar_backend && python -m pytest -q -p no:cacheprovider` (offline, network-blocked by `sitecustomize`/`network_guard`, env-scrubbed by `conftest.py`).
- Frontend: `cd northstar-os-ui && npm test` (after Vitest added in Phase 1B).
- Runner: extend `scripts/run_all_tests.ps1` to include new suites + the previously omitted autothink tests (Phase 0 finding).

## 3. Testing rules (Phase 0 constraints preserved)

- No test may make a provider call, write production data, or consume real credits (network guard + env scrub enforced).
- Dangerous files (`tools/test_chrome.py` hardcoded creds; `test_scavio.py` live `__main__`) fixed/removed before CI (Phase 0 R16/R18).
- React SPA gets a framework in Phase 1B (Phase 0 R6).

## 4. Release plan

| Stage | Activity | Gates |
|---|---|---|
| Local | unit/integration green; design-token drift guard | baseline match |
| Sandbox | run all services in sandbox mode; mock providers; preview validation | sandbox-only writes; no external calls |
| Controlled live reads | Level-3 reads within approved envelopes (§3.2) with budget + audit | budget reconciled |
| Controlled live writes | Level-4 writes with previews/confirmations (listing/ads/social) | approvals + audit + rollback plan |
| Staging | Postgres apply to staging; migration dry-run + reconciliation | acceptance thresholds |
| Production rollout | canonical endpoints live; legacy compat views active | equivalence verified |
| Rollback | `ROLLBACK_DRILL` pattern; data rollback for staging/canonical | drill passed |

## 5. Migration release

- M1–M6 jobs with `--dry-run` + reconciliation reports; promotion is flag-gated; rollback documented (`03`).
- Legacy read compatibility views until cutover.

## 6. Observability gates

- Error-rate alerting (extend `error_alerts.py`); provider budget alerts; usage run-rate alerts.
- No release if error-rate/5xx thresholds exceeded.

## 7. What this resolves

- Phase 0 R6 (SPA untested), R16 (test creds), R18 (scavio foot-gun), `10` gaps (autothink tests excluded from runner, no e2e/a11y/visual).
