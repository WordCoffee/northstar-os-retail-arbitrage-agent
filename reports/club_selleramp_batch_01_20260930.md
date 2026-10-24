# SellerAmp Research Batch 01 — Report (2026-09-30)

**Session:** existing authenticated SellerAmp page (`sas.selleramp.com`, account label **T2RetailArb**) only. No login, MFA, CAPTCHA, settings change, export, saved list, alert, or account change performed. No bulk import, mass scan, loops, API calls, page-source extraction, devtools, or retries. One lookup per candidate (5 total), ≥30 s pause after each.

## Dispositions

| # | Candidate | Query | ASIN match | Amazon Retail seller | Disposition |
|---|---|---|---|---|---|
| B01 | Post-it Super Sticky Pop-up Supernova Neons 16-pk | UPC 00638060138021 | none found | — | **INSUFFICIENT_PUBLIC_EVIDENCE** (no result) |
| B02 | BIC Brite Liner Grip Pastel 12-ct | UPC 070330364660 | **B0819FJLH7** (exact 12-ct UPC) | **YES (AMZ)** | **REJECTED** |
| B03 | Sharpie Accent 24-pk | UPC 071641019539 | **B0040R4E2O** (exact 24-ct UPC) | **YES (AMZ)** | **REJECTED** |
| B04 | Scotch Precision Ultra Edge Scissors 8" 3-ct | MPN MMM471236 | none found | — | **INSUFFICIENT_PUBLIC_EVIDENCE** (MPN not indexed) |
| B05 | Swingline Commercial Desk Stapler Value Pack | UPC 074711444200 | **B01MAZESPJ** (model 44420; PARTIAL) | **NO** | **MANUAL_VERIFICATION_REQUIRED** |

## Exact direct-seller findings
- **B02 BIC (B0819FJLH7):** Top offer = **AMZ at $8.71** (stock 1,000); 12 offers; BSR 256; Max Cost $0.81 → **Amazon Retail is an active seller → hard reject.**
- **B03 Sharpie (B0040R4E2O):** Top offer = **AMZ at $10.28**; 6 offers; Sam's price $10.28 = AMZ price → **Amazon Retail active + no spread → hard reject.**
- **B05 Swingline (B01MAZESPJ):** **No AMZ offer**; 2 FBM offers ($17.88 / $45.47); "Amazon Buy Box not seen in 6 months"; FBM-only.
- **Brand-direct seller:** UNKNOWN for all (SellerAmp did not clearly show brand-direct).

## Visible economics (SellerAmp, as shown)
- B02: Max Cost **$0.81**; fees not broken out.
- B03: Max Cost **$0.32**; fees not broken out.
- B05: Total Fees **$2.70**; Max Cost **$12.20**; Profit **$15.26 / ROI ∞%** shown but **cost price blank** → not meaningful.

## Visible warnings / risk (as shown)
- B05: Size Standard; Meltable No; Dangerous Goods No; Variations No; Private Label Unlikely; IP Analysis "No known IP issues". Any explicit per-ASIN restriction for B02/B03 not displayed → UNKNOWN.
- B05 demand warning: BSR 561k, **Est. Sales 2/mo**, "Est. Time to Sale ~20 weeks".

## All UNKNOWN fields
- B01/B04: no ASIN/title/price/seller/fees/profit (no result).
- Brand-direct seller status: UNKNOWN for all five.
- B02/B03 restriction/eligibility: UNKNOWN (not displayed).
- B05 confirmed UPC on listing: not displayed (model match only) → PARTIAL.
- Real FBA/referral/prep/inbound breakdown per ASIN: not displayed.
- Weight/dimensions numeric: not displayed.

## Counts
- Searches completed: **5** (one per candidate).
- Exact direct-seller findings: **Amazon Retail active on 2 (B02, B03)**.
- Rejections: **2** (Amazon Retail). Insufficient evidence: **2** (no result). Manual verification: **1**.

## Zero-action confirmation
No purchases, listings, account changes, saved lists, exports, alerts, settings changes, logins, MFA, or CAPTCHA handling. No bulk/loops/APIs/devtools/page-source/retries. No candidate labeled BUY/APPROVED/SAFE/UNGATED/PROFITABLE.

## Required remaining verification
1. B01: resolve 12-digit UPC / ASIN for the 16-pack; then re-screen (fresh approval).
2. B04: obtain confirmed public UPC for the 3-pack; then screen.
3. B05: confirm exact UPC/config on the listing; assess low demand (2/mo) risk; verify landed cost vs Sam's $9.98.
4. Obtain brand-direct seller status for all.

**STOP after Batch 01.** No further SellerAmp/Amazon until separate explicit owner approval.
