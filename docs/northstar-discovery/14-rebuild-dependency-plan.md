# 14 — Rebuild Dependency Plan

Dependency-first plan for taking NorthstarOS to a production-ready SaaS platform. **This is planning only — nothing here is implemented in Phase 0.**

## Phase FOUNDATION

| Track | Deliverables | Dependencies | Acceptance criteria | Must not start before | Parallelizable |
|---|---|---|---|---|---|
| Identity, org, roles, modes | Organizations + tenants, member/operator/owner/admin, customer-view/impersonation system (see `12`§9) | none | login/register, RBAC enforced on all routes, preview sessions audited, no prod writes in preview | — | with Data model? No (data first) |
| Canonical data model | Single `(marketplace, asin)` product record; suppliers, keywords, campaigns unified | Org/identity | no duplicate ASIN across services; reconciliation job | Identity | with Provider registry |
| Event + audit architecture | Event bus + unified audit (merge 3 channels) | Data model | every write audited | Data model | with Provider registry |
| Provider registry | One registry of providers, gates, budgets, fallbacks, status | — | per-provider enable/disable, budget caps, no silent calls | — | YES |
| Data provenance | Field-level provenance everywhere; null-not-zero | Data model | UI labels live/cached/computed/unknown | Data model | YES |
| Credits + billing | Meter→ledger wiring, conversion rules, invoices | Identity | consumption debits ledger; invoices queryable | Identity | no |
| Error handling/observability | Structured logs, error-rate alerting (exists: error_alerts.py), metrics | — | alerts surfaced in UI | — | YES |
| Design system | One design system (adopt SIGNAL or Analyst's Desk) | — | tokens in one place, drift-guarded | — | YES |
| Tour/help infrastructure | Per-service tours, skip/don't-show, replay, analytics | Identity (per-user state) | completion persisted per user | Identity | YES |

## Phase INTELLIGENCE

| Track | Deliverables | Dependencies | Acceptance | Must not start before | Parallelizable |
|---|---|---|---|---|---|
| Master Brain orchestration | Gateway + learning + memory fully wired to services | Data model | services read/write shared stores | Foundation | with Services |
| Product graph | Canonical product entity + reconciliation | Data model | 4 stores reconciled via job | Foundation | with Supplier graph |
| Supplier graph | Suppliers + invoice/documentation status per supplier class | Data model | retail-receipt≠invoice enforced | Foundation | YES |
| Keyword/SEO graph | keywords/keyword_performance wired to consumers (AdPilot, OfferChisel, RankLedger) | Data model | live keyword pull + read | Foundation | YES |
| Brand voice | Single brand-voice store (dedupe memory_entries/docs/fixtures) | Identity | one store, all services consume | Foundation | YES |
| Recommendation engine | Shared opportunity/portfolio recommendations | Product graph | persisted, not recomputed ad hoc | Product graph | no |
| Monitoring/alerting | Scheduler + capture loop for Watch/Rank/Rival + thresholds + alerts | Data model, provider registry | automatic snapshots, alerts | Foundation | YES |

## Phase SERVICES (per service: backend + UI wiring)

| Service | Depends on | Key acceptance |
|---|---|---|
| Prospector | Product graph, supplier graph, provider registry | broad search; supplier choice; unknown≠0 |
| Golden Goose | Prospector feed, product graph, monitoring | reads qualified candidates from shared store; two-gate live |
| OfferChisel | Product graph, keyword graph, brand voice | resolve product before generate; shared SEO intel |
| Auctioneer | Keyword graph, product economics, Ads API (if approved) | single ACoS formula; campaign CRUD gated |
| Town Crier | Brand voice, provider registry (social) | draft/review/approve/publish gated |
| The Watch / RankLedger / Rival Board | Monitoring, product graph | real tracked data + alerting |
| AutothinK | Master Brain, provider registry | agentic workbench (tools, artifacts, checkpoints) |
| Operations Hub + Ledger | all services, billing | aggregation endpoint; drill-down |

## Phase RELEASE

| Track | Deliverables | Depends on |
|---|---|---|
| Testing | SPA test framework, e2e, a11y, data-quality, formula tests | Services |
| Migration | Postgres apply (staging), schema consolidation | Data model |
| Sandbox validation | Mock/sandbox runs of every service | Services |
| Controlled live reads | Level-3 reads with budget caps | Provider registry, approvals |
| Controlled live writes | Level-4 writes with previews | Controls, audit |
| Production rollout | Cloudflare/backend deploy, env modes | Release |
| Rollback + monitoring | Rollback drill executed; alerts live | Release |

## Explicit sequencing rules

- **Identity/modes before any customer view** (no visual toggle as authorization).
- **Data model before services** (avoids building on 4 stores).
- **Provider registry before live reads** (no silent paid activity).
- **Keyword graph before AdPilot/OfferChisel/RankLedger** (they are currently schema-only).
- **Do not start live writes until Level-3 reads are proven within budget.**
- **Do not start Ads/SP-API/impersonation until owner decisions in `15`.**

## Owner decisions gating Phase 1 (top 5)

1. Product identity master key + refresh ownership (R1).
2. Environment-mode model incl. customer-view/impersonation (R15).
3. Billing: credit→USD conversion + meter wiring (R4).
4. Frontend surface target + serve path (R20).
5. Live-write scope (Amazon listing/ads/social/purchase) and their gates (R6/R7/R2).
