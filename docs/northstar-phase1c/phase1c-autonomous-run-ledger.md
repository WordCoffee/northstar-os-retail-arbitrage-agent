# Phase 1C Autonomous Run Ledger

**Authorization:** Phase 1C Local Production-Candidate Sprint (2026-09-24)
**Target designation:** `LOCAL_PRODUCTION_CANDIDATE` (not production-deployed)
**Branch/HEAD at start:** `main` / `ecef24a`

## Baseline (pre-flight, reconfirmed)

| Item | Value |
|---|---|
| Git branch / HEAD | `main` / `ecef24a` |
| Working tree | large pre-existing owner/generated changes (25 modified incl. `package-lock.json`; 381 untracked) |
| Foundation suite (SQLite) | 172 passed, 13 skipped |
| Faire economics module | present (temporary/non-canonical) → converted to adapter |
| Formula sites (py defs) | 12 defs across fee_engine/fee_calculator/pricing/finance/unit_economics/enricher/ad_pilot/word_coffee/product_analysis/scanner_data/GG |
| Commits | none (mixed owner changes; clean change manifest preserved per git rules) |

## Stages

### 1C-03 — Canonical Economics Engine — **PASS**

| Field | Value |
|---|---|
| Start/end | 2026-09-24 (single session) |
| Files added | `foundation/economics/{__init__,enums,money,inputs,outputs,engine,readiness,compatibility,benchmarks,versions}.py`; `foundation/tests/test_economics.py` |
| Files modified | `faire_research/economics.py` (authoritative math → canonical adapter) |
| Tests run | `pytest foundation/tests/test_economics.py` → 30 passed; `pytest foundation/tests` → 202 passed, 13 skipped; `pytest faire_research/tests` → 45 passed |
| Failures | 2 (multipack landed-cost scaling; legacy adapter implicit free ads) — both fixed (production logic + explicit test contract) |
| Gate result | **PASS** (one authoritative engine; Decimal; null-first; names unambiguous; Faire adapter; golden tests pass) |
| Remaining risks | consumer migration partial (adapters provided; legacy sites not all rewired); 1C-R2 staging pending |
| Evidence state | RUNTIME_CONFIRMED (tests executed) |

### 1C-04 — Durable Worker & Scheduler — **NOT STARTED**
### 1C-05 — Keyword/SEO Intelligence — **NOT STARTED**
### 1C-06 — Frontend Serving — **NOT STARTED**

Reason: this session's budget delivered 1C-03 rigorously (code + full tests + docs).
1C-04/05/06 require substantial new subsystems (Postgres-backed worker with parallel
race tests; keyword graph + importers; frontend serving) and are left for the next
authorized session so each can be implemented and tested to its gate rather than
partially and unsafely.

### Cross-phase local testing — **PARTIAL** (SQLite + Faire + economics only)

## Completion level

**PARTIAL** — 1C-03 passed; 1C-04/05/06 not started. Not yet `LOCAL_PRODUCTION_CANDIDATE`.

## Safety confirmations

- No staging/production database contacted; no provider call; no marketplace write;
  no deployment; no commit/push; Faire MODE 2 not started; `.env` ignored; AGENTS.md,
  constitution, Phase 0/1A/1B untouched.
## 1C-LC continuation run (2026-09-25) — COMPLETE

- Workstream B (1C-04): PASSED (B01–B16). Durable execution: state machine,
  additive migrations (PG-validated), authenticated submission, atomic claim,
  worker, leases, rechecks, Decimal usage, retry/cancel/dead-letter/recovery,
  concurrency, scheduler.
- Workstream C (1C-05): PASSED (C01–C11). Keyword/SEO schema, normalization,
  source registry, import pipeline, isolation, contracts, APIs.
- Workstream D (1C-06): PASSED (D01–D15). Canonical React UI served by FastAPI;
  real auth; Jobs/Schedules + Keywords UIs; pinned drawer; tours; security.
- Workstream E: LOCAL_PRODUCTION_CANDIDATE (loopback stack, e2e 37, restart
  recovery, security/accessibility/perf).
- Workstream F: STAGING_READY documentation (migration package, backup/rollback,
  smoke plan, secret names, monitoring, owner inputs). No staging contact.
- Totals: SQLite 574/28 skipped; PG 28; harness 9/9; e2e 37; frontend 30; security/perf 13.
- Safety: no staging/production DB, no provider/marketplace/Ads/social/supplier
  call or write, no deployment, no commit/push/merge. Temp local secrets cleaned.

## Staging provisioning run (owner authorization 2026-09-24) — COMPLETE

- Verified no staging PostgreSQL existed (read-only).
- Provisioned a local Docker-based staging box (postgres:15, loopback
  127.0.0.1:55433, db northstar_staging) — $0 cost; upgradeable to managed via
  connection-string change.
- Stood up the minimal encrypted secret vault (AES-256-GCM, key outside repo);
  staging DB password stored encrypted; no secret values committed/logged.
