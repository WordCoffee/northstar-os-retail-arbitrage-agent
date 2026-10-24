# Non-Office Club Candidate Queue — Batch 02 (2026-09-30)

**Scope:** existing Costco + Sam's public dataset + ordinary public manufacturer/Google research only. **No SellerAmp, no Amazon, no logins, no paid tools.** Stop after building a 5-item identity queue.

## Selected five (exactly five)

| qid | Brand | Product | Club / item | Club $ | Identity | Public UPC/GTIN |
|---|---|---|---|---|---|---|
| NOB-01 | Scotch-Brite (3M) | Zero Scratch Scrub Sponges, Individually Wrapped 24 ct | Sam's 13597950863 | 15.44 | PARTIAL_STRONG | **00051131936843** (base sponge; 3M official) |
| NOB-02 | iDesign | 4-Piece Recycled Kitchen Organization and Storage Set | Sam's 13591274872 | 29.98 | PARTIAL | UNKNOWN |
| NOB-03 | YouCopia | Tiered Snack and Packet Organizer, 2-Piece Set | Sam's 13783965712 | 25.99 | PARTIAL | UNKNOWN |
| NOB-04 | IRIS USA | Medium Modular Stacking Drawers, Set of 3, White | Sam's 15698765675 | 54.96 | PARTIAL | UNKNOWN |
| NOB-05 | Multipet | Jumbo Lamb Chop Plush Dog Toy | Sam's 13931124656 | 11.98 | PARTIAL | UNKNOWN |

## Selection reasons (summary)
Compact/durable **non-office** categories: cleaning tool (non-chemical) + home/kitchen organization + pet accessory. Clear brands with public manufacturer sites; lightweight/non-fragile; no private-label; no excluded category; no split-pack assumption.

## Public source evidence
- **NOB-01:** official 3M/Scotch-Brite page — `3M ID B5005539001 · UPC 00051131936843`; 6-pack variant UPC 00051131936836 (Binding Source, 3M SKU 7100282600).
- **NOB-02:** iDesign manufacturer/retailer pages with visible dims (10×4×5 in etc.).
- **NOB-03:** youcopia.com official — ShelfBin Packet Organizer (10.7×6.5×5.2 in) and Snack Organizer.
- **NOB-04:** irisusainc.com official brand site; Sam's item #990399205 with dims 20×16×11.5 in.
- **NOB-05:** multipet.com brand; multiple distributor pages (sizes 18 in/24 in).

## Remaining UNKNOWNs (per record)
- Exact **24-ct / 2-pc / set / jumbo** pack UPC not publicly confirmed (only base/sponge UPC for NOB-01).
- No Amazon ASIN / 1P / brand-direct / price / fees / eligibility (not examined this phase).
- Variant/size ambiguity: NOB-02 (4-pc variant), NOB-03 (2-pc combo), NOB-04 (model/SKU), NOB-05 (18 vs 24 in).
- Weight/dimensions partial for NOB-02/04/05.

## Zero-action confirmation
No SellerAmp, Amazon, logins, accounts, carts, purchases, exports, or settings changes. No exact-UPC invention; no close variants; no split-pack assumption; no private-label; no excluded categories.

## Files
- `data/club_sourcing/non_office_batch_02_identity_queue.csv` (5 rows)
- `docs/club-sourcing-research-2026-09-30/non_office_batch_02_identity.md`
- `reports/non_office_batch_02_identity_20260930.md`

**STOP after queue creation.** No SellerAmp/Amazon until separate owner authorization.

```
CARD: NON-OFFICE-BATCH-02-IDENTITY  STATUS: DONE (identity queue)
CHANGED: data/club_sourcing/non_office_batch_02_identity_queue.csv; docs/club-sourcing-research-2026-09-30/non_office_batch_02_identity.md; reports/non_office_batch_02_identity_20260930.md; 00_STATE.json
TESTS: 5 non-office candidates selected (all PARTIAL/STRONG PARTIAL); 1 public base UPC confirmed (3M); no SellerAmp/Amazon/login/paid
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: resolve exact club-pack UPC/MPN, then owner-authorized small paced SellerAmp batch
BLOCKERS: ASK OWNER — club-pack UPCs unresolved; Amazon screening needs explicit approval
```
