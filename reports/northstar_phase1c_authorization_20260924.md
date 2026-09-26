# 1C-05 Organization-Scoped Authorization & Data-Boundary Enforcement — Gate Report

**Date:** 2026-09-24
**Prior gate:** 1C-04 **ACCEPTED PASSED** — financial-integrity gate + staging evidence preserved
(`reports/northstar_phase1c_financial_integrity_20260924.md`,
`docs/northstar-phase1c/staging-smoke-report.json`,
`docs/northstar-phase1c/staging-004-apply-report.json`,
`docs/northstar-phase1c/staging-apply-ledger.json`).

**This gate decision: 1C-05 AUTHORIZATION — PASS** (PostgreSQL evidence below).

## What changed

1. **Server-side permission matrix** (`foundation/permissions.py`) — one source
   of truth. Added `view_ledger`, `view_providers`, `view_approvals` granted to
   operator+ and denied to viewer. Viewer is strictly read-only and cannot
   reach billing/ledger (`/usage/*`), provider configuration (`/providers/*`),
   the administrative approval queue (`/approvals`), or admin audit metadata
   (`/audit`, `/jobs-durable/{id}/audit`) — all now 403 for viewer.
2. **Server-derived org + actor everywhere** — every read/update/cancel/retry/
   list/detail endpoint derives `organization_id` and actor from
   `deps.get_context` (JWT tenant + membership). No endpoint honors a
   client-controlled organization field.
3. **Non-enumerating denial** — cross-org object IDs return 404 (identical
   shape to "missing") across job status, run results, cancellation, retry,
   job audit timeline, schedule detail, keyword detail, imports, and provider
   detail. Fixed a real leak: cancel/retry mapped `not_found` to 403.
4. **Mass-assignment protection** — every request/response body is an explicit
   allowlist (no `extra="allow"`). Role, organization, settlement, ledger,
   provider, secret, and audit fields cannot be client-set; `estimated_cost`,
   `provider_class`, and `state` derive from the handler spec and server flow.
5. **Denial audit** — a middleware audits every 401/403/404 on the foundation
   API as `action=authz.denied` (method/path/status/code only; never sensitive
   object data).

## Required PostgreSQL evidence (all executed)

| Proof | File | Result |
|---|---|---|
| Cross-org object-ID tests: job status, cancellation, retry, results, exports (audit/usage lists), audit events, usage/ledger | `test_authorization_postgres.py::test_cross_org_object_ids_non_enumerating` | PASS (all 404, job unmutated) |
| Role matrix (owner/operator/viewer incl. prohibited actions) | `test_authorization_postgres.py::test_role_matrix_owner_operator_viewer` | PASS |
| Mass-assignment (privileged + financial fields cannot be client-set) | `test_authorization_postgres.py::test_mass_assignment_cannot_set_privileged_fields` | PASS |
| Concurrent cross-org guesses | `test_authorization_postgres.py::test_concurrent_denials_single_worker` | PASS (8× 404) |
| Staging smoke, two orgs + two roles | `staging-smoke-report.json` item 28 | PASS (permitted succeeds; viewer blocked 403; cross-org 404, no hint) |

## Suite totals

- SQLite foundation: **594 passed / 32 skipped**.
- Disposable PostgreSQL (authz + financial + durable + integration + concurrency): **36 passed**.
- Migration harness (001–004): **9/9 PASS**.
- Staging smoke: **28/28 PASS** (incl. financial chain + authorization matrix).

## Migration status

No schema change required for 1C-05 (permissions/allowlists/middleware are
code). Migration set remains `001 → 002 → 003 → 004` (004 = financial-integrity
idempotency + audit correlation), checksums in `staging-migration-package.json`.

## Security review / threat model update

`docs/northstar-phase1c/08-security-review.md` and
`docs/northstar-phase1c/01c05-authorization.md` updated: threat model covers
cross-org ID enumeration (mitigated: uniform 404), privilege escalation via
mass assignment (mitigated: allowlists), viewer data exfiltration of
billing/provider/approval metadata (mitigated: permission gates), and
unaudited denials (mitigated: authz.denied audit).

## Known gaps

- Provider definitions remain global infrastructure; org-scoped provider
  CONFIG/credentials is a documented follow-up.
- ANALYST role retained for backward compatibility alongside the
  owner/operator/viewer minimum.

## Null-first

Unavailable source/price/Buy Box/fee/seller-count/sales/invoice data remains
unknown/null — never silently zero or verified (existing null-first tests
unchanged and passing).

## Safety

No live providers enabled, no production access, no public exposure, no paid
external calls, no autonomous rollback, no commits. Staging + disposable PG
running on loopback for inspection.

## Evidence paths

- `docs/northstar-phase1c/01c05-authorization.md` (spec + matrix + API inventory)
- `docs/northstar-phase1c/08-security-review.md` (threat model)
- `docs/northstar-phase1c/phase1c-status.json` (formal decision: PASS)
- `docs/northstar-phase1c/phase1c-continuation-state.json` (validated JSON)
- `docs/northstar-phase1c/12-known-gaps.md`, `15-evidence-index.md`,
  `restart-manifest.md`, `phase1c-autonomous-run-ledger.md`
- `reports/northstar_phase1c_authorization_20260924.md` (this report)