- Preflight + verified backup + applied 001/002/003 (41 tables/424 columns).
- Staging smoke 26/26 PASS (F03 plan).
- Rollback scripts prepared but NOT executed (Tyrone sole rollback authority).
- Fixed a PG boolean-literal defect found during smoke (preview_end, schedule
  archive); SQLite suite re-verified 574 passed / 28 skipped.
- Evidence: reports/northstar_phase1c_staging_20260924.md,
  docs/northstar-phase1c/{staging-provision-report,staging-smoke-report,
  postgres-staging-readiness,staging-migration-package}.json.

## Financial-integrity gate (owner-prioritized, 2026-09-24) — PASSED

- Idempotent submission scoped to (organization_id, job_type, idempotency_key)
  via migration 004; concurrent duplicate submissions return the ORIGINAL job/
  result (6-caller PG proof).
- Exactly-once settlement: DB-level unique `settle:{run}:{attempt}` + single
  transaction; failed/cancelled/unknown-result jobs never settle; double-settle
  attempt is a no-op.
- Audit: audit_events.correlation_id added; every transition append-only and
  correlated by request/job/actor/timestamp.
- Staging: 004 applied with a verified backup (94,789-byte dump); smoke 27/27
  including the financial chain (request -> job ece8ac3a -> succeeded -> one
  settle entry -> 7 correlated audit events).
- Suites: SQLite 582/32 skipped; PG 32; harness 9/9; financial proofs green.
- No provider calls, no production access, no public exposure, no autonomous
  rollback (Tyrone sole rollback authority).

## 1C-05 authorization + data boundaries (2026-09-24) — PASSED

- 1C-04 accepted PASSED; financial-integrity + staging evidence preserved.
- Permission matrix: viewer strictly read-only; blocked from billing/ledger,
  provider config, approval queue, audit. Operator+ granted view_ledger/
  view_providers/view_approvals.
- Server-derived org/actor on every endpoint; no client-controlled org field.
- Non-enumerating cross-org denial (404) across job status/results/cancel/
  retry/audit/usage/ledger; fixed cancel/retry not_found 403->404.
- Mass-assignment: explicit allowlists; privileged/financial/secret/audit
  fields ignored (proven by test).
- Denied attempts audited (authz.denied) without sensitive data.
- Evidence: SQLite 594/32; PG 36; staging smoke 28/28 (two orgs, two roles).
- Safety: no provider enablement, no production access, no public exposure,
  no autonomous rollback, no commits.

## 1C-06 Lean B2B beta launch controls (2026-09-24) — PASSED

- Versioned beta documents (Privacy/ToS/AUP) + mandatory acceptance (business
  use + 18+) with deny-until-accepted enforcement and append-only records.
- Data inventory (16), retention/deletion (17), incident runbook (18),
  beta-status (19) internal records.
- Migration 005 applied to staging with a verified backup; staging smoke 29/29.
- Evidence: SQLite 605/42; PG 42; harness 9/9; beta tests 11 + 6 (PG).
- Safety: no production provisioning, no provider activation, no public
  exposure, no payment-card handling, no customer marketplace credentials, no
  autonomous rollback, no commits, no secret logging.

## Master slice: private beta readiness (2026-09-24) — PRIVATE_TEST_READY

- Phase A: test-mode redirect billing, exactly-once webhook settlement.
- Phase B: tiers + centralized entitlements (explicit free limits, revoke-on-next-check).
- Phase C: invite-gated access (closed default, non-revealing, immediate suspend).
- Phase D: file sets + private-beta addendum.
- Phase E: integrated E2E (staging smoke 30/30).
- Evidence: SQLite 621/49; PG 49; harness 9/9; staging 006 applied with backup.
- Safety: no production, no live providers, no real card data, no public
  signup, no autonomous rollback, no commits, no secret logging.

## Phase 1C UI wiring & private beta experience (2026-09-24) — LOCAL_PRIVATE_BETA_UI_READY

- Added BetaTester/BetaOps/BetaSignup pages + role-aware nav + suspended screen.
- Added local_bootstrap_admin (loopback-only, audited); stack auto-migrates a
  dedicated UI PG and publishes legal docs (gate active).
- Browser E2E a-e validated (screenshots in reports/ui-evidence/).
- Fixed: onboarding/complete bool (PG), admin lifecycle on uninitialized orgs,
  plan change without subscription, org_entitlements PK race.
- Regression: SQLite 633/58; PG 58; harness 9/9; staging smoke 31/31.
- Safety: no production/live/real keys; no public signup; no autonomous
  rollback; no commits; no secret logging.

## Local legacy-UI cutoff (2026-09-24) — PASS

- Added public /ui-mode endpoint + ui_mode on /environment; local stack forces
  private_beta. React shell branches: beta-only routes + legacy tombstone +
  role-aware default landing + beta-only sidebar (Dock/Pinned hidden).
- Browser verified: admin /ui->#/beta-ops, tester /ui->#/beta, signed-out
  /ui->#/beta-signup, #/ledger->tombstone, sidebar beta-only.
- Tests: environment ui_mode contract + bundle markers (frontend gate).
- Regression: SQLite 635/58; PG 58; harness 9/9.
