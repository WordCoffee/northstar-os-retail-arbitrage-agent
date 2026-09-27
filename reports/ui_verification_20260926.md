# UI v3 Verification Report — 2026-09-27

Scope: read-only verification of commit `f296eec` (UI v3 architecture pass) per operator request,
plus one defect found by the tests and fixed.

## Task 1 — Post-commit working tree & orphaned pages

Command: `git status --short`

Result:
- Only runtime churn from the backend is modified/deleted:
  - `M Northstar_backend/data/northstar.db`, `D .../northstar.db-shm`, `D .../northstar.db-wal` (SQLite runtime)
- Untracked (not staged, not deleted): `.playwright-mcp/`, `screenshot-beta-landing.png`, `screenshot-errors.log`, root `screenshots/`, `Northstar_backend/costco_non_kirkland/`
- 9 orphaned pages remain untracked, **not deleted** (pending operator review):
  - `src/pages/customer/{Downgraded,Home,Legal,Reaccept,Suspended}.jsx`
  - `src/pages/internal/{Home,Listings,Portfolio,Sourcing}.jsx`
- Confirmed by repo-wide grep (`.jsx`/`.js`/`.cjs`/`.mjs`): none of the orphaned components is imported or routed anywhere. `App.jsx` routes only `/home` → CommandCenter and `/listings` → ListingGuardian (the only grep hit for "Listings" is that route string).

## Task 2 — Route-guard tests (direct URL access)

Command: `node verify-guards.cjs` against `http://127.0.0.1:8104/ui/` (vite preview).
Method: Playwright chromium; authenticated roles simulated by stubbing `/api/v1/foundation/{ui-mode,me,environment,preview/active}` via `page.addInitScript` + `ns-dev-session` in localStorage.

Result: **8 passed, 0 failed**

| Case | Assertion | Result |
|---|---|---|
| signed-out (invitee) | direct `#/beta-ops` → `#/home`, admin content absent | PASS |
| signed-out (invitee) | direct `#/admin` → `#/home`, admin content absent | PASS |
| customer | direct `#/beta-ops` → `#/home`, admin content absent | PASS |
| customer | direct `#/admin` → `#/home`, admin content absent | PASS |
| customer (375×667) | mobile Tools sheet shows ONLY Customer Workspace | PASS |
| platform_admin (control) | `#/beta-ops` loads | PASS |
| platform_admin (control) | `#/admin` loads | PASS |
| platform_admin (375×667) | mobile Tools sheet includes Beta Operations + Administration | PASS |

### Defect found & fixed during testing
Initial run: **FAIL customer `#/beta-ops`** — redirect worked (`#/home`) but the desktop **SuiteRail** rendered the
"Beta Operations" (and "Administration") nav items to a customer.

Root cause: `src/components/SuiteRail.jsx` filtered nav **groups** by role but rendered **all** sections inside a
passing group. The mobile Tools sheet in `App.jsx` filtered per-section correctly, which is why only the desktop rail leaked.

Fix: per-section role filter (same logic as the tools sheet):
```js
const filtered = NAV_GROUPS
  .filter(g => g.sections.some(s => canUseRole(s, role)))
  .map(g => ({ ...g, sections: g.sections.filter(s => canUseRole(s, role)) }))
  .filter(g => g.sections.length > 0)
```
Rebuilt (`npm run build` — clean, 0 errors) and re-ran: **8/8 PASS**. Guard redirects were already correct; this was a nav-visibility leak only.

## Task 3 — Smoke tests (wired actions + deep links)

Command: `node verify-smoke.cjs`.
Method: direct URL deep links asserted by body-text markers; action buttons clicked and asserted by resulting hash / toast text.

Result: **19 passed, 0 failed**

Deep links (8): `/profitability?view=scenario` (Scenario Calculator), `/autothink?view=composer` (Research Run Composer),
`/customer-workspace?view=services` (Entitled Services), `/keyword-tracker?view=terms` (Tracked Terms by ASIN),
`/commerce-ops/CO-01` (Sourcing Validation), `/product-finder/B08L5VJQ7T` (Product Set — B08L5VJQ7T),
`/golden-goose/GG-001` (Water Filter Pro), `/listings?view=rules` (Guardian Rules).

Actions (11): ListingGuardian New Rule → `#/listings?view=rules`; ListingForge Create Listing → `#/listingforge?view=editor`;
AdPilot Create Campaign → `#/adpilot?view=planner`; AutothinK New Research Run → `#/autothink?view=composer`;
ProductFinder Saved Sets → `#/product-finder?view=saved`; GoldenGoose row Open → `#/golden-goose/GG-001`;
GoldenGoose Open SourceScout → `#/product-finder/B08L5VJQ7T`; CommerceOps row Open → `#/commerce-ops/CO-01`;
CommerceOps New Workflow → info toast; Profitability Export Report → info toast; CommerceOps New Workflow no unexpected navigation.

## Task 4 — Screenshot count (fresh vs legacy)

Command: `Get-ChildItem northstar-os-ui/screenshots -File`

Result: **34 total = 26 fresh + 8 legacy**
- Fresh (numbered, this pass): `1,2,3,4,5,6,7,7b,8,8b,9,9b,10,10b,11,12,13,14,15,16,17,18,19,20,21,22` (incl. subview variants `7b/8b/9b/10b` and mobile `3`,`12`).
- Legacy retained (unnumbered): `beta-landing, beta-ops, customer-home, golden-goose, mobile-customer-home, mobile-product-finder, product-evidence, product-finder`.

## Files
- Fix: `northstar-os-ui/src/components/SuiteRail.jsx` (per-section role filter)
- Test harnesses (kept, reproducible): `northstar-os-ui/verify-guards.cjs`, `northstar-os-ui/verify-smoke.cjs`

## Summary
- Route guards: effective (redirect-only leak on desktop rail fixed).
- Wired actions & deep links: all 19 smoke checks pass.
- Screenshots: 26 fresh + 8 legacy confirmed.
- Orphaned pages: untouched, awaiting operator review; no imports/routes found.
- Build: `npm run build` clean (0 errors) after fix.