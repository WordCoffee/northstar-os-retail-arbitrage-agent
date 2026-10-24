# Non-Commodity Club Identity Cohort — Report (2026-09-30)

**Public sources only** (Google, official manufacturer/brand sites, public retailer pages). **No SellerAmp/Amazon/Keepa/paid/logged-in tools. No external state change.**

## 8-product cohort (identity + size/weight)

| qid | Product | Identity | Size/weight | SellerAmp-eligible |
|---|---|---|---|---|
| NCC-01 | Scotch-Brite Zero Scratch Sponges, IW 24 ct — Sam's | PARTIAL | LOW | YES |
| NCC-02 | Scotch-Brite Heavy Duty Sponges, IW 24 ct — Sam's | PARTIAL | LOW | YES |
| NCC-03 | Scotch-Brite Stainless Steel Scrubbers, 16 ct — Sam's | PARTIAL | LOW–MEDIUM | YES |
| NCC-04 | Mr. Clean Magic Eraser Whole Home Extra Durable, 18 ct — Sam's | PARTIAL | LOW | YES |
| NCC-05 | Mr. Clean Magic Eraser Shower & Tub, 12 ct — Sam's | PARTIAL | LOW | YES |
| NCC-06 | IRIS USA Medium Modular Stacking Drawers, Set of 3 — Sam's | PARTIAL | MEDIUM | CONDITIONAL |
| NCC-07 | Cuisinart 10-Pc Primary Tool & Gadget Set (crock) — Sam's | **PARTIAL_STRONG** | LOW (3.766 lb) | YES |
| NCC-08 | KitchenAid Dish Drying Mats, Set of 2 — Sam's | PARTIAL | LOW | YES |

Totals: **0 VERIFIED_CLUB_PACK · 1 PARTIAL_STRONG · 7 PARTIAL · 0 REJECTED.**

## Manufacturer identifiers found (public)
- **Scotch-Brite Zero Scratch** — 3M ID B5005539001, base UPC 00051131936843.
- **Scotch-Brite Heavy Duty** — 3M ID B5005539002, base UPC 00051141398334; 6-pack UPC 00051131936812 (MPN 7100333717).
- **Scotch-Brite Stainless Steel Scrubbers** — 3M ID B00027874, 3-pack UPC 00051141254449; 16-pack HD SKU 84-16.
- **Mr. Clean Magic Eraser Whole Home Extra Durable** — official product confirmed; variants 9/10/12/18-ct; no single 18-ct UPC found (Home Depot model 081016561061, 10-ct).
- **Cuisinart** — model **CTG-00-10PTS**, dims 5.75×5.875×14 in, weight 3.766, with 9 tools + stainless crock.
- **IRIS / KitchenAid** — brand + dims/description; no manufacturer UPC surfaced for the club packs.

## Remaining unknowns (per the 8)
Exact club-pack UPC/GTIN (all); pack shipping weight; club-bundle = manufacturer-SKU confirmation (NCC-01/02/03/04/05/06/08); NCC-04/05 exact variant; NCC-06 per-unit weight + FBA size tier; NCC-08 exact mat sizes/colors; brand channel/MAP not assessed.

## Governance / no-action confirmation
No inferred UPCs, weights, pack contents, seller status, eligibility, profitability, or FBA fees. Unknown preserved. No login, cart, purchase, listing, or external state change. No SellerAmp/Amazon/Keepa/paid tools.

## Files
- `data/club_sourcing/noncommodity_identity_cohort.csv` (8)
- `data/club_sourcing/noncommodity_identity_evidence.csv`
- `docs/club-sourcing-research-2026-09-30/noncommodity_identity_cohort.md`
- `reports/noncommodity_identity_cohort_20260930.md`

**Stop after identity work. Do not open SellerAmp or Amazon.**

```
CARD: NONCOMMODITY-IDENTITY-COHORT  STATUS: DONE
CHANGED: data/club_sourcing/noncommodity_identity_cohort.csv, noncommodity_identity_evidence.csv; docs/.../noncommodity_identity_cohort.md; reports/noncommodity_identity_cohort_20260930.md; 00_STATE.json
TESTS: 8-product cohort (0 verified, 1 PARTIAL_STRONG, 7 PARTIAL); public manufacturer IDs captured; no SellerAmp/Amazon/paid
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: manufacturer UPC resolution for club packs, then owner-selected paced SellerAmp spot-check (explicit approval)
BLOCKERS: ASK OWNER — club-pack UPCs unresolved; SellerAmp spot-check requires approval
```
