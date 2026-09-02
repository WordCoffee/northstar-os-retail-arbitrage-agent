# Field Audit Report — ROI / Estimated Sales / Costco Cost / Amazon Cost

Audit date: 2026-08-17. Sandboxed offline audit — no network calls, no
secrets, no live APIs. Only local files, fixtures, and the offline test
suite were used.

Fields audited:

1. **Amazon Cost** — `amazon_price` (search candidate + per-ASIN offer /
   Buy Box listing price).
2. **Costco Cost** — `costco_cost` (+ `costco_cost_basis`, `pack_match`).
3. **ROI** — `roi_pct` (fee-engine unit economics; `net_profit` as its
   companion).
4. **Estimated Sales** — `monthly_sales_estimate` / `monthly_sales_estimated`
   (provider estimate; distinct from the Phase-3 demand-model
   `estimated_monthly_sales`).

Reference contract: `docs/pre_ui_calculation_pipeline.md` (UI = pure
renderer; missing input -> `None`, never `0` / `$0.00` / blank; every
derived value ships provenance).

---

## 1. Amazon Cost (`amazon_price`)

### Flow
`amazon_search.search_kirkland_products` (BRIGHTDATA primary, ChocoData/
Scavio fallback) -> cached candidates (`data/` search cache) ->
`product_analysis.analyze_kirkland_products` -> per-ASIN
`offer_enrichment.get_scanner_offer` (or offline placeholder) ->
record `amazon_price` -> `main.SCANNER_ALLOWED_KEYS` allowlist ->
`static/index.html` (table cell, dossier g1, hover preview, gallery card,
stream row, sheet hero, research drawer, Margin Calculator prefill).

### Findings

| # | File:line | Current behavior | Correct? | Fix |
|---|-----------|------------------|----------|-----|
| A1 | `scavio_client.py:69-77` | `"amazon_price": float(price_val or 0)` — a search hit with no price becomes `0.0` | NO — violates "never 0" | Keep `None` when the provider returns no price |
| A2 | `offer_enrichment.py:188` (`_map_easyparser_offer`) | `"amazon_price": amazon_price if amazon_price else 0` — no Buy Box price -> `0` | NO — every other provider mapper (`_map_brightdata_offer` :237/241, `_map_chocodata_offer` :362, `_map_unwrangle_offer` :513) correctly uses `None` | Use `None` when no Buy Box price |
| A3 | `product_analysis.py:227` | `offer["amazon_price"] if offer.get("amazon_price", 0) > 0 else c.get("amazon_price", 0)` — (a) `None > 0` raises `TypeError` (live providers return `None` for a missing price, so a no-price row crashes the whole scan); (b) when both offer and candidate are missing the record carries `amazon_price: 0` and the Scout table renders `$0.00` | NO — crash + fabricated `$0.00` | Guard with `_is_number`; fall back to the candidate price only when positive; else `None` |
| A4 | `static/index.html:5971` (table row) | Price cell renders `NS.fmt(p.amazon_price)` with no `isNum` guard — `0` renders `$0.00`; `null` renders an em-dash `—` | NO — sibling Cost cell (:5972) renders `Unavailable` for missing/unknown; Price is inconsistent and can show `$0.00` | Guard with `isNum` (and `> 0`), render `Unavailable` like the Cost cell |
| A5 | `static/index.html:5961` (hover preview) | `Price: ' + NS.fmt(p.amazon_price)` — same unguarded pattern (dash when missing) | Minor — preview card is compact by design; flagged, not fixed | — |
| A6 | `brightdata_client.py:281-282` (`get_offer_data`) | Offline placeholder carries `amazon_price: 0` (documented fallback trigger for line A3) | Intentional per docstring — keep `0` as the "use candidate price" sentinel; harmless once A3 guards positivity | Keep as-is |

## 2. Costco Cost (`costco_cost`)

### Flow
`costco_client.get_costco_price` (CSV) + `costco_api_client.resolve_costco_cost`
(invoice_confirmed > product_detail > CSV, plus ASIN ledger) ->
`product_analysis.get_costco_price` -> record `costco_cost` +
`costco_cost_basis`/`pack_match` -> allowlist -> UI (table, dossier,
preview, gallery, stream, sheet, drawer, calculator prefill).

