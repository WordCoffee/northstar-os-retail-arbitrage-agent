# Phase 1C UI Wiring & Private Beta Experience — Completion Report

**Date:** 2026-09-24
**Prior accepted gates:** 1C-04 financial, 1C-05 authorization, 1C-06 beta controls, master slice, subscriber operations.
**Final decision: LOCAL_PRIVATE_BETA_UI_READY**

## Executive outcome
The already-tested private-beta backend is now a usable browser experience at
`http://127.0.0.1:8001/ui` (the canonical React UI): a tester/owner area
(onboarding, plan & usage, seats, support, account status), a platform-admin
Beta Operations area (dashboard, filters, org control, notes, overrides,
export), an invite-gated signup entry, and a suspended-account screen with a
support pathway. All flows were validated through the browser (not merely by
direct API calls).

## What was delivered

### Tester / organization-owner views
- Onboarding checklist + completion state.
- Current plan/cohort + entitlement visibility (export/advanced reports/
  override flags).
- Usage meter (used / max, % of monthly allowance, period reset rule).
- Seat usage (used / cap).
- Invite acceptance / signup entry flow (BetaSignup).
- Support ticket submission + history + tester-visible replies only.
- Account/lifecycle status with plain-language explanations for
  invited/onboarding/active/paused/suspended/downgraded/cancelled/archived.
- Legal-document acceptance status + re-acceptance after revision (the 1C-06
  gate is ACTIVE in the local stack — documents are published at startup).

### Internal platform-admin views
- Protected Beta Operations dashboard (cohort count, org list/detail).
- Org detail: owner, invite status, legal acceptance, onboarding, plan/cohort,
  usage, seats, subscription/test state, lifecycle, last activity, tickets.
- Filters (state, tier, invite status, onboarding, nearing-limit, suspended,
  severity) and sorting.
- Grant, plan change, downgrade, suspend, resume, cancel/archive, temporary
  override, and internal annotation actions.
- Audit-linked lifecycle history + internal notes.
- Safe CSV export action.
- Internal notes / secrets / provider identifiers / tokens / cross-org data are
  never exposed to testers (verified in the browser).

### Navigation & access
- Role-aware navigation: tester/owner sees the "Private Beta" group;
  platform admins see the "Beta Operations" group. Unauthorized users get the
  existing safe RouteGuard (no hidden controls as security).
- UI wires ONLY to the existing Phase 1C API routes (no duplicated/weakened
  backend logic).

### UX
- Obvious next actions (accept documents, complete onboarding, submit ticket).
- Loading/empty/error states; safe plain-language denial explanations;
  suspended account-status screen with a support pathway.

### Admin bootstrap (local testing)
- `python -m Northstar_backend.tools.local_bootstrap_admin --email admin@local.test`
  — loopback/disposable-PG only (refuses any non-loopback target), creates an
  auditable `internal_platform_admin` identity, records legal acceptance, and
  issues a token. Not an exposed production route.

## Browser E2E (validated live on 127.0.0.1:8001)
- a. invited owner signs up (BetaSignup) → accepts documents → completes
     onboarding → sees plan & usage → submits a support ticket (NS-FDE297B9).
- b. admin sees the tester → changes plan (trial) → adds internal note →
     suspends the organization.
- c. tester's next request shows the "Account suspended" screen and cannot
     access features.
- d. tester cannot see internal notes, admin functions, another org, or the
     CSV data (all verified negative in the browser).
- e. admin exports the safe tester-status CSV (suspended/trial/used/done/1
     ticket; no secrets/notes/tokens/card fields).

Evidence screenshots: `reports/ui-evidence/01..07` and the final export
`reports/ui-evidence/tester-status-export-final.csv`.

## Fixes made during the sprint (real product fixes)
- `/onboarding/complete` booleans on PostgreSQL (DatatypeMismatch).
- Admin lifecycle actions now work on uninitialized orgs (set_state).
- Admin plan change works without a subscription (creates an assigned
  subscription row).
- `entitlements_for_org` org_entitlements PK race (insert_ignore).
- Local stack now auto-migrates its DB and publishes legal documents (gate
  active); `local_bootstrap_admin` accepts the UI disposable port.

## Regression suites (all executed, green)
- SQLite foundation: **633 passed / 58 skipped**.
- Disposable PostgreSQL: **58 passed** (financial 4, durable 6, integration 13,
  concurrency 9, authorization 4, beta 6, private-beta 7, subscriber-ops 9).
- Migration harness (001–007): **9/9 PASS**.
- Staging smoke: **31/31 PASS**.

## Migration status
Migration set remains `001 → … → 007` (007 = private beta operations);
checksums in `staging-migration-package.json`. Staging applied through 007 with
verified backups. No new migration in this UI sprint.

## Changed files
Added: `northstar-os-ui/src/foundation/pages/{BetaTester,BetaOps,BetaSignup}.jsx`,
`Northstar_backend/tools/local_bootstrap_admin.py`,
`reports/ui-evidence/` (7 screenshots + final CSV),
`reports/northstar_phase1c_ui_wiring_20260924.md`.
Modified: `northstar-os-ui/src/{App.jsx, foundation/api.js, foundation/session.jsx, data/services.js}`,
`Northstar_backend/tools/local_production_stack.py`, `local_bootstrap_admin.py`
(port allowlist), `foundation/operations/admin.py`, `foundation/operations/support.py`,
`foundation/billing/entitlements.py`, `foundation/local_stack.py`,
`docs/northstar-phase1c/*`.

## Evidence paths
- `reports/ui-evidence/` (browser screenshots 01–07 + `tester-status-export-final.csv`)
- `reports/northstar_phase1c_ui_wiring_20260924.md` (this report)
- `docs/northstar-phase1c/{phase1c-status,phase1c-continuation-state,12-known-gaps,15-evidence-index,restart-manifest}.json/md`

## Known gaps
- Blocking (owner-authorized only): live payment keys, live providers, public
  self-serve signup, production provisioning.
- Non-blocking: file attachments not exposed (safe-upload not proven); the
  legacy port-8000 shell remains the historical entry (canonical UI is
  `/ui` on 8001); no incident deputy; business-data retention UNKNOWN until
  reviewed per customer.

## Decision
**LOCAL_PRIVATE_BETA_UI_READY** — the private-beta flows are demonstrably
usable through the browser at `http://127.0.0.1:8001/ui` (tester signup →
acceptance → onboarding → plan & usage → support; admin dashboard → plan/note/
suspend → tester blocked with account-status screen → safe CSV export), and
every regression suite is green. No production, no live providers, no real
payment keys, no public signup, no autonomous rollback, and no committed
secrets.