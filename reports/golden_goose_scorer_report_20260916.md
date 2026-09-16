# Golden Goose Finder — Opportunity Scorer + Report Generator (build report)

Date: 2026-09-16
Module: `Northstar_backend/agents/golden_goose_finder/`

## Deliverables

| File | Purpose |
|---|---|
| `opportunity_scorer.py` | Scores `BreakdownEconomics` -> `ScoredOpportunity`: 4 weighted components (profit .35 / demand .25 / competition .25 / health .15), hard filters, HIGH/MEDIUM/LOW/REJECT tiers, notes, tags. |
| `goose_report.py` | JSON report (v1.0 schema) + `summary.txt`, console table (ANSI tier colors on tty), SourceScout UI panel export, `save_report()` to `reports/golden_goose/<ts>/`. |
| `tests/conftest.py` | Shared factory `make_economics()` + per-tier fixtures (HIGH/MEDIUM/LOW/REJECT/UNKNOWN). |
| `tests/test_opportunity_scorer.py` | 31 tests: tier classification, component anchors, tier boundaries, tags, hard filters (near-baseline rating escape, undercut competition escape), batch ordering/filtering, summary stats, unknown/empty edge cases. |
| `tests/test_goose_report.py` | 15 tests: full JSON schema (5-opportunity run incl. 1 reject), fee-split nulls, breakeven math, gating heuristics, save_report (tmp + default dir), console format (no ANSI off-tty), scout-panel row model, empty data. |

## Design decisions (documented in code)

1. **Shared data models live in `opportunity_scorer.py`** with an import preference for the sibling `breakdown_economics` module (falls back to identical local dataclasses until it lands). `main.py` already imports `breakdown_economics.BreakdownEconomics`; consumers only read attributes, so either class works (duck-typed).
2. **`score_batch` filters REJECTs by default**, gains `include_rejected=True` so report `discarded` can still be populated.
3. **ROI convention: percentages.** `_as_pct()` converts values in `(0, 1.0]` (ratios) to percent; larger values pass through. Report keys use `roi_percentage` / `roi_per_costco_pack_pct` / `profit_margin_pct`.
4. **Demand via `demand_estimator.estimate_demand()`** with slug alias resolution for sourcing categories; no data -> score 0.30 + honest note (unknown is never 0).
5. **Fail-closed hard filters**: missing net/sales/sellers/rating -> filter fails with a note; competition >3 sellers uses a 2%-undercut check against the profit floor.
6. **Near-baseline demand escape**: sales within 80% of the floor pass when rating >= `min_rating` (default 4.0; spec's documented parameter).
7. **Gating status is a display heuristic** (live FBA sellers >0 -> APPROVED, 0 -> CAN_APPLY, unknown -> UNKNOWN), never asserted as fact.
8. **Fee split (referral/fulfillment/repackaging) stays null** — not derivable from `total_amazon_fees`; breakeven approximated at the current fee level and flagged in notes.

## Evidence

- `python -m pytest agents/golden_goose_finder/tests/test_opportunity_scorer.py agents/golden_goose_finder/tests/test_goose_report.py -v` -> **46 passed**
- Full package suite `python -m pytest agents/golden_goose_finder/tests/ -q` -> **238 passed**
- Smoke run verified: HIGH tier composite 0.7554, 6 tags, console table, scout-panel row, `summary.txt` output.

## Integration notes for the orchestrator

- Wire `calculate_breakdown_economics()` (sibling `breakdown_economics.py`) results into `score_batch(...)`; pass `include_rejected=True` when the JSON report must show the `discarded` section.
- Optional `WholesalePack.source_store` / `wholesale_pack_title` enrich the report; the report degrades to `Unknown`/brand when absent (getattr-safe).
- REJECT composite < 0.25 is the hard floor; MEDIUM requires profit >= roi_floor; HIGH requires composite >= 0.7 AND all four hard filters.