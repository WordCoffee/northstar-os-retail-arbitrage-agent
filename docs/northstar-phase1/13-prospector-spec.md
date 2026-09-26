# 13 — Prospector Specification

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I). Specification only.

## 1. Primary user job

Build and normalize a broad candidate universe from Amazon + wholesale/supplier sources, separate discoverability / eligibility / economics / documentation, and hand qualified candidates to Golden Goose.

## 2. Entry points

- `/prospector` (main workspace).
- Hub pipeline widget → `/prospector`.
- Deep link `/prospector/:productId` (product record).

## 3. Main workspace

- **Discovery tab**: broad catalog search (not Kirkland-only; Phase 0 gap), candidate imports, size/weight constraints, batch workflows, explicit refresh.
- **Normalization tab**: pack/variation/unit normalization review; ambiguous packs queued (never guessed).
- **Suppliers tab**: supplier options per product (list suppliers even when pricing is gated), supplier selection, average observed wholesale cost, invoice/documentation status per supplier.
- **Eligibility tab**: separate discoverability/eligibility/economics/documentation confidence.
- **Economics preview**: preliminary economics with identified cost+fee basis (never without basis).

## 4. Filters

Marketplace, category, brand, price range, size/weight, pack type, supplier, eligibility state, documentation state, cost basis, min profit/ROI, freshness.

## 5. Tables/cards

- Candidate table (dense, virtualized): product, ASIN, marketplace, pack, price, supplier count, best wholesale, net (basis-tagged), ROI, eligibility chips, doc status, freshness, provenance badge.
- Row actions: view record, normalize, match supplier, request refresh, send to Golden Goose, watch, pin.

## 6. Detail view (`/prospector/:productId`)

- Product identity (product_id, identifiers), variation family, pack config, unit normalization.
- Offer snapshots (price history), supplier offers, fees, demand/rank snapshots, eligibility snapshot.
- Documentation state per supplier (invoice verified/pending/unverified; retail receipt ≠ invoice).
- Evidence trail (provenance per field).

## 7. Actions

| Action | Gate |
|---|---|
| Search/discover | explicit refresh gate + budget |
| Import candidates | import job (no external write) |
| Normalize/confirm pack | user action |
| Match supplier | read (gated provider) |
| Request live refresh | explicit, budgeted, audited |
| Send qualified → Golden Goose | workflow (no external write) |
| Add to Watch | read-side |

## 8. Approval points

- Live refresh (budget approval if above default).
- Purchasing anything (manual, separate — never from Prospector).

## 9. States

- Empty: "No candidates yet — run your first discovery scan".
- Partial data: unknown shown as null/unknown (Phase 0 finding: 0.00 costs must become "unknown").
- Stale: amber "as of <t>" + explicit refresh.
- Provider failure: banner "provider failed at <t>; showing last cache" + retry (bounded).
- Permission denied: "requires <role>/plan".

## 10. Responsive

Table → cards on mobile; detail view stacks; filters drawer.

## 11. Tour steps

1. Run a discovery scan.
2. Review normalization queue.
3. Match a supplier.
4. Check documentation state.
5. Send a candidate to Golden Goose.

## 12. Events

Emits: `product.created`, `product.updated`, `identity.merged`, `supplier.ingested`, `supplier.offer.updated`, `snapshot.recorded`, `refresh_job.*`. Consumes: `provider.snapshot.ingested`, `provider.record.completed`.

## 13. Downstream

- Golden Goose (qualified candidates), The Watch (monitored candidates), OfferChisel (product record), Auctioneer (economics), Hub (pipeline widget).

## 14. Non-negotiable rules applied

- Unknown = null/unknown; no fabricated discovery data; club-retail pricing = discovery until invoice suitability; not purchase-ready without sourcing+eligibility+economics+documentation; ROI not decision-ready without cost+fee basis; explicit refresh only.
