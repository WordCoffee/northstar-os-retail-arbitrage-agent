# Club Goal 1 — Warehouse-Club Sourcing Playbook (research only)

**Date:** 2026-09-30 · Browser: Playwright/ChromeConnect, no-account profile. No sign-in/accounts/purchases.

## Method (evidence-based)
1. **Identity first.** Find the exact sellable unit: brand + model + **UPC/GTIN** + exact pack count + size/color/flavor. "Similar" is not a match.
2. **Sellable-unit match.** A club multipack counts only if the inner unit is independently sealed, retail-ready, separately barcoded where required, and exactly matches the Amazon offer. Otherwise `SPLIT_NOT_VERIFIED`.
3. **Club pages → club price + item number + observed date.** Mark membership/location caveats and treat member-only promos as price-UNKNOWN.
4. **Amazon public page → ASIN only when identity is VERIFIED.** Observe title/brand/price/seller status; timestamp.
5. **Hard filters:** reject if Amazon.com/1P or the brand is an active seller; reject pack/identity mismatch; reject Kirkland; reject excluded categories.
6. **Economics only when every input is known** (club cost/unit, shipping surcharge, Amazon price, referral/FBA/prep/inbound/storage). Never treat UNKNOWN as 0.
7. **Documents:** retail receipts are **not** universal Amazon invoice evidence; keep invoice/documentation risk visible.
8. **Human approval** before any purchase; only labels allowed: `DISCOVERY_LEAD`, `EXACT_MATCH_RESEARCH_CANDIDATE`, `MANUAL_VERIFICATION_REQUIRED`, `REJECTED`, `INSUFFICIENT_PUBLIC_EVIDENCE`.

## Google query families used
Costco/Sam's/BJ's + Amazon FBA exact UPC pack match; Costco Business Center; multipack split rules; clearance research; Amazon FBA retail arbitrage invoice eligibility; branded products invoice requirements; FBA condition/packaging/prep.

## YouTube query families used
Costco Amazon FBA sourcing; Costco Business Center; Sam's Club Amazon FBA; BJ's Wholesale Amazon FBA; club clearance reselling; warehouse club retail arbitrage; SellerAmp/Keepa club sourcing; multipack splitting rules; Costco/Sam's haul product research.

## Segmentation rules (12 hard rejections — applied)
Amazon 1P active seller · brand active seller · identity/UPC/size/count mismatch · Kirkland Signature · excluded category (food/beverage/supplement/cosmetic/collectible/fine jewelry/hazmat) · too heavy/bulky/fragile/return-prone · club price not public/current · gated/eligibility unsupported · MAP/channel conflict · different pack/UPC/color · YouTube-only claim · member-only promo undocumented (→ price-unknown).

## Key operational cautions
- **Costco & BJ's product pages did not render publicly in this session** (only promo/gift-card tiles) → their universes are documented as a public-access limitation.
- **Sam's Club public search pages did render** and were used for the Sam's universe.
