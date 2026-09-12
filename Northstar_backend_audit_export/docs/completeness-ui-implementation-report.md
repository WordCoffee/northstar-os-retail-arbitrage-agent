# Completeness UI Implementation Report

**Status:** IN PROGRESS (report created BEFORE edits; results sections filled
after verification).
**Date:** 2026-08-17
**Scope:** Wire the null-first ASIN completeness contract into the served
Product Scout UI (Overview, Source, Economics, Market, Verify segments + a
compact scanner-view indicator), using `completeness_score.py` as the canonical
logic. Additive and backward-compatible only.
**Hard rules:** no live/provider/network calls; no `.env`, caches, production
data, formulas, CSV contract, or `test_scavio.py` touched; GET routes stay
cache-only.

---

## 1. Null-First Semantics (canonical contract)

1. **Per-category computability:** a category score is `null` (never 0) when
   that category has NO evaluated input — no field that could earn or disprove
   points. If any evaluated input exists, the category computes a real number,
   which may legitimately be 0 points when the evidence disproves it.
2. **Total score:** `score` = sum of computable-category points; `score_max` =
   sum of the maxes of computable categories (100 only when all six are
   computable). `score` is `null` when zero categories are computable.
3. **Status:** null score from computation → `not_computable`; absent
   completeness block in a response → `unknown` (UI renders "Unknown").
   Otherwise the taxonomy ladder (`needs_mapping` → `needs_market_data` →
   `needs_fee_verification` → `needs_demand_data` →
   `needs_invoice_confirmation` → `ready_for_test_buy`, plus `blocked`).
4. **Genuine zero:** allowed only when all computable categories earn 0 from
   evaluated evidence (constructed fixture, tested separately). Never a
   stand-in for missing data.
5. **missing_inputs:** per category, the fields that would make it computable.
6. **UI:** null score renders "Unknown" / "Not computable", NEVER "0 / 100"; a
   proven genuine 0 renders "0" with its status context.

## 2. Files in This Change (all additive)

| File | Change |
|---|---|
| `docs/completeness-ui-implementation-report.md` | this report |
| `completeness_score.py` | rewrite to null-first semantics; add `compute_scanner_completeness(row)` |
| `test_asin_intel_plan.py` | update 28 tests to null-first contract; add partial + genuine-zero cases |
| `main.py` | additive scanner contract: `completeness` per product + `completeness_contract_version` in summary |
| `test_scanner_completeness.py` | new: contract tests, absent-block null, partial real score, genuine zero, backward-compat, containment |
| `static/index.html` | segments render completeness states; compact chip in Status cell; null-safe |
| `test_ui_display.cjs` | harness assertions for the new rendering |

NOT touched: `.env`, caches, data files, `product_analysis.py`/`finance.py`/
`pricing.py` formulas, CSV contract, `test_scavio.py`, provider clients.

## 3. Scanner Response Contract (backward-compatible, additive only)

Per-product (added to `SCANNER_ALLOWED_KEYS`):

```json
"completeness": {
  "score": null,
  "score_max": 0,
  "status": "not_computable",
  "category_scores": {
    "identity_mapping": null,
    "source_cost": null,
    "market_coverage": null,
    "fees_economics": null,
    "demand": null,
    "invoice_readiness": null
  },
  "missing_inputs": [],
  "roi_readiness": { "ready": null, "reason": null },
  "next_action": null,
  "computed_from": "scanner_row"
}
```

Summary gains `completeness_contract_version: 1`. Existing keys keep exact
values. Cache-miss/absent block → JS renders Unknown, no errors.

## 4. UI Plan

- **Overview segment:** score badge + status label (+ `score_max` context when
  < 100).
- **Source segment:** per-group availability states (identity / cost / market /
  fees / demand) from category_scores null-ness + missing_inputs.
- **Economics segment:** ROI readiness line + economics-input completeness.
- **Market segment:** coverage/availability states consistent with the
  contract.
- **Verify segment:** next action + missing inputs list.
- **Scanner table:** compact chip (score + status) inside the existing Status
  cell ONLY — no new column, no layout change.
- Null score → "Unknown"/"Not computable", never "0 / 100".

