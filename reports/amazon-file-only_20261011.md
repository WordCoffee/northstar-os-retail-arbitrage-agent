# File-only Amazon integration — report

**Date:** 2026-10-11 · **Branch:** `feature/overnight-remediation-20261009` · **HEAD:** `a45a7e5` (+ docs close) · **All items closed.**

---

## 1. Commits

| Commit | What |
|---|---|
| `a45a7e5` | The whole file-only integration: linkage guard + static scan, parsers/writers/change engine, tables + API, UI surface, harnesses + fixtures, inventory report |
| (this close) | Phase 10 checkpoint, D32–D35 journal, this report, regression evidence, refreshed screenshots |

## 2. Work items

1. **Inventory + disable + scan — DONE.** Every Amazon sign-in/API/live-pull path listed in `reports/amazon-linkage-inventory_20261011.md`; the guard refuses staging/production boots and the four linkage points refuse even with credentials; `test_no_amazon_linkage.py` 2127/0 (static scan + posture + refusal tests).
2. **Parsers — DONE.** Ads bulksheets (xlsx/csv, Product/Entity/Operation, entity IDs, search-term sheets, 60-day note), listing/inventory templates (TSV/xlsx by their own vocabulary), Brand Analytics, A+ ASIN lists; detection with reasons; missing columns = UNKNOWN; tenant-scoped archives with filename, observed range, upload time, checksum; legacy .xls honestly refused.
3. **Change-file writers — DONE.** Ads bulksheet delta (changed rows only, Operation Create/Update/Archive, IDs copied exactly, blank Operation refused), listing template delta (update_delete mapping), A+ asset pack; new versioned filename; originals never modified.
4. **Approval flow — DONE.** Before/after, reason, evidence (file + checksum + download date), row-level approve/reject, spend guardrail with second confirmation above the seller limit, stale-source warning, missing/unmatched IDs blocked.
5. **Round-trip validator — DONE.** Re-reads the written file, matches by ID value, proves only approved differences, diff report with source/written checksums + digest; tamper caught; no-op writes zero rows.
6. **A+ output — DONE.** Asset pack + placement instructions + required alt text; explicitly NOT an uploadable module file; ASIN bulk-upload limit UNKNOWN (sources conflict).
7. **Title rules in the listing writer — DONE.** The four rules (75 chars, banned characters, repeated word, promotional) as date-sensitive FLAGS via the Python port of the registry claims; never blocks, never edits.
8. **Tests — DONE.** Parse fixtures (built with openpyxl for real interop), round-trip no-op, single-change, bad-ID block, stale file, Excel-openability + column order, cross-tenant isolation (28/0 live), no-network scan, no API/sign-in code path. **A real Amazon upload is NOT RUN with cause — the owner performs it by design.**
9. **Regression — DONE.** **3061 passed / 0 failed / 0 FATAL** across 33 scored harnesses; 37 raw outputs in `reports/regression_20261011_phase10/`; 18 screenshots refreshed in `reports/screenshots_20261011/`; accessibility pass included.

## 3. VERIFIED / REPORTED / UNKNOWN

- **VERIFIED (this session):** the linkage guard and refusal behaviour; the parsers/writers/round-trip on real fixtures; the API + UI workflows end-to-end; cross-tenant isolation; zero non-local requests outside the app's font CDN and zero Amazon hosts; the full regression.
- **REPORTED:** the 14-day stale-source window and the spend-limit interpretation are stated engineering choices.
- **UNKNOWN (never zero):** the A+ ASIN bulk-upload limit; missing columns/values in any upload; the outcome of a real Amazon upload (NOT RUN, owner-performed).

## 4. Test counts

Full table in `research/design-studio/CHECKPOINT.md` (Phase 10). **3061 passed, 0 failed, 0 skipped, 0 FATAL.** NOT RUN (with cause): the real Amazon upload; the fidelity live trial (no photos/runtime, unchanged).

## 5. Gates hit and defaults applied

- **No hard gate was hit.** No live/paid call; no outbound network in import/export code (asserted twice); no cloud generation; generation unarmed; no model install/removal; no destructive op; credentials never read; other sessions' files untouched.
- Defaults D32–D35: linkage off by architecture; legacy .xls refused with the fix; the flat proposal contract; committed openpyxl-built fixtures.

## 6. Live/paid calls and arming

**0 live or paid provider calls. Zero Amazon contact of any kind.** Generation remains unarmed for every external provider.

## 7. Honest limits / not inspected

- A real Amazon upload was not performed (by design; the owner does it manually).
- Legacy .xls (BIFF) is refused, not parsed.
- The spend guardrail interprets bid/budget values as currency units and compares in cents; a non-numeric value is never treated as spend.
- The delta writer writes changed rows only; Amazon's bulksheet processors accept partial rows by ID, which the round-trip proves for our own format, but a real upload acceptance is the owner's step.
- The UI surface lives in Ads; listing templates and A+ lists are handled there too (one kind-aware surface).
- Not inspected: other sessions' workstreams; login-gated Amazon pages.

## 8. Owner checklist

1. Try a real round-trip: download a file from Amazon, upload it in Ads › Amazon files, approve a row, download the change file, upload it to Amazon manually.
2. Review the linkage inventory and confirm the file-only posture is what you want everywhere (the gate flag is off by default).
3. The remaining owner-blocked items from Phase 9 stand (captures, live trial, A4/A5/A7).
4. Re-run `tools/start-local.ps1` before normal use (rate-limit posture).

## 9. Next action

Owner performs one real file round-trip; then the next directive.
