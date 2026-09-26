# 08 — Security Review (Phase 1C, as at autonomous sprint)

Scope: changes made up to 1C-03. No security regression introduced.

## Authentication (1C-01F, unchanged)

- Four explicit environments; staging/production require secret + issuer + audience +
  algorithm allowlist; startup fails closed.
- Role/organization from DB memberships only; membership status enforced; cross-org denied;
  preview non-elevating; session revocation; dev shim local-development-only.

## Economics (1C-03)

- Pure module; **no provider calls**, **no DB side effects**, no secret access.
- Decimal money (no binary-float authority); null-first (unknown never zero).
- No fabricated fees/eligibility; `purchase_ready` requires sourcing + documentation +
  eligibility gates.

## Secret handling

- No secret values read/printed/copied; no secrets in code, tests, or docs.
- `.env` remains gitignored; PostgreSQL test credentials were ephemeral and deleted.
- Serialized outputs contain no credentials; error paths return structured codes.

## Provider posture

- All providers default-off; none executed. Faire economics adapter performs no I/O and
  keeps fail-closed gates.

## Findings

| ID | Finding | Severity | Status |
|---|---|---|---|
| 1C-S1 | Foundation auth was a header shim | Blocking | Resolved (1C-01/1C-01F) |
| 1C-S2 | JWKS not implemented (static key) | Low | Documented |
| 1C-S3 | Legacy user→membership bridge missing | Medium | Open (owner decisions B1–B5) |

No active secret exposure, cross-organization access, authentication bypass, or remote
development-header access was found. No external system was contacted.
## 1C-04/1C-05 authorization hardening (owner-prioritized)

- 1C-04 accepted PASSED (financial-integrity gate) with staging evidence
  preserved (reports/northstar_phase1c_financial_integrity_20260924.md,
  staging-smoke-report.json, staging-004-apply-report.json).
- 1C-05 organization-scoped authorization + data boundaries PASSED:
  - Permission matrix extended (view_ledger / view_providers / view_approvals);
    viewer is strictly read-only and blocked from billing/ledger, provider
    configuration, and administrative approval/audit metadata (403).
  - Cross-org object-ID guessing returns a non-enumerating 404 across job
    status/results/cancel/retry/audit/usage/ledger surfaces (no existence hint).
  - Cancel/retry not_found now maps to 404 (was 403 — enumeration leak fixed).
  - Mass-assignment prevented by explicit request/response allowlists; verified
    that role/organization/settlement/ledger/provider/secret/audit fields are
    ignored (server derives org/actor/cost/state).
  - Denied authorization attempts audited (action=authz.denied; method/path/
    status/code only — never sensitive object data) via an app middleware.
  - PostgreSQL evidence: test_authorization_postgres.py (4 tests) + staging
    smoke item 28 (two orgs, owner + viewer: permitted succeeds, prohibited
    gets 404/403, no existence hint).
  - Null-first semantics unchanged.