## 5. Test Plan

- Python: full suite excluding `test_scavio.py` (before: 742 OK, skipped=3).
- UI harness: `node test_ui_display.cjs` (before: 756 PASS assertions).
- Containment re-assert: GET scanner/live routes + static + debug with all
  provider clients patched to raise.

## 6. Results (filled after verification)

### Changed files (all additive)

| File | Change |
|---|---|
| `docs/completeness-ui-implementation-report.md` | this report |
| `completeness_score.py` | rewritten null-first: per-category computability (null when no evaluated input), `score` null + `score_max` when nothing computable, `status` `not_computable`; added `compute_scanner_completeness(row)` adapter + `_evidence_from_scanner_row` |
| `test_asin_intel_plan.py` | 28 → 32 tests: empty snapshot/row → null + `not_computable`; minimal fixture evaluated-statuses → genuine 0; partial row → real partial score (41/85); genuine-zero row explicitly constructed (mismatch + evaluated-empty signals), tested separately |
| `main.py` | `completeness` in `SCANNER_ALLOWED_KEYS`; scanner endpoint attaches `compute_scanner_completeness(r)` per product; summary gains `completeness_contract_version: 1`; no existing key removed/changed |
| `test_scanner_completeness.py` | new, 10 tests: contract + version present; absent data → null + `not_computable`; partial row → real partial score; genuine zero separately proven; server matches canonical logic; backward-compat key/value assertions; GET scanner/live/debug/static containment re-assert (all providers patched to raise) |
| `static/index.html` | `NS.completeness*` helpers (pure renderers); Overview/Source/Economics/Market/Verify segments each show completeness states; compact `cc-badge` chip INSIDE the existing Status cell only (no new column); null-first rendering: null → "Unknown"/"Not computable", never "0 / 100"; proven 0 → "0 / 100" + "proven 0" badge + disclosure title; absent block → Unknown, no chip |
| `test_ui_display.cjs` | Phase 16 added, 24 assertions |

NOT touched: `.env`, caches, production data, `product_analysis.py`/`finance.py`/`pricing.py` formulas, CSV contract, `test_scavio.py`, provider clients.

### Test totals

- Python suite (29 modules, `test_scavio*` excluded):
  **before 742 OK (skipped=3) → after 756 OK (skipped=3)** (+14 = +4 updated/null-first tests + 10 new contract tests).
- UI harness `node test_ui_display.cjs`:
  **before 756 PASS → after 780 PASS** (+24 Phase 16 assertions).
- Containment: `test_live_containment.py` + `test_scanner_completeness.py` containment class all pass — GET `/api/kirkland/scanner`, `/api/kirkland/live`, `GET /` (+`?ui_debug=1`), static assets, and offers/canopy GETs make **zero provider calls** (every outbound client patched to raise).
- No live refresh, no provider call, no Uvicorn browser session, no `.env` operation performed.

## 7. Manual Test Checklist (human browser)

1. Start Uvicorn as usual and open the Scout page (`GET /`). Confirm the page loads with no provider/network calls in the server log (cache-only).
2. Open a product sheet → **Overview** tab: see "Completeness" section — score as `N / M` (or "Unknown"/"Not computable" for null), status badge, next action. A `0 / 100` must NEVER appear for a null score; if a proven 0 appears it carries the "proven 0" badge.
3. **Source** tab: per-category lines show "Computed: N / M" or "Not computable — missing: <fields>".
4. **Economics** tab: ROI readiness row (Ready / Not ready / Unknown with reason tooltip) + fees/economics inputs line.
5. **Market** tab: market/offer coverage line + demand signals line.
6. **Verify** tab: status reason callout, "Missing inputs" list, "Next action" line.
7. Scanner table: each row's Status cell shows a compact completeness chip (`41 / 85` style) next to the verdict badge — no new table column, no layout shift at the 1120px minimum width.
8. Rows from an older cached response without the completeness block: chip absent, sheet shows "Unknown" — no JS errors in the console.
9. Check devtools network tab: page load triggers only the scanner GET (and static assets) — no provider calls.

NEEDS HUMAN BROWSER VERIFICATION.
