# UI Interaction & Market Data Audit

Audit date: 2026-08-17. Offline-only sandbox audit — no network, no live
providers, no secrets. The served frontend is exactly one file:
`static/index.html` (served by `main.py:63-65`, mounted at `/`). The
reference contract is `docs/pre_ui_calculation_pipeline.md`; the
field-level audit from the previous session is
`docs/field-audit-report.md`.

---

## A. User-reported broken controls — audit of the served file

**CORRECTION (2026-08-17, second pass):** the first audit pass concluded
the controls were "wired and functional" and blamed a stale cached build.
That conclusion was an artifact of the VM harness, whose
`getElementById` auto-creates stub elements and therefore masked
null-node binding failures. A real headful-browser test (focusable tabs,
click and Enter both dead) exposed the true root cause:

**The inspection sheet and the sort/column popovers are parsed AFTER the
`<script>` tag** (script block 224665..422297; sheet at 422419+,
sortPopover at 424024+, colPopover at 426082+). `init()` ran
synchronously during parse, so at binding time `el('sheetNav')`,
`el('sheetClose')`, `el('sheetOverlay')`, `el('sortPopover')`,
`el('csSortSelect')` were all `null` and **every listener targeting
those nodes was silently skipped**. The sheet still opened (openSheet
queries nodes at click time), which is why the user saw a detail panel
with dead tabs/X/sort. Escape worked because it binds to `document`.

The binding table below documents each control, its selector, and its
real pre-fix status. The fix (init deferred to `DOMContentLoaded`) is
described in the Fixed section; the harness now mirrors the real boot
path (readyState `loading` -> no bindings -> fire DOMContentLoaded ->
bindings attach) and asserts it.

| Control | Selector / binding | Current behavior in served file | Root cause / status |
|---|---|---|---|
| Detail tabs (Overview/Source/Economics/Market/Verify) | `#sheetNav` click delegation on `.sheet-segment[data-segment]` (`index.html:7573-7580`) → `syncSheetNav` (`:7278`) + `renderSheetContent(seg, _sheetProduct)` (`:7287`) | Segments render distinct panels (overview = data availability + identity, source = Costco basis/pack, economics = `NS.feeBreakdownHtml`, market = `NS.sellerSectionHtml` + counts, verify = flag callouts); active class toggled. | **WAS DEAD in a real browser**: `#sheetNav` parsed after the script; delegation never bound at init. FIXED by deferred boot; now instrumented with `uiDebug` activation recording. Gaps closed: ARIA `role=tablist/tab`, `aria-selected`, `aria-controls`, focus moved into sheet on open. |
| Close/X on detail popup | `#sheetClose` click → `closeSheet` (`:7563-7564`, `:7262`); `#sheetOverlay` click → `closeSheet` (`:7561-7562`); global Escape → topmost panel (`:7568-7572`) | Removes `.open`, hides overlay, restores scroll, refocuses opener, nulls `_sheetProduct`. | **WAS DEAD**: both `#sheetClose` and `#sheetOverlay` parsed after the script → no listeners. Escape always worked (document-level). FIXED by deferred boot. |
| Sort control | `#csSortBtn` toggles `#sortPopover.hidden` (`:6993-7008`); `#csSortSelect` change → `sortKey` + `renderScout()` (`:7009-7017`); outside-mousedown closes (`:7018-7020`); table `th.col-sortable` header clicks (`:7062-7078`); null-last via `SORTS` comparators (`:4995-5069`) | Popover opens/closes, selection applies immediately, active sort synced, rows re-render; unknowns sort last. | **WAS DEAD**: the whole block was guarded on `el('sortPopover')`, parsed after the script → skipped; header sorts kept working (th nodes pre-script). FIXED by deferred boot; `aria-expanded` + visible active-sort label added. |
| Detail page opens | stream row click → `openSheet(p, row)` (`:7552-7560`); `NS.openSheet` exported (`:7260`) | Sheet renders hero + overview. | Always worked — nodes queried at click time. Matches the user's observation that the detail page opened while its controls were dead. |

### Genuine gaps this audit found (addressed in Phase 2)

1. **No "Data availability" section.** The sheet shows `—`/`Unknown`
   for missing values but never explains *why* a field is missing or
   which source/provider supplies it. Per the task, an explicit
   availability block with per-field reasons is required.
2. **No reason chips for Unscored / Needs Fee Verification.** The
   verify segment lists flags, but the table status badge and sheet
   overview do not state *which required input is missing*.
