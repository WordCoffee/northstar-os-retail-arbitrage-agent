# UX-05 — service routes rendered the chat shell

2026-11-08 · branch `ty/ux-05` · worktree `state/worktrees/ux-05`

Starting measurement: `python -m tools.vision.ux_audit --run` → **3 of 29** service
routes rendered (`account`, `beta`, `design-studio`). 26 opened the Bojo chat shell.

## Cause

Two defects stacked. Both are in `northstar-os-ui/src/App.jsx`.

**1. The Northstar gate replaced every route with the chat shell.**
`Shell()` computed `keepAdvanced = SIMPLE_KEEP_ADVANCED.some(...)` and rendered
`<MasterBrainShell/>` for any path not on that hand-maintained regex list
(`App.jsx:336` before the change, `MasterBrainShell.jsx:227` renders
`<ChatSurface heading="Bojo">`). The router was fine — `/listings` did have
`<Route path="/listings" element={<ListingGuardian/>}` — but `Shell` never
reached `GuardedRoutes` for it. `SIMPLE_KEEP_ADVANCED` held only
account/legal/admin/public surfaces plus design-studio, workbench, improvement and
galactic; every service added after the list was written (listings, socialpulse,
competitor-monitor, adpilot, the whole legacy catalogue) fell through. This is why
`account`, `beta` and `design-studio` worked and the other 26 did not.

**2. Fourteen catalogue rooms had pages but no route at all.**
`src/pages/Hub.jsx`, `Ledger.jsx`, `Prospector.jsx`, `GoldenGoose.jsx`,
`OfferChisel.jsx`, `TownCrier.jsx`, `Auctioneer.jsx`, `TheWatch.jsx`,
`RankLedger.jsx`, `RivalBoard.jsx` and `src/foundation/pages/`
(`FoundationStatus`, `Jobs`, `Keywords`, `BetaSignup`) existed and were exported in
`ty/services.json`, but `GuardedRoutes` had no `<Route>` for `/hub`, `/ledger`,
`/prospector`, `/goldengoose`, `/offerchisel`, `/towncrier`, `/auctioneer`,
`/thewatch`, `/rankledger`, `/rivalboard`, `/foundation`, `/jobs`, `/keywords`,
`/beta-signup`. Fixing only the gate would have sent them to NotFound.

**3. Two smaller gate defects surfaced by the same audit.**
- `/beta-ops` redirected a non-admin session to `/home` — i.e. to the chat shell —
  so an entitlement gate was indistinguishable from the shell defect. The audit
  session is the dev operator (`foundation/session.jsx:45-58`), which is why
  `/account` rendered and `/beta-ops` did not.
- `/beta#support` is registered as a service but the landing page had no `#support`
  section, so the deep link was byte-identical to `/beta`.

## Fix

- **Inverted the gate** (`App.jsx:269-285`): the allowlist is gone. `CHAT_FIRST_PATHS`
  is `[/^\/$/, /^\/home(\/|$)/]`; everything else renders the page its `<Route>`
  declares. A new room cannot be swallowed again by forgetting to add it to a list,
  and an unknown path now gets NotFound instead of a chat surface pretending to be it.
  `Shell` uses `chatFirst` for the branch and the `main-content-simple` class
  (`App.jsx:333,374,382`).
- **Routed the 14 catalogue rooms** (`App.jsx:227-243`) through a single adapter,
  `src/pages/roomAdapters.jsx`, which supplies the `toast`/`navigate` props those
  pre-router pages were written against (they would throw on the first click if
  mounted bare). One translation point instead of editing eleven pages.
- **`/beta-ops` gate now renders instead of redirecting** (`App.jsx:108-126`, used at
  `App.jsx:180,311`): `data-testid="route-access-denied"` names the required role and
  shows no data. No entitlement is weakened; a platform-admin session still gets the
  tester dashboard.
- **`/beta#support`** (`pages/public/BetaLanding.jsx:47-65`) renders a real support
  section only when the hash is present. Same document as `/beta` by design; now the
  deep link lands somewhere and the route is distinguishable.
- **`/beta-signup`** is public (`App.jsx:159`): an invitee has no session yet, so the
  invite-entry page no longer bounces to `/sign-in`.
- `MasterBrainShell.jsx` header comment corrected: it is Bojo's home, not a
  replacement for every room.
