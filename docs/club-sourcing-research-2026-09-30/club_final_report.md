# Club Sourcing Research — Final Report (2026-09-30)

**Mode:** browser-driven, research only (Playwright/ChromeConnect, no-account profile). No sign-in, accounts, carts, forms, contacts, payments, purchases, listings, ungating, paid tools, or CAPTCHA bypass. Faire remains banned as a supplier (N/A here). Kirkland Signature excluded.

## Deliverables
- `data/club_sourcing/club_product_universe.csv` / `.json` (243 rows)
- `data/club_sourcing/club_exact_match_reviews.csv` (headers; 0 completed — blocked)
- `data/club_sourcing/club_rejections.csv` (54)
- `data/club_sourcing/club_youtube_transcripts.csv`
- `docs/club-sourcing-research-2026-09-30/club_goal1_sourcing_playbook.md`
- `docs/club-sourcing-research-2026-09-30/club_goal1_youtube_transcripts.md`
- `docs/club-sourcing-research-2026-09-30/club_goal2_costco_universe.csv` (limitation)
- `docs/club-sourcing-research-2026-09-30/club_goal3_sams_universe.csv` (243)
- `docs/club-sourcing-research-2026-09-30/club_goal4_bjs_universe.csv` (limitation)
- `docs/club-sourcing-research-2026-09-30/club_methodology.md`
- `docs/club-sourcing-research-2026-09-30/club_northstar_backlog.md`

## Counts
- **Costco leads:** **0** (site did not render product grids publicly → limitation).
- **Sam's leads:** **243 unique product-pack rows** (189 `DISCOVERY_LEAD`, 54 `REJECTED`).
- **BJ's leads:** **0** (site did not render → limitation).
- **Total deduplicated product-pack records:** **243**.
- **Exact UPC/GTIN records:** **0** (club tiles do not expose UPC/GTIN publicly).
- **Exact Amazon matches:** **0** (`AMAZON_SCREENING_INCOMPLETE` — no public ASIN/UPC bridge; Amazon seller data requires sign-in).
- **Amazon-1P rejections:** 0 screened (none asserted).
- **Brand-direct-seller rejections:** 0 screened (none asserted).
- **Pack-mismatch rejections:** all Sam's rows default `SPLIT_NOT_VERIFIED` (no inner-unit proof).
- **Category/fragility/hazmat rejections:** applied by rule; explicit rejections recorded = 54 (private-label/commodity; category flags UNKNOWN where not visible).
- **Manual-verification candidates:** 189 (`DISCOVERY_LEAD`).
- **Economics-complete candidates:** **0** (no verified identity/fees).
- **YouTube videos opened:** 10 club-relevant; **transcripts read:** 2 this pass (11 prior phase).

## Confirmed workflow insights
1. Identity (UPC/GTIN + exact pack) is the gate; club tiles rarely expose UPC → manual verification required.
2. Reject private-label club brands (Member's Mark; Kirkland excluded by rule).
3. Commodity paper/club-won categories have low wholesale edge.
4. Amazon seller/offer screening needs an authorized method — keep as INCOMPLETE, never assume.

## Northstar P0/P1/P2
See `club_northstar_backlog.md`. P0: exact UPC/pack normalization; 1P/brand-seller exclusion; club-price freshness/member caveats; fee completeness; invoice risk; human-approval rail.

## Remaining limitations & owner-only actions
- **Public-access limitations recorded:** Costco (product grid blocked), BJ's (blocked), Amazon (sign-in/anti-bot).
- **Owner-only:** member sign-ins, club purchases, Amazon seller screening, UPC verification, invoice/eligibility confirmation, any test order. **No external action taken.**
- **No candidate is labeled BUY/APPROVED/SAFE/PROFITABLE.**
