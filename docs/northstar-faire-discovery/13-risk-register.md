# 13 — Risk Register

Machine-readable: `risk-register.json`.

| ID | Risk | Sev | Area | Mitigation |
|---|---|---|---|---|
| FD-R1 | Faire terms prohibit Amazon resale; treating Faire as a sourcing route violates policy | critical | compliance | Faire = discovery only; `FAIRE_SOURCING_LABEL`; hard disqualifier `faire_is_only_sourcing_route` |
| FD-R2 | Canonical economics engine (1C-04) not built | high | financial correctness | temporary clearly-labeled adapter; replace at 1C-04; no permanent competing formula |
| FD-R3 | Live research cannot run (1C-03 worker, 1C-01 auth pending) | high | platform | MODE 1 offline only; MODE 2/3/4 are contracts |
| FD-R4 | No real per-ASIN Amazon eligibility/gating source | high | compliance | `ELIGIBILITY_UNKNOWN` default; never infer from other offers; require seller-account check |
| FD-R5 | Fuzzy title matches create false matches (sim 0.27–0.72) | high | data integrity | exact-match safety; only exact classes auto-advance |
| FD-R6 | Pack/case mismatch (case of 12 vs pack of 6) | medium | data integrity | pack normalization; unresolved pack disqualifies |
| FD-R7 | "Not on Amazon" misread as opportunity | medium | compliance | treat as risk; `BRAND_POLICY_RESTRICTS_MARKETPLACES` |
| FD-R8 | Packaged weight unavailable / item weight misread | medium | financial correctness | unknown weight unresolved; `FEE_UNKNOWN` cannot pass |
| FD-R9 | Referral fee treated as universal 15% | medium | financial correctness | fee-confidence states; do not hardcode |
| FD-R10 | Disconnected product universe | medium | architecture | reuse foundation identity/provenance/approvals/audit; integration contract |

Summary: critical 1, high 4, medium 5; owner decisions required: 3
(FD-R1, FD-R2, FD-R3).

## Owner decisions surfaced (batched)

1. Approve 1C-01 real auth (sole first blocker).
2. Approve 1C-04 canonical economics so the temporary adapter is retired.
3. Approve any MODE 4 live-verification budget before further provider calls.
