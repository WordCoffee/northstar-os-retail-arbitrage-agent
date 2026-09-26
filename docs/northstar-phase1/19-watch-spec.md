# 19 — The Watch Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Monitor products and listings for price, rank, seller, availability, and listing-health changes — with thresholds and alerts.

## 2. Entry points

- `/thewatch` (overview), `/thewatch/:productId` (product monitoring).

## 3. Main workspace

- **Watchlist**: products under watch; last signal; threshold status; alert count.
- **Signal feed**: recent changes (price/rank/seller/availability/listing/review).
- **Thresholds**: per-product config (price change %, rank drop, seller surge, availability).
- **Alert delivery**: in-app + notification channel (per preference).

## 4. Data acquisition

- Snapshot capture jobs (scheduler) populate `rank_snapshot`, `amazon_offer_snapshot`, `seller_offer_snapshot` — resolves Phase 0 R3 (no capture loop).
- Change detection computes diffs between consecutive snapshots.
- Sources: gated provider reads; standard UI load never triggers a capture (owner rule).

## 5. Detail view (`/thewatch/:productId`)

- Price history chart, rank history, seller count history, availability timeline, listing-health issues, review/rating movement, opportunity elevation (feeds Prospector/GG).

## 6. Actions

| Action | Gate |
|---|---|
| Add to Watch | none (config) |
| Configure thresholds | none |
| Request snapshot refresh | explicit + budget + audit |
| Promote to Prospector/GG | workflow |
| Acknowledge alert | none |

## 7. States

- Empty: "Add products to watch".
- No data yet: "waiting for first snapshot"; never fabricated history.
- Stale: "last snapshot <t>".
- Provider failure: "capture failed at <t>; showing last snapshot" + retry (bounded).

## 8. Responsive

Watchlist → cards on mobile; charts scale down.

## 9. Tour steps

1. Add a product to Watch.
2. Set a threshold.
3. Review a signal.
4. Acknowledge an alert.

## 10. Events

Emits: `alert.raised`, `watch.triggered`, `snapshot.recorded`, `signal.changed`. Consumes: `product.created`, `snapshot.recorded`.

## 11. Downstream

- Hub (monitoring alerts), Prospector/GG (elevation), notifications.
