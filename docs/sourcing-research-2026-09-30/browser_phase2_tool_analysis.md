# Browser Phase 2 — Competitor Tool / Service Analysis (Goal 6)

**Date:** 2026-09-30 · Official product pages read in-browser. Only publicly evidenced capabilities listed.

## Publicly evidenced capabilities

| Tool | Source/catalog scan | UPC/ASIN match | Pack norm. | Price history | Seller count/alerts | Restriction/eligibility | Profit/fees | Supplier compare | Deal queue | Buy-list/export | Supplier CRM | Invoice/doc handling | Replenish forecast | Alerts | Human-approval gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Keepa** | – | ASIN | – | **Yes** ("Detailed Price History charts for over 7 billion Amazon products") | **Yes** (sellers/offers) | – | – | – | Deal alerts | **Yes** ("export them"; API GET) | – | – | – | **Yes** (price alerts) | – |
| **SellerAmp SAS** | storefront search ("Find product ideas by searching other sellers' storefronts") | ASIN | – | via Keepa data | **Yes** ("Offers & stock counts") | **Yes** ("Eligibility checks") | **Yes** ("Profit calculator… profit, ROI, taxes and max cost") | – | – | – | – | – | – | – | – |
| **Tactical Arbitrage** | **Yes** ("1,400+ online retail sites"; Reverse Search; add own sites) | UPC/ASIN | – | **Yes** ("historical Buy Box prices and sales rank") | – | – | **Yes** ("calculates Amazon fees, source discounts, cash back, shipping") | – | **Yes** (Search Manager, multiple scans) | – | – | – | – | – | – |
| **SmartScout** | **Yes** (brands/sellers/subcategories) | ASIN | – | **Yes** ("Pricing history, ranking movements") | **Yes** ("2M+ third-party sellers tracked"; seller count) | – | – | – | – | – | – | – | – | – | – |
| **Helium 10** | product research | ASIN/keyword | – | via tools | – | – | – | – | – | – | – | – | – | – | – |
| **Jungle Scout** | product database | ASIN | – | – | – | – | – | – | – | – | – | – | – | – | – |
| **SellerSprite** | (already in Northstar) product/keyword | ASIN | – | – | – | – | – | – | – | – | – | – | – | – | – |
| **BuyBotPro / Scan Unlimited / SourceMogul / ProfitPath** | bulk OA scanning (publicly marketed) | UPC/ASIN | – | – | – | – | **Yes** (profit) | – | **Yes** | – | – | – | – | – | – |
| **RevSeller** | – | ASIN on page | – | – | – | – | **Yes** | – | – | – | – | – | – | – | – |

Sources: keepa.com, selleramp.com, tacticalarbitrage.com, smartscout.com (direct page reads); others from prior-phase public evidence.

## Patterns worth adopting
1. **Reverse-search** supplier catalog → UPC → Amazon (Tactical Arbitrage pattern).
2. **On-page deal check** with eligibility + profit + max-cost (SellerAmp pattern).
3. **History + offer-count gate** before scoring (Keepa/SmartScout pattern).
4. **Bulk scan + explicit deal queue** with human review.
5. **Export/buy-list** for reconciliation.

## What Northstar already covers
Decision rail/gated states; UNKNOWN handling; pack/case normalization contract; supplier discovery contracts; evidence labeling; offline economics; Faire discovery contracts; known-gaps discipline.

## What Northstar lacks (materially reduces bad buys/risk)
1. **Brand-permission register** (authorization status + evidence + date).
2. **Invoice-quality scorer** (identity/quantity/≤180-day/source).
3. Explicit **Amazon gating state** per candidate.
4. **Supplier account CRM** (application status, docs, MOQ, tiers).
5. **Club price snapshotter** with freshness (Costco/Sam's/BJ's).
6. **Test-order tracker** (3–5 units → invoice acceptance → reorder).
7. **MAP policy register** per brand.
8. **Transcript/lead pipeline** (leads only; never authoritative).

## Risk note
None of these tools provide **brand Amazon authorization** or **invoice acceptance guarantees**. That remains a human/文档 gate (see Goal 7).
