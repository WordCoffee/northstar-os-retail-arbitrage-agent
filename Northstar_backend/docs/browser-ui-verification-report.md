# Browser UI Verification Report — Tab / Close / Sort Activation

Status: **NEEDS HUMAN BROWSER VERIFICATION** (no headful browser
automation is available in this offline sandbox; all checks below are
manual and must be run by a human against a live local server).

Fix under test: `static/index.html` boot now defers `init()` until
`DOMContentLoaded` (build ID `ui-20260817.2`), because the inspection
sheet and sort/column popovers are parsed **after** the script tag — the
previous synchronous init silently skipped every listener targeting
those nodes, which is exactly the reported dead-tab/X/sort behavior.

## How to verify (10 minutes)

1. Start the backend: `uvicorn main:app` (or the project's normal server
   command) — local only, no external calls.
2. Open `http://127.0.0.1:8000/` in a real browser (Chrome/Firefox/Edge).
   Hard-refresh with Ctrl+F5 once to clear any cached old file.
3. Load a cached scan if the live scan is not wanted (do not press
   Refresh; cached rows render immediately when present). Open any
   product detail (click a stream/gallery row).

## Acceptance checks

### A. Tabs (Source / Economics / Market / Verify / Overview)

- [ ] Open a product detail sheet. Click **Source**: the panel content
      changes to the Costco source section and the Source tab is
      highlighted.
- [ ] Click **Economics**, **Market**, **Verify**, then **Overview** —
      each click swaps the panel content and highlights the clicked tab.
- [ ] Tab to the tab bar, press **Enter** on Source — panel switches.
- [ ] Tab to the tab bar, press **Space** on Market — panel switches.
- [ ] Tab to the tab bar, press **ArrowLeft/ArrowRight** — focus moves
      between tabs (native button behavior).
- [ ] Click the tab text **and** the padding around it (whole tab area) —
      both activate.

### B. Close paths

- [ ] X button (top-right of the sheet) closes the sheet and restores
      page scroll.
- [ ] Press **Escape** with the sheet open — closes the sheet.
- [ ] Click the dimmed overlay outside the sheet — closes the sheet.
- [ ] After closing via any path, Tab order skips the hidden sheet tabs
      (focus returns to the row that opened it).

### C. Sort

- [ ] Click **Sort** — the popover opens.
- [ ] Pick e.g. "Amazon Price: Low to High" — rows reorder immediately
      and the popover closes.
- [ ] The Sort button shows a small label with the active sort
      (e.g. "Amazon Price: Low to High").
- [ ] Pick "ROI: High to Low" — rows with unknown ROI move to the end.
- [ ] Pick "Product Name: A to Z" — names sort alphabetically.
- [ ] Click outside the popover — it closes without changing the sort.
- [ ] Click a sortable table header (e.g. Costco COGS) — the sort
      changes and the header indicator updates.

### D. Diagnostics (developer aid)

- [ ] Open `http://127.0.0.1:8000/?ui_debug=1`, open a product detail,
      and confirm the fixed bottom-left panel shows:
      - UI build `ui-20260817.2`
      - `tab listener bindings: 1`
      - `last UI event` updating with each click/keypress (type, target,
        tab)
      - `last tab activation: OK <segment>` after each successful tab
        click (or `FAIL <reason>` if a guard rejected it)
      - `init errors: none` (or the captured message if a script error
        occurred)
- [ ] The diagnostics panel never shows secrets and no network requests
      are triggered by it (verify in DevTools Network tab while using
      `?ui_debug=1`).

## Expected final state

- All A/B/C checks pass.
- `?ui_debug=1` shows `tab listener bindings: 1` and `last tab
  activation: OK ...` after tab clicks — proving the delegated binding is
  attached and executing in the real page.

## Report-back format

Reply with PASS/FAIL per check (A1-A7, B1-B4, C1-C7, D1-D2) plus the
browser name/version. If anything fails, re-run with `?ui_debug=1` and
report the panel contents — the `last tab activation` reason and
`init errors` fields pinpoint the failure.

## Offline test results (this sandbox)

| Suite | Result |
|-------|--------|
| `node test_ui_display.cjs` | 756 PASS assertions, ALL UI DISPLAY TESTS PASSED (includes boot-lifecycle, pointer/keyboard activation sequences, close paths, sort, honesty phases) |
| `python -m unittest <README explicit list minus test_scavio_client>` | 659 OK (skipped=3), unchanged (README `discover` = 666 incl. the never-run `test_scavio_client`, 7 tests) |