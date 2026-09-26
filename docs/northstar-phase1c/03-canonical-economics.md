# 03 — Canonical Economics Engine (1C-03)

**Status:** ✅ **PASS** — one authoritative engine; RUNTIME_CONFIRMED (tests executed).

## Module

`Northstar_backend/foundation/economics/`

| File | Responsibility |
|---|---|
| `enums.py` | `Readiness`, `MetricName`, `RoundingMode`, `CashBasis`, `ProvenanceClass` |
| `money.py` | Decimal coercion, quantization, rounding modes, safe division, serialization |
| `inputs.py` | `EconomicsInput` (all Optional; per-field provenance) |
| `outputs.py` | `EconomicsOutput` (named metrics + missing_inputs + readiness + version) |
| `engine.py` | `compute()` — pure, deterministic |
| `readiness.py` | classification facade |
| `compatibility.py` | legacy adapters (`economics_from_legacy`, `to_legacy_fields`) |
| `benchmarks.py` | Minoxidil assumption vectors |
| `versions.py` | `FORMULA_VERSION = economics-1.0.0` |

Pure and deterministic; no provider calls; no DB side effects.

## Canonical definitions (as implemented)

- `GROSS_REVENUE` = selling_price × quantity (tax-on-behalf not treated as revenue).
- `MARKETPLACE_FEES` = referral (amount or price×rate) + FBA + closing + variable closing + other; **None if referral or FBA unknown**.
- `MARKETPLACE_PAYOUT_BEFORE_ADS` = gross − fees (not profit).
- `LANDED_INVENTORY_COST` = (acquisition + inbound + prep + label + duties + storage) × quantity.
- `PRE_AD_CONTRIBUTION` = gross − fees − landed − reserves.
- `ADVERTISING_COST`, `CONTRIBUTION_PROFIT_AFTER_ADS` = pre-ad − ads.
- `ROI_ON_INVESTED_COST` = contribution / landed (denominator disclosed via `roi_denominator_label`).
- `MARGIN_ON_REVENUE` = contribution / gross; `MARKUP_ON_COST` = contribution / cost (distinct from margin).
- `BREAK_EVEN_ACOS` = pre_ad / ad-attributed revenue (when known & > 0).
- `TARGET_ACOS` = explicit policy or derived from a required post-ad profit floor — **not** a hardcoded 70%.
- `TACOS` = ad spend / total revenue (None without total revenue scope).
- `CTR/CVR/CPC/ROAS/MAXIMUM_CPC` per prompt; `CASH_AVAILABLE_FOR_REINVESTMENT` is a separate metric with a disclosed basis.

## Rounding & precision

Internal precision 34; money 2 dp; rates/ratios 4 dp; percentages 2 dp; `ROUND_HALF_UP` default (configurable); negative-zero normalized; division-by-zero → `None`; binary floats never authoritative (float inputs coerced via `str`).

## Null-first readiness

`SELLING_PRICE_MISSING`, `ACQUISITION_COST_MISSING`, `REFERRAL_FEE_UNKNOWN`,
`FULFILLMENT_FEE_UNKNOWN`, `PACK_CONFIGURATION_UNRESOLVED`, `CURRENCY_MISMATCH`,
`PROVENANCE_STALE`, `SOURCE_UNVERIFIED`, `COMPLETE_ESTIMATED`, `COMPLETE_VERIFIED`.
Unknown inputs never become zero; `purchase_ready` requires `COMPLETE_VERIFIED` **and**
sourcing + documentation + eligibility gates.

## Consumer migration

- **Faire** `faire_research/economics.py` — authoritative formulas removed; now a
  canonical adapter preserving fail-closed gates (45 Faire tests pass).
- **Legacy adapters** provided (`compatibility.py`) with **no hidden 0.15 referral / fixed
  FBA defaults**.
- Remaining legacy sites (fee_engine, fee_calculator, pricing, finance, unit_economics,
  enricher, product_analysis, scanner_data, ad_pilot, word_coffee, GG, frontend) have a
  documented disposition to delegate via the adapter — full rewire is the next step
  (see `economics-migration-report.json`).

## Minoxidil benchmark vectors

Two assumption sets preserved separately and labeled; the original records carry only
aggregate payout/profit, so the engine reports the **implied** total marketplace fee
(12.48 for both) instead of inventing a component breakdown. Reproduced:
legacy payout 25.51 / profit 7.52; newer payout 29.52 / profit 11.53.

## Tests

`foundation/tests/test_economics.py` → **30 passed** (complete/estimated, missing
price/cost/fees, zero/negative/large, currency mismatch, precision, multipack scaling,
reserves, advertising metrics, ACoS/TACoS/ROAS/CPC/CTR/CVR/max CPC, cash basis,
serialization, legacy adapter, Faire fail-closed, both Minoxidil vectors).