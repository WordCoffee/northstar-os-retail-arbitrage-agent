# NORTHSTAR OS — PLAN-TO-BUILD HANDOFF (Phase D6)

**Date:** 2026-09-20 · **Author:** Northstar Master Brain · **Purpose:** a future
session/developer can pick this project up with zero missing context.

---

## 1. Architecture decisions (Phases A–D, one page)

- **Engine & lanes:** Alpha build rides the OpenRouter DeepSeek dual-model plan
  (volume worker `deepseek/deepseek-v4-flash-0731` / relace·fp4; seam model
  `deepseek/deepseek-v4.1-flash` / deepinfra·fp8; D1–D6 locked in
  `~/.opencode/plan/northstar_alpha_build_blueprint.md`, mirror notes in
  `docs/PRODUCTION_BLUEPRINT.md` §16–19). Local Ollama qwen3 fleet remains the
  offline rollback baseline (§17.3).
- **Backend:** FastAPI app at `Northstar_backend/main.py` (port 8000) + a
  deterministic **bff/v1** response envelope everywhere (B1);
  `GET /api/golden-goose/*`, `/api/v1/credits/me`, `/legal/*` conform; legacy
  read endpoints (plans/suppliers/kirkland) still return plain dicts (debt).
- **Auth/tenancy/RBAC (B2):** single-tenant-per-account, JWT access tokens with
  `role/tenant_id/jti`, fail-closed helpers in `auth.py`/`auth_deps.py`
  (`require_role`, `require_admin`); demo fallback = foundation/member. Auth is
  stub/mock — real login/session store is post-alpha.
- **Credit ledger (B3):** `credit_ledger.py` — append-only, idempotent,
  no-negative fail-closed; per-plan allotments (0/100/500/2000) are
  **placeholders** (operator-held). No billing/Stripe.
- **Security boundaries (B4):** public vs auth vs plan vs admin tiers;
  no-leak deny-lists enforced at Functions (`_envelope.js`), backend envelope,
  and export manifest (`export_manifest.py`); admin = least-privilege whitelist.
- **Cloudflare deploy (B5):** Pages + Pages Functions only (no Workers compute);
  `functions/api/*` envelope-conformant; KV-backed; edge-gated by CF Access.
- **Disclaimers (B6):** slot registry in `docs/contracts/DISCLAIMER_EMBED_v1.md`;
  wired footers/auth/onboarding/workspaces + `/legal/*` routes serving the A6 drafts.
- **Golden Goose (B7/C5):** seam contract `docs/contracts/GOLDEN_GOOSE_SEAM_v1.md`;
  job model (opaque ids), entitlement mapping (`shared/gg-entitlements.json`,
  proposed), export manifests; **#49 dry-run**, **#23 scan manifest**,
  **#10 atomic save** implemented; `/scan` stays **403**.
- **Workspaces (C, SPA `static/index.html` behind `html[data-theme-v2]`):**
  Command Center, SourceScout, ListingForge, AdPilot V1, SocialPulse, AutothinK
  (approval states + read-only credit meter), Golden Goose, Commerce Ops,
  Creative Studio, Admin (role-gated), onboarding; all fixture/offline, no dead
  buttons, honest states; dev toggle `?v2=1` / `?dev=1`.
- **Test harness (A5):** `scripts/run_all_tests.ps1` — 5 suites
  (backend/GG/UI/shell/functions) + `tests/BASELINE.json` canary; 2 known
  pre-existing failures (protected-hash drift) are tracked, not fixed; harness
  sets `NORTHSTAR_DISABLE_RATE_LIMIT=1` (edge-limiter opt-out).

## 2. Open follow-ups / known limitations (deferred, flagged)

1. **Real Cloudflare staging push** — free tier, ready; needs operator CF/Wrangler auth (credential-gated). D3.
2. **LLM/voice endpoints for AutothinK** — voice disabled (D4-F5); inference endpoint operator-approval needed. D5 #12.
3. **Monitoring/alerting hook** (uptime probe) + **cohort ops** (invite flow, support queue) — D5 #4/#11.
4. **Legal counsel review** — all `[LEGAL REVIEW REQUIRED]` markers (arbitration, liability, breach-timeline, refund mechanics, scrape-path authorization), D5 #7.
5. **History rewrite decision** — old pipeline-output blobs (commit `009ac85`) still embed third-party URL tokens in HISTORY; F2 fixed forward (untracked/ignored), rewrite rejected as non-scoped/operator decision.
6. **Legacy-backend envelope adoption** — plans/suppliers/kirkland endpoints still plain dicts (Phase-C debt).
7. **Entitlements & credit allotments are proposed** — `shared/gg-entitlements.json` + `PLAN_CREDIT_ALLOTMENT` need operator sign-off.
8. **Real session store / plan persistence on users** — auth is stub; DB column + login UI post-alpha.
9. **test_single_match.py hygiene** — import-time env flip + top-level live code + async test; excluded from suites (B4 security item); fix deferred.
10. **FIXES_50 remaining** — items #22–#50 Phase 2/3 roadmap; alpha delivered Phase-1 subset (+ #49/#23/#10).

## 3. Spend & cost trajectory (durable record)

- **Current spend: $3.99 of $10** (OpenRouter dev fund, Tranche T1; operator
  reported). Trajectory: Phases A–C ran lean (volume-worker lane, pauses and
  reports on overrun per D6 funding rules); **Phase D ran at $0** (all offline
  audits, local staging, no external scans or paid hosting). Forward estimate
  to stay: remaining Phases B-deferred/C-deferred items are local; real
  Cloudflare staging push is free tier; paid items (large scans, hosted DB,
  external monitoring) are operator-gated and would be flagged before spend.
- **Guardrail respected:** every step in Phase D was offline/free-tier; nothing
  required a spend-stop.

## 4. Index of canonical docs

`docs/contracts/{BFF_CONTRACT,AUTH_RBAC,CREDIT_LEDGER,SECURITY_BOUNDARIES,GOLDEN_GOOSE_SEAM,DISCLAIMER_EMBED}_v1.md` ·
`docs/BUILD_RECORD.md` · `docs/legal/*` · `PIPELINE.md` · `OPERATIONS_RUNBOOK.md` ·
`NO_LEAK_AUDIT.md` (D1) · `PROMO_COMPLIANCE.md` (D2) · `STAGING_RELEASE_LOG.md`
(D3) · `LAUNCH_CHECKLIST.md` (D5) · `tests/BASELINE.json` (canary).