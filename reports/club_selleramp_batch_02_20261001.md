# SellerAmp Candidate-ASIN Batch 02 — Report (2026-10-01)

**Authorization:** owner-approved 5 paced spot-checks (Cuisinart, Scotch-Brite Zero Scratch, Scotch-Brite Heavy Duty, Mr. Clean Whole Home, KitchenAid Dish Drying Mats). Existing authenticated SellerAmp session (T2RetailArb) only; candidate suggestions only; no automatic matching; no purchases.

**Session note:** initial attempts failed on unstable Search-button clicks; reconnected and completed all 5 lookups by submitting the form with **input + Enter** (paced, ≥30 s after each). No CAPTCHA/rate-limit/sign-in event.

## Results (candidate suggestions only — `CANDIDATE_UNVERIFIED`)

| # | Candidate | Best candidates (ASIN / pack / price) | Amazon Retail | Match |
|---|---|---|---|---|
| SA2-01 | Cuisinart 10-Pc Tool & Gadget (CTG-00-10PTS) | B004YZEN0K (12-in Tongs, $16.99); B079NWGRNL (Strainer, $15.99) | **YES** (tongs) / NO (strainer) | No exact set match |
| SA2-02 | Scotch-Brite Zero Scratch 24 ct | B0043P0GRA (9-pk, $8.47); B093TQX9FR (36-pk, $31.71); B0043P0IAK (6-pk, $5.99) | **YES on all three** | No 24-ct match |
| SA2-03 | Scotch-Brite Heavy Duty 24 ct | **B000P58USY (24-pk, $18.99)**; B0FHX19GBZ (45-pk, $41.99); B004IR3044 (6-pk, $5.97) | **YES** (24-pk + 6-pk); NO (45-pk) | **Exact-ish count (24-pk)** but AMZ active |
| SA2-04 | Mr. Clean Magic Eraser Whole Home XD 18 ct | B0FX5LB87M (12-ct, $12.98); B0FX5J7PYL (4-ct, $4.99); B0FX5HKTDD (8-ct XL, $12.94) | **YES on all** | No 18-ct match |
| SA2-05 | KitchenAid Dish Drying Mats Set of 2 | B0D543DYN8 ($6.95); B0F1MZ67NX ($9.99); B0F1MHN92T ($9.99) | NO | No KitchenAid match (other brands) |

## Direct-seller findings
- **Amazon Retail (AMZ) is an active seller** on the Scotch-Brite Zero Scratch line (multiple packs), the Scotch-Brite Heavy Duty 24-pk and 6-pk, and all Mr. Clean Magic Eraser listings observed → strong **reject/caution** signal for those lines.
- **No AMZ** on the Scotch-Brite HD 45-pk, the Cuisinart strainer, or the generic mats (all FBA-only).
- **Brand-direct seller:** UNKNOWN throughout (not clearly shown).
- **No exact match** was proven for any of the five approved **club packs** (24-ct Zero Scratch, 24-ct Heavy Duty club pack, 18-ct Magic Eraser, KitchenAid set, Cuisinart set).

## All UNKNOWN / not displayed
Brand-direct status; restriction/eligibility per ASIN; full FBA/referral/prep/inbound breakdown; numeric weight/dimensions; club-pack UPCs (from the identity phase).

## No-action confirmation
No logins, MFA, CAPTCHA handling, settings changes, exports, saved lists, alerts, bulk imports, purchases, listings, ungating, or account changes. No Amazon Seller Central actions. No automatic matching; nothing labeled verified/eligible/profitable.

## Files
- `data/club_sourcing/selleramp_batch_02_results.csv` / `.json`
- `reports/club_selleramp_batch_02_20261001.md`

**Do not start another session without explicit owner approval.**

```
CARD: SELLERAMP-BATCH-02  STATUS: DONE (5 paced lookups; candidate suggestions only)
CHANGED: data/club_sourcing/selleramp_batch_02_results.csv/.json; reports/club_selleramp_batch_02_20261001.md; 00_STATE.json
TESTS: 5 lookups completed (input+Enter submit); AMZ active on Scotch-Brite Zero Scratch + Heavy Duty 24/6-pk + Mr. Clean line; no exact club-pack match; no auto-match/purchase
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner reviews candidates; decide keep/reject per AMZ-active flag
BLOCKERS: none for this batch (AMZ-active flag = likely reject on 3 lines)
```
