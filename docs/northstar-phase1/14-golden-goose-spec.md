# 14 — Golden Goose Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Validate and rank opportunities from Prospector/The Watch into an explainable, decision-ready workspace.

## 2. Entry points

- `/goldengoose` (main workspace).
- From Prospector "Send to Golden Goose".
- Deep link `/goldengoose/:opportunityId` (full opportunity record).

## 3. Handoff from Prospector (specified)

- Qualified candidates arrive as `opportunity_assessment` rows (provenance: source candidate + scored_at + basis).
- Golden Goose consumes the canonical product record (same product_id) — never a parallel universe (Phase 0 R19).
- Assessment records WHY it qualified: filters passed + score components + confidence + data gaps.

## 4. Main workspace

- Ranked list: product thumbnail, name, ASIN, pack, economics (net/ROI with basis), demand, competition, score (explainable), risk, confidence, doc status.
- Filters: tier (high/med/low), score, economics, competition, supplier, doc status, watch state, assigned.
- Sortable, virtualized; pin/compare/watch/assign/dismiss/notes.

## 5. Full opportunity record (`/goldengoose/:opportunityId`)

| Section | Content |
|---|---|
| Overview | thumbnail, identity, pack, confidence, score + explanation |
| Economics | cost basis, fee snapshot, net, ROI, margin (single canonical defs), break-even |
| Demand | demand snapshot, BSR/rank source + confidence |
| Competition | seller count, buy box, offer observations |
| Suppliers | supplier options, avg wholesale, selected supplier, pricing gate state |
| Documentation | invoice status per supplier (retail receipt ≠ invoice) |
| Risk | flagged risks (price war, crowding, size, rating) |
| History | snapshot history |
| Evidence | provenance per field |

## 6. Actions

| Action | Behavior |
|---|---|
| Compare | side-by-side 2–4 opportunities |
| Watch | adds to Watch config |
| Assign | assign to team member |
| Dismiss | mark dismissed with reason |
| Notes | per-opportunity notes (audited) |
| Approve | creates approval_request (only where a downstream write requires it) |
| Pin | pin to drawer |
| Re-scan economics | explicit recompute job (uses latest snapshots + basis) |

## 7. Score explainability (mandatory)

- A ranked score NEVER disguises missing critical data (owner rule). Score panel shows: component scores, which inputs were missing/unknown, and a "not decision-ready" marker when economics/documentation basis is absent.
- Reuse Phase 0 `opportunity_scorer` weighted composite as the base, but surface data gaps explicitly.

## 8. States

- Empty: "No opportunities yet — send candidates from Prospector".
- Partial/unknown: components marked unknown; score shown with confidence + gap list.
- Stale: amber "economics as of <t>".
- Provider failure: banner + last-cache; never fabricate.
- Permission denied: requires operator/owner for assignments/approvals.

## 9. Responsive

- Desktop: list + detail split; Mobile: list → detail stack; compare as horizontal scroll or drawer.

## 10. Tour steps

1. Open a ranked opportunity.
2. Read the score explanation + data gaps.
3. Compare two opportunities.
4. Send to Watch / assign / dismiss.
5. Check documentation state before any approval.

## 11. Events

Emits: `opportunity.assessed`, `opportunity.approved`, `opportunity.dismissed`, `opportunity.assigned`. Consumes: `product.created`, `economics.computed`, `market.snapshot`, `supplier.offer.updated`, `snapshot.recorded`.

## 12. Downstream

- The Watch (watch actions), Auctioneer (economics), OfferChisel (listing), Hub (pipeline widget), approvals module.
