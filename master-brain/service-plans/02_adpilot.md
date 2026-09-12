# AdPilot — Amazon Ads Agent — Website Plan & Architecture

> **Status:** Approved for construction (Autonomous Zone).
> **Derives from:** master plan §4.1 (four-tier campaign structure, ACoS band rules,
> keyword lifecycle, guardrails, data layer).

## 1. SERVICE IDENTITY

**Public:** AdPilot — "Pilot your ad spend."
**Internal agent:** Amazon Ads Agent (Ads Agent).
**Core promise:** PPC bid optimization, ACoS management, keyword harvesting, placement
analysis, negative-keyword hygiene — from bulk-sheet in to annotated decisions out.

## 2. SCREENS / VIEWS (hash routes within `#/adpilot`)

| View | Purpose |
|---|---|
| **Campaigns** | 4-tier campaign overview: Bench Auto ($10/day) → Scale Broad ($15) → Almost Winners ($25) → Winners Exact ($40); budget, bid strategy (Dynamic Bids — Down Only), spend/ACoS per tier |
| **Harvester** | Search-term harvesting OS: Auto→Broad→Phrase→Exact progression, negatives, movement flags (PROMOTED / DEMOTED / NO_CHANGE) |
| **Bid Optimizer** | ACoS band rule engine preview: per-keyword recommended bid delta per the band table |
| **Placements** | Placement performance (top-of-search, product pages, rest) + day-parting view |
| **Bulk Ops** | Amazon Bulk Operations CSV in → annotated decisions CSV out (fixture-based) |

## 3. COMPONENTS

1. **Tier Ladder** — visual 4-tier stacking card (Bench → Winners Exact) with live
   budget chips.
2. **Keyword Row** — physical card per keyword: impressions/clicks/spend/orders/ACoS,
   tier badge, movement flag, recommended bid delta.
3. **ACoS Band Strip** — color-zoned bar (crimson >45%, gold 30–45, steel 15–30, gold
   <15) with current ACoS marker + rule text.
4. **Placement Bars** — ink-plot horizontal bars for placement share.
5. **CSV Dock** — drag a fixture bulk-sheet; renders parsed rows annotated with
   decisions (increase ≤10%, decrease ≤20%, add negative, promote, pause).

## 4. DATA CONTRACT

```js
campaignTier = {
  tier: 'bench_auto'|'scale_broad'|'almost_winners'|'winners_exact',
  dailyBudget, bidStrategy, spend, sales, acos,
  status: 'discovery'|'exploration'|'validation'|'scaling',
}
keywordRow = {
  kw, tier, impressions, clicks, orders, spend, acos, cvr,
  movement: 'PROMOTED'|'DEMOTED'|'NO_CHANGE',
  recommendedAction, guardrail: 'autonomous'|'needs_approval',
}
bulkRow = { sku, campaign, kwOrTargeting, matchType, bid, decision, reason }
```
- Fixtures (`demo-keywords.json`) include Word Coffee harvested absolutes
  ("affirmation cards for women", "gift cards for women" 35.53x, brand term
  "word coffee" 166–177x) and negatives (free, printable, coffee beans) — labeled demo.
- Guardrail matrix surfaced per proposed action: bid ≤10% up / ≤20% down / add
  negative / promote = autonomous badge; >10% up / budget / new campaign / pause-all =
  needs-approval badge.

## 5. GATED-LIVE PATHS

- Amazon Bulk Operations CSV **execution** (upload to Amazon) — gated off.
- Ad-account read (ACoS/spend pull from Amazon Ads API) — gated off; fixtures today.
- n8n/Supabase wiring is a later phase (data layer references exist in master plan).

## 6. TEST CONTRACT

- 4 tiers render with exact budget/bid defaults from master plan §4.1.
- ACoS band rule: given mock kw ACoS 50% + ≥10 clicks → shows "−10 to −30% bid".
- Movement flags render styled badges and sort.
- Bulk CSV fixture: 3 rows parsed, annotated decisions present, no network.
- Zero `fetch` calls across interactions.

## 7. BUILD ORDER

1. Fixtures (`demo-keywords.json`, fixture bulk sheet).
2. Campaigns tier ladder + placement bars.
3. Harvester rows + movement flags.
4. Bid Optimizer band strip + guardrail badges.
5. Bulk Ops dock with fixture CSV.
6. Tests green; commit; state update.