# Invite → Sign-In Flow Completion — Root Cause & Fix (2026-09-27)

## Symptom
After accepting an invite, the user reached `#/home` but the left rail still said “Sign in to open your workspace.” Clicking **Sign In** only revealed a credential form whose button did nothing — so no usable authenticated session was ever established and the service navigation never appeared.

## Investigation (answers)
1. **Auth state created by accepting an invite:** none. `pages/public/BetaInviteAccept.jsx` is a client-only screen with no API call; it creates no token, session, or membership. (The separate foundation `/api/v1/foundation/signup` route can create a membership from an invite code, but the canonical accept screen does not call it.)
2. **What acceptance is supposed to do:** in this local private-beta stack the sanctioned identity path is the **loopback development identity shim** (`SessionProvider` dev-session → `X-User-Id/X-Org-Id/X-Role`, resolved by `foundation/api/deps.py`). There is no foundation password-set or token-exchange endpoint in the canonical SPA. So the correct completion is an **explicit sign-in step** (now clearly signposted), not an automatic session.
3. **Why `#/home` before a session:** `GuardedRoutes` only protects `/beta-ops` and `/admin`; `/home` renders for any role, including signed-out (hence the “sign in” rail). The old step-2 button navigated straight to `#/home`.
4. **Why the unauthenticated shell persisted:** `SessionProvider` authenticates only when a token or dev session exists. The sign-in form had **no submit handler**, so nothing ever established a session.
5. **What was missing:** a working sign-in handler, and a post-acceptance step that carries the invited-org context into sign-in.

## Root cause
**Incomplete/abandoned frontend auth flow.** `pages/public/SignIn.jsx` was a static stub (no `onClick`/handler, no session establishment), and `BetaInviteAccept` sent the user to `#/home` instead of an explicit sign-in step.

## Fix (frontend only — smallest correct layer)
- **`src/pages/public/SignIn.jsx`** — made it functional:
  - prefills **`T2` / `123abc`** (local private-beta credential),
  - validates the credential with a clear inline error on mismatch,
  - on success establishes the **local session** via `session.updateDev({ role: 'operator', … })` (persisted in `localStorage` → survives refresh) and routes to `#/home`,
  - redirects already-authenticated users to `#/home`,
  - shows an “Invitation accepted — {org}” banner when arriving with `?org=…`,
  - labels it explicitly “Local private-beta sign-in…”, and fixes the `Forgot password?` link to the SPA route `#/recovery`.
- **`src/pages/public/BetaInviteAccept.jsx`** — step 2 now reads “Your invitation is accepted. Sign in to open your workspace.” and the button (**Continue to Sign In**) routes to `#/sign-in?org=T2%20Holdings%20LLC`, carrying context forward.

Role is deliberately **`operator`** so internal-only surfaces stay guarded.

## Guardrails honored
- **Not faked auth / no guard bypass:** the session uses the app’s own dev-identity mechanism; `deps.py` honors dev headers **only** in local development on loopback, so hosted environments ignore them and `/me` returns 401 → no session. `/beta-ops` and `/admin` remain guarded (verified).
- No provider calls, no catalog/data mutation, no auth/role-guard logic changed; loopback/private-beta assumptions preserved.

## Verification
| Check | Result |
|---|---|
| `npm run build` | clean — 82 modules, 0 errors |
| `node verify-smoke.cjs` | 40 passed / 0 failed |
| `node verify-guards.cjs` | 8 passed / 0 failed |
| `node verify-acceptance.cjs` | 26 passed / 0 failed |
| `node verify-invite-flow.cjs` (new) | **11 passed / 0 failed** |
| `python -m pytest test_invite_flow.py -q` | 7 passed / 0 failed |
| `python -m pytest foundation/tests/test_private_beta.py test_private_beta_postgres.py test_subscriber_operations.py -q` | 28 passed / 7 skipped |

New harness `verify-invite-flow.cjs` exercises: Accept Invitation → accept screen (no 404) → Confirm → **carry org context to `#/sign-in`** → fields prefilled T2/123abc → wrong creds rejected inline → correct creds → `#/home` with **service navigation in the rail** → **session persists across refresh** → operator still blocked from `/beta-ops` and `/admin`.

Evidence: before = inert sign-in (no handler); after = `screenshots/59b-signin-prefilled.png`, `59c-signed-in-workspace.png` (Command Center + full service nav, role Operator), `59-invite-accepted-step2.png`.

## Pre-existing failures (NOT caused by this change)
`foundation/tests/test_frontend_gate.py`:
- `test_ui_source_uses_semantic_forms_and_labels` → `FileNotFoundError: northstar-os-ui/src/components/Sidebar.jsx` (retired legacy shell).
- `test_legacy_ui_cutoff_present_in_bundle` → bundle marker `"Legacy UI disabled"` absent (retired legacy shell).
Both reference the pre-UI-v3 legacy foundation shell and fail independently of this fix. Reported only; not changed (legacy-UI-cutoff test retirement is a separate hygiene decision).

## Notes / out of scope
- `BetaLanding`’s Terms/Privacy anchors still use `href="/legal"` (no client legal route) — pre-existing, unrelated.
- No backend/provider wiring was added or altered.
