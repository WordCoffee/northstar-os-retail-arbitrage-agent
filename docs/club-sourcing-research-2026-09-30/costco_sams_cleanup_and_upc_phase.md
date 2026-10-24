# Costco + Sam's — Cleanup & UPC Verification Phase (2026-09-30)

**Scope:** Costco + Sam's Club only. **BJ's excluded** (accepted final result `PUBLIC_ACCESS_LIMITED`). Research only; no SellerAmp/Amazon/logins/paid tools.

## 1–2. Clean / dedupe / filter
- Input: `public_club_scan.csv` (Costco 20 + Sam's 243 = 263 rows; BJ's removed).
- Removed: already-REJECTED rows, club private-label (Member's Mark), commodity paper, printers/electronics, appliances, bulky/heavy/fragile, food/supplements/cosmetics, unclear categories.
- **Result:** 263 in → **27 kept** → 236 filtered out.
- Output: `data/club_sourcing/costco_sams_clean_queue.csv`.

## 3–4. Ranking + first UPC_VERIFICATION_QUEUE (20)
Prioritized office supplies, clear brands, low-weight/durable, visible item number/pack, straightforward unit identity, no split assumption.
Output: `data/club_sourcing/costco_sams_upc_verification_queue.csv`.

| # | Brand | Product | Pack | Club $ | Item |
|---|---|---|---|---|---|
| UPC-001 | BIC | Brite Liner Grip Pastel Highlighters | 12 Count | 6.76 | 15235320096 |
| UPC-002 | BIC | Intensity Advanced Dry Erase Markers | 12 Count | 13.43 | 15237068677 |
| UPC-003 | Paper Mate | Flair Felt Tip Pens (dual-brush) | 17 Count | 16.98 | 15735957650 |
| UPC-004 | Post-it | Super Sticky Notes 4x6 Lined | 8 Pack | 19.67 | 2120047565 |
| UPC-005 | Post-it | Super Sticky Pop-up Supernova Neons | 16 Pack | 15.36 | 63806013802 |
| UPC-006 | Sharpie | Accent Highlighters | 24 Pack | 10.28 | 13564166907 |
| UPC-007 | 3M Scotch | Precision Ultra Edge 8" Scissors | 3-count | 8.39 | 509768 |
| UPC-008 | BIC | 4-Color Retractable Ball Point Pens | 7-Count | 9.98 | 15712658852 |
| UPC-009 | Post-it | Marseille Colors 1.5"x2" | 24/Pack | 12.48 | 13897405062 |
| UPC-010 | Post-it | Notes 3x3 Assorted Bright | 24 Pads | 19.99 | 5030909 |
| UPC-011 | Sharpie | Metal Barrel S-Gel Pens | 6-Pack | 10.98 | 13967355507 |
| UPC-012 | Swingline | Commercial Desk Stapler Value Pack | — | 9.98 | 16258861820 |
| UPC-013 | Post-it | Super Sticky Notes Canary Yellow | 24 Pads | 18.82 | 17386104264 |
| UPC-014 | (school) | Back to School Variety Pack | 42 Count | 9.91 | 20176674507 |
| UPC-015 | Pilot | FriXion Gel + Highlighters | 12 Pack | 12.67 | 13892003072 |
| UPC-016 | ClickArt | Retractable Marker Pen 0.6mm | 18 pk | 15.32 | 15234120058 |
| UPC-017 | Pilot | Precise V5 Roller Ball (Red) | 12 ct | 13.97 | 13877913252 |
| UPC-018 | Zebra | Mildliner Double Ended Highlighter | 18 pk | 14.87 | 13862473430 |
| UPC-019 | Mr. Clean | Magic Eraser Shower & Tub | 12 ct | 14.98 | 20187662807 |
| UPC-020 | Mr. Clean | Magic Eraser Whole Home Extra Durable | 18 ct | 14.98 | 18800603982 |

## 5. Public UPC/MPN verification (manufacturer pages + ordinary search only)

| # | Public evidence | Status | Confidence |
|---|---|---|---|
| UPC-005 | **Official 3M/Post-it page**: `3M Stock 7100159739 · UPC 00638060138021` (16 pads) | **VERIFIED_PUBLIC** | HIGH |
| UPC-001 | Public distributor page (bestofficegroup) `UPC 070330364660`; barcode DB agrees; BIC model GBLD11-AST | PARTIAL | MEDIUM |
| UPC-006 | Office Depot `UPC 071641019539` (Sharpie Accent Pocket 24/pk); barcode DB also shows `…546` variant | PARTIAL | MEDIUM |
| UPC-007 | Costco page shows **Model MMM471236** (3-pack); official 3M UPC not confirmed | PARTIAL (MPN only) | MEDIUM |
| UPC-012 | Official Swingline value-pack model **S7054551**; candidate value-pack UPC `074711444200` (low confidence) | PARTIAL | LOW |
| Others (15) | No public UPC/MPN confirmed; variant/pack ambiguity | PARTIAL / UNKNOWN | UNKNOWN |

- **Public UPC confirmed:** 4 of 20 (1 official/high).
- **MPN-only:** 1 (UPC-007).
- **Unresolved identity:** 15.

## 6. Constraints honored
No SellerAmp, Amazon, Amazon logins, paid tools, or account-only data. No inferred UPC/pack/sellability/profit/Amazon permission. Unknown preserved.

## Recommended next phase (owner approval required)
Manufacturer UPC verification for the 15 unresolved items; then an owner-approved **small paced SellerAmp batch** for exact Amazon identity + 1P/seller status. Do not enter Amazon/SellerAmp without explicit approval.
