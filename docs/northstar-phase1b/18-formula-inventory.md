# 18 — Formula Inventory (R13/R14 resolution prerequisite)

**Status:** REQUIRED BEFORE Phase 1C canonical-economics work. This is an inventory
only — **no formula was changed** in Phase 1B (owner rule).

Purpose: duplicated fee/ROI/profit/ACoS formulas are exactly the drift that yields
silently wrong numbers. This inventory must exist **before** a canonical module is
built, so the module replaces all sources rather than adding a fifth.

All entries are STATICALLY_CONFIRMED (source read). Line numbers as of this audit.

## A. Fee formulas

| # | Location | Symbol | Formula / behavior |
|---|---|---|---|
| F1 | `Northstar_backend/fee_engine.py:180` | `calculate_referral_fee` | category rule engine (two_rate / price_switch / progressive), min fee $0.30 |
| F2 | `Northstar_backend/fee_engine.py:263` | `calculate_fba_fulfillment_fee` | size-tier table (`amazon_us_fee_rules_2026.py:233-242`) |
| F3 | `Northstar_backend/fee_calculator.py:130` | `calculate_referral_fee` | **second implementation** of referral fees |
| F4 | `Northstar_backend/pricing.py:4` | `compute_profit` | hardcoded `referral_rate=0.15`, `fba_fee`, `fuel_rate=0.035`, `inbound_cost=0.35` |
| F5 | `northstar-os-ui/src/pages/Auctioneer.jsx:12-13` | inline | **frontend** `referral = price*0.15`; fulfillment `price>59?5.55:price>19?4.6:3.4` |
| F6 | `northstar-os-ui/src/pages/GoldenGoose.jsx:12,55` | inline | **frontend** same hardcoded 0.15 + tier fees |

## B. Net profit / ROI / margin

| # | Location | Symbol | Formula |
|---|---|---|---|
| P1 | `Northstar_backend/fee_engine.py:406` | `calculate_unit_economics` | net = price − cogs − referral − fba − inbound − prep − packaging − return_reserve(2%) ; roi = net/cogs*100 |
| P2 | `Northstar_backend/fee_calculator.py:233-254` | — | net = sale_price − landed_cost − total_fees ; net_margin = net/price*100 |
| P3 | `Northstar_backend/product_analysis.py:373-380` | — | `profit_margin_pct = net/costco_cost*100` (**cost-basis margin**, not price margin) |
| P4 | `Northstar_backend/scanner_data.py:265-267` | `net_margin_pct` | `net/price*100` (**price margin**) |
| P5 | `Northstar_backend/finance.py:129-142` | `projected_roi_pct` | roi = profit/landed*100 ; landed = cogs+prep+inbound |
| P6 | `Northstar_backend/unit_economics.py:24` | `compute_economics` | null-first unit economics |
| P7 | `Northstar_backend/enricher.py:143` | `compute_economics` | **another** economics function (origin/gap layer) |
| P8 | `Northstar_backend/agents/golden_goose_finder/breakdown_economics.py:506,590` | `calculate_breakdown_economics` | margin = net_per_unit/price*100 ; roi = net/unit_cogs*100 |
| P9 | `northstar-os-ui/src/pages/Prospector.jsx:12-15` | inline | reads backend `net_profit`/`roi_pct`; margin = net/price*100 |
| P10 | `northstar-os-ui/src/pages/GoldenGoose.jsx:6-19` | `scoreDeals` | recomputes net/roi/margin client-side when not provided |

## C. ACoS / advertising

| # | Location | Symbol | Formula |
|---|---|---|---|
| A1 | `Northstar_backend/ad_pilot.py:327` | `compute_target_acos` | breakeven = (price − cost − fees)/price*100 ; target = breakeven*(1 − desired_margin/100) |
| A2 | `Northstar_backend/word_coffee.py:47` | `breakeven_acos` | contribution = asp − cogs − fba − asp*referral_pct/100 ; breakeven = contribution/asp*100 |
| A3 | `northstar-os-ui/src/pages/Auctioneer.jsx:15-16` | inline | breakEven = gross/price*100 ; target = breakEven*0.7 |
| A4 | `Northstar_backend/agents/golden_goose_finder/opportunity_scorer.py:835-843` | `composite` | weighted score (profit/demand/competition/health/price-gap/ad-feasibility) |

## D. Confirmed conflicts (must be reconciled, not ignored)

1. **Two margin definitions coexist**: `net/price` (P4) and `net/costco_cost` (P3) — a
   different number for the same product. Any UI labeled "margin" is ambiguous.
2. **Three ACoS implementations** (A1, A2, A3) with different bases/targets.
3. **Hardcoded 0.15 referral + tier FBA fees** in the frontend (F5, F6) diverge from the
   backend rule engine (F1, F2).
4. **Multiple `compute_economics`/profit functions** (P1, P2, P5, P6, P7) with different
   input sets and null behavior.

## E. Requirement for the canonical economics module (Phase 1C 1C-04)

The canonical module MUST:
- Provide one `referral_fee`, one `fba_fee`, one `net_profit`, one `roi`, one `margin`
  (with an explicit, single definition), one `breakeven_acos`, one `target_acos`.
- Preserve formula version (`fee_rule_version`), input provenance, and null-first
  behavior (unknown → `None`, never `0`).
- Prevent division-by-zero; distinguish percentage vs decimal ratio explicitly.
- Add **regression tests** around existing behavior for each inventoried site.
- Then migrate every listed call site to it and delete/redirect the duplicates (so the
  count of formula sources **decreases**, never increases).

## F. Guardrails already enforced by Phase 1B

- The foundation does not compute or store economics yet (no fifth source added).
- `docs/northstar-phase1b/15-known-gaps.md` records this as a blocking prerequisite.
- A product is never labeled purchase-ready without economics + sourcing evidence.