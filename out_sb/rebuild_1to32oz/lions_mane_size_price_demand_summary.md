# Organic Lion's Mane Mushroom Powder — Amazon US size/price/demand summary (1.0–32.0 oz rebuild)

- Source: ScrapingBee amazon/search + amazon/product; local Qwen2.5-VL for image reading; all cached files in out_sb/
- Observation window: 2026-10-10 16:53–17:38 UTC (discovery → product details → vision pass; local Ollama vision)
- Scope: 676 unique ASINs cached from the study; widened inclusion 1.0–32.0 oz; two lenses (market vs clean comparable).
- Counts: market lens **76** (17 clean + 42 flagged + 17 review-required, all with known weights), review-required additional (weight-ambiguous) **1**, excluded **599**.
- Clean comparable (launch lens): **17**.
- Categories represented among BSR-known market rows: Grocery & Gourmet Food (7), Health & Household (54)
- Observed fields: price, rating, review count, 'bought in past month' text, label net weight (vision), BSR.
- Estimated fields: `bsr_est_monthly_sales` (ESTIMATE — not observed sales (category-specific BSR model)). Never treat estimates as observed sales.
- Cross-category rule: BSR is category-specific; cross-category comparisons in the 'combined' view are descriptive only.

**Limitations:** 15 of 76 market rows carry title-only evidence (no cached product-detail/label reading); those are kept in the market lens but flagged `review_required` for the clean lens. 17 rows are clean comparables; 42 market rows carry categorical flags (extract / mycelium / blend wording) and are excluded from the clean lens by rule. Amazon 'item weight' fields include packaging and are never used as net weight. Multipacks use label per-unit weight × confirmed unit count. Price is the cached listing price at observation time.

## A. BSR leaders by category

**Grocery & Gourmet Food — BSR leaders (ascending category BSR, top 7 of 7 with BSR)**

| category_rank | ASIN | BSR | size oz | mp | price | $/oz | rating | reviews | recent-sales | est sales/mo (ESTIMATE) | container | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | B07P2CWWVV | 4453 | 16.01 | False | $29.99 | 1.873 | 4.6 | 4897 | 1K+ bought in past month | 856 | powder_pouch | myc |
| 2 | B0D2S6H23L | 4453 | 8.01 | False | $23.95 | 2.99 | 4.6 | 4897 | 2K+ bought in past month | 856 | powder_pouch | myc |
| 3 | B0BWJVD3MK | 88763 | 32.0 | False | $33.99 | 1.062 | 4.1 | 50 | n/a | 109 | powder_bag | clean |
| 4 | B0BWJX1R3C | 88763 | 16.01 | False | $21.47 | 1.341 | 4.1 | 50 | n/a | 109 | powder_bag | clean |
| 5 | B0BWJW3SCZ | 88763 | 8.01 | False | $12.43 | 1.552 | 4.1 | 50 | n/a | 109 | powder_pouch | clean |
| 6 | B0C777FSW9 | 149555 | 3.17 | False | $24.99 | 7.883 | 4.6 | 38 | n/a | 76 | powder_jar | clean |
| 7 | B0CSL625NR | 311609 | 8.0 | False | $14.97 | 1.871 | 3.9 | 22 | n/a | 46 | powder_bag | extract |

**Health & Household — BSR leaders (ascending category BSR, top 25 of 54 with BSR)**

