# 01 — Final Authentication Hardening (1C-01F)

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R).

## 1. Environment modes

Four explicit modes: `development | test | staging | production`
(`foundation/authn.py:VALID_ENVIRONMENTS`). An unrecognised `ENVIRONMENT` resolves to
`"invalid"` and **fails closed** (`validate_auth_configuration` → `invalid_environment`).
Not inferred from any debug flag.

## 2. Configuration contract (staging/production)

`validate_auth_configuration()` requires, for staging/production:

| Requirement | Failure code |
|---|---|
| `NORTHSTAR_JWT_SECRET` present | `missing_signing_key` |
| secret is not a development placeholder | `development_secret_in_prod` |
| `NORTHSTAR_JWT_ISSUER` present | `missing_issuer` |
| `NORTHSTAR_JWT_AUDIENCE` present | `missing_audience` |
| non-empty algorithm allowlist | `missing_algorithm_allowlist` |
| `none` not in allowlist | `alg_none_allowed` |
| `NS_FOUNDATION_ALLOW_REMOTE_DEV` unset | `remote_dev_override_in_prod` |

`assert_startup_posture()` raises `AuthPostureError` on any problem, so startup fails
closed. **RUNTIME_CONFIRMED:** staging (no issuer/audience) → `AuthPostureError:
missing_issuer; missing_audience`; production (issuer+audience+secret, loopback) →
starts.

Issuer/audience are optional only in `development`/`test`.

## 3. JWT validation (`decode_and_validate`)

Accepts only when ALL hold: well-formed 3-part token; server-configured algorithm
allowlist (never selected by the token); signature valid; `exp` valid (bounded skew);
`nbf` valid when present; `iat` integer when present; issuer valid when required;
audience valid when required; `sub` present; `type` in the approved set when present.

Rejects (fail-closed, with explicit codes): `malformed_token`, `empty_algorithm`,
`alg_none_rejected`, `unexpected_algorithm`, `malformed_kid`, `unknown_kid`,
`no_signing_key_configured`, `no_algorithm_allowed`, `issuer_required`,
`audience_required`, `invalid_issuer`, `invalid_audience`, `missing_required_claim`,
`token_expired`, `token_not_yet_valid`, `malformed_iat`, `token_lifetime_exceeded`,
`unapproved_token_type`, `invalid_token`.

Bounds: `NORTHSTAR_JWT_LEEWAY_SECONDS` (default 30, clamped 0–300);
`NORTHSTAR_JWT_MAX_LIFETIME_SECONDS` (optional);
`NORTHSTAR_JWT_MAX_KID_LENGTH` (default 120); `NORTHSTAR_JWT_KEY_ID` (optional);
`NORTHSTAR_JWT_ALGORITHMS` (default `HS256`).

## 4. Algorithm confusion / alg:none

The allowlist is server-side. `alg:none` is rejected before decode; any algorithm not
in the allowlist is rejected. **RUNTIME_CONFIRMED** via tests.

## 5. kid handling and JWKS scope decision

- `kid`: rejected when empty, non-string, or longer than the max (`malformed_kid`);
  rejected when a trusted `NORTHSTAR_JWT_KEY_ID` is configured and differs
  (`unknown_kid`).
- **JWKS is intentionally NOT implemented** in 1C-01F (static-key model). All JWKS-only
  controls (HTTPS requirement, JWKS host allowlist, kid-triggered fetch bounds, rotation,
  stale cache, refresh rate-limit) are therefore **N/A**, documented rather than faked.
  A test records this scope decision.

## 6. Proxy / client resolution

`effective_client_host`: forwarded headers are honoured **only** from
`NORTHSTAR_TRUSTED_PROXIES`; an untrusted peer sending forwarding headers resolves to
`untrusted-proxy` (never loopback); missing client → `None` (treated non-local). Nearest
untrusted hop is selected walking right-to-left; no DNS lookups.

## 7. Organization resolution and membership status

- Role and organization are resolved from the `memberships` table, never from headers
  or token claims (`_resolve_org_and_role`).
- **New:** membership `status` (`active|suspended|revoked`) is enforced — only `active`
  memberships grant anything. Suspended memberships yield 403 (fail-closed).
- Cross-organization selection is denied unless the actor is a member (or platform admin).

## 8. Initial-owner provisioning (`foundation/bootstrap.py`)

Explicit CLI, not startup, not a route; idempotent; refuses when an owner exists unless
`--recover`; writes an audit event (email masked); takes no password/secret on the command
line. Contract documented in `auth-configuration-contract.md`.

## 9. Legacy identity bridge & session reconciliation

Design plans delivered (`legacy-identity-bridge-plan.md`,
`session-reconciliation-plan.md`). The bridge mapping contract is **not yet clear enough**
to implement safely, so it is a documented blocking decision (no automated backfill).

## 10. Test results

- Command: `python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider`
- Result: **172 passed, 0 failed** (was 124 → **+48**).
- New/changed suites: `test_auth_hardening.py`, `test_bootstrap.py`, `test_migrate.py`;
  `test_auth_jwt.py`/`test_auth_guard.py`/`test_auth_org_scope.py`/`test_auth_posture.py`
  updated for the hardened contract.

## 11. Gate result

**PASSED** — staging/production require issuer+audience; startup fails when absent;
algorithm allowlisting enforced; remote dev impossible in staging/production; org/role
DB-backed; revocation passes; cross-org denial passes; proxy spoofing tests pass;
bootstrap documented and implemented; bridge + session boundary explicit; suite green;
no blocking auth risk; no provider call; no deployment.