# SourceScout Visual Correction Pass — 2026-09-27

Applied the approved visual-review corrections (P0 1–5, P1 6–12, P2 13–14) for SourceScout only.
Build clean; smoke 19/19 and route-guard 8/8 regressions green afterward.

## Changes

### P0
1. **Duplicate local nav removed** — `ProductFinder.jsx` PageLayout actions now hold a single primary "New Lookup" button; the duplicate "Search / Saved Sets / Coverage" header row is gone. RoomTabs is the sole service-local navigation.
2. **Invitee rail never blank** — `SuiteRail.jsx` renders a compact "Sign in to open your workspace" card with a Sign In CTA (→ /sign-in) when the role-filtered nav is empty; no dead 200px column.
3. **Table truth pills** — Market Evidence (and Product Set / Coverage tables) render UNKNOWN/UNAVAILABLE/REQUIRED/INCOMPLETE/UNMEASURED/NOT CALCULATED as `pill-unknown`, UNVERIFIED as a new dashed ochre `pill-unverified`, and `~18%`-style estimates as `pill-muted` (with title "Estimated value — not a verified calculation").
4. **Unsafe "approved" language removed** — product status `approved` → "Internal review ready" (neutral `pill-muted`, no green semantics) in Market Evidence, Product Set, and Saved Sets (Set C focus text updated too).
5. **UNKNOWN ≠ UNVERIFIED** — UNKNOWN is a filled grey data-missing pill; UNVERIFIED is a dashed ochre not-yet-confirmed outline (`app.css` new `.pill-unverified`).

### P1
6. **Freshness = provenance** — hero "2h ago" chip is now `pill-muted` with wording "observed 2h ago" and tooltip "Cached observation — not live Amazon data".
7. **Deduped Needs Verification** — Decision Rail header now shows a computed "6 of 10 gates unverified" count (ochre); the Operator Status row keeps the single Needs Verification signal.
8. **Decision Rail grid completed** — added Physical Data (UNMEASURED) and Fee Basis (UNAVAILABLE) gates → 10 items on a new 5-column `.grid-5`; no ragged second row.
9. **Hero identity density** — thumbnail 96→72px; new `.identity-strip` exposes UPC/GTIN (UNKNOWN), MPN/Model (UNAVAILABLE), Pack Count (UNKNOWN), ASIN State (UNVERIFIED) above the fold.
10. **Secondary action affordance** — `.btn-ghost` now carries a 1px divider border; "Send to Commerce Ops" reads as a real button with tooltip "Hand off this product to the Commerce Ops workflow queue".
11. **Provenance specificity** — Market Evidence footer: "Source: Provider adapter observation — cached snapshot, not live Amazon data · observed 2h ago …"; Provenance Timeline entries tagged (cached snapshot) / (historical).
12. **Above-the-fold density** — scoped `.workbench` class (SourceScout subviews only): card padding 20→16/18px, card gaps 20→14px; Market Evidence table rises in the viewport.

### P2
13. **Search field** — input width 220→300px and placeholder shortened to "Search the Northstar Index…" (no truncation).
14. **Hero polish** — identity strip + smaller thumbnail let identity content outweigh placeholder imagery.

## Verification after changes
- `npm run build` — clean, 0 errors.
- `node verify-smoke.cjs` — 19/19 PASS (deep links + wired actions, incl. ProductFinder Saved Sets tab click).
- `node verify-guards.cjs` — 8/8 PASS (SuiteRail role filter + invitee card change regression-safe).
- Fresh screenshots: `northstar-os-ui/screenshots/23-sourcescout-visual-pass.png` (1440×900 lookup view), `23b-sourcescout-below-fold.png`.

## Files
- `northstar-os-ui/src/pages/internal/ProductFinder.jsx` (rewrite: truth-pill system, identity strip, gate matrix, terminology, density)
- `northstar-os-ui/src/components/SuiteRail.jsx` (invitee sign-in card)
- `northstar-os-ui/src/components/TopNav.jsx` (placeholder)
- `northstar-os-ui/src/styles/app.css` (pill-unverified, grid-5, identity-strip, suite-rail-signin, workbench density, btn-ghost border, search width)