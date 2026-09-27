# Invite-Accept 404 — Root Cause & Fix (2026-09-27)

## Symptom
Clicking **Accept Invitation** on the private-beta landing page produced a raw server 404 body (`{"detail":"Not Found"}` on the FastAPI-served UI) instead of the accept screen.

## Reproduction (local, browser)
- Start at `http://127.0.0.1:8104/ui/#/beta`.
- Click **Accept Invitation**.
- Result (before fix):
  - `GET http://127.0.0.1:8104/beta/accept` → **404**
  - Browser URL becomes `http://127.0.0.1:8104/beta/accept` (leaves the `/ui/` SPA base and its hash router)
  - Body: `The server is configured with a public base URL of /ui/ …` (Vite preview). On the FastAPI `/ui` mount the body is the reported `{"detail":"Not Found"}`.

## Failing request / caller
- **Request:** `GET /beta/accept` (absolute path, i.e. server route — not a client route).
- **Caller:** `northstar-os-ui/src/pages/public/BetaLanding.jsx:38`
  `onClick={() => window.location.href = '/beta/accept'}`.

## Classification
**Wrong frontend navigation.** The app uses `HashRouter` and is served under a non-root base (`/ui/`), but the button performed a full-page navigation to the absolute server path `/beta/accept`:
- `/beta/accept` is **not a backend route** (backend exposes `/legal/{name}`, `/api/v1/invites*`, etc.), so a server 404 is correct.
- There was **no client route** `/beta/accept` either, even though a purpose-built `BetaInviteAccept` component (titled "Accept Invitation") already existed but was unrouted.
- It is **not** a missing backend route, stale invite URL, or provider issue.

## Fix (smallest correct layer — frontend navigation + missing client route)
1. `src/App.jsx` — import `BetaInviteAccept` and register the client route:
   `<Route path="/beta/accept" element={<BetaInviteAccept />} />`.
2. `src/pages/public/BetaLanding.jsx` — navigate **within** the SPA hash router:
   `window.location.hash = '#/beta/accept'`.
3. `src/pages/public/BetaInviteAccept.jsx` — same bug class in the same flow: "Enter Workspace"
   changed from `window.location.href = '/home'` to `window.location.hash = '#/home'`.

No redesign; no guard/role changes; no provider changes.

## Verification
| Check | Result |
|---|---|
| Browser re-run (after fix) | `#/beta` → click → `http://127.0.0.1:8104/ui/#/beta/accept`; **Accept Invitation screen renders**, no 404 |
| `npm run build` | clean — 82 modules, 0 errors |
| `node verify-smoke.cjs` | 40 passed / 0 failed |
| `node verify-guards.cjs` | 8 passed / 0 failed |
| `node verify-acceptance.cjs` | 26 passed / 0 failed |
| `python -m pytest test_invite_flow.py -q` | 7 passed / 0 failed |

Evidence: before = repro log (`GET /beta/accept → 404`, URL left the SPA); after = `northstar-os-ui/screenshots/58-invite-accept-after.png`.

## Notes / out of scope
- The backend intentionally has no `/beta/accept` route; this surface is SPA-owned.
- The accept card's Terms/Privacy anchors still use `href="/legal"` (pre-existing, unrelated to this bug; no client legal route). Flagged, not changed, to keep this fix minimal.
- Loopback/private-beta assumptions and customer/operator/admin/Beta-Ops routing are unchanged.
