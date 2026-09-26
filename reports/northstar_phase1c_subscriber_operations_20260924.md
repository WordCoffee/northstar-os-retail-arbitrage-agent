# Private Beta Operations & Subscriber Rules — Completion Report

**Date:** 2026-09-24
**Prior accepted gates:** 1C-04 financial integrity, 1C-05 authorization, 1C-06 beta legal controls, master slice (private beta readiness).
**Final decision: PRIVATE_BETA_OPERATIONS_READY**

## Executive outcome
The service can now be manually operated end-to-end for an invite-only private
beta: subscriber plans with in-app entitlement visibility, a validated tester
lifecycle state machine, admin tools (grant/plan/suspend/resume/downgrade/
cancel/notes/overrides), onboarding + support with note separation, an
internal tester dashboard with safe exports, and six exportable operational
file sets. All evidence was executed on PostgreSQL/staging.

## Phases

### Phase A — Subscriber plans & in-app entitlements
Canonical tier→flags model (`billing/tiers.py`: seat_limit, max_jobs_per_month,
export_enabled, advanced_reports, support_level, override_allowed), one
centralized `EntitlementService`, atomic monthly-job counter (concurrent
attempts cannot exceed the limit — PG proof: 12 attempts vs trial limit 5 →
exactly 5 succeed, 7 denied), plan changes affect the NEXT check, role-aware
Plan & Usage view (owner full / operator usage / viewer restricted),
non-leaky denial explanations.

### Phase B — Invite issuance & tester lifecycle
Server-side lifecycle state machine (invited → onboarding → active → paused/
suspended → downgraded → cancelled/archived) with validated transitions and
append-only events (actor, prior, new, reason, timestamp, correlation).
Suspension blocks the NEXT authenticated request (platform admins exempt).
Invite issue/reissue/expire/revoke/accept; non-enumerating denials.

### Phase C — Admin tools
Grant/approve, assign/change plan/cohort, suspend, resume, downgrade, cancel,
archive, internal notes (never exposed to testers), audit-linked history,
temporary entitlement overrides (reason/actor/scope/expiry/permanent) with
correct expiry. All platform-admin role-protected + audited; cross-org 404s.

### Phase D — Onboarding pack & support
Onboarding pack (welcome, task script, FAQ, support/contact, expectations);
support tickets with reference IDs, categories, severities, statuses, and
tester-visible vs internal note separation; no attachments (safe-upload not
proven); testers see only their own org's tickets.

### Phase E — Internal tester dashboard
List/detail with filters (state, tier, invite status, onboarding incomplete,
nearing limit, suspended, severity) and sort; lifecycle history; safe export
CSV (excludes secrets/cards/tokens/provider credentials/unauthorized org data
— hard-checked).

### Phase F — Exportable files & private-test checklist
Six files under `docs/northstar-phase1c/operations/` + a staging-backed sample
export + the private-test readiness checklist **verified all_pass=True**
against a fully-exercised staged subscriber.

## Mandatory end-to-end acceptance evidence
- **Staging smoke 31/31**, item 31 = the full subscriber-ops E2E: admin
  approves org → invite → owner signs up → legal acceptance → onboarding →
  plan visible → usage within limits → over-limit denial explained (plan view
  shows usage) → support ticket submitted → admin triage/note → admin
  downgrade+suspend → next request blocked → dashboard + export show final
  state (suspended/free) → audit correlated.
- **PG E2E** (`test_integrated_private_beta_operations_e2e`) with audit-chain
  assertion for every step.

## Test totals (by suite, all executed)
- SQLite foundation: **633 passed / 58 skipped** (58 = PostgreSQL-only modules).
- Disposable PostgreSQL: **58 passed** (financial 4, durable 6, integration 13,
  concurrency 9, authorization 4, beta 6, private-beta 7, subscriber-ops 9).
- Migration harness (001–007): **9/9 PASS**.
- Staging smoke: **31/31 PASS**.

## Migration status
`001 → … → 007` (007 = private beta operations), checksums in
`staging-migration-package.json`. **007 applied to staging with a verified
backup** (`staging-007-apply-report.json`, 485,039-byte dump). Rollback
prepared, **NOT executed**.

## Changed files (this workstream)
Added: `foundation/operations/{__init__,lifecycle,admin,support,dashboard,plan}.py`,
`migrations_foundation/007_private_beta_operations.sql` + rollback,
`foundation/tests/test_subscriber_operations.py` (12),
`test_subscriber_operations_postgres.py` (9),
`tools/staging_apply_007.py`, `tools/gen_operations_files.py`,
`docs/northstar-phase1c/operations/*` (6 file sets + sample export + checklist),
`reports/northstar_phase1c_subscriber_operations_20260924.md`.
Modified: `foundation/{db.py, models.py, repositories.py, audit.py, billing/tiers.py,
billing/entitlements.py, billing/service.py, billing/signup.py, api/state.py,
api/deps.py, api/router.py}`, `001_foundation.sql` (regenerated), migration
harness, `tools/staging_smoke.py`, `docs/northstar-phase1c/*`,
`staging-migration-package.json`.

## Staging evidence paths
- `staging-smoke-report.json` (31/31), `staging-007-apply-report.json`
- `operations/tester-status-report-sample.csv` (staging-backed, 29 rows)
- `operations/private-test-checklist-verification.json` (all_pass True)
- `reports/northstar_phase1c_subscriber_operations_20260924.md`

## Exported file / report paths
- `docs/northstar-phase1c/operations/subscriber-rules-matrix.md`
- `docs/northstar-phase1c/operations/private-beta-operator-runbook.md`
- `docs/northstar-phase1c/operations/tester-onboarding-checklist.md`
- `docs/northstar-phase1c/operations/tester-feedback-triage-guide.md`
- `docs/northstar-phase1c/operations/private-test-readiness-checklist.md`
- `docs/northstar-phase1c/operations/tester-status-report-sample.csv`

## Known gaps
- **Blocking (owner-authorized only, by design):** live payment keys, live
  providers, public self-serve signup, production provisioning.
- **Non-blocking:** secure file-upload attachments not exposed (not yet
  proven); no incident deputy (single operator); business-data retention
  UNKNOWN until reviewed per customer; provider definitions remain global.

## Restart manifest
`docs/northstar-phase1c/restart-manifest.md` updated.

## Decision
**PRIVATE_BETA_OPERATIONS_READY** — every mandatory evidence item was executed
and preserved on PostgreSQL/staging; no item was missing, partial, unexecuted,
or simulated without disclosure. Null-first semantics, no live providers, no
production access, no public signup, no real card data, no autonomous rollback,
and no committed secrets maintained throughout.