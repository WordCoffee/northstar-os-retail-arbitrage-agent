# Golden Goose Finder — 100 Improvements Roadmap

**Date:** 2026-09-16
**Scope:** Data finding, consolidation, presentation, filter settings
**Status:** Proposed (prioritized P0/P1/P2, pending operator triage)

---

## Part 1 — Data Finding (25)

**P0 — High Value, Do First**

1. **Keepa API integration** — historical BSR/price/seller-count curves; the biggest accuracy upgrade. Requires operator key (~$17-20/mo).
2. **Amazon SP-API ungating check** — automated gating_status determination per ASIN/category instead of manual lookup.
3. **Sam's Club catalog integration** — currently Costco-only; Sam's has different pack sizes and occasionally better price-per-unit.
4. **Costco weekly flyer parser** — new deals/price drops detected the week they launch; catches 2-4 week promotion windows.
5. **Amazon autocomplete suggest harvesting** — the search bar suggestions reveal rising query demand before BSR catches up.

**P1 — Strong Value**

6. **Price history delta tracker** — record every enrichment run; flag suppliers whose wholesale price moved since last scan.
7. **Buy Box stability scoring** — count Buy Box price changes over 30/60/90 days; unstable Buy Box = fragile margin.
8. **Warehouse deal monitoring** — Amazon Warehouse (AWD) occasionally lists open-box multi-packs below wholesale.
9. **Multi-store wholesale cross-check** — same product at Costco vs Sam's vs BJ's → pick lowest pack COGS automatically.
10. **Seasonality calendar per category** — allergy meds spike in spring, OTC cold in winter; timestamp windows into scans.
11. **New-listing radar** — flag individual listings created < 12 months ago; early-stage competition is thinnest.
12. **Expiration-date feasibility note** — food/OTC categories: check pack count vs stated shelf life; max breakdown window.
13. **Suppressed/strangled listing detection** — missing # of reviews, no Buy Box → often a gating or ASIN-quality signal worth knowing.
14. **Grocery store circular scraping (local)** — Costco is not the only bulk source; Sam's, BJ's, and regional clubs add supply.
15. **MSRP/maker price monitoring** — manufacturer list-price changes (e.g., Nicorette MSRP hikes) drift Amazon Buy Box up.

**P2 — Enhancement Layer**

16. **eBay sold-listings cross-check** — validates Amazon velocity with an independent resale market.
17. **Multi-marketplace comparison (Amazon CA/MX)** — adjacent-market demand signals for the same SKU.
18. **Manufacturer outlet/wholesale site checks** — direct wholesale sometimes beats club pricing for un-gated brands.
19. **Reddit/forum demand signals** — r/QuitSmoking, r/frugal, etc. for product mentions trending (qualitative signal, low weight).
20. **TikTok/Instagram trend detection** — health/product virality often precedes Amazon demand by 2-6 weeks.
21. **Cashback/portal tracking** — Rakuten-style cashback on wholesale purchases lowers effective COGS (0.5-3%).
22. **Costco item-number ↔ ASIN persistence cache** — store the mapping so re-scans skip re-discovery.
23. **Prime Day / Deal-event calendar** — pre-scan wholesale availability 3 weeks before major events; discounts stack with retail arbitrage.
24. **Competitor ASIN follower** — watch specific competitor ASINs' stockouts; stockout = unmet demand = pricing power.
25. **Google Shopping/price-comparison API** — sanity-check that Amazon individual pricing isn't an outlier (could be a stale listing).

---

## Part 2 — Consolidation (25)

**P0 — High Value, Do First**

26. **Unified product ID registry** — one record per product: ASIN + Costco item # + Sam's # + GTIN/UPC, all cross-linked.
27. **Multi-source COGS blending** — same pack from Costco online vs warehouse vs Sam's; pick min + record variance.
28. **Field-level freshness timestamps** — price (1d old) vs BSR (3d old) vs seller count (stale) displayed independently, not as one record age.
29. **Source confidence scoring** — provider A's seller counts weighted higher than provider B's; stale/warned sources auto-downgraded.
30. **Fuzzy brand matching** — case/plural/typo-tolerant brand join across all feeds (NATUR MADE ≈ Nature Made).

**P1 — Strong Value**

