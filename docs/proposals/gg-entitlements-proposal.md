# PROPOSAL — Golden Goose Entitlements & Credit Allotments (Phase G / A3)

**Status: PROPOSAL — NOT CANONICAL.** Nothing reads this document or changes
behavior. The operator's sign-off makes it canonical; until then the working
(also-proposed) values in `shared/gg-entitlements.json` and
`PLAN_CREDIT_ALLOTMENT` (`Northstar_backend/credit_ledger.py`) stay exactly as
they are.

**Date:** 2026-09-20 · **Cost:** $0 · **Scope:** founding-cohort values for
COHORT_OPS.md (10–50 invited accounts, alpha).

---

## 1. Monthly compute credits per plan (aligns with PLAN_CREDIT_ALLOTMENT)

| Plan | Monthly compute credits | Notes |
|---|---|---|
| foundation | 0 | demo/read-only posture (no live scans) |
| scout | 100 | ~4 mock-equivalent live scans/month (25/scans) |
| mover | 500 | ~20 scans/month |
| autothink | 2000 | ~80 scans/month; founding-operator default |

Rationale: a full live GG scan is estimated at ~25 credits (10 category
searches + per-opportunity enrichment, FIXES_50 #49 constants). The allotments
keep a small cohort operational without billing: the ledger fail-closes at 0
and idle accounts cost nothing.

## 2. Feature gates (mirrors shared/gg-entitlements.json)

| Plan | GG categories | Exports |
|---|---|---|
| foundation | none | none |
| scout | vitamins_supplements, otc_health | opportunities_json |
| mover | + household_cleaning, personal_care, snacks_bars | + opportunities_csv |
| autothink | all 8 canonical categories | + export_manifest_json |

`shared/gg-entitlements.json` already carries these values reference-only and
explicitly never flips a live gate (B7 seam contract).

## 3. Assumptions to confirm

1. **Credit cost per live scan ≈ 25** — the FIXES_50 #49 estimate is the
   planning constant; the real per-scan ledger burn may differ after the first
   approved live run.
2. **Single-tenant-per-account** (B2) — allotments apply per account, not per
   seat; a 10–50 account cohort uses 1× allotment each.
3. **Alpha caps** — the founding cohort is manually operated (COHORT_OPS);
   invites are one-time codes (Phase F/S7) and email delivery is stubbed until
   an operator wires a provider.
4. **No auto-upgrade** — entitlements gate *surfaces*, they never buy a live
   call; §3 approvals remain per-action.

## 4. How sign-off happens

Operator reviews this file + the two working sources, replies with ACCEPT /
CHANGE; on ACCEPT the values become canonical and the "PROPOSAL" markers are
removed in a single follow-up commit. Until then: no behavior change, no
entitlement enforcement beyond what already exists.