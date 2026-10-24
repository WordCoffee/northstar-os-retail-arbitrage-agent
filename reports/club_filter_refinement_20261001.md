# Club-Sourcing Filter Refinement — Report (2026-10-01)

**Local only.** No SellerAmp/Amazon/Keepa/paid/logged-in tools; no external state change. Inputs: `normalized/club_catalog_normalized.csv` (140) + Batches 01–02 results + identity/evidence files.

## Row counts by new status (140 total)
| Status | Count |
|---|---|
| REJECTED | 54 |
| OBSERVED_AMAZON_RETAIL_RISK | 13 |
| LIKELY_CLUB_BUNDLE | 25 |
| LOW_PRIORITY_NATIONAL_BRAND | 11 |
| NEEDS_EXACT_IDENTITY | 36 |
| MANUAL_REVIEW | 1 |
| **SELLERAMP_READY_CANDIDATE** | **0** |

Holds log: **103** · Next identity-research queue: **37**.

## Observed evidence vs assumptions
- **Observed (not assumed) Amazon-Retail-active brand lines:** **BIC, Sharpie** (Batch 01) and **Scotch-Brite, Mr. Clean** (Batch 02). These 4 are the only brands marked `amazon_retail_observed_brand_line = YES_OBSERVED`.
- **All other brands = UNKNOWN** (no Amazon Retail asserted without evidence).
- 13 records matched those observed brand lines → `OBSERVED_AMAZON_RETAIL_RISK`.
- `national_commodity_brand_risk` used strictly as a **research-priority penalty**, never as seller status.

## Products worth public manufacturer identity research (survivors)
The 37-record `next_identity_research_queue.csv` skews toward non-brand-channel, compact accessories, e.g.: Cuisinart CTG-00-10PTS (MANUAL_REVIEW), Serta crate mat, Seville Classics organizers, Swiffer duster kit, 3M Scotch scissors (MPN MMM471236 known), Multipet Lamb Chop, Tempur-Pedic pillows, Petshop plush toy. **A few low-fit leftovers remain** (postage stamps; Gain/Bounce dryer sheets) and should be dropped in manual triage.

## SellerAmp-ready
**None.** No record met the full requirement (no observed AMZ brand line + non-commodity + resolved bundle + exact manufacturer SKU/UPC + VERIFIED pack + policy-clean). Zero `SELLERAMP_READY_CANDIDATE`.

## Recommended next discovery categories (based on what survived)
1. **Compact home/kitchen organization accessories** (Seville Classics, IRIS, YouCopia, iDesign) — branded, small, non-commodity.
2. **Lightweight pet accessories** (Multipet; small durable gear) — non-food, non-oversized.
3. **Small branded household accessories** (non-chemical) — e.g., Tempur-Pedic pillows, travel pillows.
4. **Specialty tools** with a known MPN (e.g., 3M Scotch scissors MMM471236).
Avoid: writing/marker/note commodities; mainstream cleaning consumables; club-exclusive multi-piece bundles; gallon bins/luggage/fixtures/chemicals.

## No-action confirmation
No SellerAmp/Amazon/Keepa/paid/logged-in tools; no purchases/listings/accounts; no external state change.

```
CARD: CLUB-FILTER-REFINEMENT  STATUS: DONE
CHANGED: data/club_sourcing/refined_club_catalog.csv, refined_club_rejection_and_hold_log.csv, next_identity_research_queue.csv; docs/club-sourcing-research-2026-10-01/filter_refinement_after_selleramp.md; reports/club_filter_refinement_20261001.md; 00_STATE.json
TESTS: 140 rows -> REJECTED 54, AMZ_RETAIL_RISK 13, CLUB_BUNDLE 25, LOW_PRIORITY 11, NEEDS_IDENTITY 36, MANUAL_REVIEW 1, READY 0; observed AMZ brands = BIC/Sharpie/Scotch-Brite/Mr. Clean only
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: public manufacturer identity research on the 37 survivors; then owner-approved SellerAmp spot-check (none ready yet)
BLOCKERS: ASK OWNER — no SellerAmp-ready candidates; identity research needed first
```
