# Post-Acceptance P2 Hardening (2026-09-27)

Executed only the safe P2 hygiene items. No broad redesign. SourceScout untouched. No live providers, no spend, no scraping, no catalog/production-data mutation.

---

## P2-1 — Repository / test hygiene

**Object:** untracked `Northstar_backend/costco_non_kirkland/tests/test_brightdata_schema_test.py`.

- **First inspection:** broken — `SyntaxError: closing parenthesis ')' does not match opening parenthesis '[' on line 63`, which aborted plain `pytest` collection for the whole package.
- **Re-inspection during this pass:** file is now syntactically valid and complete (102 lines). It tests `resolve_product_url`, `is_costco_product_url`, and `build_schema_test_manifest`, all of which exist in the (tracked) `brightdata_costco_enrichment.py`.
- **Classification:** **legitimate test, previously incomplete WIP**, since completed by the parallel Bright Data workstream (not owned by this pass).
- **Action taken:** none against the file — it is a parallel workstream's untracked WIP, so it was neither edited, committed, nor deleted. Plain collection verified clean.

**Plain `python -m pytest costco_non_kirkland/tests -q` → 191 passed, 0 failed.**

**Live-capability note (not touched):** a new untracked `Northstar_backend/costco_non_kirkland/brightdata_costco_live.py` appeared (a live Bright Data collector). It fails closed unless **all** gates are present (`approved`, collector id, ≤3 URLs, `max_inputs` ≤3, `spend_cap`, and an API token from env). It is not imported by any test; it was **not executed, not committed, and not modified**. Live-provider behaviour was not altered.

---

## P2-2 — Mobile layout polish (Creative Studio + Listing Guardian)

Added additive utility classes to `app.css` (desktop unchanged above 900px):

- `.grid-cards-3`, `.grid-cards-4` — fixed desktop columns; at ≤900px switch to horizontally scrollable columns with a minimum card width (scroll affordance via a visible cut card).
- `.split-aside`, `.split-aside-l`, `.split-aside-r` — desktop two-pane; at ≤900px stack to one column.

Applied:
- **Creative Studio:** briefs / variants / assets → `.grid-cards-3`; exports → `.split-aside`; library → `.grid-cards-4`.
- **Listing Guardian:** diffs → `.split-aside-l`; history → `.split-aside-r`.

No text shrinking; desktop compositions and room identity preserved. 375px screenshots captured (`57*`).

---

## P2-3 — Truth-state semantic cleanup (Provider Adapters)

- Sample adapter-state pills that used green-ish `pill-forest` (`Active`, `Configured`) → `pill-muted`, with a "sample/observed — not a live probe" title.
- Added a legend: *"Adapter states here are sample/observed. Green is reserved for genuinely probe-backed, live-verified outcomes; adverse states keep their distinct colour."*
- Adverse-state semantics preserved: `Rate Limited` → `pill-warn`, `Idle` / `Unbound` → `pill-muted`.

Path: `northstar-os-ui/src/pages/internal/ProviderAdapters.jsx`.

---

## P2-4 — Text hygiene

Investigated the reported mojibake em-dash (`"Costco products �?" Collect by URL"`).

- Byte-level scan for the Unicode replacement character (U+FFFD) across `.py/.md/.json/.csv/.sql/.txt/.js/.jsx` → **none found**.
- `config/brightdata_costco_collector.json` contains a correct UTF-8 em-dash (`Costco products — Collect by URL`); the earlier artifact was a PowerShell console-encoding rendering only.

**No change required** (avoids an unnecessary copy edit). Reported as a non-issue.

---

## P2-5 — Legacy-page inventory (report only; nothing removed)

28 page modules are imported by no router and no component. The router is `App.jsx` (the only entry from `main.jsx`).

**Tracked — unreachable legacy (candidate for a later removal PR):**
- `src/pages/Account.jsx`, `Auctioneer.jsx`, `Hub.jsx`, `Ledger.jsx`, `OfferChisel.jsx`, `Prospector.jsx`, `RankLedger.jsx`, `RivalBoard.jsx`, `TheWatch.jsx`, `TownCrier.jsx`
- `src/pages/public/BetaDenied.jsx`, `BetaInviteAccept.jsx`, `LegalPreview.jsx`
- `src/foundation/pages/BetaOps.jsx`, `BetaSignup.jsx`, `BetaTester.jsx`, `FoundationStatus.jsx`, `Jobs.jsx`, `Keywords.jsx`

**Untracked — orphaned (never committed; must be excluded from commits):**
- `src/pages/customer/Downgraded.jsx`, `Home.jsx`, `Legal.jsx`, `Reaccept.jsx`, `Suspended.jsx`
- `src/pages/internal/Home.jsx`, `Listings.jsx`, `Portfolio.jsx`, `Sourcing.jsx`

**Supporting dead references:** `src/data/services.js` is imported only by `src/foundation/components/CommandPalette.jsx`, which is itself unimported; `src/foundation/pages/*` have no importers.

**Classification:** active — none; unreachable legacy — all of the above; test fixture — none found; candidate for a later removal PR — the **tracked** legacy set (requires a dedicated removal PR, with build + smoke + guards re-run).

**Safety note:** several legacy modules (`pages/Account.jsx`, `Hub.jsx`, `TownCrier.jsx`, `OfferChisel.jsx`, `pages/Autothink.jsx`) contain provider/`fetch` calls. They are unreachable today and must not be re-wired without review. Nothing was deleted.

---

## Verification
| Check | Result |
|---|---|
| `npm run build` | clean — 82 modules, 0 errors (css 38.06 kB, js 429.41 kB) |
| `node verify-smoke.cjs` | 40 passed, 0 failed |
| `node verify-guards.cjs` | 8 passed, 0 failed |
| `node verify-acceptance.cjs` | 26 passed, 0 failed |
| `python -m pytest costco_non_kirkland/tests -q` | 191 passed, 0 failed (plain collection clean) |
| 375px captures | `screenshots/57*` (Creative briefs/variants/assets/exports/library; Guardian diffs/history; Provider Adapters) |

## Files changed (safe, localized — one commit)
- `northstar-os-ui/src/styles/app.css` (responsive room-grid utilities)
- `northstar-os-ui/src/pages/internal/CreativeStudio.jsx`
- `northstar-os-ui/src/pages/internal/ListingGuardian.jsx`
- `northstar-os-ui/src/pages/internal/ProviderAdapters.jsx`
- `northstar-os-ui/capture-p2-mobile.cjs` (new)
- `northstar-os-ui/screenshots/57*`
- `reports/post_acceptance_p2_hardening_20260927.md`

## Concurrency note
A parallel Bright Data workstream is active in the repo (uncommitted modifications to `brightdata_costco_enrichment.py`, `cli.py`, `test_brightdata_preflight.py`; new untracked `brightdata_costco_live.py`, `config/brightdata_costco_collector.json`, `provider_research_*`, DB/snapshot churn). None of it was committed, modified, executed, or deleted by this pass.
