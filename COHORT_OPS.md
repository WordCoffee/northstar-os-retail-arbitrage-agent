# COHORT OPS — Phase E2

**Date:** 2026-09-20 · **Baseline:** E1 (`0a512b…`) · **Scope:** define user
cohorts, per-cohort credit allotments, and admin visibility scope — consistent
with the least-privilege admin rule (B2/B4). Definitions only; no code change.

---

## 1. Cohort model

Cohorts map 1:1 onto **catalog plans** (`shared/subscription-plans.json`) plus a
launch cohort and a staff cohort. Role (B2) and plan are orthogonal: effective
capability = **role permission ∩ plan entitlement**.

| Cohort | Plan id | Who | Role (default) | Access |
|---|---|---|---|---|
| **C0 — Demo/anonymous** | `foundation` | Unauthenticated demo visitors | `member` | Read-only demo surfaces; no jobs/exports |
| **C1 — Foundation (free)** | `foundation` | Free learners / tire-kickers | `member` | Read-only Services Suite demo; 0 credits |
| **C2 — Scout (free-tier scouts)** | `scout` | Single-product sellers | `owner` | Sourcing + enrichment + listing copy + ads read; GG categories `vitamins_supplements`, `otc_health`; export `opportunities_json` |
| **C3 — Mover** | `mover` | Growing brands | `owner` | C2 + media + attribution; +GG `household_cleaning`, `personal_care`, `snacks_bars`; +`opportunities_csv` |
| **C4 — AutothinK (paid GG users)** | `autothink` | Full-service operators | `owner` | Everything + AutoThink workspace + bulk exec + publish; **all** GG categories + all exports incl. `export_manifest_json` |
| **C5 — Founding Operator** | `autothink` (granted) | Invite-only launch cohort (cap **10–50**) | `owner` | C4 entitlements + **manual credit grant**; billing-safe (no charge during alpha) |
| **CA — Staff/Admin** | any | Operator & staff | `admin` | **Account administration only** — least privilege (see §3). Not a tenant role. |

Golden Goose access is expressed through the **B7 entitlement mapping**
(`shared/gg-entitlements.json`, keyed by plan id) — never a separate flag.

## 2. Credit allotments per cohort

Allotments come from the B3 ledger keyed by plan id
(`credit_ledger.PLAN_CREDIT_ALLOTMENT`). **Values are placeholders pending
operator sign-off** (per the standing agreement — not changed here).

| Cohort | Plan | Monthly Compute Credits (placeholder) | Consumption basis |
|---|---|---|---|
| C0/C1 Foundation | `foundation` | **0** | read-only; no metered actions |
| C2 Scout | `scout` | **100** | per `CREDIT_LEDGER_v1.md` §3 action costs |
| C3 Mover | `mover` | **500** | same |
| C4 AutothinK | `autothink` | **2000** | same |
| C5 Founding | `autothink` | 2000 + **manual grant** | operator-granted top-up; recorded as an append-only `grant` entry with an idempotency key |
| CA Admin | n/a | n/a | admin performs no metered tenant actions |

Rules: a plan **entitles**; it never flips a live gate. Exhaustion is
fail-closed (`InsufficientCredits` → clear insufficient state; no negative
balance). The C8 credit meter reads the server value; no client cost logic.

## 3. Admin visibility scope (least privilege — unchanged)

`admin` may see **only basic account fields**: `id`, `email`, `plan`,
`created_at` (`auth.admin_account_view`, whitelist-enforced). Structurally
excluded: password hashes, tokens/session ids, gate/live state, and **tenant
product/market data**. `admin` does **not** satisfy `owner`/`operator` tenant
checks (separate axis). Enforcement: `require_admin` + `/api/v1/admin/accounts/{id}`
(403 non-admin, 404 unknown id) — verified by `test_security_boundaries.py`.

## 4. Cohort operations (definitions; build deferred)

- **Invite flow (C5):** operator-issued invite (email) → registration with plan
  binding → onboarding overlay (B6/C6) → first-run credit grant. States:
  `invited → registered → onboarded → active`. Cohort cap 10–50 enforced at
  invite issuance (D9).
- **Support queue:** operator-owned queue; each item links to an account id
  (opaque), a workspace, and a reproduction; SLA per cohort (C5 highest). No
  PII beyond account email.
- **Billing-safe states (alpha):** no billing is wired — C0–C5 are **$0**
  during alpha; when billing activates (Phase 5 / §18) C1 free, C2–C4 metered,
  C5 honored as founding terms. State machine: `alpha_free → billing_pending →
  active → past_due → cancelled` (billing states are Phase 5).
- **Cohort changes:** plan/role changes are operator-only actions, recorded
  append-only (audit); a plan change never retroactively flips a live gate.

## 5. Notes / flags

- Allotment numbers and the GG entitlement mapping remain **proposed**
  (operator-held) — no change made here.
- Cohorts C0–C4 are implemented as plan/role combinations; **C5 invite flow,
  support queue, and billing states are defined here but not built** (tracked in
  `HANDOFF.md`; D5 #11).