- `scripts/verify-galactic-deck.cjs`: two static checks updated to the new reality —
  accept the `React.lazy` import of the deck (the eager-import check had been red on
  `staging` before this branch), and assert the deck is not in `CHAT_FIRST_PATHS`
  instead of the removed `SIMPLE_KEEP_ADVANCED` regex.

## Routes now rendering

All 29 entries of `ty/services.json`, in file order:

`/hub`, `/ledger`, `/prospector`, `/goldengoose`, `/offerchisel`, `/towncrier`,
`/auctioneer`, `/autothink`, `/thewatch`, `/rankledger`, `/rivalboard`, `/account`,
`/foundation`, `/jobs`, `/keywords`, `/beta`, `/beta#support`, `/beta-signup`,
`/beta-ops`, `/design-studio`, `/product-finder`, `/golden-goose`, `/listings`,
`/keyword-tracker`, `/competitor-monitor`, `/listingforge`, `/adpilot`,
`/socialpulse`, `/profitability`.

Two honest qualifications:

- **`/beta-ops` is admin-gated.** A platform admin gets the tester dashboard
  (`bo-admin-dashboard`). The dev operator session gets the explicit access-denied
  surface, not the dashboard and not the chat shell. The entitlement is unchanged.
- **`/beta#support` is deliberately the `/beta` document.** It is a section, not a
  second page; the section renders only for the hash, which is the marker.

The same inversion also fixed routes outside the 29 that were falling into the shell:
`/monitoring`, `/spreadsheet-lab`, `/commerce-ops`, `/memory-bank`, `/shared-data`,
`/provider-adapters`, `/master-brain`, `/improvement`, `/galactic`.

**Deliberately chat-first:** none of the 29 services. `/` and `/home` remain the Bojo
shell (the product's home), and `/workbench` is the chat-docked workbench, not a room.
No service route renders a chat workspace as its only identity, so no route needed a
"Bojo-first" exception.

## Evidence

**New test** — `tests/e2e/ux_service_routes.spec.ts`: 29 route cases (marker + no
`mb-shell` + no `chat-input` + still on its own pathname) plus one test that `/home`
keeps the shell and an unknown path renders NotFound.

Proof on this worktree's code (dev server started from this worktree on `127.0.0.1:8102`,
because the already-running 8101 server serves the main worktree):

```
$ npx playwright test tests/e2e/ux_service_routes.spec.ts --reporter=line
60 passed (1.5m)          # 30 tests × chromium-desktop + chromium-mobile
```

The instrument catches the defect: the same spec run against the unmodified 8101
server (main worktree, `staging`) fails exactly where the audit did, and passes the
three routes that already worked:

```
$ npx playwright test ... --grep "hub renders|listings renders|design-studio renders|account renders"
2 failed   hub renders its own page (/hub)
           listings renders its own page (/listings)
2 passed   design-studio renders its own page (/design-studio)
           account renders its own page (/account)
```

**Build** (`northstar-os-ui`):

```
$ npm run build
dist/assets/roomAdapters-3sMznrYS.js   59.86 kB │ gzip: 15.84 kB
✓ built in 1.50s
```

**UI unit + static suite:**

```
$ npm test
ℹ pass 221
ℹ fail 0
PASS  src/data/nav-config.js parses
GALACTIC DECK VERIFIER: all checks pass
exit=0
```

**Pre-existing failure, not caused by this branch:** `tests/e2e/ux_scorecard.spec.ts`
→ `ux: scene readability` fails `stream_scroll_top` (574, expected 0) on `/home`.
Reproduced against unmodified 8101, and `/home` is untouched by this change; it is
chat history auto-scrolling the stream. The other five scorecard tests pass, including
service coverage.

## Files

- `northstar-os-ui/src/App.jsx`
- `northstar-os-ui/src/pages/roomAdapters.jsx` (new)
- `northstar-os-ui/src/pages/public/BetaLanding.jsx`
- `northstar-os-ui/src/foundation/pages/FoundationStatus.jsx` (`foundation-status` marker; page-owned loading/error/ready)
- `northstar-os-ui/src/foundation/pages/Jobs.jsx` (`jobs-status` marker)
- `northstar-os-ui/src/foundation/pages/Keywords.jsx` (`keywords-status` marker)
- `northstar-os-ui/src/shell/MasterBrainShell.jsx` (comment)
- `northstar-os-ui/scripts/verify-galactic-deck.cjs` (two stale checks)
- `tests/e2e/ux_service_routes.spec.ts` (new)