### Findings

| # | File:line | Current behavior | Correct? | Fix |
|---|-----------|------------------|----------|-----|
| C1 | `costco_client.py:510-517` | CSV cost parse rejects non-numeric and `<= 0` rows -> `None` | YES | — |
| C2 | `costco_api_client.py:1166-1175, 1267-1280` | No match -> `costco_cost: None` (basis `unavailable`); non-exact -> `candidate_match` with real cost, economics gated to Unavailable by the pack-match gate | YES | — |
| C3 | `product_analysis.py:193, 344` | `costco_cost` copied through as `None` when missing; record always includes the key | YES | — |
| C4 | UI table :5972 / dossier :5123 / preview :5961 / gallery :7122 / stream :7205 / sheet :7302 / drawer :7396 / calculator prefill :6239 | All guarded with `isNum` -> `Unavailable` (stream/sheet use `—` em-dash) | YES (dash treatment flagged under X1) | — |

## 3. ROI (`roi_pct`)

### Flow
`fee_engine.calculate_unit_economics` (net/cogs * 100; `None` when price
or COGS missing) -> `product_analysis` pack/variant gate (non-exact ->
`None`, status `mapping_verification_required`) -> record -> allowlist ->
UI (table, dossier g1, preview, gallery, stream, sheet, drawer;
opportunity strip; Risk Engine is manual-input only).

### Findings

| # | File:line | Current behavior | Correct? | Fix |
|---|-----------|------------------|----------|-----|
| R1 | `fee_engine.py:481-496, 512, 535` | Missing price/COGS -> `roi_pct: None`, status `missing_amazon_price`/`missing_costco_cogs`; `_as_price` treats `<=0` as missing | YES | — |
| R2 | `product_analysis.py:275-287` | Pack/variant gate zeroes `net_profit`/`roi_pct` for candidate/mismatch | YES | — |
| R3 | UI table :5975 / dossier :5125 / gallery :7127 / sheet :7251,7304 / drawer :7398 | All guarded `isNum` -> `Unavailable` (stream/sheet use `—`) | YES (dash flagged under X1) | — |
| R4 | `static/index.html:5601, 5616` (opportunity strip) | Rows only enter the strip when `net_profit`+`roi_pct`+`fba_sellers` are all numbers; no `0%` fabrication | YES | — |
| R5 | `main.py:389-426` (`_scanner_sort_key`) + UI `SORTS` | Nulls sort last, never ranked as 0 | YES | — |

## 4. Estimated Sales (`monthly_sales_estimate`)

### Flow
Search candidates (chocodata `_parse_sales_volume`) + per-ASIN offers
(brightdata passthrough, unwrangle `past_month_sales` parse) ->
`product_analysis` (`offer` value preferred over `candidate`) ->
allowlist -> UI (table cell, dossier g4, sheet, drawer, sales-total
line; Cycle Planner is manual-input only; gallery footer is conditional).

### Findings

| # | File:line | Current behavior | Correct? | Fix |
|---|-----------|------------------|----------|-----|
| S1 | `product_analysis.py:360-369` | `None` stays `None`; `monthly_sales_estimated` bool consistent with it | YES | — |
| S2 | UI table :5944-5949 / dossier :5268 / sheet :7327 / drawer :7435 | Missing -> `Unknown` (never 0) | YES | — |
| S3 | UI table :5978 | A provider-supplied `0` would render `0/mo` (brightdata passthrough can carry 0) | Borderline — 0 is a provider-reported value, not fabricated; flagged, not fixed | — |
| S4 | UI gallery :7143 | Sales line omitted when missing (conditional footer) | YES — compact card by design | — |
| S5 | `static/index.html:5874-5881` (sales total) | Sums known estimates only; `Unknown` when none | YES | — |
| S6 | `main.py:422` + UI `SORTS sales_*` | Sort by `monthly_sales_estimate`, nulls last | YES | — |

## Cross-cutting observations (flagged, NOT fixed)

