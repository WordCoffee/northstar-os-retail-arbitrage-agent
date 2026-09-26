# 19 — Lean B2B Beta Launch Controls (1C-06)

**Status:** ✅ **PASS** — RUNTIME_CONFIRMED (PostgreSQL evidence; SQLite 605
passed / 42 skipped; PG 42 passed; harness 9/9 (001–005); staging smoke 29/29).

## Scope
Restricted, U.S.-focused, manually approved business beta — NOT public or
international self-serve. No production provisioning, no live provider
activation, no customer marketplace credentials, no public database exposure,
no payment-card handling.

## Versioned public documents
`foundation/beta/documents.py` — Privacy Notice, Terms of Service, and
Acceptable Use Policy, versioned (v1.0) and beta-marked. Conservative,
accurate language only. No claims of: legal compliance, guaranteed outcomes,
Amazon approval, perfect security, verified sourcing, sales estimates, fees,
Buy Box status, or profitability. Unknown remains unknown.
Served at `GET /api/v1/foundation/legal/documents` and
`/legal/documents/{doc_type}/current` (public).

## Mandatory versioned acceptance
- Required at account creation and again at first authenticated use after a
  document revision.
- Requires: acceptance of Terms + Privacy Notice (+ AUP), business-use
  attestation, and an 18+ attestation.
- Persisted **append-only** (`acceptance_events`) with doc type, version,
  content hash, timestamp, actor ID, organization ID, IP handling
  (`not_stored`, consistent with the data inventory), and request/correlation
  ID. A current pointer (`account_acceptance`) enables fast deny checks.
- **Deny-until-accepted**: when documents are published, feature routes return
  409 `acceptance_required` until the actor accepts. Enforcement is driven by
  the published set; no documents published ⇒ enforcement inactive (dev state).

## Data inventory
`foundation/beta/inventory.py` + `docs/northstar-phase1c/16-data-inventory.md`
— every collected field with purpose, sensitivity, source, storage, access
roles, vendor/subprocessor, retention, deletion mechanism, and optionality.
Data minimization enforced (only identity/auth/org/support/billing-metadata/
security fields). Unknown retentions are explicitly marked UNKNOWN.

## Retention/deletion
`foundation/beta/retention.py` + `docs/northstar-phase1c/17-retention-schedule.md`
— states ACTUAL retention incl. backup limitations (no false promise of
immediate/complete deletion where backups or legally necessary financial/audit
records remain) and a documented deletion-request process.

## Incident-response runbook
`foundation/beta/incident.py` + `docs/northstar-phase1c/18-incident-runbook.md`
— named accountable role (Tyrone); access-disable steps; session invalidation;
secret-rotation checklist; evidence/log preservation; scope assessment;
customer-communication decision tree; recovery; post-incident review. Usable
without external tools or tribal knowledge.

## /beta-status readiness record
`GET /api/v1/foundation/beta-status` (operator+) reports: restricted US manual
approval; public/international self-serve off; providers disabled; payment-card
data not handled; no customer marketplace credentials; document versions
published; acceptance enforcement enabled; data inventory complete; retention
schedule complete; incident runbook complete; known gaps.

## PostgreSQL / staging evidence
- `foundation/tests/test_beta_launch_postgres.py` (6): new-account denial,
  revised-doc re-prompt, cross-tenant acceptance isolation, role validation,
  data-inventory completeness, incident tabletop (credential/session
  compromise → authorization disable, session invalidation, secret-rotation
  checklist, evidence preservation, audit correlation).
- `foundation/tests/test_beta_launch.py` (11, SQLite): documents, language,
  acceptance flows, attestation requirements, cross-tenant, roles, beta-status,
  inventory, runbook.
- Staging: migration 005 applied with a verified backup
  (`staging-005-apply-report.json`); staging smoke **29/29** incl. item 29
  (beta acceptance + access denial: fresh account denied 409 until acceptance,
  then permitted; append-only events recorded).

## Controls maintained
Unknown stays null/unknown; no live provider calls; no production access; no
public exposure; no autonomous rollback; no secret logging or committing;
financial-integrity and authorization tests preserved (all green).