| category_rank | ASIN | BSR | size oz | mp | price | $/oz | rating | reviews | recent-sales | est sales/mo (ESTIMATE) | container | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | B01DKZZFCE | 11092 | 2.12 | False | $34.79 | 16.41 | 4.5 | 5356 | 2K+ bought in past month | 466 | powder_pouch | extract |
| 2 | B0BXPVFRBN | 11092 | 5.29 | False | $69.95 | 13.223 | 4.5 | 5356 | 800+ bought in past month | 466 | powder_pouch | extract |
| 3 | B0C8LTR6L1 | 19668 | 16.0 | False | $21.99 | 1.374 | 4.5 | 673 | 1K+ bought in past month | 312 | UNKNOWN | extract,myc |
| 4 | B09FD8C16B | 21927 | 7.05 | False | $35.95 | 5.099 | 4.5 | 4182 | 800+ bought in past month | 289 | UNKNOWN | myc |
| 5 | B089X92NVD | 22006 | 17.64 | False | $26.97 | 1.529 | 4.5 | 1912 | 900+ bought in past month | 289 | powder_pouch | extract |
| 6 | B089X5P72C | 22006 | 8.82 | False | $21.97 | 2.491 | 4.5 | 1912 | 50+ bought in past month | 289 | powder_pouch | extract |
| 7 | B0BS1VTM9B | 23248 | 7.0 | False | $35.21 | 5.03 | 4.6 | 3278 | 1K+ bought in past month | 278 | UNKNOWN | myc |
| 8 | B077HH98NC | 33563 | 2.12 | False | $39.99 | 18.863 | 4.5 | 1727 | 300+ bought in past month | 215 | powder_jar | extract |
| 9 | B07W8TL9DZ | 36011 | 4.0 | False | $13.95 | 3.487 | 4.6 | 1190 | 400+ bought in past month | 204 | powder_jar | clean |
| 10 | B07W8W2PS6 | 36011 | 16.2 | False | $39.95 | 2.466 | 4.6 | 1190 | 100+ bought in past month | 204 | powder_jar | clean |
| 11 | B0CTBV1VS5 | 36011 | 8.1 | False | $22.95 | 2.833 | 4.6 | 1190 | 50+ bought in past month | 204 | powder_jar | clean |
| 12 | B06XRJZR35 | 58645 | 5.5 | False | $17.99 | 3.271 | 4.5 | 1744 | 200+ bought in past month | 145 | powder_pouch | extract |
| 13 | B01MUG4DVQ | 58645 | 5.5 | False | $29.99 | 5.453 | 4.5 | 1744 | 100+ bought in past month | 145 | powder_pouch | extract |
| 14 | B0CTJ18VH2 | 60427 | 5.3 | False | $19.97 | 3.768 | 4.4 | 208 | 100+ bought in past month | 142 | powder_pouch | clean |
| 15 | B0C7LSXBH7 | 67784 | 17.64 | False | $28.97 | 1.642 | 4.6 | 345 | 100+ bought in past month | 131 | powder_pouch | clean |
| 16 | B0C7LV717Q | 67784 | 8.82 | False | $22.97 | 2.604 | 4.6 | 345 | n/a | 131 | powder_pouch | clean |
| 17 | B0CFP9DF3C | 68988 | 16.0 | False | $21.99 | 1.374 | 4.7 | 493 | 300+ bought in past month | 130 | UNKNOWN | myc |
| 18 | B0CQKGG8N4 | 83858 | 2.12 | False | $29.99 | 14.146 | 4.4 | 132 | 100+ bought in past month | 113 | powder_jar | clean |
| 19 | B0GQ6R43K6 | 83858 | 4.24 | True | $47.38 | 11.175 | 4.4 | 132 | n/a | 113 | powder_jar | clean |
| 20 | B0B3NGHTWD | 100497 | 4.0 | False | $29.99 | 7.497 | 4.5 | 141 | n/a | 100 | powder_pouch | extract |
| 21 | B0CRM5WMQV | 100497 | 8.04 | False | $49.99 | 6.218 | 4.5 | 141 | n/a | 100 | powder_pouch | extract |
| 22 | B0CRM6HGWM | 100497 | 16.08 | False | $89.99 | 5.596 | 4.5 | 141 | n/a | 100 | powder_pouch | extract |
| 23 | B0GPY6GTK2 | 106305 | 4.0 | False | $16.97 | 4.242 | 4.7 | 172 | 50+ bought in past month | 96 | powder_bag | myc |
| 24 | B0GPXXYRDP | 106305 | 8.01 | False | $22.97 | 2.868 | 4.7 | 172 | n/a | 96 | powder_pouch | myc |
| 25 | B0DCC32S7J | 111813 | 8.5 | False | $17.99 | 2.116 | 4.3 | 206 | 100+ bought in past month | 92 | powder_pouch | extract |

## B. Estimated demand leaders by category

**Grocery & Gourmet Food — estimated demand leaders (descending BSR-model estimate; mathematically tied to BSR, not independent demand evidence)**

