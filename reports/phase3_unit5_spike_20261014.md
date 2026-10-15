# Phase-3 Unit 5 — product-matching spike (dedupe + splink) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 5 of 7).
- **Scope honesty:** the directive said "match 50 sample ASIN/UPC pairs **from our data**" — production data lives outside this workstream (parallel session's domain; `.env`/data excluded by standing rules), so the spike uses a **clearly-synthetic 50-pair set** (`FAKE-TEST-…` markers, deterministic seed `20261014`, no real users/data, no live calls, nothing written to any store). This is a methodology spike, not a production benchmark.
- **dedupe: install-blocked on this machine.** `uv`/`pip` attempts on the managed Python 3.12, 3.11, and system 3.14 all failed building C extensions (`dedupe` → `dedupe-levenshtein-search`, `affinegap`, … "Build failures … problem with the package or the build environment"). Source-evaluated (Phase-2) only; **no local run**. Any production interest should re-test with a build toolchain or on Linux CI.
- **splink 5.0.0 (MIT): ran.** `scripts/spikes/product_matching_spike.py` — 100 synthetic records = 25 true pairs (perturbed duplicates: typos, extra marketing tokens, unit-spacing variants, case changes) + 25 near-identical distractors. DuckDB backend; comparisons: Jaro-Winkler(title, [0.92, 0.84]), exact UPC, exact brand; blocking: brand / word / upc; EM trained (converged, 25 iterations; sub-second predict).

## Results
| Configuration | Predicted | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| splink raw (threshold 0.5) | 24 | 24 | 0 | 1 | **1.00** | **0.96** | **0.98** |
| + UPC-conflict veto (domain rule) | 24 | 24 | 0 | 1 | 1.00 | 0.96 | 0.98 |

- The exact-UPC + exact-brand comparisons and blocking cleanly rejected all 25 near-identical distractors; the single miss is the most degraded perturbation (a duplicate-character typo in the title that fell below both Jaro-Winkler thresholds) — the tuning path is higher thresholds or an additional phonetic comparison; noted, not chased in a spike.
- The **UPC-conflict veto** (conflicting non-null identifiers ⇒ not a match) was a no-op on this set (the model already excluded those pairs) — retained in the script as the realistic domain rule for future real-data work.
- Process notes (honest): the first run hit **splink-5 API drift** (Linker consumes registered frames via `DuckDBAPI.register`, not raw pandas/`db_api=`), and an initial **metrics-orientation bug in the spike itself** double-counted reversed true pairs as false positives; both fixed before this report — the committed script is the corrected version.

## No prod wiring (per directive)
Spike artifact only (`scripts/spikes/`); synthetic data generated in-process; no store/ledger writes; no service changes; nothing enabled.
