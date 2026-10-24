# Public Club Scan — Report (2026-09-30)

**Mode:** normal-paced visible-page research via ChromeConnect/Playwright in a signed-out profile. No scripts beyond reading visible page text; no hidden JSON/source, no bulk export loops, no CAPTCHA/proxy bypass. **No external state change** (no memberships, carts, purchases, logins).

## Pages successfully viewed per club
| Club | Category/grid viewed | Individual product pages opened (visible) |
|---|---|---|
| Costco | `costco.com/office-products.html` — grid rendered, **34 product links** | **2** (Post-it 24-pad; 3M Scotch scissors 3-count) |
| Sam's Club | search grids across 11 categories (from prior pass) | **2** this pass (Sharpie 24-pk; BIC 4-color 7-ct) |
| BJ's | search page rendered chrome only | **0** |

## Leads recorded per club
- **Costco: 20 rows** (2 product-page verified; 18 from the visible category grid).
- **Sam's Club: 243 rows** (public search tiles; 2 product-page verified this pass).
- **BJ's: 1 limitation row.**

## Access-limited pages/categories
- **BJ's** — `PUBLIC_ACCESS_LIMITED`: `bjs.com/search?q=office supplies` rendered nav/footer but the product grid did not populate (only a gift-card tile). Not bypassed.
- **Costco** — category grid and **individual product pages rendered** (no limitation). Grid was **not** mass-paginated (single page).
- **Google** — after the first `site:` query, Google pushed a **sign-in wall**; no sign-in attempted; discovery continued by direct club URLs.

## Exact UPC/GTIN confirmations
**0** — club product pages did **not** visibly show UPC/GTIN/MPN. All rows `exact_identity_confidence = PARTIAL` (pack/count visible, UPC not).

## Product-pack records with partial identity
**264** rows in `public_club_scan.csv` (194 `DISCOVERY_LEAD`, 69 `REJECTED`, 1 `PUBLIC_ACCESS_LIMITED`).

Verified-with-price examples:
- Costco `3M Scotch Precision Ultra Edge 8" Scissor, 3-count` — Item **509768**, Online Price **$8.39** (was $11.39).
- Costco `Post-it Notes 3"x3", 24 Pads` — Item **5030909**, Online Price **$19.99**.
- Sam's `Sharpie Accent Highlighters, 24 Pack` — Item **#18419**, **$10.28**.
- Sam's `BIC 4-Color Retractable Ball Point Pens, 7-Count` — Item **#990421499**, **$9.98**.

## Rejected products and reasons (69)
- Excluded characteristics: appliances/printers/electronics (HP/Brother/Epson/Lenovo/Bambu/Creality/Royal shredder), bulky (27-gal bins), heavy (hand truck) — recorded as `REJECTED`.
- Club private-label (Member's Mark) and commodity paper — `REJECTED`.

## No-action confirmation
No memberships, accounts, carts, saved lists, alerts, addresses, payment data, purchases, or logins. No retailer APIs, hidden endpoints, devtools, network interception, or proxy rotation. No CAPTCHA/limit bypass. Reading was limited to visible on-screen page text.

## Recommended next research phase
1. **Manufacturer UPC verification** (public manufacturer pages) for the best partial-identity leads.
2. **Owner-approved small SellerAmp/Keepa batch** (paid tool — owner decision) for exact Amazon identity + seller/1P status.
3. **Operator review** — not automatic buying.
