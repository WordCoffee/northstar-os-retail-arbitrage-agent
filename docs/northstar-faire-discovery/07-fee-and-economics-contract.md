# 07 — Fee and Economics Contract

Implementation: `faire_research/economics.py` (**TEMPORARY** research adapter,
`Decimal`-based). Canonical engine is Phase 1C item **1C-04** (not yet built).

## Correct economics (do NOT use Faire price − Amazon price)

```
LANDED WHOLESALE UNIT COST =
  (wholesale case cost + supplier shipping + nonrecoverable tax + duties
   + receiving cost + case-level prep cost) / verified sellable units

CONTRIBUTION PROFIT =
  Amazon sale price
  - referral fee
  - FBA fulfillment fee
  - landed wholesale unit cost
  - inbound FBA shipping per unit
  - prep/label cost
  - storage allocation
  - advertising reserve
  - return/refund reserve
  - other known per-unit costs

ROI ON INVESTED COST = contribution profit / total invested cost per sellable unit × 100
MARGIN ON REVENUE    = contribution profit / Amazon sale price × 100
```

ROI, margin, markup, payout, revenue and contribution profit are **distinct**.

## Rules enforced

- `Decimal` for all money; results quantized to cents.
- Unknown fee/cost is **never** zero → result is *unresolved*.
- Unknown units or unknown case component → landed cost *unresolved*.
- `FEE_UNKNOWN` cannot pass.
- Downside scenarios at 0/-5/-10/-15% (referral scales with price); reject if
  economics disappear.
- Default exploration thresholds: contribution ≥ \$5, ROI ≥ 30%
  (secondary lane 20–29.99%), margin ≥ 15%. Configurable, not universal.

## Fee-confidence states

`AMAZON_API_VERIFIED`, `OFFICIAL_TABLE_CALCULATED`,
`ESTIMATED_FROM_COMPLETE_INPUTS`, `ESTIMATED_FROM_INCOMPLETE_INPUTS`,
`FEE_UNKNOWN`. Candidates with `FEE_UNKNOWN` cannot enter the approved shortlist.

## Fee inputs required

Marketplace, category, selling price, fulfillment channel, product/shipping
dimensions, shipping weight, dimensional weight, dangerous-goods status, apparel
status, peak/non-peak period, storage period. Referral fees vary by category and
may include minimum per-item fees — **do not hardcode a universal 15%**.

## Fee tables in-repo

`amazon_us_fee_rules_2026.py` (referral rules + FBA size-tier table) and
`pricing.estimate_fba_fee` / `fee_engine.calculate_*` are the closest existing
calculators. They are **not** the gated canonical engine; use with explicit
fee-confidence labels.

> Replace this adapter with the canonical engine at 1C-04. Do not extend it into a
> second permanent implementation.
