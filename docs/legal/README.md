# Legal Scaffolding — Index (Phase A, A6)

**Date:** 2026-09-19 · **Status:** DRAFTS for early paid launch boundary
(`docs/PRODUCTION_BLUEPRINT.md` §18). **Not committed, not legal advice.**

## Docs

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)
- [Refund/Cancellation Policy](REFUND_CANCELLATION.md)

## Catalog cross-check (A6 requirement)

All tier names, prices, and gate arrays in these docs **reference**
`shared/subscription-plans.json` as the single source of truth — the docs do
not duplicate the price/gate numbers so they cannot drift. Verified at writing:
Foundation / Scout / Mover / AutothinK exist in the catalog; no "unlimited"
language anywhere; billing terms in all three docs are marked
**effective upon payment processor integration**.

## Placeholder registry — every `[LEGAL REVIEW REQUIRED]` marker (consolidated)

| Clause | Where | Why not drafted |
|---|---|---|
| Arbitration / dispute-resolution forum | ToS §10 | Requires counsel; type of forum is a business decision |
| Limitation of liability / caps by jurisdiction | ToS §10 | Jurisdiction-specific; must be reviewed |
| Governing-law / venue specificity | ToS §10 | Operator is Texas-based; final venue language needs review |
| Indemnification & severability | ToS §10 | Standard boilerplate varies; avoid guessing |
| Recurring-billing / auto-renewal / tax / price-change wording | ToS §4 | Billing not live; exact mechanics needed at integration |
| Data-retention schedules per category | Privacy §3 | Regulatory review needed |
| Cross-border transfers / sub-processor schedule | Privacy §4 | None named yet; review before naming |
| Deletion-request SLA | Privacy §5 | Needs a committed timeline only after counsel input |
| **Data-breach notification timeline** | Privacy §6 (explicitly called out in A6) | Statutory timelines vary; must not guess |
| Children / minor terms | Privacy §7 | Only if marketing ever targets individuals |
| Advance-notice on policy changes | Privacy §8 / Refund §7 | Needs a committed period |
| Refund window / pro-rata mechanics | Refund §3 | Statutory rights interaction; counsel |
| Unused-credit formula / expiry | Refund §4 | Business + legal decision |
| Chargeback & dispute mechanics | Refund §6 | Belongs with arbitration clause |

## Revisit triggers

1. When a payment processor is integrated (all "effective upon integration"
   clauses become activatable).
2. At the D8 counsel trigger ($10K MRR OR 25–50 paying customers OR 6 weeks
   live, whichever comes first).
3. Before any public marketing beyond the invite cohort.