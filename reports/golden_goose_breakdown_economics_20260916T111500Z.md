# Golden Goose Finder — Breakdown Economics Engine (breakdown_economics.py)

**Date:** 2026-09-16 · **Module:** `Northstar_backend/agents/golden_goose_finder/breakdown_economics.py`
**Tests:** `Northstar_backend/agents/golden_goose_finder/tests/test_breakdown_economics.py` (41 tests)

## What landed

Full breakdown economics for multi-pack arbitrage (Costco/Sam's Club bulk pack → individual Amazon units), integrated with the existing fee stack under the house honesty rules.

### Dataclasses (shared models — consumers duck-type)
- **`WholesalePack`** — source_store, product_title, brand, category_slug, pack_count (number of *individual sellable units* the pack yields), wholesale_price + optional weights/dims. Includes a read-only `wholesale_pack_title` alias property so `goose_report` / the slim `opportunity_scorer` fallback keep working.
- **`IndividualListing`** — asin, title, brand, category_slug, amazon_price + fee signals (amazon_category, browse_node, weight_oz, dimensions_in, listing_fba_fee) and demand signal `monthly_sales_estimate` (matches `AmazonMatch`; consumed by the scorer).
- **`BreakdownEconomics`** — full per-unit + per-pack economics with confidence and provenance notes.

### Calculation (`calculate_breakdown_economics`)
Per-unit stack built exactly as specified:
`unit_cogs = wholesale_price / pack_count` + repackaging (default $0.75 = $0.50 labor + $0.25 packaging; explicit `$0.00` honored as a configured zero) + referral fee (versioned `fee_engine.calculate_referral_fee`, honoring the $0.30 min-fee floor and 8%/15% price switches) + FBA fulfillment (versioned table via `fee_engine.calculate_fba_fulfillment_fee`, listing-reported fee, or `pricing.estimate_fba_fee` fallback) + inbound ($0.35) + prep ($0.25) + return reserve (2% of sale price) → `total_costs_per_unit == breakeven_amazon_price`.

Metrics: net profit/unit & /pack, ROI/unit & /pack (%), margin %, breakeven, all rounded for storage with raw-math internals (fee_engine precedent).

### Confidence & honesty
- `estimated` — full engine-derived fee stack.
- `provisional` — FBA fee unavailable (no weight data → **excluded**, never guessed) or any fee came from a fallback estimator (flat 15% referral / pricing table).
- `unavailable` — missing price / wholesale price / pack_count: money fields stay `None`, never $0.00.
- Every assumption/fallback recorded in `economics_notes` (default-category resolution, weight-missing, ROI-below-floor, pack_count=1, engine-down, pricing fallback, over-budget repackaging).
- Import-time and call-time graceful degradation: both `fee_engine` and `pricing` are optional; failures fall back to documented estimates with notes. Duck-typed attribute reads (`getattr`) so scanner/mock pipeline objects work as inputs.

### Batch + filter
- `evaluate_batch(opportunities, roi_floor=10.00)` — one result per pair, in order (empty → `[]`).
- `passes_economics_filter(economics, roi_floor=10.00, min_margin_pct=0.0)` — roi_per_unit ≥ floor AND margin ≥ min, **fails closed** on unavailable/missing numbers.

## Test coverage (41 tests, all passing)
- Realistic scenarios: Nicorette lozenge (200ct→10×20ct), Advil (500ct→5×100ct), Tide Pods (152ct→3×42ct), Nature Made Vitamin D (250ct→4×60ct), Dove Body Wash (6pk→single) — exact fee-stack numbers verified against the 2026 rules (price switches, min referral fee, FBA bands).
- Edge cases: pack_count=1, very expensive ($800/2pk), very cheap ($1.29 min-fee floor), custom/zero repackaging budgets.
- Breakeven == total costs; ROI/margin formulas; confidence transitions; warnings in notes; batch evaluation; None/missing-data paths (missing price/weight/listings fields, zero-weight-as-missing).
- Fallback paths via monkeypatch: fee_engine import missing (15% flat + pricing FBA, provisional), fee_engine raising (pricing fallback, provisional), pricing missing (fee excluded).
- ROI-floor/margin-gate filters incl. boundary (`>=` semantics) and fail-closed on unavailable.

## Integration fixes made
- `tests/conftest.py` rebuilt around the shared dataclasses: field-introspection (`dataclasses.fields`) so fixtures work against the full shared model; `wholesale_pack_title`/`product_title` normalization; new required `BreakdownEconomics` fields filled with internally consistent defaults (`total_costs_per_unit == breakeven == price − net`).
- `opportunity_scorer.py` (sibling) already imports the models from this module — verified compatible with its attribute reads.

## Verification
- `python -m pytest agents/golden_goose_finder/tests/ -q` → **279 passed**
- Full backend: `python -m pytest -q` → **1835 passed, 3 skipped, 48 subtests passed** (no regressions)
- Smoke test with real pipeline mock objects (duck-typed inputs) → correct provisional economics with FBA-excluded note when weights are absent.

## Files
- Added: `breakdown_economics.py`, `tests/test_breakdown_economics.py`
- Modified: `tests/conftest.py` (shared fixtures to the new contract)