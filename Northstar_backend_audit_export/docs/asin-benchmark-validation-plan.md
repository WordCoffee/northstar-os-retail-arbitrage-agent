# ASIN Benchmark Validation Database — Plan (Phase 1)

Status: PLAN (written before any code edits) — final results appended in Phase 7.
Scope: offline-only benchmark reference database + pure comparison engine for the
future guarded 20-ASIN live enrichment batch. No live calls, no production data
touched, no CSV contract changed.

---

## 1. Exact column mapping (both benchmark files)

Source files (user-provided, found in `C:\Users\T2Hol\Downloads\`, to be copied
byte-for-byte into `data/benchmark/source/` with provenance):

| File | Columns (exact, header row 1) | Rows |
|---|---|---|
| `BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv` | `# (BSR-proxy rank)`, `Product`, `ASIN`, `Reviews`, `Price`, `Prime/FBA` | 47 |
| `Rank-Product-ASIN-Reviews-Price-BSR.csv` | `Rank`, `Product`, `ASIN`, `Reviews`, `Price`, `BSR` | 20 |

Mapping to the normalized store:

| Normalized field | Source column | Parsing |
|---|---|---|
| `asin` | `ASIN` (both) | trim + uppercase; MUST match `^[A-Za-z0-9]{10}$`; store as string always |
| `title` | `Product` (both) | raw text preserved; normalized copy lowercased/collapsed for similarity |
| `proxy_rank` | `# (BSR-proxy rank)` (file A) | integer 1–47 (exact 47 rows) |
| `source_rank` | `Rank` (file B) | integer 1–20 |
| `price` | `Price` (both) | `$x.xx` → decimal; `null` when unparseable |
| `reviews` | `Reviews` (both) | `11,114` → int; `null` when unparseable/non-numeric |
| `prime_fba_raw` | `Prime/FBA` (file A only) | raw text preserved verbatim |
| `prime_fba` | derived | normalized state: `yes` / `no` / `unknown` (see below) |
| `bsr_raw` | `BSR` (file B only) | raw text preserved verbatim |
| `bsr_rank_number` | derived | first `#N` parse; `null` when none |
| `bsr_category` | derived | category text with trailing `amazon` scraping noise stripped |
| `capture_timestamp` | — | NO timestamp column exists in either file → always `null` |
| `source_file` | — | exact source filename |

Prime/FBA normalization (file A distinct values — exactly 3):
- `"Yes"` → `prime_fba: "yes"`, note none
- `"No"` → `prime_fba: "no"`
- `"No (Amazon-shipped, non-Prime badge)"` → `prime_fba: "no"`, note `"Amazon-shipped, non-Prime badge"`
- anything else → `prime_fba: "unknown"` (raw text always kept)

BSR parse notes (file B): 15/20 rows carry ≥1 `#N in Category` fragment; 5 rows
are the literal string `Not listed on page` (rank `null`, category `null`).
Category text is noisy — scraping artifact appends `amazon` to the category name
(e.g. `Health & Householdamazon`, `Antacidsamazon`). The parser strips a
trailing `amazon` token before classification. Where multiple fragments exist
(e.g. `#4,960 in Health & Household; #32 in Dietary Fiber Nutritional
Supplements`) the FIRST fragment (top-level category rank) is kept as the
primary `bsr_rank_number`/`bsr_category`; all raw text remains in `bsr_raw`.

## 2. Inventory of both files (measured 2026-08-17, offline)

| Metric | File A (proxyrank) | File B (rank) |
|---|---|---|
| Data rows (after header) | 47 | 20 |
| Unique ASINs | 47 | 20 |
| Duplicate ASINs within file | 0 | 0 |
| ASINs malformed (not 10 alnum) | 0 | 0 |
| Missing cells (any column) | 0 | 0 |
| Rows where BSR = `Not listed on page` | n/a | 5 (B01H40O42I, B081THWMDK, B01LY71217, B007MWNFBA, B0C54GXFQ8) |
| Rows with ≥1 parseable BSR rank number | n/a | 15 |
| Capture timestamp column | none | none → capture time UNKNOWN for every row |

Cross-file (20 ASINs appear in both — file B is exactly file A's first 20 ranks;
rank positions align 1:1):
- Price conflicts (same ASIN, different price): **0**
- Review conflicts: **0**
- Title conflicts: **3** — B00N54AJZE (`Stool Softener 100mg (400ct, alt
  listing)` vs `Stool Softener 100mg (alt)`), B01H40O42I (`Aller-Flo
  Fluticasone (Pack of 5)` vs `Aller-Flo (Pack of 5)`), B08R2SRN88 (`Aller-Flo
  Fluticasone (5 Bottles/600 sprays)` vs `Aller-Flo (5 Bottles/600 sprays)`).
  File A titles are the more specific variants.
- ASINs only in file A: 27 (file B is a strict subset).

Store policy:
- All 47 ASINs retained as observations (file A) + 20 merged BSR/rank extras
  (file B) — nothing discarded.
- Canonical view built only when values agree or a deterministic documented
  rule applies:
  - price/reviews: agree across files (verified) → canonical from either.
  - Prime/FBA: file A only → canonical from file A.
  - BSR/rank: file B only → canonical from file B.
  - title: files disagree on 3 ASINs → canonical title = file A title
    (file A is the 47-row primary reference), each conflict flagged
    `title_conflict: true` for review.
- Missing/unknown benchmark values are ALWAYS `null`/`unknown`, never 0.

## 3. Trustworthy validation scope (equality-checkable against benchmark)

1. **ASIN exact match** — pass/fail; the join key for the whole comparison.
2. **Normalized title / pack-size signal** — normalized-title similarity →
   `match | likely_match | mismatch | unavailable`; pack-size tokens
   (counts like `400ct`, `5 Bottles/600 sprays`, `2pk/192ct`) compared as a
   signal; **a pack mismatch is NEVER auto-resolved**.
3. **Reference price comparison** — only when both values exist; absolute +
   percentage variance with drift classification (see §6).
4. **Review count comparison** — only when both exist; direction + relative
   change; lower live count flagged but not auto-failed (listing/variation
   context required).
5. **Prime/FBA reference signal comparison** — benchmark normalized state vs
   live signal state: `match | changed | unavailable`.
6. **BSR/category/rank comparison** — only when both BSR rank numbers exist
   AND category context matches; observed change + percent change; category
   mismatch flagged separately. Rank (proxy/`Rank` column) is a reference
   ordering, never compared against live BSR.

## 4. Fields NOT benchmarked (never equality-checked)

The CSVs contain no data for these; the comparator may only run INTERNAL
coverage/provenance checks on them:
- current seller roster, seller identity, per-offer price, shipping terms
- total sellers, Buy Box winner, live FBA/FBM distribution
- current fees (FBA/referral), ROI, estimated monthly sales
- any economics/demand output (see §7)

## 5. Time-awareness policy

- Every comparison result carries `capture_time_status`:
  `known | unknown`. Both benchmark files have NO timestamp →
  `capture_time_status: "unknown"` on every record.
- Unknown capture time → `"reference only, not freshness proof"` — stated in
  every report and in the UI note (if a UI is ever enabled).
- Price and BSR differences may be legitimate market drift: drift classifications
  are labeled `requires freshness/context review`, NEVER "provider error".
- `observed_at` on a future live snapshot comes from the snapshot itself and is
  reported next to the benchmark's unknown capture time.

## 6. Tolerance & classification policy (PROPOSED — for human approval)

Proposed defaults (configurable constants in `benchmark_validation.py`):

| Comparison | Class | Rule (proposed) |
|---|---|---|
| Price | `exact` | |Δ| == 0 |
| Price | `within_tolerance` | 0 < |Δ%| <= 5% |
| Price | `moderate_drift` | 5% < |Δ%| <= 15% |
| Price | `material_drift` | |Δ%| > 15% |
| Price | `unavailable` | either value missing |
| Reviews | `expected_growth` | live > benchmark |
| Reviews | `decline_flag` | live < benchmark (flagged, not failed) |
| Reviews | `unavailable` | either value missing |
| Prime/FBA | `match / changed / unavailable` | state equality |
| BSR | `comparable` only when both rank numbers exist AND category matches (after noise-strip) |
| BSR | `category_mismatch_flag` | BSR exists on both but category context differs |
| Title/pack | `match / likely_match / mismatch / unavailable` | normalized similarity; pack mismatch never auto-resolved |
| Offer coverage | `full / partial / unknown / unavailable` | from live snapshot offer stages + returned counts |
| Buy Box | `present` only when offer data present | never inferred |

All thresholds are **proposals pending human approval** (Phase 7 item 1).

## 7. Internal-only validation (never benchmarked externally)

- **Offer/seller data**: validate presence/source/timestamp/coverage and
  internal consistency (total sellers == FBA + FBM when all three exist, and
  the sum is internally consistent). Never claim accuracy from absent
  benchmark data.
- **Economics**: ROI is NOT benchmarked. Validate internally only:
  ROI unavailable when material inputs missing; cost/fee provenance present;
  unknown never converted to 0. Label: `"not externally benchmarked"`.
- **Demand**: estimated monthly sales NOT benchmarked. Validate BSR input
  presence + estimator provenance/confidence only. Label: `"estimate
  validation, not sales-truth validation"`.

## 8. Design decisions for the implementation

- New modules (isolated from live provider execution):
  - `asin_benchmark_store.py` — CSV ingestion, normalization, dedupe/conflict
    preservation, canonical view, provenance manifest, offline artifact;
    CLI: `python asin_benchmark_store.py build|status|inspect`.
  - `benchmark_validation.py` — pure comparator + batch metrics + CLI
    `python benchmark_validation.py compare --benchmark <reference.json>
    --snapshots <snapshots.json>`.
- Data locations (separate from scanner catalog / scanner cache / live
  provider snapshots / Costco data / invoice imports):
  - `data/benchmarks/raw/` — byte-for-byte copies of the user files
    (`BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv` 3406 bytes,
    `Rank-Product-ASIN-Reviews-Price-BSR.csv` 2338 bytes).
  - `data/benchmarks/manifest.json` — provenance manifest: source filename,
    destination filename, sha256, byte size, imported_at (UTC),
    source_type `user_provided_reference`, capture_time null,
    capture_time_status `unknown`, limitation note.
  - `data/benchmarks/asin_benchmark_reference.json` — versioned normalized
    reference artifact, generated ONLY from the raw copies.
  - All paths env-overridable (`BENCHMARK_RAW_DIR`, `BENCHMARK_REFERENCE_PATH`,
    `BENCHMARK_MANIFEST_PATH`) so tests use temporary dirs and never touch the
    user CSVs or the production artifact.
- Loader contract: `asin_benchmark_store.load_reference()` reads ONLY
  `asin_benchmark_reference.json` and returns an EMPTY benchmark state when
  the file is absent (callers must handle empty state; nothing is fabricated).
- No route changes, no `.env`, no provider imports, no network imports.
- `intel_schema.py` shape accepted as the hypothetical future snapshot input;
  the comparator reads only the documented keys (ASIN, title, prices,
  reviews, prime/fba signal, BSR, offer snapshot fields) and treats everything
  else as absent.

## 9. UI design (Phase 5 — design only; human decision D4 pending)

Benchmark Validation panel for the future Product Sheet / Proof Batch review
— NOT implemented in this task (see §10 decision flag):

- Side-by-side Benchmark reference vs Live snapshot columns.
- Per-field status: match / drift / mismatch / unavailable (null-first).
- Benchmark source file + capture-time limitation line.
- Prominent note: "Price and BSR may legitimately change. This comparison
  validates mapping and plausibility; it does not guarantee live market
  stability."
- Two separated sections: "Externally benchmarked" vs "Internal
  coverage/provenance check".
- Never renders a comparison when no benchmark ASIN match exists.
- Data flow (if later enabled): offline artifact → static JSON asset, panel
  reads scanner row + benchmark row client-side; zero new routes, zero
  provider calls.

## 10. Implementation flags for human decision (pre-authorized by mission §NEEDS HUMAN DECISION)

- D4: benchmark panel ships in the UI now or after the first stored 20-ASIN
  snapshot → recommendation: AFTER (nothing live to compare today; avoids
  premature UI surface). Design is frozen in §9.

## 11. Test plan (Phase 6)

Offline unit tests (new files, temp paths via env overrides):
- `test_asin_benchmark_store.py` — CSV parse, ASIN string normalization,
  price/review/BSR parsing, Prime/FBA raw+normalized, dup/conflict
  preservation, unknown-never-zero, canonical rules, provenance + sha256.
- `test_benchmark_validation.py` — identity exact/likely/mismatch/unavailable,
  pack-mismatch never auto-resolved, price classification (all 5 classes),
  review trend, BSR rules + category mismatch, offer internal-consistency,
  ROI/demand internal-only labels, batch metrics.
- Containment class: every provider client patched to raise + no network
  imports reachable → prove import/compare makes zero outbound calls.
- Existing GET containment tests (`test_live_containment.py`,
  `test_scanner_completeness.py`) remain green.

## 12. Phase 7 — Final Report

### Import report (required by the input-file instruction)

| Item | Result |
|---|---|
| Both files found | YES — NOT inside the workspace; located in `C:\Users\T2Hol\Downloads\` and copied byte-for-byte |
| SHA-256 A | `ffb25c8284126dcfcd577171af4ab8ac5099ae484b72fcd718e2dfade20fe9da` |
| SHA-256 B | `ae85c5d72f2ebe2d15e8558ce29ad86ae4c8015fc10105e111595533db09368b` |
| Raw rows | 47 (file A) + 20 (file B) = 67 observations |
| Unique ASINs | 47 |
| Duplicate observations | 0 within each file; 20 ASINs observed in BOTH files (file B is a strict subset of file A, positions align 1:1) |
| Cross-file conflicts | 3 title-only conflicts (B00N54AJZE, B01H40O42I, B08R2SRN88); 0 price, 0 review conflicts |
| Malformed/missing | 0 malformed ASINs, 0 missing cells, 0 malformed prices/reviews |
| BSR unavailable | 5 rows `Not listed on page`; 15 rows with ≥1 parseable rank |

Files created:
- `data/benchmarks/raw/BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv` (3406 bytes)
- `data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv` (2338 bytes)
- `data/benchmarks/manifest.json`
- `data/benchmarks/asin_benchmark_reference.json`
- `asin_benchmark_store.py`
- `benchmark_validation.py`
- `test_asin_benchmark_store.py`
- `test_benchmark_validation.py`
- `docs/asin-benchmark-validation-plan.md` (this file)
(Old scaffolding dir `data/benchmark/` created during early work was removed; only `data/benchmarks/` remains.)

### Files changed in this task

| File | Change |
|---|---|
| `asin_benchmark_store.py` | NEW — offline benchmark repository: raw CSV import, parsers, canonical view with documented rules, conflict flags, provenance manifest, reference artifact writer, empty-state loader |
| `benchmark_validation.py` | NEW — pure comparator (identity/price/reviews/Prime-FBA/BSR) + internal offer/economics/demand checks + batch metrics + CLI |
| `test_asin_benchmark_store.py` | NEW — 26 tests (parsing, normalization, conflicts, unknown-never-zero, manifest, loader empty state, containment) |
| `test_benchmark_validation.py` | NEW — 31 tests (identity/price/review/BSR/Prime-FBA, offer consistency, econ/demand labels, batch metrics, zero provider calls) |
| `docs/asin-benchmark-validation-plan.md` | plan + this report |

Untouched: scanner catalog, caches, live snapshots, Costco data, invoice
imports, CSV contract, `main.py` routes, `intel_schema.py`,
`completeness_score.py`, `enrichment_preflight.py`, `market_snapshot_store.py`,
`static/index.html`, formulas, `.env`, `test_scavio.py`.

### Benchmark inventory summary

- 47 unique ASINs; canonical reference rows for all 47 (title/price/reviews
  from primary file A; BSR/rank from file B; Prime/FBA from file A).
- 3 title conflicts flagged (`title_conflict: true`) with both titles
  retained in observations; canonical title = file A variant.
- Capture timestamp: null on every record; `capture_time_status: "unknown"`
  — "reference only, not freshness proof".
- 5 ASINs have no BSR benchmark (not listed on page).

### Comparator limitations (honest boundaries)

- Reviews/BSR/Prime-FBA compare only when the live snapshot carries the
  field; the current intel_schema.py has no review field yet — the comparator
  reads `facts.identity.reviews_count` / `facts.market.reviews_count` /
  `facts.demand.reviews_count` (first present) and `facts.demand.bsr` /
  `facts.market.bsr` — documented future keys, so coverage depends on the
  future enrichment snapshot shape.
- No seller-roster, economics or demand benchmarks exist → those sections are
  internal coverage/provenance checks only, always labeled "not externally
  benchmarked" / "estimate validation, not sales-truth validation".
- Pack-size mismatch is NEVER auto-resolved; `pack_mismatch_block` stops the
  row from purchase eligibility until human review.
- No single accuracy percentage is produced; measured metrics and coverage
  metrics are reported separately.

### Human-approved tolerance values still needed

1. Price bands: `within_tolerance <= 5%`, `moderate_drift <= 15%`,
   `material_drift > 15%` — currently PROPOSED constants in
   `benchmark_validation.py` (`PRICE_WITHIN_TOLERANCE`,
   `PRICE_MODERATE_TOLERANCE`); must be approved or changed before the first
   live run.
2. Title similarity: `match >= 0.90`, `likely_match >= 0.55` token overlap —
   PROPOSED constants (`TITLE_MATCH_SIMILARITY`, `TITLE_LIKELY_SIMILARITY`).

### Test commands and before/after totals

Commands:
```
python -m unittest test_asin_benchmark_store test_benchmark_validation
python -m unittest discover -s . -p "test_*.py"   # full offline suite
```

Totals (full suite, `test_scavio*` excluded):
- BEFORE this task: 756 OK (skipped=3)
- AFTER: **813 OK (skipped=3)** (+57 = 26 store + 31 comparator)
- Existing live-call containment tests (`test_live_containment.py`,
  `test_scanner_completeness.py`) still green; the new containment classes
  prove benchmark import/build/compare make zero provider calls (every
  provider client patched to raise).

### No live data pulled — confirmation

No HTTP/network/provider call, no Uvicorn, no browser, no
`POST /api/kirkland/refresh`, no `.env` access, no enrichment execution
occurred at any point. All processing ran offline against the copied CSVs and
in-memory fixtures.

### First 20-ASIN Validation Run Checklist (starts only AFTER a future
guarded live enrichment snapshot is stored)

1. Confirm the guarded live run stored a normalized snapshot set matching the
   intel_schema.py shape (schema_version, asin, ingested_at, sources, facts)
   — cache-only merge, no production writes.
2. Confirm the chosen 20 ASINs are present in `data/benchmarks/`
   (`asin_benchmark_reference.json` canonical) — human-approved selection.
3. Run `python benchmark_validation.py compare --benchmark
   data/benchmarks/asin_benchmark_reference.json --snapshots
   <snapshot-file.json>` and review `metrics`:
   - benchmark matched ASIN count == 20; unmatched == 0
   - identity/title match rate and any `pack_mismatch_block` rows
   - price within-tolerance vs moderate/material drift counts
   - review decline flags, Prime/FBA changes, BSR category mismatches
4. Review each report where: pack mismatch block OR material price drift OR
   review decline OR BSR category mismatch — all flagged rows need human
   review with listing/variation context.
5. Confirm offer_section coverage (full/partial/unknown), Buy Box presence
   and seller-count internal consistency per row.
6. Re-confirm zero provider calls during the whole validation pass (network
   log/guard) — validation itself must stay fully offline.
7. Only then proceed to any purchase-authorization workflow, and only for
   rows where identity pack-match + invoice-confirmed cost + verified fees
   all pass; benchmark drift alone never authorizes or blocks a purchase.

NEEDS HUMAN DECISION:
1. Price tolerance bands for within/moderate/material drift (proposed 5%/15%)
   — approve or adjust the constants.
2. Whether title/pack mismatch blocks enrichment or only blocks purchase
   authorization (current: blocks only purchase authorization; never blocks a
   future scan from storing data).
3. Whether reference capture timestamps can be supplied later (currently
   null/"unknown" — the manifest and store are ready to accept them).
4. Whether the benchmark panel should ship in the UI now or after the first
   stored 20-ASIN snapshot (recommendation: after — design frozen in §9).
5. Approval of the selected 20 ASINs before any guarded live run (file B's 20
   ASINs are the natural candidates).

## 12. Phase 7 � Final Report
