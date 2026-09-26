# 09 — AGENTS / Policy Audit

Evidence states: STATICALLY_CONFIRMED (S) unless noted. **The proposed L0–L5 policy lives only in `16-proposed-agents-md.md` as a draft — it is NOT installed and NOT active.**

## 1. Instruction/policy file inventory

| File | Scope | Status this audit |
|---|---|---|
| `AGENTS.md` (root) | Session capsule | Active (unchanged) |
| `docs/OPERATING_CONSTITUTION.md` | Full law (§0–§10) | Active (unchanged) |
| `docs/PRODUCTION_BLUEPRINT.md` | Build spec + launch boundary + security/admin boundary | Reference |
| `docs/PRIVATE_ALPHA_DEPLOY.md` | Deploy intent | Reference |
| `docs/MARGIN_SAFE_BUDGETS.md` | Economics/caps invariants | Reference (test-enforced) |
| `docs/UI_SUITe_PLAN.md`, `docs/API_REFERENCE.md`, `docs/DATA_STREAMS.md`, `docs/PHASE_B_SECURITY_ITEMS.md` | Plans/specs | Reference |
| `master-brain/README.md`, `northstar-os-master-plan.md`, `service-plans/00-05` | Platform brain specs | Reference |
| `shared/master-brain/constitution.json` | Machine rules | Reference (no runtime loader) |
| `shared/master-brain/standing-approvals.json` | §3.6 approval registry | Active (1 live entry) |
| `shared/master-brain/audit.log.jsonl` | Audit trail | Active (append-only) |
| `PROD_POSTURE.md` (root) | Rate-limiter production guard | Active (enforced) |
| `PROMO_COMPLIANCE.md` (root) | ToS posture audit | Reference (2 review flags) |
| `ROLLBACK_DRILL.md` | Rollback guarantee | Reference |
| `MIGRATION_GUIDE.md` | Postgres migration | Gated (NOT APPLIED) |
| `COHORT_OPS.md` | Cohort model | Definitions (deferred dev) |
| `NO_LEAK_AUDIT.md` | Secret hygiene | Reference |
| `MONITORING_SETUP.md`, `LAUNCH_CHECKLIST.md`, `LEGAL_REVIEW_PACKAGE.md` | Ops/launch | Reference |

## 2. Per-rule classification (root AGENTS.md)

| Rule (AGENTS.md) | Classification | Effect | Recommendation |
|---|---|---|---|
| Autonomous zone: build & run product end-to-end; product's own outbound calls are normal operation (L11-12) | Production-only control | Permits live product ops | Keep |
| Credential hygiene — never read/print/echo/commit secrets (L15) | Permanent safety control | Blocks secret exposure | Keep verbatim |
| Real-money & transactions — named approval required (L16) | Permanent safety control | Blocks purchases/listings/pricing | Keep verbatim |
| Git safety — no push to protected branches (L17) | Permanent safety control | Blocks remote risk | Keep |
| Protected data — never delete/overwrite protected files (L18) | Permanent safety control | Blocks fixture destruction | Keep |
| Circuit breaker — stop/persist/report, no auto-retry (L19) | Permanent safety control | Blocks silent failure | Keep |
| Batch LIVE AUTHORIZED boundaries (L20) | Production-only control | Respects batch flags | Keep |
| Reporting protocol (L25-30) | Process control | Discipline | Keep |
| Blocker protocol (L32-33) | Process control | Stub+log+surface once | Keep |
| Memory bank §8 (L35-36) | Production-only control | Knowledge store | Keep |
| Authority order (L38-39) | Process control | Precedence | Keep |

**No rule in the current AGENTS.md was classified as an obsolete development blocker.** (Some DID block live execution in a prior revision; the current text already permits the product's own live operations.)

## 3. Constitution §3 guardrail items — classification

| Item | Classification | Effect |
|---|---|---|
| Reading/writing/printing `.env` or credentials (non-secret §3.1 excepted) | Permanent safety control | Blocks secret exposure |
| Amazon listing/pricing/purchase/transaction + real-money spend beyond named envelope | Permanent safety control | Blocks money moves |
| Git remote ops on protected branches | Permanent safety control | Blocks remote risk |
| Deleting protected files/fixtures | Permanent safety control | Blocks data destruction |
| Batch LIVE AUTHORIZED steps without §3.5 | Production-only control | Enforces batch gates |
| §3.1 non-secret `.env` set | Test-mode + production control | Allows specific config writes |
| §3.2 envelopes / §3.4 low-risk / §3.6 standing approvals | Production-only control | Permits bounded live calls |

## 4. Legitimate controls that must remain (non-negotiable)

1. Never expose, print, copy, or modify secrets.
2. Normal GET routes / page loads must not silently invoke paid providers.
3. Explicit authorization for consequential live writes.
4. Preserve data provenance.
5. Do not fabricate market/seller/fee/supplier/eligibility information.
6. Keep unknown data null or explicitly unavailable.
7. Keep live enrichment scoped, logged, budgeted, controllable.
8. Preserve Amazon account-safety and invoice-legitimacy controls.

## 5. Potential blockers to test/verify (evaluate individually; do NOT blanket-remove)

| Constraint | Currently blocks? | Does it block legitimate local/offline/sandbox work? | Recommended Phase-1 handling |
|---|---|---|---|
| `sitecustomize.py` network block | Blocks all `requests` in tests | Intended (offline tests). Bypass `NS_ALLOW_NETWORK=1` exists | Keep; add explicit sandbox flag |
| `conftest.py` env scrubbing | Scrubs credential-shaped env in tests | Intended | Keep |
| Rate-limit prod posture | Blocks `NORTHSTAR_DISABLE_RATE_LIMIT` in production | Intended | Keep |
| GG live gate 1 | Blocks live GG scan | Intended | Keep; add gate 2 enforcement |
| `SCANNER_LIVE_ALLOWED` default off | Blocks live scan | Intended; offline/cache fine | Keep |
| Protected-hash fixture guards | Blocks modifying protected files | Intended | Keep |
| Alpha-gate allowlist | Blocks non-allowlisted API in private alpha | Intended | Keep |
| `adapters/` orphan status | Nothing blocks; code unused | Not a policy block | Phase-1 decision (adopt or delete) |

## 6. The L0–L5 execution ladder (DRAFT — in `16-proposed-agents-md.md`)

The proposed policy replaces binary hard-stops with a graduated ladder while keeping every non-negotiable control:

- **LEVEL 0** — Read-only static inspection.
- **LEVEL 1** — Local tests and local data only.
- **LEVEL 2** — Mock/sandbox integrations.
- **LEVEL 3** — Explicitly approved live READ operations with budget caps.
- **LEVEL 4** — Explicitly approved live WRITE operations with previews and confirmations.
- **LEVEL 5** — Production automation governed by roles, policies, budgets, logs, rollback.

Each level maps to existing mechanisms (§3.2 envelopes, §3.4 low-risk, §3.6 standing approvals, live gates, usage caps). The draft is written but **not installed**.

## 7. Note on earlier hard-stop history

A prior capsule revision had a blanket "never EXECUTE live/paid outbound calls" hard-stop. In an earlier session it was replaced (per operator directive) with the current guardrail text. This audit documents the CURRENT file state (L11-20 as guardrails). No policy file was modified in this phase.
