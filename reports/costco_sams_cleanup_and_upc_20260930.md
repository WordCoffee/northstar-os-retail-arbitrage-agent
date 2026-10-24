# Costco + Sam's — Cleanup & UPC Verification — Report (2026-09-30)

**Scope:** Costco + Sam's only. **BJ's excluded** (final: `PUBLIC_ACCESS_LIMITED`). Research only; no SellerAmp/Amazon/logins/paid tools; no inferred UPC/pack/sellability/profit/permission.

## Records
- Scan input (Costco+Sam's): **263**.
- Cleaned/deduped kept: **27**.
- Rejected/filtered: **236** (already-REJECTED, Member's Mark/private-label, commodity paper, printers/electronics/appliances, bulky/heavy/fragile, food/supplements/cosmetics, unclear categories).
- UPC_VERIFICATION_QUEUE: **20**.

## First 20 UPC-verification candidates
`UPC-001` BIC Brite Liner Grip Pastel 12ct · `UPC-002` BIC Intensity Dry Erase 12ct · `UPC-003` Paper Mate Flair 17ct · `UPC-004` Post-it Super Sticky 4x6 8pk · `UPC-005` Post-it Super Sticky Pop-up Supernova Neons 16pk · `UPC-006` Sharpie Accent 24pk · `UPC-007` 3M Scotch Scissors 3ct · `UPC-008` BIC 4-Color 7ct · `UPC-009` Post-it Marseille 24pk · `UPC-010` Post-it 24 pads · `UPC-011` Sharpie S-Gel 6pk · `UPC-012` Swingline Stapler Value Pack · `UPC-013` Post-it Canary 24 pads · `UPC-014` Back-to-School Variety 42ct · `UPC-015` Pilot FriXion 12pk · `UPC-016` ClickArt 18pk · `UPC-017` Pilot Precise V5 12ct · `UPC-018` Zebra Mildliner 18pk · `UPC-019` Mr. Clean Magic Eraser Shower&Tub 12ct · `UPC-020` Mr. Clean Magic Eraser Whole Home 18ct.

## Public UPC/MPN confirmations
- **UPC-005 Post-it Pop-up Supernova Neons 16-pk — UPC `00638060138021`** (official 3M/Post-it page; 3M Stock 7100159739) → **VERIFIED_PUBLIC (HIGH)**.
- **UPC-001 BIC Brite Liner Grip Pastel 12-ct — UPC `070330364660`** (public distributor page) → PARTIAL (MEDIUM).
- **UPC-006 Sharpie Accent 24-pk — UPC `071641019539`** (Office Depot; variant ambiguity) → PARTIAL (MEDIUM).
- **UPC-007 3M Scotch Scissors 3-ct — MPN `MMM471236`** (Costco page); no official UPC → MPN-only (MEDIUM).
- **UPC-012 Swingline Value Pack — MPN `S7054551`** (official Swingline); candidate UPC `074711444200` low confidence → PARTIAL (LOW).
- Totals: **public UPC confirmed 4/20** (1 official/high) · **MPN-only 1** · **unresolved 15**.

## Unresolved identity cases (15)
UPC-002, 003, 004, 008, 009, 010, 011, 013, 014, 015, 016, 017, 018, 019, 020 — pack/variant ambiguity or no public barcode source found this phase.

## Zero-action confirmation
No SellerAmp, Amazon, Amazon login, paid tool, or account-only data. No memberships/carts/purchases. No inferred UPC/pack/sellability/profitability/Amazon permission. Unknowns preserved.

## Files
- `data/club_sourcing/costco_sams_clean_queue.csv` (27)
- `data/club_sourcing/costco_sams_upc_verification_queue.csv` (20)
- `docs/club-sourcing-research-2026-09-30/costco_sams_cleanup_and_upc_phase.md`
- `reports/costco_sams_cleanup_and_upc_20260930.md`

**Stop:** UPC verification only. No SellerAmp/Amazon until separate explicit owner approval for a small paced batch.

```
CARD: COSTCO-SAMS-CLEANUP-UPC  STATUS: DONE (UPC phase)
CHANGED: data/club_sourcing/costco_sams_clean_queue.csv, costco_sams_upc_verification_queue.csv; docs/club-sourcing-research-2026-09-30/costco_sams_cleanup_and_upc_phase.md; reports/costco_sams_cleanup_and_upc_20260930.md; 00_STATE.json
TESTS: 263 in -> 27 clean -> 20 queue; public UPC confirmed 4 (1 official HIGH), MPN-only 1, unresolved 15; no Amazon/SellerAmp/paid/login
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner-approved small paced SellerAmp batch (separate approval required)
BLOCKERS: ASK OWNER — 15 items need UPC resolution; Amazon identity/seller screening needs explicit approval
```
