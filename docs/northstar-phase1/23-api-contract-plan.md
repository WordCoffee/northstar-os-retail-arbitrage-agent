# 23 — API Contract Plan

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Principles

- REST under `/api/v1/*`, versioned, JSON; `bff/v1` envelope retained for legacy compat during migration.
- Idempotency keys on all creation/write endpoints.
- Provenance metadata on data-bearing responses (`meta.provenance`, `meta.captured_at`, `meta.confidence`, `meta.verification_state`, `meta.staleness`).
- Errors: structured `{error:{code, message, details, request_id}}`; never leak secrets.
- Pagination: cursor-based for lists; sort/filter query params.
- No GET triggers provider activity/writes/enrichment/credit debits (owner rule).

## 2. Endpoint families (contract-level)

| Family | Base | Notes |
|---|---|---|
| Identity | `/api/v1/auth/*`, `/api/v1/orgs/*` | login/register/refresh/me; org CRUD |
| Catalog | `/api/v1/products/*`, `/api/v1/marketplaces` | canonical product identity |
| Suppliers | `/api/v1/suppliers/*` | supplier + products + offers + invoice status |
| Market | `/api/v1/products/{pid}/snapshots` | offer/seller/demand/rank snapshots |
| Economics | `/api/v1/products/{pid}/economics` | fee + economics snapshots |
| Opportunities | `/api/v1/opportunities/*` | assessments + scoring |
| Keywords | `/api/v1/keywords/*` | shared keyword graph |
| Listings | `/api/v1/listings/*` | drafts/versions/approval |
| Advertising | `/api/v1/advertising/*` | campaigns/performance |
| Social | `/api/v1/social/*` | content/calendar/assets |
| Monitoring | `/api/v1/monitoring/*` | watch configs/alerts |
| Rival | `/api/v1/rival/*` | competitors/observations |
| Brain | `/api/v1/brain/*` | runs/tools/artifacts/approvals |
| Providers | `/api/v1/providers/*` | registry/gates/budgets |
| Usage/Billing | `/api/v1/usage/*`, `/api/v1/billing/*` | events/invoices/pricing |
| Approvals | `/api/v1/approvals/*` | queues/grants |
| Audit | `/api/v1/audit/*` | unified log queries |
| Notifications | `/api/v1/notifications/*` | prefs/delivery |
| Help | `/api/v1/help/*` | tours/context |
| Legacy | `/api/kirkland/*`, `/api/sourcescout/*`, `/api/golden-goose/*`, `/api/autothink/*` | retained during migration; deprecated after |

## 3. Representative contract (product identity)

```
GET /api/v1/products/{product_id}
→ 200 { product: {
    product_id, marketplace: {id, name, domain}, asin,
    identifiers: [{kind, value, normalized, verification_state}],
    brand, canonical_title, pack_config, variation_family,
    sources: [{source, captured_at, confidence, raw_source_ref}],
    meta.provenance
  }}

POST /api/v1/products/{product_id}/refresh   // explicit live refresh
→ 202 { refresh_job: {id, status, budget, provider, estimated_cost} }
```

## 4. Write contracts (all approval-gated)

```
POST /api/v1/listings/{listing_id}/approve
→ 200 { approval_request: {id, diff, cost_estimate, requires: "operator"} }

POST /api/v1/listings/{listing_id}/publish   // external write
→ 202 { approval_request: {id, status:"awaiting_approval", ...} }
```

## 5. Auth contract

- `POST /api/v1/auth/login` → `{access_token, refresh_token, user, org, environment, view_context}`.
- Protected routes: `Authorization: Bearer <access>`.
- Preview context returned in `/me` when active: `{view_context:"audited_customer_preview", target_org, target_user}`.
- Environment in every response meta: `{environment:"sandbox|production"}`.

## 6. Contract testing

- OpenAPI schema + contract tests (pact-style or JSON schema validation) in Phase 1B; every endpoint has request/response schema fixtures.
