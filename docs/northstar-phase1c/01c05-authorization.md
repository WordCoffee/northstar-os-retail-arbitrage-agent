# 1C-05 — Organization-Scoped Authorization & Data-Boundary Enforcement

**Status:** ✅ **PASS** — RUNTIME_CONFIRMED (PostgreSQL evidence; SQLite 594
passed / 32 skipped; PG 36 passed; staging smoke 28/28 incl. two-org/two-role).

## Scope

Every read, update, cancel, retry, export, audit lookup, ledger lookup, and
job-status endpoint derives `organization_id` and actor identity from the
authenticated server-side context (`deps.get_context` → `RequestContext`),
NEVER from client-controlled request fields. Direct object-ID guessing across
organizations returns a non-enumerating denial (404) and never discloses
whether the target exists.

## Server-side permission matrix (single source of truth)

Source: `foundation/permissions.py` (`_ROLE_PERMISSIONS`).

| Capability | viewer | operator | admin | owner | platform-admin |
|---|---|---|---|---|---|
| view | ✅ | ✅ | ✅ | ✅ | ✅ |
| draft | — | ✅ | ✅ | ✅ | ✅ |
| run_local | — | ✅ | ✅ | ✅ | ✅ |
| request_refresh (create/operate jobs) | — | ✅ | ✅ | ✅ | ✅ |
| approve | — | ✅ | ✅ | ✅ | ✅ |
| view_audit | — | ✅ | ✅ | ✅ | ✅ |
| view_ledger (billing/usage) | — | ✅ | ✅ | ✅ | ✅ |
| view_providers (provider config) | — | ✅ | ✅ | ✅ | ✅ |
| view_approvals (approval queue) | — | ✅ | ✅ | ✅ | ✅ |
| manage_team (membership) | — | — | ✅ | ✅ | ✅ |
| manage_org (org settings) | — | — | — | ✅ | ✅ |
| purchase / write_external | — | — | — | ✅ (gated) | ✅ |
| platform_admin | — | — | — | — | ✅ |

- **Owner** — manages organization-level settings and membership; purchase.
- **Operator** — creates and operates permitted research jobs; sees the usage/
  provider/approval surfaces needed to operate.
- **Viewer** — strictly read-only; **cannot** access billing/ledger records,
  secrets, provider configuration, or administrative audit/approval metadata.

## Data-boundary rules

- Org + actor derived server-side; `X-Org-Id`/body `organization_id` never
  override the authenticated tenant (JWT `tenant_id` / membership).
- Cross-org object IDs → **404** (`not_found`) on: job status/detail, run
  results, cancellation, retry, job audit timeline, schedule detail, keyword
  detail, import batches, rejected rows, provider detail. The 404 body shape is
  identical for "missing" and "not yours" (no enumeration).
- Mass-assignment: every request/response body uses an **explicit allowlist**
  (pydantic `BaseModel`, no `extra="allow"`); role, organization, settlement,
  ledger, provider, secret, and audit fields cannot be client-set. Jobs derive
  `estimated_cost`, `provider_class`, and `state` from the handler spec and
  server flow, not the request body.
- Denied authorization attempts are **audited** (`action=authz.denied`) with
  method/path/status/code only — never sensitive object data.

## Endpoints protected

All `/api/v1/foundation/*` read/update/cancel/retry/list/detail routes resolve
org + actor from context; sensitive surfaces gated as above. No client-controlled
org field is honored anywhere.

## PostgreSQL evidence (mandatory)

`foundation/tests/test_authorization_postgres.py` (4 tests, real PG):

1. **Cross-org object IDs non-enumerating** — job status, run results,
   cancellation, retry, audit events, usage/ledger lists, and audit exports:
   every cross-org guess returns 404; org-A's job is not mutated; viewer gets
   403 on ledger.
2. **Role matrix (owner/operator/viewer)** — permitted activity succeeds;
   operator cannot manage org; viewer is blocked from billing/ledger,
   providers, approvals, and audit, and cannot create jobs.
3. **Mass-assignment** — body fields `organization_id`, `role`,
   `estimated_cost`, `state`, `provider_class`, `approval_id`, `secret`,
   `ledger_entry`, `settled_cost`, `reserved_cost` are all ignored; the job is
   created with server-derived org/actor and spec-derived cost/class.
4. **Concurrent denials** — 8 concurrent cross-org guesses all return 404.

Staging: `staging-smoke-report.json` item 28 — two orgs, owner + viewer:
owner submission succeeds, viewer own-org read succeeds, viewer blocked from
ledger/providers/submission (403), cross-org job guess → 404 with no
existence hint in the body.

## Null-first

Unavailable source/price/Buy Box/fee/seller-count/sales/invoice data stays
unknown/null (never silently zero or verified) — enforced across economics,
scanner, keyword, and job paths (existing null-first tests unchanged).

## Related files

`foundation/permissions.py`, `foundation/context.py`, `foundation/api/deps.py`,
`foundation/api/router.py`, `foundation/app.py` (denial-audit middleware),
`foundation/tests/test_authorization_matrix.py`,
`foundation/tests/test_authorization_postgres.py`,
`foundation/tests/test_permissions.py`, `tools/staging_smoke.py`.