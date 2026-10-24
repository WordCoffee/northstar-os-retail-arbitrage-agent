# Costco → SellerAmp Session 1 — Report (2026-09-30)

**Authorization:** existing authenticated SellerAmp session (`sas.selleramp.com`, account label T2RetailArb) only. No Chrome launch, profile attach, credentials, MFA, CAPTCHA, settings, exports, saved lists, alerts, purchases, listings, or account changes. No Amazon Seller Central actions.

## Phase 0 — queue
- **Inventory:** `costco_source_products` = **800 rows** (fields incl. costco_item_number, title, brand, upc, ean, gtin, mpn, costco_price, costco_pack_raw, size_or_weight_raw). Also `costco_identity_enrichment` = 51 rows, `costco_identifier_resolution_queue` = 181, `costco_evidence` = 113. `data/northstar.db` does **not** exist; the DB is `Northstar_backend/data/northstar.db`.
- **Filter applied:** exclude Kirkland/club private label, food/beverage/supplement/cosmetic, appliance/electronics/printer, chemical, fragile (glass/ceramic), bulky/heavy, collectibles, and Batch-01 office commodities.
- **Queue size:** **5** → `data/club_sourcing/costco_selleramp_queue.csv` (statuses PENDING/DONE/STOPPED; all weight_status UNKNOWN → sorted below known-weight).
- First session items (all 5): COSQ-0001 kangaroo hanger 30-ct; COSQ-0002 swiffer sweep&mop deluxe kit; COSQ-0003 calpak evry 8-piece luggage bundle; COSQ-0004 greenmade 27-gal bin 8-pack; COSQ-0005 tubshroom drain protector bundle.

## Phase 1 — paced SellerAmp lookups
- **Lookups completed:** **1** of max 25 (queue only had 5).
- **Lookup 1 (COSQ-0001, Kangaroo hanger):** candidates captured (all `CANDIDATE_UNVERIFIED`):
  - **B0DXQCQV3S** "Kangaroo Space Saving Suit Hangers, Black 10 Pack" — UPC 850061864680; $24.95; Amazon Retail **NO** (FBA only, 1 offer); BSR 209k; est 50+/mo; Max Cost $11.04; **match WEAK (10 vs 30 pack)**.
  - B0DXQFPYBL (women's 10 Pack) — WEAK; B0GDNPB2X7 (No Hassle-Hangers 3-pk) — NONE.
- **Stop event:** on **lookup 2 (Swiffer)**, the SellerAmp page produced **repeated Playwright interaction timeouts** (element not stable; search did not execute). Per the stop rule (browser error / degraded interaction), the session was **STOPPED and NOT retried**.
- **Amazon-Retail flags:** none among lookup-1 candidates (all FBA-only). Brand-seller: UNKNOWN. Restriction/size tier: UNKNOWN.

## Remaining queue
COSQ-0002 STOPPED (blocked by the stop event); COSQ-0003/0004/0005 PENDING.

## No-action confirmation
No logins, MFA, CAPTCHA handling, settings changes, exports, saved lists, alerts, purchases, listings, or account changes. No retries after the stop event.

## Files
- `data/club_sourcing/costco_selleramp_queue.csv` (checkpoint, 5 rows)
- `data/club_sourcing/costco_selleramp_candidates.csv` (3 candidate ASIN rows) / `.json`
- `reports/costco_selleramp_session_1_20260930.md`

**Do not start another session without explicit owner approval.**

```
CARD: COSTCO-SELLERAMP-SESSION-1  STATUS: STOPPED (browser interaction degradation)
CHANGED: data/club_sourcing/costco_selleramp_queue.csv, costco_selleramp_candidates.csv/.json; reports/costco_selleramp_session_1_20260930.md; 00_STATE.json
TESTS: Phase0 queue=5 (from 800 rows); 1 lookup completed (Kangaroo, WEAK candidates, no AMZ); lookup 2 STOPPED (Playwright timeouts, no retry)
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner approval to resume session 2 (from COSQ-0002)
BLOCKERS: ASK OWNER — SellerAmp page degraded; session stopped per rule
```
