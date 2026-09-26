# 14 — Known Gaps

Honest statement of what is **not** built and why (phase gates).

## Blocking dependencies (must clear before live research)

| Gap | Dependency | Impact |
|---|---|---|
| Real authentication + org/role resolution (dev shim only) | Phase 1C **1C-01** | No authenticated org-scoped live runs |
| Canonical economics engine | Phase 1C **1C-04** | Temporary adapter used instead; not purchase-authoritative |
| Job worker + queue + scheduler | Phase 1C **1C-03** | No controlled live research jobs / budgets / rate limits |
| Keyword module (provider-neutral) | Phase 1C **1C-07** | No provider-neutral keyword contract |
| Frontend serve + foundation auth wiring | Phase 1C **1C-06** | No research UI surface |

## Capability gaps (no source exists yet)

1. **Per-ASIN Amazon eligibility / brand gating** — no live source. The in-repo
   `check_brand_gating_sp_api` is a stub returning `unknown`. Eligibility can
   only be confirmed via an authorized seller account (SP-API), out of scope.
2. **Amazon dimensions** — no provider currently returns numeric L×W×H; weight
   is parsed (item vs package ambiguity). Unknown dimensions remain unresolved.
3. **Faire packaged weight/dimensions** — not exposed via the discovery search
   payload; product detail endpoint not identified. Small-item filtering used a
   name heuristic as a proxy.
4. **Stale/duplicate/conflict data tests** (spec DATA family) — logic is
   specified but not exercised because live ingestion is gated.
5. **Security tests for the Faire routes** — not applicable yet (routes not
   implemented); rely on existing `foundation` security tests until then.

## Non-blocking observations

- Existing Amazon caches (~269 ASINs) are Costco/Kirkland-centric with little
  overlap to Faire categories; they are reusable as timestamped evidence only.
- Automated title matching similarity was frequently low; expect a high
  `MATCH_REVIEW` rate until GTIN/MPN evidence is obtained.

## What is safe to implement now (and was)

- Offline (MODE 1) research logic: identity matching, exact-match safety, pack
  normalization, compliance gate, hard disqualifiers, scoring, state machine.
- A clearly-labeled TEMPORARY economics adapter (`Decimal`).
- The documentation + schema package in this folder.
- Offline tests (45 passing).