| ASIN | est sales/mo | BSR | size oz | price | $/oz | reviews | recent-sales | flags |
|---|---|---|---|---|---|---|---|---|
| B07P2CWWVV | 856 | 4453 | 16.01 | $29.99 | 1.873 | 4897 | 1K+ bought in past month | myc |
| B0D2S6H23L | 856 | 4453 | 8.01 | $23.95 | 2.99 | 4897 | 2K+ bought in past month | myc |
| B0BWJVD3MK | 109 | 88763 | 32.0 | $33.99 | 1.062 | 50 | n/a | clean |
| B0BWJX1R3C | 109 | 88763 | 16.01 | $21.47 | 1.341 | 50 | n/a | clean |
| B0BWJW3SCZ | 109 | 88763 | 8.01 | $12.43 | 1.552 | 50 | n/a | clean |
| B0C777FSW9 | 76 | 149555 | 3.17 | $24.99 | 7.883 | 38 | n/a | clean |
| B0CSL625NR | 46 | 311609 | 8.0 | $14.97 | 1.871 | 22 | n/a | extract |

**Health & Household — estimated demand leaders (descending BSR-model estimate; mathematically tied to BSR, not independent demand evidence)**

| ASIN | est sales/mo | BSR | size oz | price | $/oz | reviews | recent-sales | flags |
|---|---|---|---|---|---|---|---|---|
| B01DKZZFCE | 466 | 11092 | 2.12 | $34.79 | 16.41 | 5356 | 2K+ bought in past month | extract |
| B0BXPVFRBN | 466 | 11092 | 5.29 | $69.95 | 13.223 | 5356 | 800+ bought in past month | extract |
| B0C8LTR6L1 | 312 | 19668 | 16.0 | $21.99 | 1.374 | 673 | 1K+ bought in past month | extract,myc |
| B09FD8C16B | 289 | 21927 | 7.05 | $35.95 | 5.099 | 4182 | 800+ bought in past month | myc |
| B089X92NVD | 289 | 22006 | 17.64 | $26.97 | 1.529 | 1912 | 900+ bought in past month | extract |
| B089X5P72C | 289 | 22006 | 8.82 | $21.97 | 2.491 | 1912 | 50+ bought in past month | extract |
| B0BS1VTM9B | 278 | 23248 | 7.0 | $35.21 | 5.03 | 3278 | 1K+ bought in past month | myc |
| B077HH98NC | 215 | 33563 | 2.12 | $39.99 | 18.863 | 1727 | 300+ bought in past month | extract |
| B07W8TL9DZ | 204 | 36011 | 4.0 | $13.95 | 3.487 | 1190 | 400+ bought in past month | clean |
| B07W8W2PS6 | 204 | 36011 | 16.2 | $39.95 | 2.466 | 1190 | 100+ bought in past month | clean |
| B0CTBV1VS5 | 204 | 36011 | 8.1 | $22.95 | 2.833 | 1190 | 50+ bought in past month | clean |
| B06XRJZR35 | 145 | 58645 | 5.5 | $17.99 | 3.271 | 1744 | 200+ bought in past month | extract |
| B01MUG4DVQ | 145 | 58645 | 5.5 | $29.99 | 5.453 | 1744 | 100+ bought in past month | extract |
| B0CTJ18VH2 | 142 | 60427 | 5.3 | $19.97 | 3.768 | 208 | 100+ bought in past month | clean |
| B0C7LSXBH7 | 131 | 67784 | 17.64 | $28.97 | 1.642 | 345 | 100+ bought in past month | clean |
| B0C7LV717Q | 131 | 67784 | 8.82 | $22.97 | 2.604 | 345 | n/a | clean |
| B0CFP9DF3C | 130 | 68988 | 16.0 | $21.99 | 1.374 | 493 | 300+ bought in past month | myc |
| B0CQKGG8N4 | 113 | 83858 | 2.12 | $29.99 | 14.146 | 132 | 100+ bought in past month | clean |
| B0GQ6R43K6 | 113 | 83858 | 4.24 | $47.38 | 11.175 | 132 | n/a | clean |
| B0B3NGHTWD | 100 | 100497 | 4.0 | $29.99 | 7.497 | 141 | n/a | extract |
| B0CRM5WMQV | 100 | 100497 | 8.04 | $49.99 | 6.218 | 141 | n/a | extract |
| B0CRM6HGWM | 100 | 100497 | 16.08 | $89.99 | 5.596 | 141 | n/a | extract |
| B0GPY6GTK2 | 96 | 106305 | 4.0 | $16.97 | 4.242 | 172 | 50+ bought in past month | myc |
| B0GPXXYRDP | 96 | 106305 | 8.01 | $22.97 | 2.868 | 172 | n/a | myc |
| B0DCC32S7J | 92 | 111813 | 8.5 | $17.99 | 2.116 | 206 | 100+ bought in past month | extract |

