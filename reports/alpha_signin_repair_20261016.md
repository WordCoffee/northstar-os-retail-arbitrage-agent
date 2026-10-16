# Alpha sign-in repair — 2026-10-16

Symptom (operator): the tunnel link shows "Invalid email or password" at the
sign-in page. Nothing was wrong with the password — the UI sign-in path had a
**triple** configuration gap.

## Root causes (all three were live)

1. **Wrong auth store / no credential.** The product UI authenticates at
   `POST /api/v1/foundation/auth/login` (HttpOnly `ns_session` cookie) — NOT
   the legacy `/api/v1/auth/login` (Bearer/token) that was reset earlier.
   The foundation store had **no owner credential at all** because
   `FoundationState.build()` with no path/DB_URL falls back to a *throwaway
   per-process SQLite DB* (documented in `foundation/db.py`: "NEVER points at
   the production-like northstar.db by default"). The UI even masks every
   login failure (403/503/401) as "Invalid email or password." (SignIn.jsx
   catch-all), which hid the real errors.
2. **The private-alpha gate did not speak cookie.** With `-Gate`, the gate
   middleware only recognized Bearer tokens, so it 403'd the foundation login
   POST itself and every cookie-authenticated UI call.
3. **Missing signing key.** Foundation auth fails closed (503
   `auth_unconfigured`) without `NORTHSTAR_JWT_SECRET`; the local alpha
   launcher never provided it (legacy auth.py hides this with an ephemeral
   random fallback; the foundation path does not).

## Fixes (5 files)

| File | Change |
|---|---|
| `Northstar_backend/alpha_gate.py` | Resolves the Foundation `ns_session` cookie as an allowlisted identity (email via the shared foundation user store); public list now carries only the pre-auth entry points: `/api/v1/foundation/auth`, `/api/v1/foundation/signup`, `/api/v1/foundation/ui-mode`, `/api/v1/invites`. The legacy surface stays locked to allowlisted identities. |
| `Northstar_backend/main.py` | `FoundationState.build(os.environ.get("FOUNDATION_DB_PATH") or None)` — hosted still uses DB_URL/Postgres. |
| `scripts/launch_alpha.ps1` | Pins `FOUNDATION_DB_PATH=Northstar_backend/data/foundation.db`; wires `NORTHSTAR_JWT_SECRET` from the existing out-of-repo store `%LOCALAPPDATA%\NorthstarOS\jwt-secret.txt` (owner-only ACL; same mechanism as `tools/start-local.ps1`; never printed/committed). |
| `Northstar_backend/foundation/tests/test_auth_session.py` | Two stale assertions synced to the documented P0-04 decision (session cookie path `/`, single-origin suite). Pre-existing failures, not caused by this repair. |
| `docs/PRIVATE_ALPHA_DEPLOY.md` | New "Owner sign-in, signing key, persistence" section + verify-table row. |

Owner credential seeded via the app's own tool
(`foundation_seed_owner`, bcrypt, single `internal_platform_admin`, org
"T2 Holdings LLC") into the persistent `Northstar_backend/data/foundation.db`
(639 KB). The plaintext was provided by the operator and never recorded.

## Verification (real calls, this session)

| Check | Result |
|---|---|
| foundation login (local) | 200 + `ns_session` cookie |
| foundation `/api/v1/foundation/me` (local) | 200 |
| foundation login through the tunnel | 200 |
| foundation `/api/v1/foundation/me` through the tunnel | 200 |
| `GET /api/v1/reasoning/models` WITH cookie (cookie-aware gate) | 200 |
| `GET /api/v1/models` no creds (lock intact) | 403 `private_alpha_locked` |
| legacy `POST /api/v1/auth/login` | 200 |
| `/ui/sign-in` page | 200 |
| `pytest test_alpha_gate.py` | 15 passed |
| `pytest foundation/tests/test_auth_session.py + test_auth_guard.py` | 25 passed |

## Operator

- Sign in at https://thoroughly-pursuant-sensor-contain.trycloudflare.com/ui/sign-in
  with `northstarosllc@gmail.com`.
- Partner (OA-10): send the email — the partner credential is seeded into the
  same persistent store the same way (or via the foundation invite + signup
  path once its UI form lands).
