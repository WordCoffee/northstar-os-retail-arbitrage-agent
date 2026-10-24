# Club-Sourcing Filter Refinement (after SellerAmp Batches 01–02) — 2026-10-01

**Local only.** No SellerAmp/Amazon/Keepa/paid/logged-in tools. Inputs: `normalized/club_catalog_normalized.csv` (140 kept records) + prior identity/evidence + `selleramp_batch_01_results.csv` / `selleramp_batch_02_results.csv`.

## New policy flags
1. `amazon_retail_observed_brand_line` — YES_OBSERVED only for brands with **observed** Amazon-Retail activity; else **UNKNOWN** (never asserted).
2. `national_commodity_brand_risk` — research-priority penalty only (never seller status).
3. `club_bundle_identity_risk` — set/bundle without a unique manufacturer ID.
4. `exact_manufacturer_sku_or_upc_available` — from public identity work (else UNKNOWN).
5. `selleramp_research_outcome` — AMAZON_RETAIL_OBSERVED / NO_EXACT_MATCH / NOT_RESEARCHED.
6. `selleramp_lookup_priority` — HIGH/MEDIUM/LOW/NONE.

## Observed Amazon-Retail-active brand lines (evidence-based)
From Batch 01/02 results (not assumed):
- **BIC** (Batch 01: ASIN B0819FJLH7 AMZ active).
- **Sharpie** (Batch 01: ASIN B0040R4E2O AMZ active).
- **Scotch-Brite** (Batch 02: Zero Scratch 9/36/6-pk + Heavy Duty 24-pk B000P58USY & 6-pk — AMZ active).
- **Mr. Clean** (Batch 02: 12-ct B0FX5LB87M, 4-ct B0FX5J7PYL, 8-ct XL B0FX5HKTDD — AMZ active).
All other brands = **UNKNOWN**.

## Refined status policy
`SELLERAMP_READY_CANDIDATE` requires **all**: no observed AMZ brand-line flag; not a generic commodity office/cleaning consumable; not an unresolved club bundle; exact manufacturer SKU/UPC (or unique ID); pack identity VERIFIED; not excluded by weight/fragility/category. Otherwise: `NEEDS_EXACT_IDENTITY` · `LOW_PRIORITY_NATIONAL_BRAND` · `LIKELY_CLUB_BUNDLE` · `OBSERVED_AMAZON_RETAIL_RISK` · `MANUAL_REVIEW` · `REJECTED`.

## Results (140 records)
| Status | Count |
|---|---|
| REJECTED (category/weight/chemical/excluded) | 54 |
| OBSERVED_AMAZON_RETAIL_RISK | 13 |
| LIKELY_CLUB_BUNDLE | 25 |
| LOW_PRIORITY_NATIONAL_BRAND | 11 |
| NEEDS_EXACT_IDENTITY | 36 |
| MANUAL_REVIEW | 1 (Cuisinart CTG-00-10PTS) |
| **SELLERAMP_READY_CANDIDATE** | **0** |

Holds log: 103 · Identity research queue: 37.

## Outputs
- `data/club_sourcing/refined_club_catalog.csv`
- `data/club_sourcing/refined_club_rejection_and_hold_log.csv`
- `data/club_sourcing/next_identity_research_queue.csv`

## Note
The identity queue still contains a few low-fit leftovers (e.g., postage stamps, laundry dryer sheets) that further manual triage should drop; they are kept visible, not auto-promoted.

## Next
Public manufacturer identity research on the survivors; only then an owner-approved SellerAmp spot-check for genuine `SELLERAMP_READY_CANDIDATE`s (currently none).
