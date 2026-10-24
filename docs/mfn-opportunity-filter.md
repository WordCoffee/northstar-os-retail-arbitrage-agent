# MFN Opportunity Filter (`mfn_opportunity_score_v1`)

This document explains how the manual-export workflow decides whether a
candidate may enter a qualified/test-buy state based **only** on provider-
reported seller composition. Amazon.com is never directly scanned.

## 1. Purpose

The MFN opportunity filter identifies candidates where you could fulfill
yourself (Merchant Fulfilled Network, MFN) with **zero active FBA competition**
and **at least 3 active MFN sellers** (a sign of sellable demand with limited
fulfillment-by-Amazon competition). It is deliberately conservative: **unknown is
never favorable**.

## 2. Required marketplace conditions (default)

A candidate may only enter qualified/test-buy recommendation state if ALL of
these are provider-reported, fresh, and complete:

| Condition | Required value |
|---|---|
| Amazon Retail active | explicitly `false` |
| Brand owner seller active | explicitly `false` when identifiable |
| Active FBA seller count | explicitly `0` |
| Active MFN seller count | `>= minimum_active_mfn_sellers` (default 3) |
| Buy Box / expected sale price | required |
| Seller count evidence freshness | required |
| Exact listing identity | required |
| ASIN sellability status | eligible / sellable |
| Restriction status | unrestricted |

Any unknown → the candidate becomes `needs_enrichment` or
`manual_review_required`. Any violation → `blocked`.

## 3. Configurable thresholds

Defined in `costco_non_kirkland/settings.py` (`DEFAULT_SETTINGS`) and overridable
via `NORTHSTAR_<NAME>` env vars or a `settings` dict:

```text
minimum_active_mfn_sellers: 3
maximum_active_fba_sellers: 0
maximum_shipping_weight_lb: 3.0
minimum_net_profit: 5.00
minimum_roi_pct: 30.0
qualified_net_profit: 11.00
priority_net_profit: 20.00
market_snapshot_max_age_minutes: 60
source_price_max_age_minutes: 60
price_history_max_age_hours: 24
```

## 4. `mfn_opportunity_score_v1`

Applied **only after hard blockers pass**. Weights (sum 100):

```text
Net profit:                  25
ROI:                         20
Demand / BSR / sales signal: 15
MFN competition quality:     15
Zero active FBA sellers:     10
Low weight / standard size:   5
Price stability:              5
Source repeatability:         5
Total:                      100
```

- Unknown inputs score 0 for that component (never favorable).
- A high MFN seller count is **not** automatically rewarded; a penalty applies
  if provider data indicates high seller count **and** unstable price history
  (surfaced as a risk flag).

## 5. What does NOT pass

- Amazon Retail active
- Brand-owner seller active
- Any active FBA seller (default)
- Fewer than 3 MFN sellers
- Overweight (default > 3.0 lb)
- Unknown sellability, restriction, or seller counts
- Stale provider snapshot or stale source cost

## 6. Where it lives

- Filter: `costco_non_kirkland/competition.py` (`assess_competition`)
- Score: `costco_non_kirkland/competition.py` (`mfn_opportunity_score`)
- Decision: `costco_non_kirkland/workflow.py` (`decide_candidate`)
- Thresholds: `costco_non_kirkland/settings.py`