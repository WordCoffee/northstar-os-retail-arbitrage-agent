# 16 — Phase 1C Recommendation

> **AMENDED (see `19-amendments-and-blockers.md`).** The entry order below is a strict
> sequence with **1C-01 (real auth) as a sole blocker first**, 1C-02 (staging Postgres
> + rollback) second and **not bundled** with 1C-01, then 1C-03 (canonical economics,
> informed by `18-formula-inventory.md`), then the worker, keyword module, and frontend.

Dependency-ordered recommendation for the next phase. Phase 1C should complete the
**foundation hardening** and begin the first **controlled service workflows**, without
enabling external writes.

## P0-completion (foundation hardening) — must precede service work

| ID | Item | Depends | Notes |
|---|---|---|---|
| 1C-01 | Real authentication + org/role resolution (replace dev shim) | — | **Security blocker**; JWT from existing `auth.py`; forward to foundation context |
| 1C-02 | Postgres apply to **staging** + repository backend switch | 1C-01 | `migrations_foundation/001_foundation.sql`; keep SQLite for tests |
| 1C-03 | Job worker + Redis queue + scheduler | 1C-02 | enable fixture/local job execution loop; no external providers |
| 1C-04 | Canonical economics module (single margin/ROI/ACoS) | — | resolve R13/R14; golden-parameter tests |
| 1C-05 | Migration import jobs M1–M6 (dry-run → staged) | 1C-02 | use `foundation_migrate_dryrun` output; attach provenance |
| 1C-06 | Frontend: serve `dist/` via FastAPI mount or CDN; wire foundation auth | 1C-01 | single canonical surface |
| 1C-07 | Keyword module (provider-neutral contract + fixture adapter) | 1C-02 | P1-04 from Phase 1A backlog |

## P1 (first controlled customer workflows)

| ID | Item | Depends |
|---|---|---|
| 1C-08 | Prospector read path on canonical DB | 1C-02, 1C-05 |
| 1C-09 | Golden Goose ranked opportunities on canonical assessments | 1C-08, 1C-04 |
| 1C-10 | OfferChisel draft flow (draft/version/approve; publish gated) | 1C-04, 1C-07 |
| 1C-11 | AutothinK agentic runs (plan/tools/artifacts/checkpoints) | 1C-03, 1C-04, 1C-01 |
| 1C-12 | Operations Hub widget read-model | 1C-08..1C-11 |
| 1C-13 | Ledger UI on real (shadow) usage projection | 1C-03 |
| 1C-14 | Account center + connections store + single brand voice | 1C-01 |

## Explicit non-goals for 1C (still gated)

- Amazon listing/ads/social/purchase execution (separate scoped permission + approvals).
- Paid keyword provider integration.
- Production migration application.
- Any GET-triggered provider activity.

## Owner approvals needed before 1C begins

1. Approve real-auth implementation (1C-01) and its scope.
2. Approve staging Postgres apply (1C-02).
3. Confirm the credit→USD conversion policy (still open).
4. Confirm keyword provider direction (1C-07).
5. Confirm frontend serve mechanism (FastAPI mount vs CDN).