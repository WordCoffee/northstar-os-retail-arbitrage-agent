# 06 — Canonical Frontend Serving (1C-06)

**Status:** ✅ **PASS** — RUNTIME_CONFIRMED (SQLite 517 passed / 28 skipped;
frontend gate 23 + 7 passed).

## D01 — Serving

- **React/Vite is canonical.** `northstar-os-ui` builds to `northstar-os-ui/dist`
  (`npm run build`). The foundation FastAPI app serves it loopback-only at
  `/ui/` with an SPA fallback: `/ui/{path}` returns the built index.html for
  unknown paths, and hash routing (`#/jobs`) keeps deep links client-side.
- Static hashed assets are served with `immutable` caching; the authenticated
  shell HTML is `no-store`.
- Legacy/demo frontend status: the pre-existing Analyst's Desk shell under
  `/northstar-os` (static `css/js` SPA) is documented as legacy and NOT the
  canonical frontend. It is left untouched.
- Development proxy: `vite.config.js` proxies `/api`, `/health` to
  `127.0.0.1:8000`.

## D02–D04 — Authentication, organization, preview

- `foundation/api.js`: JWT bearer token support (stored in localStorage, never
  in URLs/logs); falls back to local dev identity headers in development only.
- `foundation/session.jsx`: signed-in/signed-out/expired/revoked states;
  401 clears the token; server-validated organization switching; suspended
  membership → 403; preview banner + audited entry/exit.
- Server enforcement unchanged and authoritative (Phase 1C-01): issuer,
  audience, signature, expiry, revocation, memberships, cross-org denial.

## D05 — Account

Production-shaped foundation Account page: profile, organization & members,
roles, security & sessions (revocation), plan/credits/usage (shadow ledger),
integrations & provider posture (Amazon / Amazon Ads / suppliers / social all
labeled truthfully as not configured), recent audit activity. No raw keys
exposed.

## D06 — Operations Hub

`foundation/pages/FoundationStatus.jsx` consumes REAL foundation data:
authentication posture, environment, queue posture (queued/leased/running/
dead-letter), scheduler posture, approval queue, shadow credits, reservations,
provider status, import status, recent audit activity, exceptions, and
actionable next steps. No fabricated operating metrics.

## D07 — Ledger

Foundation shadow ledger wired through `/usage/summary` (granted / consumed /
reserved / balance) — no duplicate Balance/Available presentation.

## D08 — Jobs & Schedules UI

New `foundation/pages/Jobs.jsx`: queue posture metrics, job list with states,
job detail + audit timeline, submit (job type + payload), cancel, authorized
retry, schedules list + enable/disable, worker posture. Mutations only via
explicit buttons; page load performs zero writes.

## D09 — Keywords UI

New `foundation/pages/Keywords.jsx`: keyword search + detail, product
relationships, listing coverage, search-term performance, target performance,
import history + detail, rejected rows, provenance, conflicts, rank history
where data exists, source registry status. Unknown stays unavailable.

## D10 — Pinned drawer

`foundation/components/PinnedDrawer.jsx` — collapsible, hide/show, persistent
per-user preference via the UI-preferences API, keyboard accessible.

## D11 — Tours

`foundation/HelpTour.jsx` — first entry per service, Skip/Back/Next/Done,
Don't-show-again, per-user persistence, replay from Help, keyboard/focus
support via `role="dialog" aria-modal`.

## D12 — Accessibility

Static baseline verified (semantic forms with labels, dialog roles, aria
controls, nav labels, non-color status pills). Dynamic scan / keyboard-only
flows run in Workstream E.

## D13 — Security

CSP (`default-src 'self'`, `frame-ancestors 'none'`, `script-src 'self'`),
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
correct cache controls, bundle secret scan, no token in URLs.

## D14–D15 — Gate

`test_frontend_gate.py` (23 tests) + `test_1c06_gate.py` (7 tests): canonical
build + serving, SPA fallback/deep links, auth flows (401/403/revoked/
suspended/issuer/audience), organization switching + cross-org denial, preview
audit, security headers, bundle scan, GET-side-effect audit (no jobs/runs/
usage created on load), no provider calls on load, canonical economics contract
consumed from the UI.

## Evidence

| Command | Result |
|---|---|
| `npm run build` (northstar-os-ui) | ✓ built |
| `pytest foundation/tests` | 517 passed, 28 skipped |
| `pytest test_frontend_gate.py` | 23 passed |
| `pytest test_1c06_gate.py` | 7 passed |

## Warnings / gaps

- The built shell references Google Fonts (external CDN) — a passive network
  resource; the CSP permits only fonts.googleapis.com / fonts.gstatic.com.
  Loopback serving otherwise makes zero network calls.
- Dynamic accessibility scan is deferred to Workstream E (needs a running
  stack + browser).