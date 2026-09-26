# 14 — Phase 1D Recommendations

Based on the 1C autonomous sprint (1C-03 passed; 1C-04/05/06 not started).

## Immediate (finish 1C locally)

1. **1C-04 durable worker + scheduler**
   - PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` claiming; short claim transaction; no
     transaction held during provider execution.
   - Lease/heartbeat/crash-recovery; bounded retries with exponential backoff + jitter;
     dead-letter; cancellation; graceful shutdown.
   - Re-checks before execution: authorization, membership, approval, provider enablement,
     budget.
   - Scheduler: org-scoped, disabled for provider-backed jobs, no catch-up storm, no
     duplicate firing, no GET-triggered scheduling.
   - Deterministic fake providers (success/timeout/transient/permanent/rate-limit/garbage/
     high-cost/disabled/cancel/slow/duplicate).
   - **Parallel race tests** against disposable PostgreSQL (reprovision via the 1C-02B
     recipe): multi-worker single-job claim, crash/lease recovery, duplicate idempotency,
     concurrent scheduler ticks, concurrent approval changes, concurrent cancellation,
     concurrent budget reservation, membership-revocation-during-wait, org-suspension-during-wait.

2. **1C-05 keyword/SEO intelligence**
   - Distinct Keyword vs Search-term entities; deterministic normalization; provenance,
     freshness, confidence.
   - Idempotent, hashed, dry-run imports of existing advertising exports (read-only source).
   - Org-scoped read APIs; large imports via jobs; GET read-only; cross-org denied.
   - Service contracts (OfferChisel/Auctioneer/RankLedger/Town Crier/AutothinK).

3. **1C-06 canonical frontend serving**
   - Confirm React/Vite as canonical; Analyst's Desk → demo/legacy (no delete without
     migration record).
   - Real JWT auth transport (no token in URL; expiry/revocation/cross-tab logout; 401/403/
     suspended/offline states).
   - Shell: org selector, env badge, preview banner (audited), collapsible/hideable
     preference-backed Pinned drawer, command palette, tours, error/loading boundaries.
   - Account sections production-shaped; truthful "not connected" states.
   - Operations Hub + Ledger truthful (fix duplicate balance/available).
   - Accessibility (WCAG 2.2 AA target) + security checks (CSP/CORS/redirects/no secrets in
     bundle/no provider-on-load/no job-on-load).

4. **Rewire remaining economics consumers** to `foundation/economics` (fee_engine,
   fee_calculator, pricing, finance, unit_economics, enricher, product_analysis,
   scanner_data, ad_pilot, word_coffee, GG breakdown/scorer, frontend calculators).

## Then (staging, needs owner infra)

5. **1C-02C/D/E** — staged apply on a designated staging PostgreSQL with backup/restore
   verification and explicit authorization (`postgres-staging-readiness.json`).

## Phase 1D (beyond local)

- Real integration sandboxes (Amazon SP-API/Ads/social/suppliers) under named approval.
- Deployment validation, operational monitoring, incident/rollback exercise.
- Owner go-live approval.

## Hard boundaries unchanged

No staging/production writes, no live provider execution, no marketplace writes without
explicit scoped authorization.