- **X1 — `—` em-dash vs `Unavailable`.** The stream row
  (`index.html:7204-7207`) and sheet hero (`:7250-7253`) render missing
  values as `—`, while the table/dossier/gallery/drawer render
  `Unavailable`. The dash is a deliberate compact styling (also used for
  non-audited fields like Net), it never shows `0`, and the UI harness
  does not pin it. Left as-is to keep the change minimal; flagged for a
  future styling pass if full vocabulary consistency is wanted.
- **X2 — dossier g2 identity fields.** `costco_item_id`, `upc_or_ean`,
  `pack_count`, `net_weight`, `formula_or_flavor` are rendered by
  `NS.feeBreakdownHtml` (`index.html:5145-5149`) but are NOT in
  `main.SCANNER_ALLOWED_KEYS` — they are silently dropped by
  `_clean_scanner_product`. Not one of the four audited fields; flagged
  only.
- **X3 — two sales vocabularies.** `monthly_sales_estimate` (provider,
  table) vs `estimated_monthly_sales` (Phase-3 demand model, dossier g6)
  are intentionally distinct signals per AGENTS.md; labels differ
  (`Est. Monthly Sales` vs `Demand (est.)`). Consistent with spec.
- **X4 — `finance.py`/`pricing.py`/`product_analysis.py` math.** No
  formula changes were made; all audited issues are wiring/display only.

---

## Fixed (fix pass applied 2026-08-17)

All four confirmed defects (A1-A4) were fixed with minimal wiring/display
changes only — no formula changes, no secrets, no live API access, no CSV
contract changes.

| # | File | Change | Tests |
|---|------|--------|-------|
| A1 | `scavio_client.py` (~:77) | `float(price_val or 0)` -> `float(price_val) if price_val else None` — missing/zero provider price stays `None` | New `test_scavio_client.py::test_missing_price_stays_none_not_zero` |
| A2 | `offer_enrichment.py:188` | `amazon_price if amazon_price else 0` -> plain `amazon_price` (already `None`-safe upstream) — matches the other three provider mappers | Updated `test_offer_enrichment.py` provider-failure test: `assertIsNone(result["amazon_price"])` |
| A3 | `product_analysis.py:227` | `_is_number` guard; offer price used when positive, else candidate price when positive, else `None` — no more `TypeError` on `None > 0`, no `$0.00` leak, documented candidate fallback preserved | New `test_product_analysis.py::test_missing_offer_and_candidate_price_stays_none` (asserts `None` + `missing_amazon_price`) and `test_offer_price_zero_falls_back_to_candidate_price` (asserts 48.87 fallback) |
| A4 | `static/index.html:5971-5972, 5962` | Table Price cell + hover preview now `isNum(...) && > 0` guarded; missing/zero renders `Unavailable` (table) / `—` (preview) — never `$0.00`, never a bare dash in the table | New `test_ui_display.cjs` block: null and 0 `amazon_price` render `No Amazon price on record`, no `$0.00`, no bare-dash price cell |

### Verification

- Baseline (before fixes): `python -m unittest <README suite>` =
  **663 tests OK (skipped=3)**; `node test_ui_display.cjs` = **ALL UI
  DISPLAY TESTS PASSED**.
- After fixes: **666 tests OK (skipped=3)** (663 + 3 new tests;
  `test_scavio_client`, `test_product_analysis`, `test_offer_enrichment`
  all pass) and **ALL UI DISPLAY TESTS PASSED** (new price-cell
  assertions included). No regressions.
- README no-live-call discipline preserved: `test_scavio.py` was never
  run; no network calls; `SCANNER_OFFER_ENRICHMENT` pinned in tests.

### Notes

- The offline placeholder sentinel `amazon_price: 0` in
  `brightdata_client.get_offer_data` (A6) is intentionally kept — A3 now
  treats non-positive prices as missing, so the sentinel triggers the
  candidate-price fallback exactly as its docstring documents.
- The A5 preview-dash behavior is subsumed by the A4 preview guard (now
  `—` for missing, matching the COGS sibling). Flagged-not-fixed items
  (X1-X3, S3) are unchanged and documented above.

---

## NEEDS HUMAN DECISION

None encountered during discovery or the fix pass — no formula change was
required, no secrets were touched, and no live API access was needed.