3. **No ARIA tab semantics / focus management** for the sheet nav
   (keyboard works — the segments are native `<button>`s — but there is
   no `aria-selected`, no `tabpanel` id, and focus is not moved into the
   sheet on open).
4. **Sort has no active-state indication** on the trigger button.

---

## B. Field contract matrix

Legend — Offline availability: `YES` = present in normal scan output
today (via cache/CSV), `CACHED` = present only when a cached provider
payload exists, `ON-DEMAND` = present only via the explicit
`GET /api/products/{asin}/offers` call, `NO` = no current source.

| Field | Backend field(s) | Source / provider | Offline availability | UI views | Honest label when unavailable | Future provider/live pull needed? |
|---|---|---|---|---|---|---|
| ROI | `roi_pct` (+ `net_profit`) | `fee_engine.calculate_unit_economics`; gated by pack/variant match | YES (estimated rows only; `None` otherwise) | table, dossier g1, preview, gallery, stream, sheet, drawer | "Unavailable — <economics_status reason>" (`missing_amazon_price` / `missing_costco_cogs` / `needs_fee_verification` / `mapping_verification_required`) | No new provider — needs price + verified FBA fee + exact cost (re-enrichment) |
| Estimated monthly sales | `monthly_sales_estimate` + `monthly_sales_estimated` | Provider passthrough: brightdata dataset, unwrangle `past_month_sales`, chocodata parse; Phase-3 offline model uses a separate `estimated_monthly_sales` | CACHED | table, dossier g4, sheet market, drawer, sales total | "Unavailable — monthly sales source is not connected" (label never claims verified sales; `(est.)` chip when estimated) | Yes — dedicated demand source OR explicitly documented estimator wiring |
| Costco discovery cost | `costco_cost` (basis `estimated`/`costco_online`, `match_quality` exact/candidate/mismatch) | `costco_api_client` discovery catalog (OPENWEBNINJA/UNWRANGLE) + local CSV; freshness via run report | YES (CSV rows; catalog only when last run fresh) | table, dossier g2, sheet source, drawer | "Unknown — no Costco cost on record"; catalog rows additionally carry the STALE banner when last run blocked/rate-limited/failed/old | Yes — catalog refresh is scheduled-only (Sunday), then Business Center confirmation |
| Invoice-confirmed Costco cost | `costco_cost` (basis `invoice_confirmed`, `cost_is_purchase_authorized`) | `costco_api_client invoices import` (business-center invoice/order rows) | CACHED (only if imported) | sheet source, dossier g2 | "Unknown — no invoice-confirmed Costco cost" | Yes — manual invoice import (operator step) |
| Amazon / Buy Box price | `amazon_price` (candidate + offer), `buy_box_price` (offer payloads) | search providers (brightdata/chocodata/scavio) + offer enrichment (brightdata web unlocker / easyparser / unwrangle) | CACHED | table, dossier g1, preview, gallery, stream, sheet, drawer, calculator prefill | "Unavailable — no Amazon price on record" (never `$0.00`; fixed in `field-audit-report.md`) | Yes — scoped enrichment on finalists only, never a 221-ASIN broad scan |
| Net profit | `net_profit` | fee engine (same inputs as ROI) | YES (estimated rows only) | table, dossier, sheet, drawer, opportunity strip | "Unavailable — <economics_status reason>" | Same as ROI |
| Amazon fees | `fba_fee`, `referral_fee`, `amazon_fees_total`, fee-breakdown fields | `fee_engine` (referral = category rule; FBA = size/weight table, requires weight) | YES (referral); `fba_fee` only when weight present | table, dossier g3, sheet economics, drawer | "Unavailable — FBA fee not yet verified (weight or fee source missing)" | No new provider; verify weight/fee source for finalists |
| Total sellers | `total_sellers` (aggregate only) | offer enrichment (brightdata/unwrangle aggregates; easyparser rosters) | CACHED | sheet market, dossier g4 | "Unavailable — offer enrichment has not been run for this ASIN" | Yes — scoped offer call per finalist |
| FBA sellers | `fba_sellers` (+ `fba_sellers_estimated`) | same | CACHED | sheet market, dossier g4, opportunity strip | "Unavailable — offer enrichment has not been run for this ASIN" | Yes — scoped offer call |
| FBM sellers | `fbm_sellers` (derived where provider returns it; not a scan-row contract field) | same | CACHED (only when provider returns roster) | sheet market (via seller detail) | "Unavailable — FBM breakdown not supplied" | Yes — easyparser roster call |
| Per-seller offer price | `offers[].price` in `/api/products/{asin}/offers` | easyparser OFFER (on-demand, ~5 credits/ASIN) | ON-DEMAND | seller detail section (load button, never auto-fetched) | "Unavailable — per-seller offers require the on-demand seller load" | Yes — explicit click only |
| Shipping | — (no provider field) | none | NO | — | "Unavailable — provider does not supply shipping" | Yes — provider payload confirmation needed |
| Buy Box winner | `buy_box.winner` / `snapshot_buy_box_seller` (offer payloads; never inferred from lowest price) | easyparser / local market snapshot | ON-DEMAND / CACHED | seller detail section, dossier g4 | "Unavailable — Buy Box winner not loaded (not inferred from lowest price)" | Yes — scoped seller call |
| Qualification score/status | `verdict` (Pass/Hold/Reject/Needs Fee Verification/null), `profit_tier`, `economics_status` | `product_analysis` gate + `_catalog_verdict_or_none` (product_analysis.py:413-425) | YES | table status, KPI, sheet overview, drawer | "Unscored — <economics_status + pack_match reason>" | No — backend rule; needs upstream inputs only |