## C. Pack-size clusters

**Market lens — all qualified/flagged/review rows (weights in range)**

| bin | SKUs | brands | med price | med $/oz | med BSR | med est sales/mo | med reviews | med recent-sales | containers | extract/myc/blend | clean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0–<3 oz | 12 | 8 | $29.99 | $14.161 | 277621.5 | 50.0 | 36.5 | 200.0 | powder_jar:7, powder_pouch:3, UNKNOWN:2 | 9 | 2 |
| 3–<5 oz | 24 | 12 | $23.11 | $6.556 | 152384.5 | 75.0 | 42.5 | 50.0 | UNKNOWN:12, powder_jar:5, powder_pouch:5 | 13 | 4 |
| 5–<8 oz | 12 | 8 | $35.58 | $5.27 | 60427.0 | 142.0 | 884.0 | 500.0 | powder_pouch:5, UNKNOWN:4, powder_jar:3 | 10 | 1 |
| 8–<12 oz | 12 | 11 | $22.96 | $2.849 | 103401.0 | 98.0 | 189.0 | 100.0 | powder_pouch:9, powder_jar:2, powder_bag:1 | 8 | 3 |
| 12–<16 oz | 1 | 1 | $32.26 | $2.512 | 129018.0 | 84.0 | 145.0 | 50.0 | powder_jar:1 | 0 | 1 |
| 16–<24 oz | 14 | 12 | $34.445 | $2.152 | 94630.0 | 104.5 | 95.5 | 600.0 | powder_pouch:7, powder_bag:4, UNKNOWN:2 | 9 | 5 |
| 24–32 oz | 1 | 1 | $33.99 | $1.062 | 88763.0 | 109.0 | 50.0 | n/a | powder_bag:1 | 0 | 1 |

**Clean comparable lens**

| bin | SKUs | brands | med price | med $/oz | med BSR | med est sales/mo | med reviews | med recent-sales | containers | extract/myc/blend | clean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0–<3 oz | 2 | 2 | $38.49 | $15.405 | 107467.0 | 98.0 | 87.5 | 75.0 | powder_jar:1, powder_pouch:1 | 0 | 2 |
| 3–<5 oz | 4 | 4 | $23.11 | $6.595 | 116706.5 | 94.5 | 85.0 | 400.0 | powder_jar:3, powder_pouch:1 | 0 | 4 |
| 5–<8 oz | 1 | 1 | $19.97 | $3.768 | 60427.0 | 142.0 | 208.0 | 100.0 | powder_pouch:1 | 0 | 1 |
| 8–<12 oz | 3 | 3 | $22.95 | $2.604 | 67784.0 | 131.0 | 345.0 | 50.0 | powder_pouch:2, powder_jar:1 | 0 | 3 |
| 12–<16 oz | 1 | 1 | $32.26 | $2.512 | 129018.0 | 84.0 | 145.0 | 50.0 | powder_jar:1 | 0 | 1 |
| 16–<24 oz | 5 | 5 | $38.9 | $2.431 | 88763.0 | 109.0 | 50.0 | 100.0 | powder_pouch:2, powder_bag:2, powder_jar:1 | 0 | 5 |
| 24–32 oz | 1 | 1 | $33.99 | $1.062 | 88763.0 | 109.0 | 50.0 | n/a | powder_bag:1 | 0 | 1 |

**Health & Household (descriptive)**

| bin | SKUs | brands | med price | med $/oz | med BSR | med est sales/mo | med reviews | med recent-sales | containers | extract/myc/blend | clean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0–<3 oz | 10 | 8 | $32.39 | $15.293 | 277621.5 | 50.0 | 42.0 | 200.0 | powder_jar:7, powder_pouch:3 | 8 | 2 |
| 3–<5 oz | 11 | 11 | $26.5 | $6.023 | 155214.0 | 74.0 | 132.0 | 50.0 | powder_pouch:5, powder_jar:4, powder_bag:2 | 7 | 3 |
| 5–<8 oz | 11 | 8 | $35.95 | $5.361 | 60427.0 | 142.0 | 1553.0 | 500.0 | powder_pouch:5, UNKNOWN:3, powder_jar:3 | 10 | 1 |
| 8–<12 oz | 9 | 8 | $22.97 | $2.865 | 106305.0 | 96.0 | 206.0 | 75.0 | powder_pouch:7, powder_jar:2 | 6 | 2 |
| 12–<16 oz | 1 | 1 | $32.26 | $2.512 | 129018.0 | 84.0 | 145.0 | 50.0 | powder_jar:1 | 0 | 1 |
| 16–<24 oz | 12 | 10 | $39.425 | $2.449 | 251287.0 | 69.0 | 89.5 | 300.0 | powder_pouch:6, powder_bag:3, UNKNOWN:2 | 8 | 4 |

