# SourceScout P2 Polish + Reference-Standard Freeze — 2026-09-27

Applied the six approved P2 polish items only; SourceScout frozen as the reference-standard room
for all future suite visual reviews. No redesign pass unless a regression appears.

## Changes
1. **Decision Rail grid pinned** — `app.css`: `@media (min-width: 1100px) { .grid-5 { grid-template-columns: repeat(5, 1fr); } }` → 10 gates split cleanly 5+5 (no empty slots).
2. **StatusPill neutral** — `ProductFinder.jsx`: "Researching"/"Watch" now `pill-muted`; ochre reserved for actual warning/risk states (Restricted/Blocked/Failed).
3. **Hero identity strip full-width** — strip moved out of the text column; now spans the entire card beneath text and actions, closing the blank band.
4. **Related buttons capped** — "Open Golden Goose" / "Send to Commerce Ops": `align-self: flex-start; min-width: 180px`.
5. **Avatar identity consistency** — `TopNav.jsx`: unauthenticated renders "?" avatar (title "Guest"), matching the INVITEE rail state.
6. **Identity strip spacing** — column gap 16→24px for even distribution.

## Verification
- `npm run build` — clean, 0 errors (703ms).
- `node verify-smoke.cjs` — 19/19 PASS.
- `node verify-guards.cjs` — 8/8 PASS.
- Reference screenshots captured: `screenshots/24-sourcescout-reference-standard.png` (1440×900 above-fold), `24b-sourcescout-reference-below-fold.png`.
- `00_STATE.json` current_phase updated with the freeze note.

## Benchmark contract for next service reviews
SourceScout (`ProductFinder.jsx` + `.workbench` density + truth-pill system) is the visual/structural benchmark:
- RoomTabs owns service-local nav (`?view=` deep links); single primary header action.
- Hero with identity strip; truth pills (UNKNOWN filled grey / UNVERIFIED dashed ochre / estimates muted) in hero, rails, and tables.
- Neutral internal statuses ("Internal review ready"), ochre reserved for real warnings, no green implying authorization.
- Provenance wording: observed/cached snapshot/historical; "not live Amazon data" explicit.
- Scoped `.workbench` density; invitee rail shows sign-in card; suite shell never blank.