---

## C. Why 221 candidates can show 0 qualified

The KPI counts `visible.filter(p => p.verdict === 'Pass')`
(`index.html:5643`). A row can only reach `Pass` when the full chain is
verified (product_analysis.py:413-425):

1. `match_quality` must be purchase-gate (`exact`/`invoice_confirmed`/
   `high_confidence`); everything else → `verdict = None` → **Unscored**.
2. `fba_fee` must be present (needs weight + fee source); otherwise
   **Needs Fee Verification** (still not Pass).
3. `net_profit`, `monthly_sales_estimate`, and `monthly_sales_estimated`
   must be verified → `_catalog_verdict_or_none` decides Pass/Hold/Reject.

With the Costco discovery last run **stale/blocked/rate-limited** (per
`data/costco-catalog-run-report.json` surfaced by the STALE banner), the
majority of the 221 candidates have no usable COGS (or only a
`candidate_match`), so `economics_status` is `missing_costco_cogs` /
`mapping_verification_required`. Rows with `candidate_match` COGS keep
their **computed price + COGS economics visible as provisional**
(net/ROI surfaced for triage — never nulled, never hidden); rows with no
Costco cost at all show honest `missing_costco_cogs` -> net/ROI
Unavailable. Verdict stays None ("Unscored") until identity and fee are
verified. Rows that do resolve to an exact cost but lack a verified FBA
fee are honestly labeled Needs Fee Verification. **0 qualified is the
correct, honest output for that dataset** — qualification is not "not
wired"; it is gated on inputs that are currently stale or unverified. The
repair is not in the scoring path but in (a) refreshing/confirming Costco
data for
finalists and (b) enriching a handful of finalists with fee + offer data.

---

## D. Repair plan (Phase 2) and offline test plan (Phase 3)

### File-by-file plan (all changes in `static/index.html` + `test_ui_display.cjs`)

1. `static/index.html` — sheet nav ARIA + focus:
   - `#sheetNav` → `role="tablist"`, `aria-label="Detail sections"`; each
     `.sheet-segment` → `role="tab"`, `aria-selected` (synced in
     `syncSheetNav`), `aria-controls="sheetPanel"`; `#sheetContent` →
     `role="tabpanel"`, `id="sheetPanel"`, `tabindex="0"`.
   - `openSheet` moves focus to the first tab (or `#sheetContent`) after
     render; `closeSheet` already restores focus to the opener.
2. `static/index.html` — sheet Data availability section:
   - New `renderDataAvailability(p)` producing a per-field list: label,
     value or exact honest reason (strings from section B), source label,
     and `enriched_at`/`snapshot_fetched_at`/`generatedAt` timestamp where
     the record carries one. Rendered as the first section of the
     overview segment (and referenced from Market for the
     on-demand seller fields).
3. `static/index.html` — reason chips:
   - Status badge in table/stream/preview: `title` =
     `NS.econUnavailableReason(p)` (already exists for cells) when
     verdict is null or Needs Fee Verification.
   - Sheet overview: "Why this row is not Pass" chip row derived from
     `pack_match`, `economics_status`, `fba_fee`, `verdict` — one chip
     per missing input.
