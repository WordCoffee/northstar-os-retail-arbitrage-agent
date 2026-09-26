# 26 — Phase 1B Implementation Backlog

Evidence states: INFERRED (I) from this Phase 1A specification. Dependency-ordered. No calendar estimates (owner instruction).

**Priorities:** P0 = required before meaningful service UI; P1 = first controlled customer workflows; P2 = expanded capability; P3 = later optimization.

Complexity: S/M/L/XL. `provider` = provider access required. `owner` = owner approval required.

## P0 — Foundation

| ID | Module | User value | Scope | Depends | Acceptance | Tests | Security | Migration impact | Size | Provider | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P0-01 | identity | Log in/register; org context | auth v2 (orgs/users/memberships/sessions/invites); JWT rotation; MFA-ready | — | login/register/me; roles enforced | unit+integration | JWT, bcrypt, session revocation | none | L | no | no |
| P0-02 | modes | Sandbox/production separation | environment context middleware; preview context (banner/guards/reauthorization/audit) | P0-01 | sandbox/prod/preview guards pass | security tests | no prod writes in preview; no impersonation | none | L | no | yes (Q6) |
| P0-03 | catalog | Canonical product identity | marketplace, catalog_product, identifiers, variation, pack_config, unit_normalization + migration M1-M5 (dry-run + promote) | P0-01 | four stores → one product_id; reconciliation report | data-quality + unit | provenance; null-not-zero | **primary** | XL | no | yes (Q1/Q2) |
| P0-04 | provider registry | gates/budgets/fallbacks/status | provider_registry tables + gate middleware + budget checks + usage_event emission | P0-01 | per-provider enable/disable; no GET triggers provider | integration | budget caps; no silent calls | read-side | L | no | no |
| P0-05 | usage ledger | real metered credits | usage_event append-only + pricing_policy + derived balance + ledger debits (idempotent) | P0-01, P0-04 | every call/job → usage_event; balance derived | unit+integration | idempotency; no mutable balance | none | L | no | yes (Q3) |
| P0-06 | audit | unified audit | audit_event subscriber on all events; audit queries | P0-01 | every write audited | integration | retention policy | none | M | no | no |
| P0-07 | design system | coherent professional UI | tokens, type, spacing, components, state patterns (per `09`) | — | token/drift guard; a11y baseline | visual + a11y | — | none | L | no | no |
| P0-08 | frontend shell | canonical app served | React shell + routing + API client + env/flags + error/loading boundaries | P0-01, P0-07 | serves via FastAPI; guards per route | component | token storage; no secrets in browser | none | L | no | no |
| P0-09 | job runner | async jobs exist | worker + queue + refresh_job + dead-letter + circuit breaker | P0-04 | jobs run, retries bounded, DLQ | integration | bounded retries | read-side | M | no | no |
| P0-10 | help/tours | onboarding | tour_completion, help API, tour driver | P0-01, P0-08 | per-service tours + skip/don't-show | component | per-user state | none | M | no | no |

## P1 — First controlled customer workflows

| ID | Module | User value | Scope | Depends | Acceptance | Tests | Security | Migration impact | Size | Provider | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1-01 | catalog+market | Prospector read path | scanner pipeline reads canonical DB; snapshot jobs; provenance UI | P0-03, P0-09 | Prospector shows canonical products with provenance | integration | null-not-zero | read-side | XL | yes (gated) | no |
| P1-02 | economics | correct single formula set | fee/economics snapshots; single margin/ROI/ACoS modules | P0-03 | formulas golden-tested; no duplication | formula tests | basis required | none | M | no | no |
| P1-03 | opportunity | Golden Goose ranked | opportunity_assessment + explainable scoring + UI | P1-01, P1-02 | explainable scores; gaps surfaced | unit+component | no fake data | read-side | L | no | no |
| P1-04 | keyword | shared SEO graph | keyword + observations + associations; single universe | P0-03 | services share keyword graph | integration | provenance | read-side | L | yes (gated) | yes (Q15) |
| P1-05 | ai_orchestration | real agentic AutothinK | brain_run + tools + artifacts + approvals + cost | P0-05, P0-09, P0-03 | agentic run with checkpoints | integration | approval gates | none | XL | yes (cloud gated) | yes (Q12) |
| P1-06 | listing | OfferChisel draft flow | draft/version/approve; generation via brain; publish = approval | P1-02, P1-04, P1-05 | draft → approve flow | integration | publish gated | none | L | local OK | no |
| P1-07 | account | Account + connections + brand voice | account sections; connection store; single brand voice | P0-01, P0-07 | sections work; no secrets in browser | component+integration | no client secrets | none | L | no | no |
| P1-08 | hub | command center | widget read-model + drill-down + approval queue | P1-01..P1-07 | widgets live; drill-down works | component | role-scoped | read-side | L | no | no |
| P1-09 | ledger | real usage display | ledger UI from usage projection | P0-05 | balance/usage/invoice views | component | — | none | M | no | no |

## P2 — Expanded capability

| ID | Module | User value | Scope | Depends | Acceptance | Size | Provider | Owner |
|---|---|---|---|---|---|---|---|---|
| P2-01 | monitoring | The Watch live | watch_config + snapshot diff + alerts | P1-01, P0-09 | thresholds + alerts | L | yes | no |
| P2-02 | rankledger | RankLedger | keyword rank tracking UI | P1-04, P2-01 | rank history + groups + annotations | L | yes (Q10) | yes |
| P2-03 | rival | Rival Board | competitor entities + comparisons | P1-04, P2-01 | side-by-side + overlap | L | yes | no |
| P2-04 | advertising | Auctioneer analysis | campaign read + recommendations + single ACoS | P1-02, P1-04 | recommendations w/ impact | L | yes | yes (Q5) |
| P2-05 | social | Town Crier full | studio + calendar + assets; publish gated | P1-06, P1-04 | draft→approve→schedule | L | yes (media) | yes (Q8) |
| P2-06 | supplier | supplier flows | supplier ingest + invoice status + supplier UI | P0-03, P1-01 | invoice status per supplier | L | yes | yes (Q9) |

## P3 — Later optimization

| ID | Module | User value | Scope | Depends | Size | Provider | Owner |
|---|---|---|---|---|---|---|---|
| P3-01 | brain | scheduled recurring runs | scheduler + recurring brain runs | P1-05 | M | no | no |
| P3-02 | media | image/video gen | media providers wired | P2-05 | L | yes | yes (Q21) |
| P3-03 | notifications | richer delivery | email/webhook/in-app channels | P2-* | M | no | no |
| P3-04 | embeddings | memory retrieval | local embeddings for memory | P1-05 | L | no | no |
| P3-05 | api | developer API/webhooks | public API keys + webhooks | P1-* | L | no | yes (Q18) |
| P3-06 | perf | scale reads | read models, caching, virtualized tables | P2-* | XL | no | no |

## Dependencies summary

- Everything depends on P0-01 (identity) + P0-07 (design) + P0-08 (shell).
- Canonical data (P0-03) gates P1 service reads.
- Usage ledger (P0-05) gates brain cost + ledger UI.
- Provider registry (P0-04) gates every live integration.
- No live writes before Level-3 reads proven within budget (owner rule).

## Rules

- No calendar estimates (owner instruction).
- No provider call, DB migration, policy change, or production write is performed in Phase 1B without the explicit approvals listed under `owner`.
