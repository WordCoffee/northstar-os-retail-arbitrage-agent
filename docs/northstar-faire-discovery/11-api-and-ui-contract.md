# 11 — API and UI Contract

**Not implemented now** (frontend serve + foundation frontend mount are Phase 1C
1C-06; real auth is 1C-01). This document specifies the contract so the
implementation can proceed once gates clear, **without** creating a disconnected
product universe.

## Reuse (do NOT fork)

| Concern | Reuse |
|---|---|
| Org/membership/permissions | `foundation/context.py`, `foundation/permissions.py` |
| Product identity | `foundation/identity.py`, `foundation/models.py` |
| Provenance/freshness | `foundation/provenance.py` |
| Approvals | `foundation/approvals.py` |
| Audit | `foundation/audit.py` |
| Jobs/cost ceiling/idempotency | `foundation/jobs.py` |
| Providers/health | `foundation/providers.py` |
| Usage (shadow) | `foundation/usage.py` |
| Opportunities | Golden Goose opportunity model + Prospector + Watch |

## Proposed shared entities (map to foundation equivalents where present)

`discovery_sources`, `discovery_products`, `brand_channel_policies`,
`direct_supplier_candidates`, `supplier_product_offers`, `marketplace_matches`,
`pack_match_assessments`, `fee_estimates`, `economics_snapshots`,
`eligibility_checks`, `brand_risk_assessments`, `opportunity_assessments`,
`research_batches`.

Every record carries: org id, source, source record id, capture time, effective
time, provenance, confidence, staleness, created by, updated by, correlation/job id.

## Routes (namespaced under the foundation API)

- `GET  /api/v1/foundation/faire-discovery/brands` (read; no provider call)
- `GET  /api/v1/foundation/faire-discovery/products`
- `GET  /api/v1/foundation/faire-discovery/opportunities`
- `GET  /api/v1/foundation/faire-discovery/opportunities/{id}` (detail view)
- `POST /api/v1/foundation/faire-discovery/batches` (creates a research job request; **approval-gated**)

Hard rules: ordinary GET routes make **zero** provider calls; live research
requires an approved job + recorded run; no route lists, orders, contacts
suppliers or writes to any marketplace.

## UI

- Ranked table with the full column set (see spec RECOMMENDED OUTPUT TABLE); no
  absent data rendered as zero.
- Product detail view with the 20 required sections.
- No decorative rows/buttons: every control performs a real, audited action.
- Eligibility/authorization/economics states are first-class badges with evidence links.