4. `static/index.html` — sort active state:
   - `#csSortBtn` gets `aria-expanded` + `aria-pressed`-style state and a
     visible "Sorted by: <label>" readout (`#sortActiveLabel`) synced by
     `syncFilterInputs`/sort handlers; keep null-last comparators as-is.
5. `test_ui_display.cjs` — harness upgrade + Phase 14/15:
   - Upgrade the DOM stub so `addEventListener` stores handlers,
     `classList` tracks classes, elements are per-id singletons with
     `querySelectorAll`/`closest`/`contains`/`getAttribute`, and dispatch
     helpers (`click(id, target)` / `change(id, value)`) fire registered
     handlers — enabling true interaction tests offline (no jsdom
     dependency).
   - Phase 14 (interaction): click each of the 5 tabs → active class +
     distinct panel content; X close, Escape close, overlay click close →
     `.open` removed / overlay hidden; sort popover open/close, select →
     applied sort order in the stream for `price_asc`, `roi_desc`,
     `name_asc` with nulls last.
   - Phase 15 (honesty): data-availability section renders exact reason
     strings for missing ROI/sales/COGS/sellers/price; reason chips for
     Unscored + Needs Fee Verification rows; no `$0.00`/`0`/fabricated
     values anywhere in sheet output; nothing fetches network (fetch stub
     remains never-resolving).

### Verification commands (Phase 4)

- `node test_ui_display.cjs` — interaction + honesty phases.
- `python -m unittest <README suite minus test_scavio.py>` — unchanged
  backend contract (no Python files are modified by this repair).
- Record before/after counts in this file.

---

## Fixed (Phase 2-4 applied 2026-08-17)

### Files changed

| File | Change |
|------|--------|
| `static/index.html` | Sheet nav ARIA (`role=tablist/tab/tabpanel`, `aria-selected` synced in `syncSheetNav`, `aria-controls="sheetContent"`, `tabindex=0` panel); focus moved into the sheet (first tab) on open (focus returns to opener on close, existing behavior); new `NS.dataAvailabilityRows` + `NS.renderDataAvailability` (per-field value-or-honest-reason rows with source/basis labels) rendered as the first section of the sheet Overview; new `NS.sheetReasonChips` (one chip per missing/incomplete input) in the new "Status & Qualification" overview block; sort trigger now has `aria-expanded` + a visible active-sort label (`#sortActiveLabel`, `.cs-sort-label`, synced by `syncSortLabel` on open and after every selection); **boot fix (build `ui-20260817.2`): `init()` deferred to `DOMContentLoaded`** — the sheet and popovers are parsed after the script tag, so the synchronous init silently skipped their bindings (the true root cause); new `?ui_debug=1` diagnostics (build ID, active tab, tab listener count, last UI event, last tab activation result with reason, init errors via global error handler; never secrets/network) |
| `test_ui_display.cjs` | DOM stub upgraded from no-op to stateful: per-id element singletons, real listener storage, class/attribute tracking, `closest`/`contains`/`querySelector(All)` seeding for the sheet tabs and sort select options, and dispatch helpers (`click`/`change`/`fireDoc`) — no jsdom, no network. **Boot-lifecycle mirroring: `readyState: 'loading'`, no bindings asserted before DOMContentLoaded, then `fireDoc('DOMContentLoaded')` and bindings asserted (exactly 1 each for tabs/overlay/X/sort/Escape).** New Phase 14 (42 + 3 browser-style sequence assertions: pointerdown→pointerup→click, focus→Enter→click, focus→Space→click on real seeded tab nodes) and Phase 15 (19 assertions: Data availability reason strings, Unscored/Needs Fee Verification reason chips, invoice-confirmed basis label, no `0`/`$0.00` fabrication, zero fetch calls) |
| `docs/browser-ui-verification-report.md` | New: manual acceptance checklist for tabs (mouse + Enter + Space + arrows), X/Escape/overlay close, sort popover + header sorts, and the `?ui_debug=1` panel contents; report-back format; status **NEEDS HUMAN BROWSER VERIFICATION** |

### Verification