31. **Duplicate suppression by composite key** — (ASIN, source_store, pack_size) vs pure ASIN; prevents double-counting multi-source rows.
32. **Pack-count extraction voting** — three independent extractors; majority wins; disagreement = flagged for review.
33. **Unit economics normalization** — every opportunity expressed as per-unit (1 count) so packs of 10 vs 200 compare apples-to-apples.
34. **Item-size canonicalization** — oz/g/ml/lb converged to one unit system; pack_weight_lbs always present.
35. **ASIN rotation tracking** — listings change parent ASINs; keep a lineage map so history isn't lost.
36. **Variation/bundle detection** — parent-child mapping; flag "item + free gift" bundles that skew price data.
37. **Enrichment merge semantics** — explicit merge-vs-replace policy; a newer partial record never blanks older complete fields.
38. **TTL expiry for volatile fields** — BSR/price/seller-count expire after 3/7/14 days respectively; stale rows enter "needs refresh" queue.
39. **Provenance per field** — every number carries which provider + when; report exports include data lineage.
40. **Multi-pass matching pipeline** — exact GTIN → exact title-brand → fuzzy → human review queue; nothing silently dropped.

**P2 — Enhancement Layer**

41. **Standardized tag ontology** — one canonical tag list shared by scanner, scorer, UI, and reports (no drift).
42. **JSON schema versioning** — report/opportunity schemas carry explicit version; migrations are explicit, not silent.
43. **Historical snapshot diffing** — each scan stores a delta vs the previous scan ("price +12%, sellers 1→3, new HIGH tier").
44. **Reusable wholesale→individual mapping cache** — known-good mappings stored; re-scan only revalidates price/velocity.
45. **Buy Box vs FBM price split** — store both; margin is only valid against the Buy Box you can win.
46. **Wholesale cost basis metadata** — tag each COGS as warehouse scan / online / cashback-adjusted / estimated.
47. **Dead-listening detection** — Costco still lists a pack but Amazon individual sales collapsed; auto-demote.
48. **Inventory state tracking** — wholesale in-stock/out-of-stock history; out-of-stock circuits into next scan.
49. **Unit price-per-ounce/gram/lozenge calculation** — a true value metric that pack size cannot hide behind.
50. **Consolidation audit log** — every merge/transform writes an audit row; 100% replayable data pipeline.

---

## Part 3 — Presentation (25)

**P0 — High Value, Do First**

51. **"Why this score" tooltip** — per-opportunity breakdown of the composite score with hover details on each component.
52. **Confidence badges on data fields** — 🟢 estimated / 🟡 provisional / ⚪ unknown shown per field, not buried in notes.
53. **Scenario planner modal** — drag price/cost sliders and live-update net profit, ROI, and tier; locking in a price change.
54. **Trend sparklines** — inline mini-charts for BSR + Buy Box history per listing (even a 30-day window is powerful).
55. **Category drill-down** — sidebar tree: All → Category → Brand → ASIN; breadcrumbs enabled.

**P1 — Strong Value**

56. **Opportunity score gauge** — radial gauge per row/tier (HIGH ≥ 0.7, MEDIUM ≥ 0.45, LOW ≥ 0.25).
57. **Heat-map profitability grid** — cells colored by net profit; scan a dozen candidates at once.
58. **Buy-ready report (print/PDF)** — per-batch purchasing summary: items, pack sizes, unit economics, shelf photos slot.
59. **Alerts (Slack/Telegram/Email)** — HIGH-tier discoveries push immediately; configurable quiet hours.
60. **Watchlist pinning** — pin opportunities to track over weeks; price/velocity movement visible on re-scan.
61. **Historical report replay** — open any previous scan's report; compare "this week vs last week" side-by-side.
62. **Annotation layer** — per-opportunity operator notes; feed back into scoring weights (learning loop).
63. **Mobile wallet card view** — store floor reference: barcode, unit COGS, buy-box target, net profit — phone-friendly.
64. **CSV full-export** — every field incl. breakdown data; not just the visible columns.
65. **Tag filter + bulk actions** — multi-select rows → tag, export, watchlist, or schedule re-scan.

**P2 — Enhancement Layer**

