# 27 — Open Owner Decisions

Evidence states: UNKNOWN (K) — product intent; cannot be answered from the repository. Carried forward from Phase 0 `15` and this Phase 1A specification. Grouped by severity/impact.

## Required before Phase 1B foundation completes (HIGH impact)

| ID | Decision | Why it blocks | Where it lands |
|---|---|---|---|
| Q1 | Amazon marketplaces supported (US only vs others) | marketplace dimension in product identity + fees | `03` |
| Q2 | Canonical product identity master-key + refresh ownership confirmed | canonical data model | `02`, `03` |
| Q3 | Credit→USD conversion rules + meter→ledger wiring + overage | billing/usage ledger | `07` |
| Q4 | (recorded) Canonical frontend = React app served by FastAPI — confirm serve mechanism (static mount vs CDN) | frontend deploy | `08` |
| Q5 | Live-write scope: which of Amazon listing / Ads / social / purchases are in-scope for production, with which gates | approval flows | `15`,`17`,`16` |
| Q6 | Environment-mode model incl. customer-preview vs impersonation scope (confirm no impersonation) | modes | `05` |
| Q7 | Default opportunity formula + single ACoS/margin definitions confirmed | economics | `14`,`17` |
| Q10 | Rank-data provider (DataForSEO doesn't return BSR; Unwrangle blocked) | RankLedger + Watch | `20` |
| Q11 | Product-demand provider + confidence model | demand snapshots | `13`,`19` |
| Q12 | Required user roles (is `operator` distinct from `owner`; is `admin` org-scoped or platform) | RBAC | `05` |
| Q15 | Keyword/SEO provider (Ads API / DataForSEO / manual) | shared keyword graph | `20`,`15`,`17` |

## Medium impact (Phase 1B/2)

| ID | Decision |
|---|---|
| Q8 | Social platforms + publish permissions |
| Q9 | Supplier classes + per-class invoice/documentation requirements (Costco/Sam's/BJ's/distributors/Tundra) |
| Q13 | Data retention rules (caches, snapshots, audit, per-account) |
| Q14 | Organization/team model: single vs multi-tenant; white-label requirements |
| Q16 | Golden Goose live scan budget envelope + two-gate enforcement policy |
| Q17 | Tour/help system scope (all services? per-role?) |
| Q18 | Developer API / webhook surface |
| Q19 | n8n integration (docker-compose has n8n; blueprint references) |
| Q20 | Embeddings/vector store for memory |
| Q21 | Media/image generation provider |

## Decisions explicitly NOT required (resolved by owner in Phase 1A)

- Canonical product identity shape (`00` §1) — APPROVED.
- Operating modes (`00` §2) — APPROVED (no impersonation).
- Billing/usage ledger principles (`00` §3) — APPROVED (conversion open).
- Canonical frontend (`00` §4) — APPROVED.
- Live-write boundaries (`00` §5) — APPROVED (writes disabled by default; purchases manual).