| Suite | Before | After |
|-------|--------|-------|
| `node test_ui_display.cjs` | All phases through p13/seller/p12 passing (683 PASS assertions) | **756 PASS assertions, ALL UI DISPLAY TESTS PASSED** (+73: 42 Phase 14 + 3 browser-style activation sequences + 9 boot-lifecycle + 19 Phase 15) |
| `python -m unittest <README explicit list minus test_scavio_client>` | 659 OK (skipped=3), unchanged | **659 OK (skipped=3)** — no Python files touched, backend contract unchanged. (Note: the README `discover` command includes `test_scavio_client` (7 tests) and yields 666; that module is never run per the safety rules.) |

`test_scavio.py` was never run; no network calls occurred (fetch stub
never resolves and Phase 15 asserts zero fetch calls); no secrets, no
formula, no CSV changes, no commits.

### What the interaction tests prove (per the task's Phase 3 checklist)

- Clicking each of the five tabs changes the active tab (`active` class +
  `aria-selected`) and swaps `#sheetContent` to that segment's panel;
  the same holds for real browser-style sequences (pointerdown →
  pointerup → click and focus → keydown → keyup → synthesized click for
  Enter and Space).
- X close, Escape close, and overlay click close all remove `.open`,
  hide the overlay, and clear `_sheetProduct`.
- Sort menu opens/closes with correct `aria-expanded`; three sorts
  (`price_asc`, `roi_desc`, `name_asc`) apply to the visible rows with
  Unknown/Unavailable values sorted last; the active sort is displayed.
- Known numeric values render correctly; missing fields render the exact
  honest reason strings from section B; nothing renders `0`/`$0.00`/
  blank/invented; no network is attempted.

### Root-cause summary (reported breakage) — corrected

**CORRECTION:** the first pass wrongly concluded the controls were
"wired and functional" and blamed a stale cached build. That was an
artifact of the harness, whose `getElementById` never returns null.
Confirmed root cause by byte-position audit: the inspection sheet
(`#sheetOverlay` at 422419, `#inspectionSheet` 422487, `#sheetClose`
422645, `#sheetNav` 422952, `#sheetContent` 423857) and popovers
(`#sortPopover` 424024, `#csSortSelect` 424302, `#colPopover` 426082)
are all parsed **after** the script block (224665..422297), while
`init()` ran synchronously during parse — so `el('sheetNav')`,
`el('sheetClose')`, `el('sheetOverlay')`, `el('sortPopover')` were null
and every binding targeting them was silently skipped. The sheet still
opened (openSheet queries nodes at click time), and Escape worked
(document-level) — matching the user's report exactly (focusable tabs,
click and Enter dead, detail page opens, X/Sort dead).

Fix: `boot()` defers `init()` to `DOMContentLoaded` when
`document.readyState === 'loading'` (the normal inline-script case),
else calls `init()` directly. The harness now mirrors that boot path and
asserts it (no bindings pre-DOMContentLoaded, exactly one per control
after). The Phase-2 hardening (ARIA, active-sort label, focus, Data
availability section, reason chips) and the diagnostics panel remain;
the diagnostics give a human browser session direct visibility into
whether the binding is attached and what each activation did.

---

## NEEDS HUMAN DECISION

1. **Browser verification of the boot fix.** The root cause was found
   and fixed offline (init deferred to `DOMContentLoaded`), but no
   headful browser is available in this sandbox. A human must run the
   manual acceptance checks in `docs/browser-ui-verification-report.md`
   (tabs via mouse/Enter/Space, X/Escape/overlay close, sort popover +
   header sorts, `?ui_debug=1` panel contents) and report PASS/FAIL.
   Also verify the served file is current (hard refresh Ctrl+F5).
2. **Costco data freshness.** The discovery catalog last run is
   stale/blocked. Refresh is operator-triggered (Sunday schedule or
   `refresh-costco-catalog.ps1`) and Business Center invoice
   confirmation is a manual import step for finalists. No code change;
   a data-acquisition decision per the task's "After this repair" list.
3. **Estimated monthly sales source.** Renders "Unavailable — monthly
   sales source is not connected" until a dedicated demand source or an
   explicitly documented estimator is wired (the Phase-3 offline model
   produces a distinct `estimated_monthly_sales` signal). Requires a
   data-source decision, not a UI change.
4. **Seller offers / shipping / Buy Box winner.** The scan rows carry
   aggregate seller counts only; per-seller offers + Buy Box winner come
   from the on-demand Easyparser call, and shipping is supplied by no
   provider. Scoping a live enrichment to a handful of finalists is a
   provider/billing decision per the task's "After this repair" list.