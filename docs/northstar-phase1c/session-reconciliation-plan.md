# Session Reconciliation Plan (1C-01F)

**Status:** boundary defined and enforced; cleanup scheduling deferred to 1C-04.

## Current state

- **Legacy sessions:** `sessions` table in `Northstar_backend/data/northstar.db`
  (written by `auth.py:_record_session`), used by the legacy auth surface.
- **Foundation sessions:** `sessions` table in the foundation store
  (`foundation/db.py:SCHEMA["sessions"]`, PK `jti`), used by the foundation router for
  revocation.

They are **separate stores** (different databases). This is deliberate.

## Boundary rules (enforced / to enforce)

| Rule | Status |
|---|---|
| Foundation-protected routes use **foundation** revocation checks | ✅ enforced (`deps.get_context` checks `sessions.is_revoked(jti)`) |
| Legacy session cookies must NOT silently authenticate foundation routes | ✅ — the foundation reads only `Bearer` JWT + its own dev shim (local dev); no cookie auth |
| Foundation JWTs must NOT silently authenticate legacy routes unless explicitly integrated | ✅ — legacy routes use `auth.py`/`auth_deps.py`; no shared validation |
| No route discloses raw session tokens | ✅ — `/session/revoke` returns only `{jti, revoked}`; `/me` returns no token |
| Revocation is auditable | ✅ — `session.revoke` audit event |
| Expired sessions must not remain active indefinitely | ⏳ enforcement at request time via `exp`; **physical cleanup scheduled in 1C-04** |
| Multiple active sessions queryable by the account owner | ⏳ planned (Account → Sessions) in 1C-06 |

## Logout / revocation semantics

- Revoking a session (`POST /api/v1/foundation/session/revoke?jti=...`) marks
  `revoked_at`; subsequent requests with that `jti` return **401 `session_revoked`**.
- A user may revoke their own sessions; an internal platform admin may revoke any.
- Logout of the legacy surface does not revoke foundation sessions (and vice versa)
  until an explicit integration is approved.

## Cleanup (deferred to 1C-04)

A scheduled, organization-scoped job will remove expired/revoked foundation session rows
after a retention window. It must be safe (idempotent, bounded, audited) and must not run
from any GET route. Not implemented in 1C-01F.