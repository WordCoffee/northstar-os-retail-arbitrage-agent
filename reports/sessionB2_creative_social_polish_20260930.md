# Session B2 — Creative Studio + SocialPulse Visual-Polish Fixes

> Branch: `fix/creative-social-polish-v2` (never pushed). Worktree:
> `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`.
> Base commit: `bd8e385`. Date: 2026-09-30.
> Mission: seven bounded, low-risk UI fixes from the screenshot review. Local-only;
> no provider, publishing, analytics, or generated media was touched or fabricated.

## Fixes

| # | Fix | Change |
|---|-----|--------|
| 1 | SocialPulse calendar day-match bug | `SocialPulse.jsx` — new `postsOnDay()` parses the day number from `Sep N` and compares numerically; a substring test (`includes('Sep 2')`) no longer matches `Sep 28`. |
| 2 | SocialPulse Workflow badge contradiction | `SocialPulse.jsx` — removed hard-coded `count: 2`; tab `count` is now `reviewCount` (posts in `In Review`) via `useMemo`, the same live local source as the Approvals queue and the board's "In Review" column. |
| 3 | Mobile bottom-nav occlusion (both rooms) | `app.css` — new `.room-bottom-safe` shell class + `@media (max-width:900px)` bottom padding `calc(28px + env(safe-area-inset-bottom,0px))`; applied to both room shells in the two JSX files. Final room content clears the fixed nav. |
| 4 | SocialPulse mobile calendar | `SocialPulse.jsx` + `app.css` — the 7-column grid (`display:none` under `480px`) is replaced by a compact `.sp-cal-agenda` list built from the same honest local schedule records (date · title · platform · state). |
| 5 | Creative Studio invalid variant actions | `CreativeStudio.jsx` — an `Approved` variant renders only a muted "Approved — no action needed" pill; the pending `Approve` / `Request Changes` buttons are gone. Non-approved variants keep state-appropriate actions (`Request Changes` hidden once already requested). |
| 6 | SocialPulse duplicated composer actions | `SocialPulse.jsx` — the in-card Draft Post footer now keeps only `Save Draft`; `Generate Variants`, `Schedule`, and `Send for Approval` remain in the room header, so destinations are not duplicated. |
| 7 | Creative Studio selected reference-chip styling | `CreativeStudio.jsx` + `app.css` — the reference chips (which sat outside `.room-toolbar` and had no styling) now use a dedicated `.ref-chip` / `.ref-chip.selected` class: unfilled base, and a filled pine background + white ink + check mark when selected. |

## Files changed (allowed scope only)

- `northstar-os-ui/src/pages/internal/SocialPulse.jsx`
- `northstar-os-ui/src/pages/internal/CreativeStudio.jsx`
- `northstar-os-ui/src/styles/app.css`

No backend, routes/APIs/auth/provider wiring, deployment, package manifest/lockfile,
shared business logic, or unrelated room was changed.

## Verification

- `npm run build` (Vite 5) → **0 errors**, 88 modules transformed (css 39.28 kB).
- `node verify-smoke.cjs` → **42 passed, 0 failed** (HARNESS_BASE_URL = local preview server).
- `node verify-guards.cjs` → **11 passed, 0 failed**.
- `git diff --check` → clean (exit 0).
- Local capture helper `capture-sessionB2.cjs` (untracked, not committed) → **15 passed, 0 failed**:
  day-match, live Workflow badge, agenda swap at 390px, variant-action state,
  single composer footer action, selected chip fill, and bottom-nav clearance are
  all asserted programmatically.

## Screenshots

New folder `northstar-os-ui/screenshots/sessionB-creative-social-polish-v2-20260930/`
(untracked; not staged). All are non-empty valid PNGs (IHDR-verified):

| File | Viewport | View |
|---|---|---|
| `creative-studio-desktop-populated-workflow.png` | 1440×900 | Variants & History — state-appropriate actions (V-101/V-105 Approved → no pending buttons) |
| `creative-studio-mobile-primary.png` | 390×844 @2x | Briefs (mobile shell) |
| `socialpulse-desktop-calendar-or-planning.png` | 1440×900 | September 2026 grid — `Sep 28` on day 28, day 2 empty |
| `socialpulse-desktop-queue.png` | 1440×900 | Workflow board |
| `socialpulse-mobile-primary.png` | 390×844 @2x | Calendar — mobile agenda (`Sep 28 · Installation guide`) |
| `socialpulse-mobile-composer.png` | 390×844 @2x | Composer (mobile) |
| `socialpulse-desktop-approvals.png` | 1440×900 | Approvals queue (optional) |
| `creative-studio-desktop-exports.png` | 1440×900 | Bundle Builder (optional) |

## Honesty notes

- The rooms remain local/stubbed exactly as before: browser-persisted sample records,
  no social OAuth, no publishing, no connected analytics provider (performance stays
  `UNKNOWN`), and no generated media. All honesty copy and provider-required
  boundaries are preserved unchanged.
- The mobile screenshots are full-page captures; the fixed bottom nav renders once at
  its viewport position (a capture artifact). The real bottom clearance is verified by
  the scroll-to-bottom assertion in the capture helper.

## Known limitations

- The phone-width calendar breakpoint is `480px` (safest local implementation); the
  390px target is well inside it.
- The `capture-sessionB2.cjs` helper is untracked and intentionally not committed; a
  `playwright` dev dependency was installed with `--no-save` (manifests untouched).

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `fix/creative-social-polish-v2`
**Base SHA:** `bd8e385`
**Commit:** single focused local commit (see chat)
**Files changed:** `SocialPulse.jsx`, `CreativeStudio.jsx`, `app.css` (+ this report)
**Checks:** build 0 errors · smoke 42/0 · guards 11/0 · `git diff --check` clean · capture assertions 15/0
**Screenshots:** 8 valid PNGs in `screenshots/sessionB-creative-social-polish-v2-20260930/` (not staged)
**Fixes verified:** all 7 (programmatic assertions + visual review)
**Known limitations:** 480px calendar breakpoint; full-page fixed-nav capture artifact; capture helper untracked
**Blocked items:** none
