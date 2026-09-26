# Faire MODE 2 (Live) — Dependency Note
**Date:** 2026-09-24
**Status:** NOT authorized. MODE 2 remains a contract until all three gates below clear.

## Why MODE 2 is blocked
Live research requires authenticated, org-scoped, budgeted, auditable jobs.
Three Phase 1C gates are incomplete. Each is a hard dependency for Faire MODE 2;
none may be skipped.

## 1C-01 — Real authentication + org/role resolution
- **Required for:** every live Faire/Amazon read to be org-scoped and permission-checked; prevents cross-org leakage; enables audit attribution.
- **Status:** dev shim only (`foundation/authn.py` uses a documented dev context; real JWT org resolution not wired).
- **Remaining work (exact):**
  - `Northstar_backend/foundation/authn.py` — replace dev shim with real JWT verify (from existing `Northstar_backend/auth.py`), map claims → org/membership.
  - `Northstar_backend/foundation/api/deps.py` — resolve org context from verified identity for all foundation routes.
  - `Northstar_backend/foundation/context.py` / `foundation/permissions.py` — confirm role/permission evaluation against real membership.
  - Tests: `Northstar_backend/foundation/tests/test_auth_jwt.py`, `test_auth_org_scope.py`, `test_auth_hardening.py` must pass against real tokens.
  - Acceptance: 1C-01 closes the "real authentication" blocker; dev shim removed.
- **Docs:** `docs/northstar-phase1b/20-phase1c01-auth-completion.md`, `docs/northstar-phase1b/16-phase1c-recommendation.md`.

## 1C-03 — Canonical economics engine (not a worker; see correction)
- **Required for:** any economics that can feed QUALIFIED/PURCHASE_READY. The temporary adapter in `faire_research/economics.py` must be **deleted/replaced**.
- **Status:** NOT built. `faire_research/economics.py` is flagged TEMPORARY / NON-CANONICAL (header lines 1–5, closing line 22) for deletion/replacement at 1C-04.
- **Remaining work (exact):**
  - Build the canonical engine per `docs/northstar-phase1b/18-formula-inventory.md` (resolve R13/R14; golden-parameter tests).
  - Create `Northstar_backend/foundation/economics.py` (or the approved canonical module) with Decimal, fee-confidence states, landed cost, contribution profit, ROI, margin, downside.
  - Wire it into the research layer: `faire_research/` must import the canonical engine, not the temporary adapter.
  - Delete `Northstar_backend/faire_research/economics.py` and update `__init__.py` exports.
  - Acceptance: canonical economics has passed its acceptance gate; `FEE_UNKNOWN` cannot pass; no candidate reaches QUALIFIED/PURCHASE_READY without complete economics.
- **Docs:** `docs/northstar-phase1b/16-phase1c-recommendation.md` (1C-04), `docs/northstar-faire-discovery/07-fee-and-economics-contract.md`, `14-known-gaps.md`.

## 1C-04 — Job worker + Redis queue + scheduler
- **Required for:** controlled, budgeted, rate-limited live research jobs (MODE 2/4), idempotency, cost ceilings, cancellations, recorded runs. Without a worker, no approved live run can execute safely.
- **Status:** `foundation/jobs.py` defines the request/run state machine, idempotency, cost ceiling and cancellation **contracts only** — no worker loop, no Redis, no scheduler.
- **Remaining work (exact):**
  - `Northstar_backend/foundation/jobs.py` — extend with a worker execution loop + queue adapter.
  - Add `Northstar_backend/foundation/jobs_worker.py` (worker + scheduler entry point).
  - Queue transport (Redis) config; job budget/cost-ceiling enforcement at execution time.
  - Wire Faire MODE 2 as a job type: `faire_research/jobs.py` (job contract), enqueue path, recorded run manifest, provider budget ledger.
  - Tests: `Northstar_backend/foundation/tests/test_jobs.py` must pass with a real worker; add MODE-2 job tests.
  - Acceptance: a live research job runs under an approved envelope with budget, rate limit, cancellation, and full audit; zero provider calls without a job.
- **Docs:** `docs/northstar-phase1b/16-phase1c-recommendation.md` (1C-03 in that doc = worker), `docs/northstar-faire-discovery/10-research-batch-plan.md`.

## Ordering
1C-01 (auth) is the sole first blocker, then 1C-04 (worker), then 1C-03/1C-04
(economics, per the Phase 1C recommendation's amended ordering). MODE 2 must not
start until all three are complete **and** the operator approves a MODE 2 budget
and a named request count.

## Also still required for full MODE 2 (non-blocking-adjacent)
- Per-ASIN Amazon eligibility/gating source (`tasks/brand_blacklist_updater.check_brand_gating_sp_api` is a stub) — without it, eligibility stays `ELIGIBILITY_UNKNOWN` and MODE 2 findings cannot reach QUALIFIED.
- Amazon dimensions provider (none returns numeric L×W×H) and Faire packaged-weight source.

## Current posture
`faire_research/` and `docs/northstar-faire-discovery/` remain **untracked** (no commit, no push). 1C-07 (keyword module) is **not started**. No MODE 2 work has begun.