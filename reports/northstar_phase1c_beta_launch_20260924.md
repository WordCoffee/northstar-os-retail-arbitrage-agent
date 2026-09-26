# 1C-06 Lean B2B Beta Launch Controls — Gate Report

**Date:** 2026-09-24
**Prior gate:** 1C-05 authorization **ACCEPTED PASSED**.
**This gate decision: 1C-06 BETA LAUNCH CONTROLS — PASS** (PostgreSQL evidence).

## What was delivered

1. **Versioned public documents** (`foundation/beta/documents.py`): Privacy
   Notice, Terms of Service, Acceptable Use Policy (v1.0), beta-marked,
   conservative/accurate language only. No claims of legal compliance,
   guaranteed outcomes, Amazon approval, perfect security, verified sourcing,
   sales estimates, fees, Buy Box status, or profitability. Served publicly at
   `/legal/documents` and `/legal/documents/{doc_type}/current`.
2. **Mandatory versioned acceptance**: Terms + Privacy (+AUP), business-use
   attestation, 18+ attestation. Append-only `acceptance_events` (doc type,
   version, content hash, timestamp, actor ID, org ID, IP handling
   `not_stored`, request/correlation ID) + current pointer. **Deny-until-
   accepted**: once documents are published, feature routes return 409 until
   the actor accepts; a document revision re-prompts and denies until
   re-accepted. Enforcement is inactive until documents are published (dev
   state preserved).
3. **Internal data inventory** (`16-data-inventory.md`) — field, purpose,
   sensitivity, source, storage, access roles, subprocessor, retention,
   deletion mechanism, optionality. Data minimization applied; unknown
   retentions explicitly marked UNKNOWN.
4. **Retention/deletion schedule** (`17-retention-schedule.md`) — actual
   retention incl. backup limitations; no false promise of immediate/complete
   deletion; documented deletion-request process.
5. **Incident-response runbook** (`18-incident-runbook.md`) — named accountable
   role (Tyrone); access-disable; session invalidation; secret rotation;
   evidence/log preservation; scope assessment; customer-communication decision
   tree; recovery; post-incident review. No external tools required.
6. **/beta-status readiness record** — U.S.-only manual approval; providers
   disabled; payment cards not handled; no customer marketplace credentials;
   document versions published; acceptance enforcement enabled; data inventory
   complete; retention complete; incident runbook complete; known gaps listed.

## Required acceptance evidence on PostgreSQL / staging (all executed)

| Proof | Where | Result |
|---|---|---|
| New-account flow denied until acceptance | `test_beta_launch_postgres.py::test_new_account_denied_until_acceptance` + staging smoke item 29 | PASS (409 until accepted, then 201) |
| Revised-document re-prompt denies continued use | `test_beta_launch_postgres.py::test_revised_document_reprompts_existing_user` | PASS |
| Two orgs' acceptance records cross-tenant isolated | `test_beta_launch_postgres.py::test_acceptance_cross_tenant_isolation` | PASS |
| Viewer/operator/owner validated on document + acceptance endpoints | `test_beta_launch_postgres.py::test_document_acceptance_role_validation` | PASS |
| Data-inventory completeness (unknown retention explicit) | `test_data_inventory_completeness_pg` + SQLite test | PASS |
| Incident tabletop (credential/session compromise) | `test_incident_tabletop_credential_compromise` | PASS (disable → invalidate → rotate → preserve → audit-correlated) |
| Staging smoke (beta acceptance + access denial) | `staging-smoke-report.json` item 29 | PASS |

## Totals
- SQLite foundation: **605 passed / 42 skipped** (42 = PostgreSQL-only modules).
- Disposable PostgreSQL: **42 passed** (financial 4 + durable 6 + integration
  13 + concurrency 9 + authorization 4 + beta 6).
- Migration harness (001–005): **9/9 PASS**.
- Staging smoke: **29/29 PASS**.

## Migration status
`001 → 002 → 003 → 004 → 005` (005 = beta launch controls), checksums in
`staging-migration-package.json`. **005 applied to staging with a verified
backup** (`staging-005-apply-report.json`, 203,552-byte dump; backup never
skipped). Rollback prepared, **NOT executed**.

## Changed files (1C-06)
Added: `foundation/beta/{__init__,documents,acceptance,inventory,retention,
incident,beta_status}.py`, `migrations_foundation/005_beta_launch_controls.sql`,
`005_rollback_beta_launch_controls.sql`, `foundation/tests/test_beta_launch.py`,
`test_beta_launch_postgres.py`, `tools/staging_apply_005.py`,
`docs/northstar-phase1c/{16-data-inventory,17-retention-schedule,18-incident-runbook,19-beta-controls}.md`,
`reports/northstar_phase1c_beta_launch_20260924.md`.
Modified: `foundation/{db.py, models.py, repositories.py, api/router.py}`,
`001_foundation.sql` (regenerated), migration harness, `tools/staging_smoke.py`,
`docs/northstar-phase1c/*` (status/continuation/known-gaps/evidence/manifest/
ledger), `staging-migration-package.json`.

## Controls maintained
Unknown stays null/unknown; no live provider calls; no production access; no
public exposure; no payment-card handling; no customer marketplace
credentials; no autonomous rollback; no secret logging or committing; all
financial-integrity and authorization tests preserved and green.

## Evidence paths
`docs/northstar-phase1c/19-beta-controls.md`, `16-data-inventory.md`,
`17-retention-schedule.md`, `18-incident-runbook.md`, `phase1c-status.json`
(formal decision: PASS), `phase1c-continuation-state.json`, `12-known-gaps.md`,
`15-evidence-index.md`, `restart-manifest.md`,
`phase1c-autonomous-run-ledger.md`, `staging-005-apply-report.json`,
`staging-smoke-report.json`, `staging-migration-package.json`.