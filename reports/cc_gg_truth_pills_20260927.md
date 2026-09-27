# Command Center + Golden Goose — Review Fixes (2026-09-27)

## Scope
Applied the fixes approved in the joint Command Center / Golden Goose Finder visual review (both rooms had passed with P1/P2 polish items; SourceScout remains the frozen reference-standard room — untouched).

## Golden Goose Finder (P1)
File: `northstar-os-ui/src/pages/internal/GoldenGoose.jsx`

1. **Freshness/provenance column added to Opportunity Queue** — new `FRESHNESS` column renders `surfaced 2d ago · cached snapshot` as a muted pill with tooltip "Provenance stamp — cached snapshot, not live market data". Freshness data added to both sample opportunities (`freshness` field).
2. **"Confidence" renamed to "Research Confidence"** in all three surfaces:
   - Queue DataTable column header
   - Opportunity Detail card pill (`Moderate research confidence`)
   - Decision Log column header (with `—` passthrough for no-confidence rows)
   - All confidence pills carry `title="Data-quality signal — not a purchase recommendation"`. Pill tone mapping centralized in `CONF_PILL` (High → forest, Moderate → ochre, Low → warn); detail-card pill no longer uses `pill-ok` for High.

## Command Center (P2)
File: `northstar-os-ui/src/pages/internal/CommandCenter.jsx`

1. **Metric tile basis captions** — each of the four tiles now carries a muted 10px basis line with tooltip: "Basis: sample task list / sample queue / sample exception feed / sample portfolio", so counts can't read as live telemetry.
2. **Portfolio Exposure truth pills** (re-scoped from the review's "room grid" item — no room grid exists on this page; this is the only status grid):
   - Margin: `~18%` / `~22%` → muted pill + "Estimated value — not a verified calculation"; `UNKNOWN` → `pill-unknown`.
   - Status: `Research` → warn, `Approved` → muted pill + "Internal review state — not an authorization to purchase" (no green approval signal), `Active` → forest.
3. **What Changed truth-tone tags** — each timeline row now carries a `cached`/`observed` muted pill next to its date (cached = derived from cached sample data; observed = directly observed lifecycle event), so feed rows can't read as live streaming.

## Note on the "room grid" review item
The reviewed Command Center screenshot shows no room grid (the page is metric tiles + decision/queue cards + portfolio table + timeline). The approved fix ("per-room live status pills, pill-unknown fallback") was applied to the Portfolio Exposure status grid, the only grid on the page carrying statuses. If the reviewer intended a different surface (e.g., internal Home quick-access), flag it and it will be handled in that room's review.

## Verification
- `npm run build` — clean (81 modules, 662ms, 0 errors)
- `node verify-smoke.cjs` — **19 passed, 0 failed** (incl. `/golden-goose/GG-001` deep link + row-Open action)
- `node verify-guards.cjs` — **8 passed, 0 failed**

## Screenshots (recaptured post-fix, signed-out/invitee view matching review conditions)
- `25-command-center-truth-pills.png` — above fold: basis captions, portfolio pills at fold
- `25b-command-center-below-fold.png` — Portfolio truth pills + What Changed tone tags
- `26-golden-goose-truth-pills.png` — Research Confidence + Freshness columns
- Also confirms the committed TopNav "?" avatar and invitee rail sign-in card now render in captures (review item "screenshots predate avatar fix" resolved)

## Acceptance state
- Both rooms approved in review; GG P1s applied first as directed; no P0 blockers before ListingForge/AdPilot reviews.
- Harness `capture-cc-gg.cjs` kept alongside verify scripts for reproducible recapture.
