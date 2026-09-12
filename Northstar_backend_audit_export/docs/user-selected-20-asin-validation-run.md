# User-Selected 20-ASIN Validation Run — Plan (Phase 1)

Status: PLAN (written before implementation edits). Final results appended in
Phase 7. This task implements the local selection batch, zero-network
preflight, future run-result envelope, benchmark comparison integration and a
Proof Batch UI — WITHOUT executing any live enrichment.

Safety posture (unchanged): zero live calls, zero .env access, no Uvicorn, no
refresh endpoint, no `SCANNER_LIVE_ALLOWED`, no `test_scavio.py`, no formula
changes, no CSV contract change, no production cache/catalog/raw benchmark
writes, no git operations.

---

## 1. Audit summary (Phase 1 findings)

| Asset | Finding |
|---|---|
| `enrichment_preflight.py` | Already provides `plan_enrichment` (dry-run, cap 20, fresh-skip, credit estimates, budget stop, `requires_human_confirmation`) + `missing_field_groups` + `CREDIT_ESTIMATES` (EASYPARSER 5, CHOCODATA 5, BRIGHTDATA 1, UNWRANGLE 1, SCAVIO None) + `FRESHNESS_NOTE`. Reused as-is — no edits. |
| `market_snapshot_store.py` | SCHEMA_VERSION 1; freshness: offers 7d, sales 30d, identity 90d; per-ASIN snapshots with stages/coverage; `load_snapshots()` read-only. Scanner rows already carry `snapshot_status`, `snapshot_fetched_at`, `snapshot_offers_complete`, `snapshot_offers_returned` — the UI preflight reads these instead of touching store files. |
| `intel_schema.py` | `validate_snapshot()` is the validation gate for the future run-result envelope (facts.identity/cost/fees/demand/market/economics + provenance; ZERO_FORBIDDEN; coverage statuses). No edits. |
| `completeness_score.py` | `compute_scanner_completeness(row)` — scanner rows carry a `completeness` block (score/status/category_scores/missing_inputs). Selection records snapshot the current completeness block. No edits. |
| `asin_benchmark_store.py` | `load_reference()` (empty state when absent), canonical rows keyed by ASIN, capture_time_status "unknown". No edits. |
| `benchmark_validation.py` | `compare_benchmark_record(bench, snapshot)`, `summarize_batch(reports)` — the comparison engine for the future snapshot. No edits. |
| `main.py` | GET routes: `/`, `/api/kirkland/scanner`, `/api/kirkland/live`, `/api/products/{asin}/canopy|offers`, `/health` — all cache-only zero-provider. No route changes in this task. |
| `static/index.html` | NS helpers block (line ~4464+), `streamRowHtml` (~7508, the only row renderer used by the table body at 7549), `openSheet`/`renderSheetContent` (~7560/7644), `init()` (~7908), localStorage keys at ~4466-4469. No existing selection capability — proof batch is new. |
| Containment tests | `test_live_containment.py`, `test_scanner_completeness.py` + harness final "no network was attempted by any interaction" assertion. Must stay green. |
| Benchmark assets | `data/benchmarks/raw/` (2 CSVs, sha256 recorded), `manifest.json`, `asin_benchmark_reference.json` (67 observations, 47 unique ASINs, 3 title conflicts, capture time unknown). Read-only. |

## 2. Exact selection data structure

Browser-local only. Single localStorage key `t2.kirklandScout.selection.v1`:

```json
{
  "schema_version": 1,
  "updated_at": "2026-08-18T12:00:00.000Z",
  "asins": [
    {
      "asin": "B00BISGJXA",
      "title": "Stool Softener 100mg (400ct)",
      "selected_at": "2026-08-18T12:00:00.000Z",
      "completeness": { "score": 41, "score_max": 85, "status": "needs_mapping" },
      "amazon_price": 12.99,
      "costco_cost": 5.99,
      "roi_pct": 31.4,
      "benchmark_match": true,
      "missing_enrichment_fields": ["identity_pack", "fees", "demand"]
    }
  ]
}
```