**Grocery & Gourmet Food (descriptive)**

| bin | SKUs | brands | med price | med $/oz | med BSR | med est sales/mo | med reviews | med recent-sales | containers | extract/myc/blend | clean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3–<5 oz | 1 | 1 | $24.99 | $7.883 | 149555.0 | 76.0 | 38.0 | n/a | powder_jar:1 | 0 | 1 |
| 8–<12 oz | 3 | 3 | $14.97 | $1.871 | 88763.0 | 109.0 | 50.0 | 2000.0 | powder_pouch:2, powder_bag:1 | 2 | 1 |
| 16–<24 oz | 2 | 2 | $25.73 | $1.607 | 46608.0 | 482.5 | 2473.5 | 1000.0 | powder_bag:1, powder_pouch:1 | 1 | 1 |
| 24–32 oz | 1 | 1 | $33.99 | $1.062 | 88763.0 | 109.0 | 50.0 | n/a | powder_bag:1 | 0 | 1 |

## D. Price architecture

**Price architecture by size tier** (P25 / median / P75; raw rows when n<3)

| tier | n | P25 | median | P75 |
|---|---|---|---|---|
| 1.0–<3 oz | 12 | $12.07 | $14.16 | $18.86 |
| 3–<5 oz | 22 | $4.24 | $6.56 | $8.83 |
| 5–<8 oz | 11 | $3.77 | $5.27 | $10.36 |
| 8–<12 oz | 12 | $2.49 | $2.85 | $3.12 |
| 12–<16 oz | 1 | raw: B0CZPGXZ2T $2.51/oz | — | — |
| 16–<24 oz | 14 | $1.53 | $2.15 | $2.81 |
| 24–32 oz | 1 | raw: B0BWJVD3MK $1.06/oz | — | — |

Clean-lens price architecture:

**Price architecture by size tier** (P25 / median / P75; raw rows when n<3)

| tier | n | P25 | median | P75 |
|---|---|---|---|---|
| 1.0–<3 oz | 2 | raw: B0CQKGG8N4 $14.15/oz; B0FY71CYK8 $16.66/oz | — | — |
| 3–<5 oz | 4 | $5.31 | $6.60 | $11.18 |
| 5–<8 oz | 1 | raw: B0CTJ18VH2 $3.77/oz | — | — |
| 8–<12 oz | 3 | $1.55 | $2.60 | $2.83 |
| 12–<16 oz | 1 | raw: B0CZPGXZ2T $2.51/oz | — | — |
| 16–<24 oz | 5 | $1.64 | $2.43 | $2.47 |
| 24–32 oz | 1 | raw: B0BWJVD3MK $1.06/oz | — | — |

## E. Packaging & positioning

**Packaging & positioning word counts (market lens, from cached titles)**

- Container forms: powder_pouch (29), UNKNOWN (20), powder_jar (19), powder_bag (8)

| bucket | top terms (count) |
|---|---|
| factual product descriptors | powder (85), pure (6), fruiting body (6), freeze-dried (2), finely milled (1) |
| certifications / evidence | organic (64), vegan (19), non-gmo (11), usda organic (6), gluten-free (4), gluten free (3), beta-glucans (2), kosher (1), beta glucans (1) |
| usage occasions | coffee (11), smoothies (9), tea (5), juice (2), latte (2), baking (2), soups (1), recipes (1) |
| health/performance claims | focus (22), brain (17), memory (17), nootropic (9), immune (8), cognitive (7), nerve (6), clarity (3), energy (2), mood (1) |

_Health/performance claim terms are recorded as observed listing language only; no copy recommendation is made._

## Market-size caveat

Any subtotal of `bsr_est_monthly_sales` is a sum of row-level BSR-model estimates; not a deduplicated market-size estimate. Variant families and duplicate search returns can inflate it.