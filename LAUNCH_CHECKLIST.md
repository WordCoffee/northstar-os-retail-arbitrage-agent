# LAUNCH CHECKLIST — Phase D5

**Date:** 2026-09-20 · **Baseline:** `41d765a` (D4 hardening complete) · Legend:
**PASS** = done & verified · **FAIL** = blocking/needs action · **N/A** = not
applicable at this stage · **D4/D5-reviewed** = confirmed in this pass.

| # | Item | Status | Justification |
|---|---|---|---|
| 1 | DNS / domain readiness | **N/A** | No production domain is provisioned; staging/alpha runs behind Cloudflare Access on the local/dev URL. A domain is needed only at the paid-launch gate (documented in `CLOUDFLARE_DEPLOY.md`, D6 follow-up DNS). |
| 2 | SSL/TLS | **PASS** | Cloudflare terminates TLS automatically on Pages/AnyCast IPs (free tier); local dev uses HTTP on 127.0.0.1. Verified pattern in `CLOUDFLARE_DEPLOY.md`. |
| 3 | Backup / rollback plan | **PASS** | Full git history is the code/DB-migration rollback (Phase D commits); `00_STATE.json` + `docs/BUILD_RECORD.md` track state; KV-backed output is regenerable from the pipeline. Rollback = `git checkout <phase-commit>` + re-run pipeline. |
| 4 | Monitoring / alerting hooks | **FAIL** | Health endpoints exist (`/health`, `/health/detailed`) and D3 smoke verifies liveness, but **no external uptime/alerting hook** is wired (UptimeRobot/PagerDuty class). Action before production flip: add one free-tier external probe + Cloudflare Access alerts. |
| 5 | Rate limiting on scraping modules | **PASS** | `RateLimitMiddleware` (30/60/120/300 per plan) + provider-side retry/backoff + Costco circuit-breaker/delays (`costco_live_runner`, env `COSTCO_CATALOG_REQUEST_DELAY_SECONDS`); harness-only disable env (`NORTHSTAR_DISABLE_RATE_LIMIT=1`) is not part of production posture. |
| 6 | Credit ledger reconciliation | **PASS** | `credit_ledger.py` (append-only, idempotent, no-negative fail-closed) + `test_credit_ledger.py`; period/month reading route `/api/v1/credits/me`; a billing-time reconciliation procedure is documented in `docs/contracts/CREDIT_LEDGER_v1.md` (production DB = Phase 5). |
| 7 | Legal disclaimer final review | **PASS** *(counsel pending)* | All B6 slots + workspace disclaimers verified present; `/legal/{terms,privacy,refund}` routes live; `[LEGAL REVIEW REQUIRED]` markers stand for counsel sign-off — **final legal review is the D6/deferred gate item** (not silently waived). |
| 8 | Admin access lockdown | **PASS** | Admin requires `admin` role (server `require_admin` + client role-gate), least-privilege field whitelist (`id/email/plan/created_at`), IDOR-safe (`/api/v1/admin/accounts/{id}` 404s unknown). Verified by `test_security_boundaries.py` + D3 smoke (403 anonymous). |
| 9 | `.env` / secrets hygiene | **PASS** | D1 audit: no secrets committed; `.env*` ignored; only `.env.example` placeholders. |
| 10 | Staging verified before prod | **PASS** | D3 local staging smoke 15/15; Cloudflare push ready (credential-gated, free tier). |
| 11 | Foundational cohort readiness (invite flow, support queue, billing-safe states) | **FAIL** | Not built (deferred): invite flow, support queue, and billing-safe states are Phase C/D deferred (see D6). Blocks **paid** go-live only; alpha invite cohort unaffected. |
| 12 | LLM/voice endpoints configured for prod | **FAIL** | Voice intentionally disabled (D4-F5) pending a production server; AutothinK needs an operator-approved inference endpoint at launch. |

**Go / no-go (for the operator):** **HOLD for production flip** — items 4, 11, 12
(monitoring probe, cohort ops, voice/LLM endpoint) plus legal counsel review are
required before paid production. **Alpha staging is ready** to proceed on the
current build.

**Checked and scored 2026-09-20 (D5). PASS 7 · FAIL 3 · N/A 1 (of 12 tracked).**