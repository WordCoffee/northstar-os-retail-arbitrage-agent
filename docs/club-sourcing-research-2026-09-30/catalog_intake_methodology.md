# Warehouse-Club Catalog Intake — Methodology (2026-09-30)

**Correct operating model:** club category data → local dataset → local filter/rank → manual review → small manually selected SellerAmp shortlist. **SellerAmp is the last step for 5–10 confirmed candidates, not a discovery engine. No SellerAmp/Amazon/Keepa/paid tools in this workstream.**

## Pipeline
1. **Raw capture** — visible category/product pages (public only; no login/cart/API/hidden data). One snapshot per club+category.
2. **Local raw files** — `data/club_sourcing/raw/<club>_<category>_<date>.csv`.
3. **Normalize** — title, brand, price, pack, category, URL, club.
4. **Exclude** — private label (Kirkland/Member's Mark), food/beverage/supplement/cosmetic, appliances/electronics/printers, chemicals/hazmat, glass/ceramic/knives, heavy/bulky/luggage, missing title/brand/price/URL.
5. **Rank for research priority** (never a buy score): known brand, known pack, known price, small/light signals, office lane bonus; missing weight/pack/identity penalized (kept as UNKNOWN, never fabricated).
6. **Manual review queue** — top 40 non-rejected with priority reasons + missing identity + manufacturer-UPC likelihood.
7. **Only then** — owner selects 5–10 for a paced SellerAmp spot-check.

## Files
- Raw: `data/club_sourcing/raw/sams_<category>_20260930.csv` (11 categories), `raw/costco_office_20260930.csv`.
- Normalized: `normalized/club_catalog_normalized.csv` + `.json` (140 kept).
- Rejections: `normalized/club_catalog_rejections.csv` (155).
- Manual review queue: `normalized/club_manual_review_queue.csv` (40).

## Fields
- **Raw:** source_club, category, subcategory, title, brand, club_item_number, visible_price, sale_price, price_observed_at, visible_pack_text, visible_weight_text, visible_dimension_text, product_url, source_page_url, visible_description, visible_image_reference, public_access_status, raw_notes.
- **Normalized:** research_id, source_club, category, product_title, brand, club_item_number, visible_price, exact_pack_status, weight_status, size_risk, fragility_risk, hazmat_risk, private_label_status, exclusion_status, exclusion_reason, identity_status, UPC_status, ASIN_status, selleramp_status, research_status, evidence_urls, evidence_date, source_caveats.

## Access limitations
- **Costco:** category grid rendered for `office-products.html` (20 rows captured); other Costco category grids were not captured this pass.
- **Sam's Club:** public search tiles rendered for 11 categories (office, household, home organization, pet, travel, cleaning, kitchen, storage, bathroom, laundry, pet supplies).
- **BJ's:** out of scope (`PUBLIC_ACCESS_LIMITED`).

## Governance
No fabricated weights/UPCs; `UNKNOWN` preserved; ranking is research priority only; no external state change.

## Next (owner-approved)
Manufacturer UPC/MPN verification for the top review candidates; then owner picks 5–10 for a paced SellerAmp spot-check. Do not open SellerAmp/Amazon until then.
