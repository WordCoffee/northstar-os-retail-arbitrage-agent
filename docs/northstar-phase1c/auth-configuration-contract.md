# Authentication Configuration Contract (1C-01F)

This documents the required platform authentication configuration per environment.
**No secret values appear here — names only.**

## Environment modes

`ENVIRONMENT ∈ {development, test, staging, production}` (default `development`).
An unknown value fails closed.

## Required by environment

| Setting (name) | development | test | staging | production |
|---|---|---|---|---|
| `NORTHSTAR_JWT_SECRET` | optional | optional | **required** | **required** |
| secret must not be a dev placeholder | — | — | **required** | **required** |
| `NORTHSTAR_JWT_ISSUER` | optional | optional | **required** | **required** |
| `NORTHSTAR_JWT_AUDIENCE` | optional | optional | **required** | **required** |
| `NORTHSTAR_JWT_ALGORITHMS` (allowlist, no `none`) | optional | optional | **required** | **required** |
| `NS_FOUNDATION_ALLOW_REMOTE_DEV` | may be set | may be set | **forbidden** | **forbidden** |
| dev identity headers (`X-User-Id`) | allowed (loopback) | **ignored** | **ignored** | **ignored** |

Optional tightening controls (any environment):
`NORTHSTAR_JWT_LEEWAY_SECONDS` (≤300), `NORTHSTAR_JWT_MAX_LIFETIME_SECONDS`,
`NORTHSTAR_JWT_KEY_ID`, `NORTHSTAR_JWT_MAX_KID_LENGTH`, `NORTHSTAR_JWT_TOKEN_TYPES`,
`NORTHSTAR_TRUSTED_PROXIES`.

## Startup behavior

`assert_startup_posture()` runs at application startup and **fails closed** if required
configuration is missing or unsafe. It also refuses to bind beyond loopback while the
development shim is active unless `ENVIRONMENT=development` **and**
`NS_FOUNDATION_ALLOW_REMOTE_DEV` are both present.

## Key management posture

- **Static key model** (HS256 by default). JWKS is NOT implemented in 1C-01F.
- Signing keys are never printed, logged, or returned by any endpoint; posture
  endpoints report presence only (`jwt_secret_present: true/false`).
- Shared development secrets are rejected in staging/production
  (`development_secret_in_prod`).

## Initial-owner provisioning contract

```
python -m foundation.bootstrap --org-name "<name>" --email "<owner@example>" [--recover] [--db <path>]
```
- Explicit, CLI-only; never triggered by startup or an HTTP request.
- Idempotent; refuses when an owner already exists unless `--recover` (explicit recovery).
- Writes an audit event (`bootstrap.owner`) with the email masked.
- Takes no password/secret on the command line.
- If an external identity provider is required, this command contract is the stop point:
  the provider integration is an owner decision, not invented here.

## Rotation / recovery (procedure, not automated)

1. Issue a new signing key out-of-band; distribute to the app as `NORTHSTAR_JWT_SECRET`.
2. Tokens signed with the old key fail validation (fail-closed) until re-issued.
3. For emergency owner recovery, use `--recover` with an operator-approved runbook and
   confirm the resulting `bootstrap.owner` audit event.