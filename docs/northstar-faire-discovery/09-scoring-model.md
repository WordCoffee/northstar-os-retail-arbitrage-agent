# 09 — Scoring Model

Machine-readable: `opportunity-score-contract.json`. Implementation:
`faire_research/qualification.py`.

## Hard disqualifiers run BEFORE scoring

`faire_is_only_sourcing_route`, `brand_prohibits_amazon`,
`direct_supplier_prohibits_amazon`,
`amazon_eligibility_restricted_or_not_eligible`, `exact_match_failed`,
`pack_mismatch_unresolved`, `invoice_path_absent`, `product_authenticity_uncertain`,
`required_cost_or_fee_missing`, `contribution_profit_non_positive`,
`exceeds_weight_or_dimensions`, `hazmat_expiration_meltable_over_tolerance`,
`amazon_retail_or_brand_dominance`, `ip_enforcement_or_detail_page_mismatch`,
`case_break_terms_violation`.

(An as-yet-uncomputed economics record routes to `ECONOMICS_INCOMPLETE`, not a
hard reject; a present-but-unresolved economics record is a hard disqualifier.)

## Score 0–100 (transparent, configurable)

| Component | Max |
|---|---|
| Verified contribution profit and ROI | 20 |
| Compact size, low weight, low FBA burden | 15 |
| Marketplace eligibility and authorization | 15 |
| Direct supplier and invoice readiness | 15 |
| Demand evidence | 10 |
| Competition quality | 10 |
| Price stability | 5 |
| Replenishment quality | 5 |
| Operational simplicity | 5 |

Missing components earn **0** (never assumed). There is no unsupported "easy" badge.

## Opportunity states

`DISCOVERED`, `MATCH_REVIEW`, `DIRECT_SUPPLIER_RESEARCH`,
`AUTHORIZATION_REQUIRED`, `ELIGIBILITY_CHECK_REQUIRED`, `ECONOMICS_INCOMPLETE`,
`QUALIFIED_FOR_MANUAL_REVIEW`, `WATCHLIST`, `REJECTED`, `SOURCE_READY`,
`PURCHASE_READY`.

- `SOURCE_READY` requires a verified direct supplier **and** no disqualifiers
  (`can_be_source_ready`).
- `PURCHASE_READY` additionally requires confirmed eligibility, confirmed brand
  authorization, exact pack match, complete fees/landed cost, acceptable
  economics, current evidence and operator approval (`can_be_purchase_ready`).

## Competition and sellability decomposition

Eligibility (account/category/brand/product/dangerous-goods/docs); Demand (rank,
history, approved sales estimate, review velocity, offer/price activity,
seasonality); Competition (FBA/FBM counts, Amazon Retail, brand-owner presence,
buy-box rotation, concentration, stability, price compression, entry/exit);
Listing quality (match accuracy, completeness, review quality, variation
stability, suppression/duplicate risk); Operational difficulty (prep, fragility,
leakage, meltability, hazmat, expiration, returns, inspection, packaging, label,
storage, lead time); Supply (direct availability, authorization, invoice quality,
MOQ, reorder, lead time, consistency, price stability, case quantity, relationship).