- `completeness`/`amazon_price`/`costco_cost`/`roi_pct` copied from the scanner
  row ONLY when present; absent → null (never 0).
- `benchmark_match` = ASIN present in the embedded offline benchmark index.
- `missing_enrichment_fields` from `enrichment_preflight.missing_field_groups`
  semantics (identity_pack | source_cost | market_offers | fees | demand).

## 3. Local persistence approach + sanitization policy

- Persistence: browser `localStorage` only. No backend writes, no cookies.
- Sanitization on load (`NS.loadSelection`):
  - parse JSON; invalid → empty selection.
  - `schema_version` must be 1; unknown versions → empty selection.
  - each record: ASIN must match `^[A-Za-z0-9]{10}$` (uppercased); title
    truncated to 200 chars; `selected_at` ISO string or now; numbers kept
    only when finite; completeness block re-validated (score/score_max null
    or number, status string); every other key dropped.
  - dedupe by ASIN; enforce max 20; sort stable.
- No secret-like keys can survive: sanitizer drops any key matching
  /key|token|secret|credential|password|api/i at every nesting level of the
  stored record (defense in depth; the UI never writes such keys).
- "Clear all" removes the key entirely.

## 4. Max 20 unique ASINs

- Hard cap `MAX_SELECTION = 20`. `NS.toggleSelection(asin, title, row)` refuses
  adds beyond 20 with an explicit message ("Proof batch is full (20/20). Remove
  an ASIN first."). No auto-ranking, no auto-selection, no candidate
  suggestion — user-driven only.

## 5. Future provider profiles + requested field contract

| Profile | Provides | Credit/request status |
|---|---|---|
| Easyparser OFFER | seller roster, per-offer price, shipping, fulfillment, Buy Box where available | documented estimate 5 credits/ASIN (AGENTS.md) |
| Keepa | BSR, category, price/rank history where available | **unknown — requires provider plan confirmation** |
| Costco cache | discovery cost only | 0 credits |
| Invoice/manual input | purchase-authorized COGS | 0 credits |
| Seller Central/manual | fee + restriction confirmation | 0 credits |

Requested field groups per ASIN (missing only): `identity_pack`,
`source_cost`, `market_offers`, `fees`, `demand` — from
`enrichment_preflight.missing_field_groups`.

## 6. Cache TTL + fresh-data skip policy

- Freshness from `market_snapshot_store.py` (offers 7d, sales 30d, identity
  90d). Scanner rows expose `snapshot_status`/`snapshot_offers_complete`/
  `snapshot_fetched_at`.
- Preflight treats a selected ASIN as `fresh` (skip, zero cost) when its
  scanner row reports a snapshot with offers complete and fetched within the
  offers TTL; `stale` → 1 planned request; `absent` → 1 planned request
  (mirrors `enrichment_preflight.FRESHNESS_NOTE`).

## 7. Budget/credit fields: known vs unknown

- KNOWN: Easyparser OFFER ≈ 5 credits/ASIN (documented planning estimate);
  per-ASIN planned request count (1 per non-fresh ASIN per provider);
  hard batch cap 20 → max 20 planned Easyparser requests ≈ 100 credits ceiling
  at default 5.
- UNKNOWN: Keepa per-request credit cost; SCAVIO; live provider quotes. These
  render `"requires provider plan confirmation"` — never a guessed number.
- Budget stop policy: configured per-run cap (`max_credits`); the plan
  truncates and defers over-budget ASINs explicitly (never silently dropped).
  Since no cap is configured in this offline task, the preflight reports
  `budget_stop: "not configured — operator-defined cap required before any
  live run"`.

## 8. Explicit human-confirmation checkpoint

- Every preflight draft ends with the exact line:
  `HUMAN CONFIRMATION REQUIRED — NO LIVE CALLS EXECUTED`.
- UI shows a disabled action: "Live enrichment requires a separate guarded
  workflow and human confirmation." There is NO functioning "Run Live" button.
- Phase 7 of this task ends with `READY FOR HUMAN APPROVAL` (5 checkpoints).

## 9. Snapshot storage/provenance policy (future run envelope)

New module `proof_batch.py` defines the normalized run-result envelope:

```json
{
  "envelope_schema_version": 1,
  "run_id": "proof-20260818-<uuid>",
  "asin": "B00BISGJXA",
  "provider": "EASYPARSER",
  "requested_fields": ["market_offers"],
  "provider_status": "success",
  "result_status": "available",
  "captured_at": "2026-08-18T12:00:00+00:00",
  "snapshot": { "... intel_schema.py shape ..." },
  "provenance": { "source": "EASYPARSER", "coverage": "full" },
  "error": null
}
```

- `snapshot` validated through `intel_schema.validate_snapshot()`.
- `error` shape: `{"code", "message"}` with a secret-key scrub applied —
  envelopes containing /key|token|secret|credential|password/i keys are
  REJECTED by `validate_envelope`.
- During THIS task only fixture/test results may be stored, and only to
  explicit temp paths (CLI `--out`). No production snapshot files are written.
- A future guarded live run (NOT executed here) would produce one envelope
  per ASIN per provider, validated before storage.

## 10. Benchmark comparison policy + limits

- After a future envelope exists: `benchmark_validation.compare_benchmark_record`
  (benchmark canonical row × envelope snapshot) per ASIN; batch via
  `summarize_batch`.
- Outputs: benchmark matched/unmatched counts, identity/title rate, price
  classification (exact/within/moderate/material/unavailable), review trend,
  Prime/FBA match/changed, BSR category-context rules, offer coverage + Buy
  Box + FBA/FBM internal consistency, economics/demand labeled "internally
  validated — not externally benchmarked".
- Mapping mismatch flags (`pack_mismatch_block`, title mismatch, BSR category
  mismatch) are review flags, never auto-fails.
- NEVER a single deceptive accuracy percentage.
- Capture-time limitation shown in every report: "reference capture time
  unknown — reference only, not freshness proof".

## 11. Exact file-by-file plan

| File | Change |
|---|---|
| `docs/user-selected-20-asin-validation-run.md` | this plan (+ Phase 7 report) |
| `proof_batch.py` | NEW — envelope build/validate/sanitize, fixture-only result runner (writes ONLY to explicit `--out`), batch coverage/drift report builder, CLI |
| `static/index.html` | selection state (`t2.kirklandScout.selection.v1`), add/remove/clear controls (stream row + sheet), Proof Batch panel (count N/20, badges, present vs planned fields, completeness, missing fields, provider profile, preflight summary + JSON export, offline banner, disabled live action), embedded offline benchmark ASIN index (47), fixture-only result view, sanitizer |
| `test_ui_display.cjs` | Phase 17 — selection add/remove/cap/dup/sanitize/persistence, preflight zero-network + export no-secrets, panel rendering, fixture view, benchmark badge, no new network calls |
| `test_proof_batch.py` | NEW — envelope validation (through intel_schema), sanitization/secret rejection, fixture comparisons, batch report, unknown-never-zero, containment (all provider clients patched) |
| `test_asin_benchmark_store.py` / `test_benchmark_validation.py` | unchanged (still green) |
| `enrichment_preflight.py`, `intel_schema.py`, `completeness_score.py`, `asin_benchmark_store.py`, `benchmark_validation.py`, `market_snapshot_store.py`, `main.py` | NO edits (reused as-is) |

## 12. Offline tests

- Selection: add/remove, 20-cap, duplicate prevention, clear-all,
  sanitized persistence (garbage keys dropped, secret-like keys dropped,
  invalid ASINs dropped, max-20 enforced on load).
- Preflight: zero provider calls by construction (pure JS over scanner rows);
  contents (run id, N/20, benchmark match, cache status, present vs missing
  fields, provider profile, requests per ASIN, skips, credit known/unknown,
  cap, budget stop, HUMAN CONFIRMATION line); export JSON contains no
  secret-like keys.
- Envelope: build → validate via `intel_schema.validate_snapshot`; bad
  snapshots rejected; error shape scrubbed; nulls stay null.
- Fixture comparisons: matched/unmatched, price drift classes, review trend,
  BSR rules, offer consistency, econ/demand labels, batch metrics, no
  accuracy percentage.
- Containment: new Python class patches every provider client to raise and
  runs envelope build/validate/fixture-compare/export-parse; harness final
  assertion proves no network during any UI interaction.
- Existing full Python suite + UI harness remain green.

---

## 13. Phase 7 implementation report (post-implementation)

Status: IMPLEMENTED + VERIFIED OFFLINE. No live enrichment was executed.

### 13.1 Files changed

| File | Change |
|---|---|
| `docs/user-selected-20-asin-validation-run.md` | this Phase 7 report |
| `proof_batch.py` | NEW (357 lines) — `ENVELOPE_SCHEMA_VERSION=1`, `VALID_PROVIDERS` (EASYPARSER/KEEPA/COSTCO_CACHE/INVOICE_MANUAL/SELLER_CENTRAL_MANUAL), `PROVIDER_STATUSES`/`RESULT_STATUSES` (incl. `fixture`), `PROVIDER_PROFILES` (Easyparser 5 credits documented, Keepa unknown), `SECRET_KEY_RE`, `contains_secret_like`, `sanitize_error`, `build_envelope`, `validate_envelope` (envelope rules + `intel_schema.validate_snapshot`), `fixture_snapshot_for` (provenance-stamped), `build_fixture_envelopes` (2 rows, within-tolerance + material-drift), `compare_envelope` (via `benchmark_validation.compare_benchmark_record`), `build_batch_report` (metrics + `mapping_mismatch_flags` + limitations, never a universal accuracy percentage), CLI `fixture-run --out <path>` / `report --benchmark <ref> --results <envs>` (fixture/test artifacts only; production snapshot files never written). |
| `static/index.html` | Proof Batch CSS; `#proofBatchPanel` (offline banner "Selection only — no live data, provider calls, or credits used.", `proofCount` N/20, `proofList`, `proofClearAll`, `proofExportBtn`, `proofFixtureBtn`, `proofDisabledLive` "Live enrichment requires a separate guarded workflow and human confirmation.", preflight + fixture boxes); NS block: `SELECTION_KEY`, `MAX_SELECTION=20`, `BENCHMARK_ASINS` (47, mirrors artifact), `SECRET_KEY_RE`, `secretLike`, `benchmarkMatch`, `missingEnrichmentFields`, `selectionRecordFrom`, `sanitizeSelection` (schema gate, drop secret-like/invalid, dedupe, cap 20), `loadSelection`/`saveSelection`/`clearSelection` (via `NS._ls()` with `localStorage`-then-`window.localStorage` fallback), `toggleSelection`, `selectionButtonHtml` (disabled at 20/20 with "Proof batch is full (20/20). Remove an ASIN first."), `cacheStatusOf`, `preflightForSelection` (run_id `proof-preflight-*`, N/20, benchmark_match_count, cache skips, Easyparser credit estimate, Keepa "requires provider plan confirmation", budget_stop "not configured — operator-defined per-run cap required before any live run", zero_provider_calls, `HUMAN CONFIRMATION REQUIRED — NO LIVE CALLS EXECUTED`), `preflightHtml`, `exportPreflightJson`, `FIXTURE_RESULT` (labeled SYNTHETIC FIXTURE, capture time unknown, internally validated limits), `renderProofFixture`, `renderProofBatch`; `streamRowHtml` + table Action cell toggles; sheet Overview "Proof Batch" section; `renderScout()` hook; `init()` delegated handlers (`proofList`, `proofBatchPanel`, `proofClearAll`, `proofExportBtn`, `proofFixtureBtn`, global `document` click for `[data-proof-toggle]`; stream-row click ignores proof toggles). |
| `test_proof_batch.py` | NEW (17 tests) — envelope build/validate through intel_schema (bad snapshot, bad ASIN/provider, secret-like rejection, error-shape sanitization, error-requires-error-object), unknown-never-zero comparisons, fixture envelopes valid + comparable, price drift classification (material_drift + freshness note), `fixture-run --out` explicit-path-only subprocess + report pipeline, batch report (metrics keys carry no `accuracy_percentage`/`overall_accuracy`; limitations true), internally-validated labels, unmatched-ASIN flag, BSR category mismatch flag, containment (no network imports; all provider clients patched to raise). |
| `test_ui_display.cjs` | Phase 17 (47 assertions) — 47-ASIN index, benchmark match, sanitizer (secret-like/invalid/schema/dedupe/cap 20), missing-field derivation, selection record snapshotting, add/remove through the real delegated path, panel show/hide + badge + chip, 20-cap through UI + disabled button, zero-network preflight contents, export no-secret-like + run_id, table/stream/sheet toggles, selection-only + disabled-live labels, fixture view (SYNTHETIC FIXTURE, within_tolerance, limitations). |

Unchanged (reused as-is, still green): `enrichment_preflight.py`, `intel_schema.py`,
`completeness_score.py`, `asin_benchmark_store.py`, `benchmark_validation.py`,
`market_snapshot_store.py`, `main.py` (no route changes), `data/benchmarks/*`
(read-only).

### 13.2 Verification (before → after)

| Suite | Before | After |
|---|---|---|
| Python full suite (`python -m unittest` all `test_*.py`, excluding `test_scavio*`) | 813 OK (skipped=3) | **830 OK (skipped=3)** (+17) |
| UI harness (`node test_ui_display.cjs`) | 780 PASS | **827 PASS** (+47, phases 1–17 + final zero-network assertion) |

CLI smoke: `python proof_batch.py fixture-run --out <tmp>` writes only the
explicit fixture path; `report --benchmark data/benchmarks/asin_benchmark_reference.json
--results <tmp>` prints envelope_count 2, benchmark_matched_asin_count 2,
price_material_drift_count 1, no_universal_accuracy_percentage true.

### 13.3 Manual verification checklist (browser, human)

1. `npm run serve` → open the Scout; select up to 20 rows (stream, table, or
   sheet toggles); confirm Proof Batch panel counts N/20, benchmark badges,
   completeness chips, missing-field lists, preflight summary + export JSON
   (no secrets), fixture-only view, disabled live action.
2. Confirm selection persists across reload; removing clears panel; 21st add
   is refused with the full-batch message.
3. Confirm no network activity: browser DevTools Network tab stays empty for
   all Proof Batch interactions.

### 13.4 Not executed in this task (future guarded live run)

1. Approve the 20-ASIN selection (this UI) and the exported preflight JSON.
2. Set per-run credit caps + budget stop for the chosen provider mix
   (Easyparser ~5 credits/ASIN; Keepa requires provider plan confirmation).
3. Run the separate guarded live-enrichment workflow (NOT part of this task)
   producing per-ASIN envelopes validated by `intel_schema.validate_snapshot`.
4. Compare envelopes against `data/benchmarks/asin_benchmark_reference.json`
   via `proof_batch.report`; review `mapping_mismatch_flags`, price/BSR drift
   (labeled freshness/context review — never provider error), offer
   consistency, and internally-validated economics/demand labels before any
   test buy.

### 13.5 Limitations (honest economics)

- Selection is browser-local only (no server persistence, no sync).
- Preflight is a planning draft: credits are documented estimates, Keepa is
  unknown until the provider plan is confirmed, and cache-skip expectations
  are based on the last scan's snapshot timestamps.
- Benchmark reference capture time is unknown; comparisons validate mapping
  and plausibility, not live market stability.
- Economics/demand/seller coverage are internally validated only — never
  benchmarked against the reference CSVs.