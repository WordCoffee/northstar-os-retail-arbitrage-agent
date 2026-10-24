# Warehouse-Club Catalog Intake — Report (2026-09-30)

**Model correction applied:** club category data → local dataset → local filter/rank → manual review → small manually selected SellerAmp shortlist. **All SellerAmp work stopped (COSQ-0002 and beyond NOT resumed). No SellerAmp/Amazon/Keepa/paid tools used.**

## Datasets produced
- **Raw snapshots (`data/club_sourcing/raw/`):** 13 files — `sams_<category>_20260930.csv` (11 categories: office supplies, household supplies, home organization, pet accessories, cleaning supplies, kitchen accessories, storage bins, bathroom accessories, laundry supplies, pet supplies, travel accessories) + `costco_office_20260930.csv`.
- **Normalized:** `normalized/club_catalog_normalized.csv` + `.json` — **140 kept** records.
- **Rejections:** `normalized/club_catalog_rejections.csv` — **155** records.
- **Manual review queue:** `normalized/club_manual_review_queue.csv` — **40** records (ranked).
- **Methodology:** `docs/club-sourcing-research-2026-09-30/catalog_intake_methodology.md`.

## Counts by club
- Sam's: ~264 raw rows → normalized/rejected split; Costco: 20 rows.
- Kept 140 · Rejected 155 (private label, chemicals/hazmat, glass/ceramic, appliances/electronics, luggage/bulky, food/supplement/cosmetic, missing fields).

## Category quality (which yielded best manual-review candidates)
- **Highest quality:** **Cleaning tools/accessories** (Scotch-Brite, Mr. Clean) and **Office supplies / desk organization** (BIC, Pilot, Post-it, Sharpie, Zebra, U Style, Bankers Box, ClickArt) — clear brands + visible pack + compact.
- **Moderate:** **Home/kitchen organization** (IRIS, iDesign, YouCopia, Seville Classics, Cuisinart gadgets), **Pet accessories** (Multipet, Serta crate mat).
- **Dominated by excluded/private-label/bulky:** **Storage bins** (Greenmade/IRIS gallon bins), **Bathroom** (vanities/shower bases), **Laundry/household** (chemical cleaners), **Office Products** (printers/electronics/laptops).

## First 25 products worth manual identity verification
1. Paper Mate Flair Felt Tip Pens, 17 ct — Sam's
2. U Style Office Supply & Storage Set — Sam's
3. BIC Wite-Out EZ Correct Tape, 6 ct — Sam's
4. BIC Intensity Advanced Dry Erase Markers, 12 ct — Sam's
5. BIC Brite Liner Grip Pastel Highlighters, 12 ct — Sam's
6. ClickArt Retractable Marker Pen, 18 pk — Sam's
7. IRIS USA Medium Modular Stacking Drawers, Set of 3 — Sam's
8. Mr. Clean Magic Eraser Whole Home Extra Durable, 18 ct — Sam's
9. Mr. Clean Magic Eraser Shower & Tub, 12 ct — Sam's
10. Pilot Precise V5 Roller Ball Pens, 12 ct — Sam's
11. Pilot FriXion Gel + Highlighters, 12 pk — Sam's
12. Post-it Super Sticky Pop-up Notes, Supernova Neons, 16 pk — Sam's
13. Post-it Super Sticky Notes, 4x6 Lined, 8 pk — Sam's
14. Post-it Super Sticky Notes, Canary Yellow, 24 pads — Sam's
15. Scotch-Brite Heavy Duty Scrub Sponges, IW 24 ct — Sam's
16. Scotch-Brite Zero Scratch Scrub Sponges, IW 24 ct — Sam's
17. Scotch-Brite Stainless Steel Extra Large Scrubbers, 16 ct — Sam's
18. Sharpie Accent Highlighters, 24 pk — Sam's
19. Zebra Mildliner Double-Ended Highlighter, 18 pk — Sam's
20. Post-it Notes, 3x3 Assorted Bright, 24 pads — **Costco**
21. BIC 4-Color Retractable Pens, 7 ct — Sam's
22. Bankers Box Heavy Duty Storage Boxes, 10 pk — Sam's
23. Cuisinart 10-Piece Tool & Gadget Set — Sam's
24. KitchenAid Dish Drying Mats, Set of 2 — Sam's
25. Serta Therapeutic Crate Mat — Sam's

*(Note: several are office commodity brands already hard-rejected in Batch 01 for Amazon Retail; they remain listed as review candidates only, not buy candidates.)*

## Access limits encountered
- Costco: only the office category grid was captured this pass.
- Sam's: 11 category search grids captured.
- BJ's: out of scope (PUBLIC_ACCESS_LIMITED). No retries/workarounds.

## No-action confirmation
No login, membership, cart, API, hidden-data inspection, high-speed scraping, purchase, listing, or external state change. No SellerAmp/Amazon/Keepa/paid tools. `UNKNOWN` preserved; no fabricated weights/UPCs.

```
CARD: CLUB-CATALOG-INTAKE  STATUS: DONE
CHANGED: data/club_sourcing/raw/* (13), normalized/* (normalized csv+json, rejections, manual_review_queue); docs/club-sourcing-research-2026-09-30/catalog_intake_methodology.md; reports/club_catalog_intake_20260930.md; 00_STATE.json
TESTS: 284 raw rows -> normalized kept 140, rejected 155, review queue 40; ranking research-priority only; no SellerAmp/Amazon
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner selects 5–10 review candidates; manufacturer UPC/MPN verification; then a paced SellerAmp spot-check (explicit approval)
BLOCKERS: ASK OWNER — Costco non-office grids not captured; SellerAmp spot-check requires approval
```
