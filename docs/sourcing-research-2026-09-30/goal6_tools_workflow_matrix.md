# GOAL 6 — Competitive-Tool & Workflow Analysis

**Date:** 2026-09-30 · **Status:** COMPLETE (matrix + adoptable patterns + Northstar gaps/backlog)
**Method:** public vendor pages, third-party reviews, public demos/docs. No proprietary content copied; no private scraping; only publicly claimed features.

## A. Capability matrix (public claims only)

| Tool | Category | Core public functions | Notes / limits |
|---|---|---|---|
| **Keepa** | Price/BSR history | Price, BSR, offer-count, deal alerts, history charts | History authority; sold (not offered) tax/fee eligibility |
| **SellerAmp SAS** | Deal analysis | Profit, fees, eligibility, buy/skip, alerts; includes Keepa chart data (E-TOOLS-3) | Single-deal oriented |
| **Tactical Arbitrage** | Bulk sourcing | Bulk catalog scanning, reverse search, supplier lists | Bulk OA; not a brand-permission source |
| **BuyBotPro** | Bulk OA | Bulk analysis + profit | OA focused |
| **Scan Unlimited** | OA scanning | Bulk scan of supplier sites | OA focused |
| **Helium 10** | Suite | Product research, keywords, listing tools | Broad; product finder (retail/PL leaning) |
| **Jungle Scout** | Suite | Product database, validation | Beginner-friendly (E-TOOLS-1) |
| **AMZScout** | Suite | Product DB + extension | Budget (search) |
| **RevSeller** | Extension | Quick profit/verification on ASIN page | Lightweight |
| **SmartScout** | Brand/data | Brand & seller analytics | Brand analytics |
| **SellerSprite** | Suite | Product/keyword research (already in Northstar) | In-repo |
| **BrickSeek** | Retail/clearance | Local/online inventory + price tracking | Retail arbitrage lead |
| **ProfitPath / SourceMogul** | OA | Sourcing/analysis | OA |
| **Amazon Seller Central** | Authority | Ungating, invoice policy, Bulk Services | Not a sourcing tool; **authority** for eligibility/invoice rules |
| **Faire** | Discovery | Brand/product discovery | **BANNED as supplier**; data only |

## B. Workflow patterns worth adopting

1. **Reverse screening:** supplier catalog → UPC → Amazon match → history → economics (Tactical/Scan pattern).
2. **Live deal check:** on-page profit + eligibility + alert thresholds (SellerAmp pattern).
3. **History gate:** BSR/price/offer-count trend as a hard gate before scoring (Keepa pattern).
4. **Human review queue + decision rail:** explicit pass/review/block states, never auto-buy (Northstar already has).
5. **Identity-first matching:** exact UPC/GTIN + pack normalization before any margin math.
6. **Document vault:** purchase orders/invoices stored for re-verification (few tools do this well — gap).

## C. Gaps Northstar already covers

- Decision rail / gated states; UNKNOWN handling; pack/case normalization contract; supplier discovery contracts; evidence labeling; offline-first economics; Faire discovery contracts; known-gaps discipline.

## D. Missing Northstar capabilities (from this research)

1. **Brand-permission register** (per brand: authorized? evidence URL, date, LOA).
2. **Invoice-quality scorer** (business identity match, quantity, ≤180 days, manufacturer/distributor).
3. **Amazon gating field** (present but UNKNOWN-capable; needs explicit `BRAND_AUTH_REQUIRED` state).
4. **Supplier account CRM** (application status, docs, terms, MOQ, price-tier).
5. **Club price snapshotter** (Costco/Sam's/BJ's exact-unit, timestamped, freshness-gated).
6. **Test-order tracker** (3–5 unit test → invoice acceptance → reorder decision).
7. **Price/MAP policy register** per brand.
8. **Transcript/extraction pipeline** for YouTube leads (leads only, non-authoritative).

## E. Priority backlog tied to real purchase-risk reduction

- **P0:** brand-permission register; invoice-quality scorer; gating state; unknown-fee hard block.
- **P1:** supplier account CRM; club price snapshotter; test-order tracker.
- **P2:** scope/brand analytics; transcript pipeline; OA bulk-scan adapters.

## F. YouTube-derived ideas (verification status)

| Idea | Source (lead) | Verification | Status |
|---|---|---|---|
| Kole Imports FBA program (labeling/bagging/bundling) | YT12 (hB8SlPyMrk0) + E-KOLE-2 | Official support page partially confirms dropship/Fed ID; FBA services | PARTIAL |
| Open first wholesale account step-by-step | YT9 (_oPQWDcRLDo) | Generic; verify per supplier | LEAD |
| Webstaurant ungating | YT15 | Contradicted by E-WSS-2 (not authorized wholesaler) | CAUTION |
| Find wholesale distributors (ACCO) | YT16 | ACCO partner portal confirms distributor program | PARTIAL |
| Essendant approval walkthrough | YT1 | E-ESS 官方 + news (exit) | PARTIAL/CAUTION |

**Rule:** none of the above is actionable until corroborated by an official supplier/brand source.
