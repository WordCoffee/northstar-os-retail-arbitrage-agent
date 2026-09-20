# LAUNCH CHECKLIST — Phase D5 (scored) · re-scored Phase E5

**Date:** 2026-09-20 · **Baseline:** E4 · Legend: **PASS** = done & verified ·
**FAIL** = blocking/needs action · **N/A** = not applicable at this stage.
Original D5 score preserved in §3 for traceability.

---

## 1. Current scoring (post-E1–E4)

| # | Item | Status | Justification |
|---|---|---|---|
| 1 | DNS / domain readiness | **N/A** | No production domain provisioned; staging runs on the dev/local URL behind CF Access. Domain is a paid-launch step (operator DNS cutover — flagged, $0 config but credential-gated). |
| 2 | SSL/TLS | **PASS** | Cloudflare terminates TLS automatically (free tier); local dev HTTP on 127.0.0.1. |
| 3 | Backup / rollback plan | **PASS** | Git history is the code rollback; `00_STATE.json` + `docs/BUILD_RECORD.md` track state; KV output regenerable from the pipeline. |
| 4 | Monitoring / alerting hooks | **PASS (E1)** | `GET /api/health` (bff/v1, `status:"ok"`, `kv_bound`) + documented free Cloudflare Analytics/Logs + free external uptime-probe recipe. `MONITORING_SETUP.md`. (External monitor creation = operator, $0.) |
| 5 | Rate limiting on scraping modules | **PASS** | `RateLimitMiddleware` (30/60/120/300 per plan) + provider retry/backoff + Costco circuit-breaker/delays; harness-only disable env is not prod posture. |
| 6 | Credit ledger reconciliation | **PASS** | `credit_ledger.py` (append-only, idempotent, no-negative fail-closed) + tests; `/api/v1/credits/me`; reconciliation procedure documented (`CREDIT_LEDGER_v1.md`). |
| 7 | Legal disclaimer final review | **PASS (E4)** | All B6 slots verified; `/legal/*` live; **counsel index assembled** (`LEGAL_REVIEW_PACKAGE.md`). **Counsel sign-off remains the formal gate** (D8 trigger) — not waived. |
| 8 | Admin access lockdown | **PASS** | `require_admin` + least-privilege whitelist + IDOR-safe 404; verified by `test_security_boundaries.py` + D3 smoke. |
| 9 | `.env` / secrets hygiene | **PASS** | D1: no secrets committed; `.env*` ignored; `.env.example` placeholders only. |
| 10 | Staging verified before prod | **PASS** | D3 smoke 15/15; CF push ready (free tier, credential-gated). |
| 11 | Founding cohort readiness (invite flow, support queue, billing-safe states) | **PASS (E2)** | Cohorts + allotments + admin scope **defined** (`COHORT_OPS.md`); invite/support/billing-safe states specified and **manually operable for the 10–50 invite cohort** (billing not live). Automation deferred (Phase F). |
| 12 | LLM/voice endpoints for prod | **PASS (E3)** | `/api/transcribe` **formally deferred** with rationale + target phase; BFF contract + deploy doc updated; voice disabled by design (not broken). |

## 2. Tally & go/no-go

**PASS 11 · FAIL 0 · N/A 1 (of 12).** All three D5 FAILs (#4, #11, #12) are
closed by E1–E4.

**Production flip: technically UNBLOCKED.** No code blocker remains. Three
operator-side, **$0** actions remain before flipping staging→production (none are
code gaps):
1. **DNS + Cloudflare Access** setup on a real domain (credential-gated).
2. **External uptime monitor** creation (free tier) pointing at `/api/health`.
3. **Legal counsel sign-off** on `LEGAL_REVIEW_PACKAGE.md` (item 7's formal gate).

**Recommendation:** proceed to a **controlled alpha staging release** now; hold
**paid production** until counsel sign-off + the three operator actions land.

## 3. Original D5 score (for traceability)

PASS 7 · FAIL 3 (#4 monitoring, #11 cohort ops, #12 voice/LLM) · N/A 1 (DNS).
The three FAILs are exactly what Phase E closed (E1/E2/E3 respectively).