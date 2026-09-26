# 17 — Auctioneer Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Plan, analyze, and (with scoped permission) manage Amazon advertising with sound economics and shared keyword intelligence.

## 2. Entry points

- `/auctioneer` (overview), `/auctioneer/campaigns/:campaignId`.

## 3. Main workspace

- **Overview**: portfolio metrics (ACoS, TACoS, ROAS, spend, sales, profit), alerts, recommendation list.
- **Campaigns**: campaign hierarchy (portfolio → campaign → ad group → ads); SP first, extensible.
- **Search terms**: SQR analysis, harvest/negation candidates.
- **Keywords**: shared keyword graph (with OfferChisel/RankLedger); no parallel keyword universe.
- **Placement**: placement analysis.
- **Dayparting**: if supported (owner Q).
- **Change history**: audit of campaign changes + rollback (approval-gated).

## 4. Economics (single canonical formulas — resolves Phase 0 R13)

- **Break-even ACoS** = `(price − cogs − fees) / price × 100` (single shared module).
- **Target ACoS** = `break-even × (1 − desired_margin/100)`.
- **CPC / CTR / CVR / ROAS / TACoS** with explicit units; edge cases guarded (division by zero → unknown).
- All three Phase 0 implementations (ad_pilot, word_coffee, frontend Auctioneer.jsx) converge to one shared module used by backend + frontend.

## 5. Recommendation engine

- Bid/budget recommendations with expected impact + confidence; keyword harvest/negate candidates; placement recommendations.
- Every recommendation shows data + rationale + expected impact + confidence; never presented as fact without evidence.

## 6. Actions

| Action | Gate |
|---|---|
| Analyze | read (gated import if Ads connected) |
| Build campaign plan (draft) | none |
| Create/modify campaign | **external write — scoped approval + diff preview** |
| Harvest/negate keywords | draft first; apply = external write |
| Dayparting config | draft; apply = external write |
| Rollback change | approval + audit |

## 7. States

- Empty: "Connect advertising account / import campaign data".
- Partial: missing performance → unknown; metrics labeled by basis.
- Stale: "as of <t>".
- Provider failure: banner + last cache.
- Permission denied: write actions require grant.

## 8. Responsive

Overview → stacked; campaign table → cards on mobile.

## 9. Tour steps

1. Read portfolio economics.
2. Open a campaign.
3. Review a recommendation (impact + confidence).
4. Harvest negatives (draft).
5. Build a campaign plan.

## 10. Events

Emits: `campaign.changed`, `campaign.approval.requested`, `ad.performance.recorded`, `recommendation.generated`. Consumes: `keyword.observed`, `economics.computed`, `product.updated`, `snapshot.recorded`.

## 11. Downstream

- Hub (ad alerts), OfferChisel (shared keywords), RankLedger (sponsored performance), Ledger (provider cost).
