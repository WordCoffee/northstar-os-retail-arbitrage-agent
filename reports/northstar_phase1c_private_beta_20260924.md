# 1C-06 Master Slice — Complete Private Beta Readiness — Gate Report

**Date:** 2026-09-24
**Prior gates:** 1C-04 (financial integrity), 1C-05 (authorization), 1C-06 (beta legal controls) — all ACCEPTED PASSED.
**Final decision: PRIVATE_TEST_READY** — with reasons below (PostgreSQL/staging evidence).

## Phases

### Phase A — Billing (test-mode only) — PASS
- Redirect-based hosted checkout (a hosted page; **no embedded card fields, no card data**).
- Stores ONLY processor customer/subscription/price IDs + status.
- Webhook-driven settlement reusing the existing exactly-once ledger pattern,
  keyed on the processor event ID (`billing_events.processor_event_id` UNIQUE +
  `usage_events.idempotency_key=billing:{event_id}` UNIQUE), with HMAC signature
  verification (bad signature → 400 `invalid_signature`).
- Billing endpoints restricted to **owner role only** (operator → 403).
- Concurrency: 6 concurrent duplicate webhooks → exactly one `processed`,
  five `already_processed`, one ledger entry (PG, real threads).

### Phase B — Subscriber Tiers & Entitlements — PASS
- `billing/tiers.py` single mapping tier → atomic flags
  (`max_jobs_per_month`, `export_enabled`, `advanced_reports`, `seat_limit`).
- One centralized `EntitlementService`; no hardcoded plan checks anywhere.
- Free tier has explicit, enforced limits (max_jobs=1000/month etc.).
- Downgrade / cancellation / non-payment **revokes gated features on the next
  entitlement check** (not just next login).
- Over-tier job submission → 403 `entitlement_denied` (non-revealing).

### Phase C — Invite-Gated Private Access — PASS
- Default closed. Admin-managed invite/approved-email allowlist required at signup.
- Uninvited/revoked/expired/used/wrong-email attempts → identical 403
  `signup_denied` (no confirmation of email/org existence).
- Admin can revoke an invite (blocks new signup) or suspend an account
  (membership → suspended) which **immediately blocks future authenticated
  requests** (membership status enforced per request).
- Cross-org isolation: org B cannot revoke/list org A's invites (404/absent).

### Phase D — File Sets & Document Finalization — PASS
- Subscriber file sets served publicly: onboarding/setup guide, FAQ,
  support/contact (versioned v1.0, conservative language).
- New **Private Beta Addendum** legal document (invite-only status, trial/tier
  limits, billing test-mode disclosure) — versioned and part of acceptance;
  any revision triggers re-acceptance (existing mechanism).
- Legal docs remain versioned; re-acceptance triggers on revision.

### Phase E — Integrated End-to-End Private Test Validation — PASS
Staging smoke **30/30** (item 30) + `test_private_beta_postgres.py::test_integrated_private_beta_scenario`:
admin invite → invited user signs up → accepts 4 legal documents → subscribes via
test-mode hosted checkout → webhook settles → trial tier grants features →
operates within tier (5 jobs) → 6th over-tier blocked (403, non-revealing) →
admin revokes invite + cancels subscription → entitlement downgrades to free →
full audit trail correlated (`signup.accepted`, `legal.acceptance`,
`billing.subscription.settled`, `billing.subscription.cancel`, `invite.issue`,
`invite.revoke`).

## Required evidence (all executed)

| Proof | Where | Result |
|---|---|---|
| Concurrent/duplicate webhook safety | `test_webhook_concurrent_duplicate_single_settlement` (PG) + SQLite duplicate-delivery | PASS |
| Cross-org isolation (billing, invites, signup) | `test_billing_owner_only_and_cross_org`, `test_signup_non_revealing_and_invite_flow` (PG) | PASS |
| Role restriction (billing owner-only; invites owner-only) | SQLite + PG | PASS |
| Non-enumerating denial (signup, over-tier) | SQLite + PG | PASS |
| Single integrated E2E | staging smoke item 30 + PG scenario | PASS |
| Data-inventory / acceptance / incident evidence (prior gates) | unchanged, preserved | PASS |

## Totals
- SQLite foundation: **621 passed / 49 skipped** (49 = PostgreSQL-only modules).
- Disposable PostgreSQL: **49 passed** (financial 4, durable 6, integration 13,
  concurrency 9, authorization 4, beta 6, private-beta 7).
- Migration harness (001–006): **9/9 PASS**.
- Staging smoke: **30/30 PASS** (includes beta acceptance/access-denial + master-slice E2E).

## Migration status
`001 → 002 → 003 → 004 → 005 → 006` (006 = private beta readiness), checksums in
`staging-migration-package.json`. **006 applied to staging with a verified
backup** (`staging-006-apply-report.json`, 304,476-byte dump). Rollback prepared,
**NOT executed**.

## Changed files (master slice)
Added: `foundation/billing/{__init__,tiers,entitlements,processor,service,signup}.py`,
`migrations_foundation/006_private_beta_readiness.sql` + rollback,
`foundation/beta/filesets.py` (+ addendum in `documents.py`),
`foundation/tests/test_private_beta.py` (16), `test_private_beta_postgres.py` (7),
`tools/staging_apply_006.py`, `reports/northstar_phase1c_private_beta_20260924.md`.
Modified: `foundation/{db.py, models.py, repositories.py, api/state.py, api/router.py,
jobs_durable.py}`, `001_foundation.sql` (regenerated), migration harness,
`tools/staging_smoke.py`, `docs/northstar-phase1c/*`, `staging-migration-package.json`,
beta tests (4-doc acceptance).

## Known gaps
- Real payment keys / live provider activation not enabled (require explicit
  owner authorization). Public self-serve signup disabled. Provider definitions
  remain global. Business-data retention UNKNOWN until reviewed per customer.

## Controls maintained
Null-first unknown semantics; no live providers; no production access; no public
unrestricted signup; no real card data; no autonomous rollback; no committed
secrets; financial-integrity and authorization tests preserved and green.

## Why PRIVATE_TEST_READY (not BLOCKED)
All five phases passed with PostgreSQL evidence; the integrated E2E passed on
staging; no unresolved blocking issue remains. The ONLY outstanding items are
explicitly owner-authorized future steps (live keys/providers/public signup),
which are out of scope by design. Decision: **PRIVATE_TEST_READY**.