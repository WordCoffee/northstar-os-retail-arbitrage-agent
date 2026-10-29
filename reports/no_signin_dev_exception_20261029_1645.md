# Sign-in removed for local dev (until production is ready)

**Date:** 2026-10-29 · **Branch:** `feature/chrome-connect-3.0`
**Directive:** owner — "I can't log in. Remove the sign in for now until production is ready."

## What was wrong
The built UI (served at `/ui/` on port 8000) is a production bundle, so
`LOCAL_DEV` is false: it neither shows the dev session nor sends the
`X-User-Id` shim headers. With no cookie, every foundation call returned 401,
the session bootstrap failed, and the app sat on `/sign-in`. Credential login
also failed (the backend had no JWT secret / the demo identity wasn't usable),
so there was no way in.

## What changed
### Backend — owner-authorized dev-only loopback exception
The AGENTS capsule already sanctions this: *with `ENVIRONMENT=development` and a
loopback-only bind, the auth check may return a demo session
(userId `demo-t2` / orgId `org-t2` / role `operator`) before `/me`, with the
"DEV: AUTH DISABLED" banner.* Implemented narrowly:

| File | Change |
|---|---|
| `Northstar_backend/foundation/api/deps.py` | When no token/cookie exists **and** the API is in development posture **and** the peer is loopback **and** the real app opted in (`app.state.dev_auto_session`), resolve `demo-t2`. An explicit `X-User-Id` still wins. Otherwise 401 as before. |
| `Northstar_backend/foundation/dev_identity.py` (new) | Idempotent provisioning of org `org-t2` / user `demo-t2` / active `operator` membership in the state's **own** store. Dev posture + local SQLite only; never PostgreSQL; no secrets, no credential row. This makes the exception work even when the launcher did not pin `FOUNDATION_DB_PATH` (temp DB). |
| `Northstar_backend/main.py` | Calls `ensure_dev_identity()` after state build in development posture and sets `app.state.dev_auto_session` accordingly. The isolated foundation app (`create_app`, used by the security tests) never opts in, so its fail-closed contract is unchanged. |
| `Northstar_backend/auth_deps.py` | The legacy strict `require_session` (chat, Design Studio, shell) honours the same opt-in: no header + loopback + development + `dev_auto_session` resolves `demo-t2` with tenant `org-t2`, so those surfaces no longer 401 on the locally-served bundle. Same fail-closed edges (production / remote / no opt-in). |

Safety is unchanged at the edges: production (`ENVIRONMENT!=development`) still
401s; a remote peer still 401s; `assert_startup_posture` still refuses a remote
bind while the shim is active.

### Frontend
| File | Change |
|---|---|
| `northstar-os-ui/src/foundation/session.jsx` | Tracks `authMethod`; in a Vite dev build (`LOCAL_DEV`) an unresolved/401/network session falls back to the demo identity instead of bouncing to `/sign-in`. Production builds tree-shake the constant and branch (verified). |
| `northstar-os-ui/src/App.jsx` | The "DEV: AUTH DISABLED — local loopback only" banner now also renders when the backend reports `auth_method: dev_shim` (covers the locally-served production bundle). |
| `northstar-os-ui/verify-no-signin.cjs` (new) | Playwright harness: asserts the served UI has no sign-in form, is not redirected to `/sign-in`, and shows the dev banner. |

Production builds are unaffected: `LOCAL_DEV` is compile-time false; the bundle
contains no `demo-t2`, `org-t2` or `X-User-Id` (checked with `Select-String`
over `dist/assets/*.js` — zero matches).

## Verification
- **No-header auth on the real app** (`127.0.0.1:8000`):
  - `GET /api/v1/foundation/me` → **200** `demo-t2`, `active_organization_id: org-t2`, `role: operator`, full permission set.
  - `GET /api/v1/foundation/environment` → **200**, `auth_method: dev_shim`, `auth_posture: dev_shim_local_only`.
- **Built UI** `http://127.0.0.1:8000/ui/` → `verify-no-signin.cjs` **PASS**:
  `finalUrl=/ui/`, `hasSigninForm=0`, `hasSigninTitle=0`, `devBanner=1`, all foundation calls 200.
  Chat/studio calls also 200 with no session (`/api/chat/health`, `/api/chat/sessions`,
  `/api/chat/voice/status`), scoped to `org-t2`.
- **Vite dev UI** `http://127.0.0.1:8101/ui/` → **PASS** (same assertions).
- **Security regression suite** (`test_api_contracts`, `test_auth_guard`,
  `test_auth_guard_extra`, `test_auth_posture`, `test_rate_limit_dev_shim`):
  **58 passed** — the no-credentials 401 contract still holds for the isolated
  foundation app, production and non-loopback clients.
- **Build:** `npm run build` → 174 modules, **0 errors** (pre-existing chunk
  warnings only).

## Chat/TTS note
`/api/chat/*` now returns 200 on the locally-served bundle (sessions, health,
voice status). The only remaining non-200 is `GET /api/chat/voice/voices` → 503,
which is the local TTS provider not running — an availability signal, not
authentication.

## Operational notes
- Backend left running on `127.0.0.1:8000` with `ENVIRONMENT=development` and
  `FOUNDATION_DB_PATH` pinned to `Northstar_backend/data/foundation.db`.
- Dev server (8101) stopped.
- To undo when production is ready: remove the `dev_auto_session` opt-in in
  `main.py` and the `LOCAL_DEV` session fallback (the `auth_deps.py` and
  `deps.py` branches are already gated on that flag) — no data migration needed.
