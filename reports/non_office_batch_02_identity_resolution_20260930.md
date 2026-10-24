# Batch 02 — Exact Club-Pack Identity Resolution (2026-09-30)

**Public sources only** (Google, manufacturer/brand sites, public retailer pages, visible packaging images). **No SellerAmp, Amazon, paid UPC DB, private catalog, logins, or purchases.**

## Classification results

| qid | Product | Manufacturer SKU | Club-pack UPC | Result |
|---|---|---|---|---|
| NOB-01 | Scotch-Brite Zero Scratch Scrub Sponges, Individually Wrapped 24 ct | 3M ID B5005539001 | UNKNOWN (base sponge 00051131936843) | PARTIAL |
| NOB-02 | iDesign 4-Piece Recycled Kitchen Organization and Storage Set | UNKNOWN | UNKNOWN | PARTIAL |
| NOB-03 | YouCopia ShelfBin 2-Piece Tiered Organizer Set | Packet + Snack Organizer (no combo SKU) | UNKNOWN | PARTIAL |
| NOB-04 | IRIS USA Medium Modular Stacking Drawers, Set of 3, White | UNKNOWN (medium 11.5 in) | UNKNOWN | PARTIAL |
| NOB-05 | Multipet Jumbo Lamb Chop Plush Dog Toy | 48312 (24 in) candidate | UNKNOWN | PARTIAL |

- **VERIFIED_CLUB_PACK:** 0
- **PARTIAL:** 5
- **CLUB_EXCLUSIVE_OR_UNKNOWN:** noted for NOB-01 (24-ct), NOB-03 (2-pc bundle), NOB-04 (likely bundle); NOB-05 likely standard SKU (48312).
- **REJECTED:** 0

## Evidence URLs + quotations
- NOB-01: `scotch-brite.com/3M/en_US/p/d/b5005539001` — *"3M ID B5005539001 · UPC 00051131936843"*; Sam's page — *"Item #990332122 … $14.97 … 24 ct."*
- NOB-02: `samsclub.com/ip/.../13591274872` — *"4-piece set of opaque white organization bins … Each bin measures 10\" x 4.25\" x 5\"."*
- NOB-03: `youcopia.com/collections/shelfbin-collection` — Packet/Snack Organizers sold separately; Sam's — *"10.7\" D x 6.5\" W x 5.2\" H … 10.7\" D x 10.0\" W x 5.2\" H."*
- NOB-04: `samsclub.com/ip/.../15698765675` — *"Item #990399205 … 20\" D x 16\" L x 11.5\" H … Stacks with the 7\" & 9\" Drawers."*
- NOB-05: `multipet.com/shop/lamb-chop` — *"48371 – 6 inch … 48375 – 10.5 inch … 48312 – 24 inch"*; Sam's — *"Item #990303784."*

## Remaining unknowns
Club-pack UPC/GTIN (all five); pack weight; manufacturer-defined model for the exact club bundle (NOB-01/02/03/04); NOB-05 size/model confirmation.

## SellerAmp eligibility (owner-approved, paced)
**All five eligible.** Owner approval required before any SellerAmp lookup.

## Zero-action confirmation
No SellerAmp, Amazon, logins, accounts, carts, purchases, paid tools, or private catalogs. No base UPC inferred as club-pack UPC; no similar bundle treated as exact; no guessed SKUs/weights.

## Files
- `data/club_sourcing/non_office_batch_02_identity_queue.csv` (updated)
- `data/club_sourcing/non_office_batch_02_identity_evidence.csv`
- `docs/club-sourcing-research-2026-09-30/non_office_batch_02_identity_resolution.md`
- `reports/non_office_batch_02_identity_resolution_20260930.md`

```
CARD: NON-OFFICE-BATCH-02-RESOLUTION  STATUS: DONE
CHANGED: data/club_sourcing/non_office_batch_02_identity_queue.csv, non_office_batch_02_identity_evidence.csv; docs/.../non_office_batch_02_identity_resolution.md; reports/non_office_batch_02_identity_resolution_20260930.md; 00_STATE.json
TESTS: 5 items classified PARTIAL (0 VERIFIED_CLUB_PACK, 0 REJECTED); public evidence quoted; no SellerAmp/Amazon
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner-approved paced SellerAmp lookups for the 5
BLOCKERS: ASK OWNER — club-pack UPCs unresolved; SellerAmp requires explicit approval
```
