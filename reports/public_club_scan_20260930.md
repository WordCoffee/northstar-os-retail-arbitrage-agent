# Public Club Scan — Final Report (2026-09-30)

**Scope:** Costco / Sam's Club / BJ's public pages, normal-paced, visible-page research only. Signed-out profile. No external state changes.

## Pages successfully viewed per club
- **Costco:** category grid `office-products.html` (34 visible product links) + **2 individual product pages**.
- **Sam's Club:** public search grids (11 categories) + **2 product-page verifications** this pass.
- **BJ's:** search page rendered chrome only — grid did not populate.

## Leads recorded per club
| Club | Rows | Notes |
|---|---|---|
| Costco | **20** | 2 verified product pages + 18 visible grid rows |
| Sam's Club | **243** | public search tiles |
| BJ's | **1** | `PUBLIC_ACCESS_LIMITED` |
| **Total** | **264** | 194 DISCOVERY_LEAD · 69 REJECTED · 1 PUBLIC_ACCESS_LIMITED |

## Access-limited pages/categories
- **BJ's** — product grid did not render → `PUBLIC_ACCESS_LIMITED` (not bypassed).
- **Google** — pushed a sign-in wall after the first `site:` query; no sign-in attempted.

## Exact UPC/GTIN confirmations
**0** — club pages did not visibly show UPC/GTIN; all rows `PARTIAL`.

## Partial-identity product-pack records
**264** (pack/count visible; UPC not). Verified-with-price examples: Costco 3M Scotch Scissors 3-ct Item 509768 $8.39; Costco Post-it 24 Pads Item 5030909 $19.99; Sam's Sharpie Highlighters 24-pk #18419 $10.28; Sam's BIC 4-Color 7-ct #990421499 $9.98.

## Rejected products and reasons (69)
Excluded category/characteristic (appliances/printers/electronics, bulky bins, heavy hand truck) + club private-label (Member's Mark) + commodity paper.

## No-action confirmation
No memberships, accounts, carts, lists, alerts, addresses, payment/tax data, logins, purchases, listings, or ungating. No retailer APIs, hidden endpoints, devtools, network interception, bulk exports, proxy rotation, or CAPTCHA/limit bypass.

## Files
- `data/club_sourcing/public_club_scan.csv` (+ `.json`, 264 rows)
- `data/club_sourcing/public_club_scan_rejections.csv` (70)
- `data/club_sourcing/costco_grid_items.csv`, `sams_raw_items.csv`, `sams_raw_items2.csv`
- `docs/club-sourcing-research-2026-09-30/public_club_scan_report.md`

## Recommended next research phase
1. Manufacturer **UPC verification** (public manufacturer pages).
2. Owner-approved small **SellerAmp/Keepa batch** (paid — owner decision).
3. **Operator review** — not automatic buying.

```
CARD: PUBLIC-CLUB-SCAN  STATUS: PARTIAL (BJ's + Google limited)
CHANGED: data/club_sourcing/public_club_scan.csv/.json, public_club_scan_rejections.csv, costco_grid_items.csv; docs/club-sourcing-research-2026-09-30/public_club_scan_report.md; reports/public_club_scan_20260930.md; 00_STATE.json
TESTS: Costco grid 34 links + 2 product pages; Sam's 243 rows + 2 product pages; BJ's grid=0 (PUBLIC_ACCESS_LIMITED); UPC confirmations 0; no sign-in/cart/purchase
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: manufacturer UPC verification, then owner-approved SellerAmp batch, then operator review
BLOCKERS: ASK OWNER — BJ's grid non-public (limited); Google sign-in wall; UPC/ASIN verification needs owner tools/approval
```
