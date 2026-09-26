# 20 — RankLedger Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Track organic keyword and product rank over time with keyword groups, competitor comparison, and trend alerts — feeding and reading the shared keyword graph.

## 2. Entry points

- `/rankledger` (overview), `/rankledger/keywords/:keywordId`.

## 3. Main workspace

- **Rank overview**: tracked keywords; latest rank; trend; group.
- **Keyword groups**: user-defined groups.
- **Rank history**: per keyword chart (organic/sponsored where measurable).
- **Annotations**: listing-change / ad-change annotations overlaid on rank history.
- **Trend alerts**: rank drop/rise thresholds.

## 4. Data acquisition

- `keyword_observation` rows from provider (rank source — owner Q10) or shared keyword graph ingestion; explicit refresh.
- No silent page-load capture (owner rule).

## 5. Shared SEO integration (mandatory)

- Reads/writes the **single keyword graph** (`keyword`, `keyword_observation`, `keyword_association`) shared with OfferChisel, Auctioneer, Town Crier, Rival Board. No parallel keyword universe (Phase 0 R2).

## 6. Actions

| Action | Gate |
|---|---|
| Track keyword | none |
| Create group | none |
| Refresh rank | explicit + budget |
| Annotate change | none (audited) |
| Set alert | none |

## 7. States

- Empty: "Add keywords to track".
- Partial: no rank data for a keyword → unknown; never fabricated rank.
- Stale: "as of <t>".
- Provider failure: banner + last data.

## 8. Responsive

Charts scale; table → cards on mobile.

## 9. Tour steps

1. Add a keyword.
2. Create a keyword group.
3. Read rank history.
4. Add an annotation.
5. Set a trend alert.

## 10. Events

Emits: `keyword.observed`, `rank.alert.raised`. Consumes: `snapshot.recorded`, `listing.changed`, `campaign.changed`.

## 11. Downstream

- Hub (rank alerts), OfferChisel/Auctioneer (shared graph), Rival Board (comparison).
