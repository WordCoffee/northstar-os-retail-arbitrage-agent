# 00 — Owner Decisions (Approved for Phase 1)

**Date:** 2026-09-23
**Phase:** 1A — Architecture and Product-Experience Specification
**Status:** RECORD OF APPROVED DECISIONS — informs every downstream Phase 1A spec.

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / HISTORICALLY_RECORDED (H) / INFERRED (I) / UNKNOWN (K).

## 1. Canonical Product Identity (APPROVED)

- **`product_id`** — immutable internal UUID; the only durable database key for a product.
- **Unique Amazon identity** — `(marketplace_id, asin)`; ASIN alone is NEVER the global key (same ASIN may exist in different marketplaces).
- Normalize all identifiers (ASIN, UPC, EAN, GTIN, MPN) on capture; store raw + normalized forms.
- Multipacks, bundles, variations, and supplier pack sizes are NEVER collapsed into one ambiguous product row.

**Design consequence:** the current four-store divergence (products table, scanner caches, sourcescout manifest, GG reports — see Phase 0 `08`) resolves to a single canonical `catalog_product` table keyed by `product_id` with marketplace-scoped Amazon identity and a `pack_config`/`unit_normalization` model.

## 2. Operating Modes (APPROVED)

Three separate control dimensions — NOT one cosmetic toggle:

| Dimension | Values |
|---|---|
| ENVIRONMENT | `sandbox` \| `production` |
| ROLE | `customer` \| `operator` \| `admin` |
| VIEW CONTEXT | `normal` \| `audited_customer_preview` |

- Customer preview: preserves the operator's real identity; records target org+user context; persistent preview banner; blocks unauthorized production writes; logs entry/exit/actions; reauthorization for sensitive actions; never exposes secrets.
- **No unrestricted identity impersonation in Phase 1.**

## 3. Billing and Usage (APPROVED)

- **Append-only usage-event ledger.** Each metered event supports: `usage_event_id`, organization, user, service, workflow/run, provider, model/endpoint, input units, output units, provider-reported cost, estimated cost (when delayed), Northstar credits debited, event status, idempotency key, timestamp, reversal/adjustment reference, provenance, sandbox/production environment.
- **Credit→USD conversion is NOT finalized.** A configurable pricing-policy layer supports: provider cost, platform markup, minimum charge, included monthly credits, promotional credits, service-specific multipliers, free local execution, failed-run charging rules, refunds/reversals, provider-price versioning.
- **The ledger must NEVER derive consumption from a mutable balance field** — balance is always a derived projection over append-only entries.

## 4. Canonical Frontend (APPROVED)

- **The React/Vite application (`northstar-os-ui`) is the target public-facing product.**
- **FastAPI remains the API backend.**
- Analyst's Desk = labeled fixture/design reference until migrated.
- Single-file workbench = experimental/internal surface pending evidence.
- Legacy HTML = legacy (no Phase 0 evidence of active ownership).
- AutothinK UI = candidate for integration into the canonical React app.
- Migration is specified (Phase 1A `08`) but NOT performed.

## 5. Live-Write Boundaries (APPROVED)

- All consequential external writes remain disabled by default.
- Phase 1A may specify: draft creation, preview, validation, approval queues, permission checks, cost estimates, change diffs, idempotency, audit events, rollback strategy, provider capability checks.
- Amazon listing writes, Ads changes, social publishing, supplier actions, purchases → separate scoped permission.
- **Purchases remain manual.**
- **No normal GET/page load may trigger:** paid provider activity, external writes, background enrichment, or credit debits.

## 6. Non-negotiable data rules (APPROVED — carried into every spec)

1. Unknown remains null/unknown.
2. No invented prices, sales, seller counts, Buy Box, fees, rank, eligibility, supplier legitimacy, or invoice status.
3. Label data: live / cached / imported / benchmark / estimated / calculated / mocked / stale / unavailable.
4. Club-retail pricing is discovery data unless invoice/documentation suitability is established.
5. Not purchase-ready without confirmed sourcing + eligibility + economics + documentation.
6. ROI not decision-ready without identified cost and fee basis.
7. Standard UI loads = cache/database only.
8. Live refresh = explicit command with scope, budget, provider, audit trail.
9. Provider failures never silently substitute fabricated values.

## 7. Evidence for these decisions

- Owner directive (this Phase 1A prompt) — recorded as authoritative.
- Phase 0 findings these resolve: R1 (product identity), R15 (modes), R4 (billing), R20 (frontend), R6/R7 (live-write scope).
- No decision in this file was implemented; all are specifications for Phase 1B.
