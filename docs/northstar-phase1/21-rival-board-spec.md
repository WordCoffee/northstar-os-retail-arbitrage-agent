# 21 — Rival Board Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Analyze competitors (products, sellers, prices, ranks, reviews, listings, keywords, ads) for opportunity and risk signals.

## 2. Entry points

- `/rivalboard` (overview), `/rivalboard/:competitorId`.

## 3. Main workspace

- **Competitors**: list of competitor products/sellers; posture class (undercutting/benign/high-demand).
- **Comparison**: side-by-side product comparison (price, rank, review, listing content, keyword overlap).
- **Signals**: price movements, rank/review trends, offer/seller changes, promotions, keyword overlap/gaps.
- **Alerts**: competitive threat alerts.

## 4. Data acquisition

- `competitor_observation` from market snapshots + keyword graph + (ads overlap where available — owner Q).
- Phase 0 finding: competitor data computed from static catalog/snapshots only; no competitor-ASIN ingestion pipeline → this is the gap the module fills via snapshot jobs.

## 5. Keyword overlap

- Reads shared keyword graph: overlap/gaps between own listings and competitor listings (shared SEO intelligence).

## 6. Actions

| Action | Gate |
|---|---|
| Add competitor | none |
| Compare | none |
| Refresh competitor data | explicit + budget |
| Set alert | none |
| Export comparison | none |

## 7. States

- Empty: "Add competitors to track".
- Partial: missing competitor fields → unknown.
- Stale: "as of <t>".
- Provider failure: banner + last data.

## 8. Responsive

Comparison → stacked on mobile.

## 9. Tour steps

1. Add a competitor.
2. Run a comparison.
3. Read keyword overlap.
4. Set a threat alert.

## 10. Events

Emits: `rival.observed`, `rival.alert.raised`. Consumes: `market.snapshot`, `keyword.observed`, `snapshot.recorded`.

## 11. Downstream

- Hub (competitive signals), RankLedger/Auctioneer (shared graph), notifications.
