# 09 — Data Integrity Review (Phase 1C, as at autonomous sprint)

## Economics data integrity (1C-03)

- One authoritative engine; canonical metric names; Decimal money.
- **Unknown stays unknown**: missing price/cost/fees → `None` + readiness state + `missing_inputs`;
  never substituted with zero.
- Fees only summed when referral and FBA are known; optional fees default to 0 (documented).
- `target_acos` is policy, not a hardcoded constant; `tacos` requires total-revenue scope.
- ROI denominator disclosed (`landed_inventory_cost`); markup not labelled margin.
- `purchase_ready` requires economics + sourcing + documentation + eligibility; the engine
  never asserts invoice acceptance, brand authorization, or eligibility.

## Benchmark honesty

- Minoxidil vectors stored separately and labelled; only aggregate payout/profit exist, so
  the engine reports the **implied** fee (12.48) rather than inventing a component split.
- Neither set is presented as live market data.

## Provenance / null-first preserved

- Provenance classification (`verified/estimated/imported/...`) drives readiness;
  `PROVENANCE_STALE` honoured.
- PostgreSQL behavior differences documented (`postgres-behavior-differences.md`).

## Faire / Amazon sourcing safety (unchanged)

- Faire discovery does not establish Amazon eligibility, invoice acceptance, brand
  authorization, or purchase readiness.
- Retail/club receipts are never auto-classified as sufficient wholesale invoices.
- Pack/quantity/variation differences preserved; ambiguous multipacks remain unresolved.
- Amazon listing/advertising writes remain disabled.

## No fabricated data

No invented search volume, rank, seller counts, Buy Box ownership, eligibility, invoice
acceptance, supplier authorization, or brand authorization was introduced.