66. **Side-by-side comparison view** — two ASINs inline comparison of economics, velocity, competition.
67. **FBA vs FBM market share pie** — visual crowd depth per listing.
68. **Annualized monthly profit** — "est. $X/mo if we list 10 units/wk" realistic projection per opportunity.
69. **Estimated monthly profit per Costco run** — nets the whole pack (buy once, sell 200 units) — the truest "golden goose" number.
70. **Keyboard-first navigation** — j/k scroll, Enter detail, "." watchlist toggle; power-user speed.
71. **Dark/light theme + accessibility pass** — WCAG AA contrast, screen-reader labels, keyboard focus states.
72. **Photo attachments** — upload shelf tag + invoice image per opportunity (receipt-proof for ungating/IR).
73. **Batch progress UI** — live pipeline stage display during scans (Discovery → Matching → Economics → Scoring).
74. **Watchlist digest email** — weekly summary of watched ASINs' price/velocity deltas.
75. **Tier distribution overview** — donut chart of HIGH/MED/LOW/REJECT per scan; tune floors against reality.

---

## Part 4 — Filter Settings (25)

**P0 — High Value, Do First**

76. **Per-category ROI floors** — nicotine/OTC higher floor than cleaning/snacks (profit must scale with pack-count labor).
77. **Absolute profit AND relative ROI dual gate** — $10+ per unit AND 50%+ ROI; both configurable, both enforced.
78. **Repackaging cost slider** — $/unit labor + packaging; realistic numbers wipe out fake margins, so make it prominent.
79. **FBA seller ceiling** — 0/1/2/3/5/unlimited configurable; no hard-coded "1 max".
80. **Buy Box stability filter** — exclude listings whose Buy Box moved > X% in 30/60/90 days.

**P1 — Strong Value**

81. **Size/weight sliders** — max weight oz + max dimensions in; "small items only" becomes a real filter.
82. **Minimum pack count** — skip 2-count packs; require N+ (default 10+) per breakdown.
83. **Price range sliders** — min/max Amazon individual price AND min/max wholesale pack price.
84. **Demand floor per category** — 500/mo for OTC, 200/mo for premium pet; independent of ROI.
85. **Rating gate as a function of velocity** — near-baseline sales require 4.5★; high velocity relaxes to 4.0★ (per directive).
86. **Seasonality exclusion dates** — hide Christmas-only toys in March; hide allergy meds in November (unless stockpiling).
87. **Prime eligibility toggle** — mandatory / preferred / don't-care; Prime listings win Buy Box more.
88. **New-listing window** — only ASINs listed < 12 months (early competition), configurable.
89. **Margin-after-everything toggle** — include return reserve + prep + inbound + repackaging, or show simpler gross margin.
90. **Brand allowlist/denylist editor** — UI-managed brand lists; changes apply to next scan.

**P2 — Enhancement Layer**

91. **Store source toggle** — Costco only / Sam's only / both / weighted priority.
92. **Category multipliers** — weight nicotine 1.5×, snacks 0.5× in composite scoring (per profile, not master brain).
93. **Named filter profiles** — save/load/duplicate (e.g., "Nicotine Hunter", "Pet Premium", "Volume Play").
94. **AND/OR filter logic groups** — advanced: (profit ≥ $10 AND fba ≤ 2) OR (profit ≥ $25).
95. **BSR history window selector** — 7/30/90/365-day price and rank windows for stability metrics.
96. **Sales smoothing period** — 7-day vs 30-day average; short window captures spikes, long window hides noise.
97. **Shelf-life / expiry filter** — exclude items whose per-day consumption exceeds pack shelf life.
98. **Ungating-effort filter** — already gated / can-apply / apply + documents; weigh effort vs margin.
99. **Batch investment cap** — total COGS ceiling per buying run (e.g., "don't exceed $2,000/batch").
100. **ASIN blocklist** — permanently hide specific ASINs / brands / categories; operator-curated, persists across scans.

---

## Priority Summary

| Priority | Count | Effort | Value |
|---|---|---|---|
| P0 (do first) | 20 | Low-Med | Highest |
| P1 (strong value) | 40 | Med | High |
| P2 (enhancement) | 40 | Med-High | Good |

**Recommended sequencing:** Land P0 items 1-5 (data finding), 26-30 (consolidation), 51-55 (presentation), 76-80 (filters) as "Golden Goose 1.1". Then stack P1s. P2s ride along opportunistically.