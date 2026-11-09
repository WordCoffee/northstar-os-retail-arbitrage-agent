# ux-06 — shell chrome on every service route

Branch `ty/ux-06-shell` (from `6ae869b8`). Worktree `state/worktrees/ux-06`.

## What was wrong

`App.jsx` rendered `<TopNav>` unconditionally but the side rail only in advanced view
(`{!simpleMode && <SuiteRail/>}`). The default view is Northstar (`mode !== 'advanced'`), so every
room — /listings, /product-finder, the whole catalogue — rendered with a top bar and **no side
nav**. The dev banner was inline markup in `App.jsx` while `pages/public/SignIn.jsx:34` already
claimed "DevBanner renders on every page via the shell" — there was no such component.

## What changed

New files (all under `northstar-os-ui/src/shell/`):

- `ShellLayout.jsx` — the chrome. TopNav + SuiteRail + `<main data-testid="workspace-outlet">`
  containing a real React Router `<Outlet/>`, plus MobileBottomNav, the tools sheet and the
  CommandPalette (moved out of `App.jsx`). The outlet is a slot: a room keeps its own header,
  grid, panels and scroll container. Chat-first routes get the same frame with the
  `main-content-simple` class, so `/` and `/home` keep the chat as the page's own layout.
- `DevBanner.jsx` — the dev notice, rendered by `Shell` **above** the chrome switch, so it appears
  on every page including the exempt entry surfaces.
- `devBanner.js` — `devBannerVisible({ authMethod, localDev })`. Reads the backend flag:
  `/environment` (`foundation/api/router.py:466`) reports `auth_method`, resolved by
  `foundation/api/deps.py` (`"dev_shim"` when `dev_shim_enabled() && is_local`), carried on
  `session.authMethod`. `LOCAL_DEV` (`foundation/dev.js`, compile-time) covers a Vite dev bundle
  before the session resolves. No literal is hardcoded.
- `shellRoutes.js` — one source of truth for `SHELL_EXEMPT_PATHS = ['/beta', '/beta/accept',
  '/sign-in', '/recovery', '/legal']`, `isShellExempt()` and `isPublicPath()`. Replaces the
  duplicated `PUBLIC_PATHS.some(...)` gate that appeared twice in `App.jsx`.
- `shellRoutes.test.js`, `devBanner.test.js` — 9 unit tests. One parses `App.jsx` and pins the
  exempt list to the registered table, so the two cannot drift.

Changed:

- `northstar-os-ui/src/App.jsx` — `GuardedRoutes` now declares **one layout route**
  (`<Route element={<ShellLayout role={role} />}>`) and every authed route is a child of it. A route
  added there cannot be missing the chrome. The five exempt surfaces are siblings rendered through
  `ShellLayout`'s exempt branch (outlet only, no top bar, no rail). `AccessDenied` renders inside the
  layout. `RouteFallback`, `MOBILE_ACTIVE`, the tools-sheet markup and the four chrome imports moved
  into `ShellLayout`.

Added test: `tests/e2e/shell-chrome.spec.ts` (reads the route table from `App.jsx` at run time and
classifies with the app's own `shellRoutes.js`).

## Route table count

- 72 `<Route path="…">` entries in `App.jsx` (pinned by both the unit test and the e2e spec).
- 66 concrete in-shell patterns + the `*` catch-all (in-shell) + 5 exempt = 72.
- All 67 in-shell paths were visited and asserted; the 5 exempt were asserted to have no chrome.

## Commands and real output

```
cd northstar-os-ui
npm ci                        # completed (audit summary only)
npm run build                 ->  ✓ built in 1.42s        (0 errors)
npx vitest run src/shell      ->  Test Files  2 passed (2)
                                  Tests  9 passed (9)
npx playwright test tests/e2e/shell-chrome.spec.ts --project=chromium-desktop
                              ->  6 passed (1.8m)
```

Notes on the commands:

- `vitest` is **not** a project dependency and was not added (no new dependencies). It ran
  ephemerally via `npx` (v5.1.0, `npm_config_yes=true`). `package.json` / `package-lock.json` are
  unchanged.
- The Playwright glob `tests/e2e/shell*.spec.ts` is passed to the explicit filename on PowerShell
  (PowerShell does not expand native-command globs); the file matches the pattern.
- The backend on `127.0.0.1:8000` was **down** during the e2e run (vite proxy `ECONNREFUSED` in the
  log). The chrome assertions do not depend on backend data, and the data-gated pages still rendered
  their own route; the banner still appears because it is a dev-build + backend-auth-method signal.

## What I did NOT do

- Did not run pytest (belongs to the other lane) or any non-localhost browser target.
- Did not run the other e2e suites (`ux_scorecard`, `ux_service_routes`, `smoke`, …); the changes
  keep their selectors (`[data-testid="dev-banner"]`, `mb-shell`, `chat-input`, `.top-nav`, `main`).
- Did not change any CSS, any page, any component outside `src/shell/**` and `src/App.jsx`
  (plus the required test spec and this report).
- No new dependencies; no merge, no push, no tag.

## Reviewer should look at first

`ShellLayout.jsx` + the single `<Route element={<ShellLayout role={role} />}>` block in `App.jsx`:
that layout route is the whole mechanism, and the known visual consequence is that the side rail now
also appears beside the chat on `/` and `/home` (the chat column narrows by the 200 px rail).
