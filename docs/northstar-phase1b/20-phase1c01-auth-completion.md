# 20 — Phase 1C-01 Completion Report: Real Authentication & Organization Resolution

**Date:** 2026-09-23
**Scope authorized:** 1C-01 ONLY (real JWT auth + org resolution + guardrail).
**Status:** COMPLETE — implemented, runtime-tested, documented. No 1C-02..1C-06 work
started; no Postgres migration; no economics change; no workers; frontend not exposed.

---

## 1. What changed

| File | Change |
|---|---|
| `Northstar_backend/foundation/authn.py` | **NEW** — JWT validation, proxy-aware client-host resolution, startup posture enforcement |
| `Northstar_backend/foundation/api/deps.py` | **REWRITTEN** — JWT-first auth, dev shim strictly local-development-only, server-side org/role resolution, preview authorization |
| `Northstar_backend/foundation/db.py` | Added `sessions` table (25 tables total; still one SCHEMA source) |
| `Northstar_backend/foundation/repositories.py` | Added `SessionRepo` (revocation) |
| `Northstar_backend/foundation/context.py` | Added `auth_method` to `RequestContext` |
| `Northstar_backend/foundation/api/router.py` | `/environment` + `/auth-posture` report posture; `POST /session/revoke`; preview target-org authorization |
| `Northstar_backend/foundation/app.py` | Calls `assert_startup_posture()` at startup |
| `Northstar_backend/main.py` | Foundation mount now asserts posture (still additive) |
| `Northstar_backend/foundation/tests/*` | 4 auth test suites added; 2 contract tests updated |

The header shim is no longer the primary mechanism: the **JWT path is executed first**;
the shim survives only as a local-development convenience.

## 2. Acceptance criteria — final auth guardrail

| # | Criterion | Status | Evidence |
|---|---|---|---|
| G1 | `NS_FOUNDATION_ALLOW_REMOTE_DEV` rejected in staging/production | ✅ | `authn.assert_startup_posture`; live: production+override → `AuthPostureError` |
| G2 | Startup fails if binding beyond loopback while dev shim active, unless dev env + override | ✅ | `assert_startup_posture`; tests `test_auth_posture.py` (10) |
| G3 | Reverse-proxy traffic cannot appear as loopback and bypass auth | ✅ | `effective_client_host` returns `untrusted-proxy` for untrusted peer with forwarding headers; live test #6 → 401 |
| G4 | Forwarded headers trusted only from configured proxy addresses | ✅ | `trusted_proxies()`; XFF honoured only when peer ∈ `NORTHSTAR_TRUSTED_PROXIES` |
| G5 | JWT validation executes before org/role headers | ✅ | `deps.get_context` validates bearer first; identity headers ignored in JWT path |
| G6 | Dev identity headers ignored outside local development | ✅ | `dev_shim_enabled()` requires `ENVIRONMENT=development`; test + live #4 |
| G7 | All auth failures fail-closed | ✅ | `AuthError` on any JWT/secret/expiry/iss/aud failure → 401; missing key → fail closed |

## 3. Phase 1C-01 scope items

| Requirement | Status |
|---|---|
| Replace header shim with validated JWT auth | ✅ JWT first; shim dev-only |
| Resolve organization membership server-side | ✅ `_resolve_org_and_role` from `memberships` table |
| Enforce roles/permissions from trusted DB records | ✅ role from membership; headers/claims not trusted |
| Preserve audited customer-view preview without true identity replacement | ✅ `PreviewContext`; actor preserved; entry/exit audited; no impersonation |
| Session revocation + token expiration | ✅ `sessions` table + `/session/revoke`; `exp` required |
| Remote access succeeds only with valid auth | ✅ live #5 → 200 (JWT), #4 → 401 (no JWT) |
| Cross-organization access denied | ✅ live #7 → 403; `test_auth_org_scope.py` |
| Preserve local development without weakening staging/production | ✅ dev shim local-only; prod requires secret |

## 4. Runtime evidence (real HTTP, provisioned app on a spare port, then stopped)

| # | Check | Result |
|---|---|---|
| 1 | localhost `/me` no auth | **401** |
| 2 | localhost `/me` valid JWT | **200** |
| 3 | localhost `/me` bad JWT | **401** |
| 4 | LAN (non-loopback) `/me` dev headers, no JWT | **401** |
| 5 | LAN `/me` valid JWT | **200** |
| 6 | LAN `/me` spoofed `X-Forwarded-For: 127.0.0.1` + dev headers | **401** |
| 7 | localhost cross-org `X-Org-Id` | **403** |
| 8 | `/auth-posture` (JWT) | `{"auth_posture":"jwt","real_authentication_active":true,...}` |
| S1 | startup: production without secret | **AuthPostureError** |
| S2 | startup: production + remote-dev override | **AuthPostureError** |

## 5. Test results

- Command: `python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider`
- Result: **124 passed, 0 failed** (was 92; +32 auth tests).
- New suites: `test_auth_guard.py` (client-host/proxy/dev-shim), `test_auth_jwt.py`
  (validation/expiry/issuer/audience/revocation), `test_auth_org_scope.py`
  (role-from-DB, cross-org, preview), `test_auth_posture.py` (startup posture).

## 6. Security notes

- Tokens are consumed (validated), never issued, by the foundation.
- The signing key is read from `NORTHSTAR_JWT_SECRET` at runtime; never printed/read by
  tooling. Tests use a `test-`placeholder value that the ancestor conftest preserves.
- Roles are never taken from `X-Role` or token claims for authorization decisions.
- Preview cannot elevate (min-role) and cannot be used by a non-owner.

## 7. Known gaps (carried, not blocking 1C-01)

1. **Membership provisioning bridge** — tokens issued by `Northstar_backend/auth.py`
   reference the legacy `users` table; the foundation resolves roles from its own
   `memberships` table. A provisioning/sync bridge is needed before live login flows
   into the foundation (Phase 1C follow-up).
2. **issuer/audience are optional** — validated only when configured via
   `NORTHSTAR_JWT_ISSUER` / `NORTHSTAR_JWT_AUDIENCE`. Recommend configuring in staging.
3. **Foundation sessions** are separate from the legacy `sessions` table in
   `northstar.db`; revocation applies to foundation-registered jtis.

## 8. Confirmations

- No Postgres migration applied; no migration files changed this phase.
- No economics formula changed.
- No worker/scheduler started.
- Frontend not exposed.
- No external provider call; no deployment; no commit; no push.
- `AGENTS.md`, constitution, Phase 0, and Phase 1A documentation untouched.