# Club Sourcing Research — Methodology & Access Limitations

**Date:** 2026-09-30 · **Tool:** Playwright/ChromeConnect, no-account profile (`Northstar Research`, signed-out). Research only.

## What was executed in-browser
- Google searches (club sourcing + invoice/eligibility families).
- Costco.com, samsclub.com, bjs.com home/search/category pages.
- Sam's Club public search pages across 11 categories (office, household, home organization, pet, travel, cleaning, kitchen, storage, bathroom, laundry, pet supplies).
- YouTube search + opened videos + on-page transcript extraction.
- Amazon: **not scraped** (would require sign-in/anti-bot); screening recorded as INCOMPLETE.

## Access results
| Source | Public extraction | Note |
|---|---|---|
| Sam's Club (samsclub.com) | **WORKED** | Search tiles expose title + price + product URL publicly. 243 unique product-pack rows captured. |
| Costco (costco.com) | **BLOCKED** | Search/category pages rendered only a persistent promo tile; product grid did not load for this automated/incognito session. |
| BJ's (bjs.com) | **BLOCKED** | Search rendered only a gift-card tile; product grid did not load. |
| Amazon.com | **NOT ATTEMPTED / INCOMPLETE** | Requires sign-in for seller/offer data; anti-bot. No Amazon seller-status asserted. |
| YouTube | WORKED | 11 club videos discovered; 2 transcripts read this pass. |

## Dataset construction rules
- One row per exact product/pack configuration; dedupe by club + item id + title.
- No invented UPC/price/ASIN/seller/fee/permission/profitability.
- Club price parsed from the public tile as displayed; date-stamped; membership/location caveat recorded.
- Default `split_eligibility = SPLIT_NOT_VERIFIED`; `exact_identity_confidence = UNKNOWN`.
- Rejections kept (not deleted): private-label (Member's Mark), commodity paper, and (by rule) any club multipack without proven inner-unit identity.
- Brand heuristic from title prefix (best-effort, marked best-effort).

## Honest gap vs targets
| Target | Achieved |
|---|---|
| Costco ≥250 | **0** (site blocked) |
| Sam's ≥250 | **243 unique rows** (189 DISCOVERY_LEAD + 54 REJECTED) |
| BJ's ≥150 | **0** (site blocked) |
| Screen ≥300 combined | **0 Amazon screens** (blocked/requires sign-in) |
| ≥75 exact-identity reviews | **0** (no public UPC/GTIN on club tiles captured) |
| ≥30 YouTube videos opened | **~10 club videos opened** (2 transcripts read this pass) |

**Conclusion:** the numeric targets are not reachable through public, no-account pages in this environment. A public-access limitation is recorded for Costco, BJ's, and Amazon. Sam's was the only club with extractable public product data.
