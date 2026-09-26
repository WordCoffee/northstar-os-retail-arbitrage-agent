# 10 — Research Batch Plan

Machine-readable: `research-batch-contract.json`.

Batches are bounded and **never self-enlarge**. Each batch requires operator
approval. No purchase, listing, supplier-contact or marketplace-write mode exists.

## Modes (only MODE 1 is implemented now)

| Mode | Status | Notes |
|---|---|---|
| MODE 1 — OFFLINE | **Implemented** | existing imports/caches/saved records; zero external requests; default |
| MODE 2 — PUBLIC DISCOVERY | Contract only | permitted public pages; no auth; rate-limited; explicit start |
| MODE 3 — AUTHORIZED IMPORT | Contract only | operator exports; source files unaltered; hashes + provenance |
| MODE 4 — APPROVED LIVE VERIFICATION | Contract only | needs approval, budgets, logging; no listings/orders/contacts |

## Sequence

| Batch | Scope | Limit |
|---|---|---|
| 1 | Faire-discovered brands — classify marketplace policy, find direct route, estimate Amazon overlap, exclude channel conflicts | 100 brands |
| 2 | Products from permitted brands — normalize SKUs/packs, match Amazon, record unresolved | 500 products |
| 3 | High-confidence Amazon matches — fee/size data, full economics, eligibility where authorized | 100 matches |
| 4 | Qualified opportunities — deeper competition/price-history/authorization/supplier/invoice research → manual review records | 25 opportunities |

## Gate rationale (why we stopped here)

- **1C-01 real auth** — not complete → no authenticated, org-scoped live runs.
- **1C-03 job worker/scheduler** — not complete → no controlled live research jobs.
- **1C-04 canonical economics** — not complete → temporary adapter only, no purchase math.
- **1C-07 keyword module** — not complete → no provider-neutral keyword contract.

MODE 1 (offline) is therefore the highest permitted stage. Batches 2–4 remain
contractual until the gates above are cleared and the operator approves a budget.

## Current research-run accounting (this session, evidence)

- Discovery pull: 2,703 Faire products normalized; 978 small-item candidates.
- Bounded Amazon screen: 84 Bright Data requests (60 search + 24 detail);
  25 likely winners detailed. Match quality often low → `MATCH_REVIEW`.
- Purchases / listings / supplier contacts / marketplace writes: **0**.
