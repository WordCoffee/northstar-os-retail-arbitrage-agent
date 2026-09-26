# 15 — Open Questions (Owner Decisions)

Evidence states: these are product-intent questions; many cannot be answered from the repository. Grouped by severity/impact.

## Must answer before Phase 1 architecture (HIGH impact)

| # | Question | Why it matters | Evidence of ambiguity |
|---|---|---|---|
| Q1 | Which Amazon marketplaces are supported (US only today)? | drives marketplace dimension in product identity + fees | `DEFAULT_MARKETPLACE=https://www.amazon.com` (.env.example); fee rules US-only (`amazon_us_fee_rules_2026.py`) |
| Q2 | Is the canonical product identity `(marketplace, asin)`? Who owns refresh (scanner vs cache vs GG)? | R1 — the top data-integrity risk | `08` |
| Q3 | Billing model: credit↔USD conversion, meter→ledger wiring, overage rules | R4 — credits are display-only | main.py:1717; `MARGIN_SAFE_BUDGETS.md:80-83` (display meter) |
| Q4 | Which frontend is THE product, and where is it served? | R20 — four surfaces | `03` |
| Q5 | Live-write scope: Amazon listing, Ads, social publish, purchases — which are in-scope for production, with what approval gates? | R6/R7/R2; account safety | `06` (SP-API/Ads unwired), `12` |
| Q6 | Environment-mode model: sandbox / production / operator / customer-view / impersonation semantics | R15 | `12` (no mode architecture) |
| Q7 | Default opportunity formula and whether it should be shared | R13/R14 | three ACoS copies; two margin definitions |

## Medium impact (decisions during Phase 1)

| # | Question |
|---|---|
| Q8 | Supported social platforms and publish permissions (Meta/TikTok/IG today are placeholders). |
| Q9 | Supported supplier classes (Costco, Sam's, BJ's, distributors, Tundra) and their invoice/documentation requirements per class. |
| Q10 | Rank-data provider (DataForSEO does not return BSR; Unwrangle blocked; which provider becomes rank source?). |
| Q11 | Product-demand provider and confidence model. |
| Q12 | Required user roles (is `operator` distinct from `owner`; is `admin` org-scoped or platform-scoped?). |
| Q13 | Data retention rules for caches, snapshots, audit logs, and per-account data. |
| Q14 | Organization/team model: single-tenant vs multi-tenant; white-label requirements. |
| Q15 | Keyword/SEO provider (who feeds keyword_performance — Ads API, DataForSEO, or manual?). |
| Q16 | Golden Goose live scan budget envelope + two-gate enforcement policy. |

## Low impact / nice-to-have (can be deferred)

| # | Question |
|---|---|
| Q17 | Tour/help system scope (all services? per-role?). |
| Q18 | Developer API / webhook surface. |
| Q19 | n8n integration (docker-compose includes n8n :5678; blueprint references it). |
| Q20 | Embeddings/vector store for memory (planned, not built). |
| Q21 | Media/image generation provider (ComfyUI/HF/CF — standalone tool only). |

## Constraints this audit did NOT change

- No fabricated data; unknown stays null/unknown.
- Retail receipts are not wholesale invoices.
- Live enrichment stays scoped, logged, budgeted, controllable.
- No silent paid activity from GET routes.
- Amazon account safety + invoice legitimacy outrank short-term opportunity.
