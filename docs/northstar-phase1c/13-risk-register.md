# 13 — Phase 1C Risk Register (2026-09-25)

| ID | Risk | Status | Severity | Area | Notes |
|---|---|---|---|---|---|
| 1C-R2 | PostgreSQL apply/rollback unvalidated | EPHEMERAL_VALIDATED_STAGING_PENDING | Medium | database | 1C-04/05 additive migrations validated on PostgreSQL 15.19 (harness 9/9). Staging application still pending. |
| 1C-R1 | Legacy users not bridged to foundation memberships | Open | Medium | security/integration | Owner decisions B1–B5 |
| 1C-R5 | Frontend not serving foundation | Resolved (1C-06) | — | product | Canonical React UI served at /ui |
| 1C-R6 | No NUMERIC money type | Resolved (1C-04) | — | financial | money->NUMERIC; Decimal in app code |
| 1C-R3 | JWKS not implemented | Open | Low | security | static-key model |
| 1C-R4 | Session cleanup not scheduled | Open | Low | hygiene | scheduled-cleanup follow-up |

Summary: 0 blocking, 1 staging-pending, 0 high, 2 medium, 2 low; 2 owner decisions
required (staging infra; legacy bridge).
