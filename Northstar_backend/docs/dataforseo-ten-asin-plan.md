# DataForSEO Live Pilot Plan — Ten Mapping-Approved ASINs

**Status: NOT YET AUTHORIZED.** This is a staged expansion. Every stage is
gated behind the one-ASIN `sellers` pilot completing successfully (create
**and** retrieval), a separate human authorization checkpoint, and an
explicit budget cap. No stage auto-proceeds.

## 0. Base rail (prerequisite)

Before any of the 10-ASIN work, the one-ASIN `sellers` pilot in
`docs/dataforseo-live-pilot-plan.md` must have: created **and** retrieved a
real Seller task for the approved ASIN with an ASIN match, within the one-run
USD 0.01 first-run cap. Only then is this plan eligible to begin.

## 1. Stage 1 — 10 mapping-approved Seller tasks (base rail)

10 ASINs, all mapping-approved, all via **`sellers` family only**:

- Create: `POST /v3/merchant/amazon/sellers/task_post`
- Body: `{"asin": "<approved-asin>", "language_code": "en_US", "location_code": 2840}`
- Retrieve: `GET /v3/merchant/amazon/sellers/task_get/<task_id>`
- Evidence: per-seller condition, price, shipment, seller rating.

**Per-family request cap:** 1 create + 1 retrieve per ASIN (10 × 2 = 20
requests). **Hard budget cap placeholder:** USD 1.00 ceiling for the whole
stage (set `DATAFORSEO_BUDGET_CENTS` locally; the ledger reserves
`DATAFORSEO_ESTIMATED_COST_CENTS` = 5 per planned row and enforces the cap).
Stop the stage on any of the stop conditions in §4.

**Unknown fields after retrieval remain:** Buy Box owner, Buy Box price,
seller count (unless a complete explicit roster is returned), UPC/EAN/GTIN,
monthly unit sales, FBA fee, referral fee, COGS, Amazon purchase
authorization.

**Human checkpoint:** after create+retrieve of all 10, a human must review the
10 Seller observations against the Bright Data shortlist before Stage 2.

## 2. Stage 2 — Conditional `asin` rail (only as needed)

- Family: `asin` (Merchant Standard).
- Create: `POST /v3/merchant/amazon/asin/task_post`
- Body: `{"asin": "<asin>", ...}`
- Use **only** for variation/pack-size ambiguity that the `sellers` result
  could not resolve (e.g. pack-of-N variants of the same product).

**Request cap (stage):** N creates + N retrieves, where N ≤ 10 and only for
asins that had an unresolved ambiguity in Stage 1.
**Hard budget cap placeholder:** USD 1.00 (separate, approved run).
**Human checkpoint** before submission: an operator must confirm each ASIN
needs the `asin` family and that the candidate is still mapping-approved.
**Unknown fields:** same as §1; `asin` returns product-level data, not a
seller roster.

## 3. Stage 3 — Conditional `products` rail (keyword/listing cross-checks)

- Family: `products`.
- Create: `POST /v3/merchant/amazon/products/task_post`
- Body: `{"keyword": "<benchmark-title-derived>", "language_code": "en_US",
  "location_code": 2840}` — keyword sourced **only** from the candidate
  benchmark title; never a marketplace-free-text search, never fabricated,
  and never includes `asin`/`query`/`search_term` in the request body.
- Use **only** for keyword/listing/SERP cross-checks to validate that the
  shortlist title resolves to the expected product on Amazon's SERP.

**Request cap (stage):** N creates, where N ≤ 10 and only for candidates
requiring a SERP cross-check. No `task_get` retrieval beyond matching results.
**Hard budget cap placeholder:** USD 1.00 (separate, approved run).
**Human checkpoint** before submission.
**Unknown fields:** same as §1.

## 4. Stage 4 — Labs Live (only with separate approval)

Labs Live is **immediate/inline** (no `task_get`). Each sub-family needs its
own approval and budget:

- `product_rank_overview` — `POST /v3/dataforseo_labs/amazon/product_rank_overview/live`
  — **only** after a separate Labs preflight + explicit approval, and only
  for finalists from Stage 1–3.
- `ranked_keywords` — `POST /v3/dataforseo_labs/amazon/ranked_keywords/live`
  — for finalists only.
- `bulk_search_volume` — `POST /v3/dataforseo_labs/amazon/bulk_search_volume/live`
  — as a batched keyword-demand proxy only; **never** converted into unit
  sales or purchase signals.

**Hard budget cap placeholders** (each its own approved run): USD 1.00 per
sub-family, capped and reserved via `DATAFORSEO_ESTIMATED_COST_CENTS`.
**Human checkpoint** before each Labs sub-family: Labs auto-submit is gated
off (`DATAFORSEO_LABS_AUTO_SUBMIT` unset/off) and must be explicitly enabled
locally for one invocation, then restored.
**Explicit prohibition:** search volume, ranking, and review data are
demand/SEO signals only and are **never** used to infer monthly unit sales,
profit, margin, or purchase eligibility.

## 5. Universal stop conditions (all stages)

Abort the stage (and do not proceed to the next stage) on any of:

- provider rejection (`provider_rejected_*`),
- path/URL mismatch (route is not the approved family URL),
- zero or negative provider-reported `cost`,
- malformed response (not a dict / missing `tasks`),
- missing / non-UUID-like / slash-containing `task_id`,
- ASIN mismatch between request body and retrieved ASIN,
- budget breach (`DATAFORSEO_BUDGET_CENTS` exceeded for the run),
- returned family does not match the requested family,
- secret-like output in the response (redact, halt, manual review),
- persistence failure (raw-evidence write error),
- timeout / `AmbiguousTransportError` → `needs_manual_reconciliation`,
  never retried,
- any `mapping_incompatible` row (unresolved mappings stay blocked).

## 6. Per-family evidence & Unknown fields

| Family | Expected evidence | Remains Unknown until explicitly present |
|--------|-------------------|------------------------------------------|
| `sellers` | per-seller condition, price, shipment, seller rating | Buy Box owner, Buy Box price, seller count (if roster not complete), UPC/EAN/GTIN, monthly unit sales, FBA fee, referral fee, COGS, Amazon purchase authorization |
| `asin` | product-level offers/condition/price for the ASIN | same as above, plus seller roster (asin family does not yield a per-seller roster) |
| `products` | listing/SERP result for the keyword (title/brand/observed_price/condition) | same as above, plus per-seller roster |
| Labs `product_rank_overview` / `ranked_keywords` / `bulk_search_volume` | rank, keyword, search volume numbers | all demand/sales, fee, COGS, Buy Box, seller-count, and purchase-authorization signals (never inferred) |

## 7. Authorization checkpoints

- [ ] Stage 0 (one-ASIN `sellers` pilot) complete with create + retrieve + ASIN match
- [ ] Stage 1 (`sellers`, 10 ASINs) — explicit approval + USD 1.00 cap + `DATAFORSEO_TRANSPORT_ENABLED=true` locally
- [ ] Stage 2 (`asin`) — explicit approval only if ambiguity unresolved; separate cap
- [ ] Stage 3 (`products`) — explicit approval only for SERP cross-checks; separate cap
- [ ] Stage 4 (Labs) — separate approval per sub-family; Labs auto-submit off by default
- [ ] Transport disabled (`false`) restored after every stage

**Remaining implementation blocker:** *Create an explicitly mapping-approved
Merchant Sellers planning/submission path; keep unresolved mappings
blocked.*
