# SEO + Keyword + Search-Term Tie-In (Northstar's differentiator)

Track C of the Design Studio research corpus. Pulled at 2026-10-10.
Tags: `[documented]` = Amazon/vendor primary source, `[observed]` = seen
directly, `[inferred]` = vendor-reported or derived.

## 1. How creative assets can be SEO'd

### 1.1 Image text (OCR)
- A vendor guide states plainly that Rufus is multimodal and "sees" images using
  Computer Vision and OCR, that infographic text is read, and that alt text in
  A+ now provides critical context for the AI, giving the contrast of a bad alt
  ("Blender image 1.") against a Rufus-optimised alt ("Woman making green
  smoothie with high-speed blender using tamper tool to crush ice") ? and
  asserting this tells COSMO the product is compatible with "Ice" and "Green
  Smoothies" and includes a "Tamper Tool" [inferred ? agency blog, not Amazon].
- A competing vendor guide contradicts the confidence: "Amazon has not published
  documentation specifying exactly which image signals influence recommendation
  outcomes, how visual analysis is weighted relative to listing text, or what
  image features are most influential" [documented by that vendor AS AN ABSENCE].
- A trade-press analysis claims A+ Content body text is NOT indexed by A9 or
  COSMO and instead trains the assistant through conversions [inferred ? single
  claim, unverified].
- Amazon's OWN Store guidance actively pushes against embedded image text:
  "Uploading images with embedded text is not encouraged as the text will not be
  readable by search engines ? outside of Amazon ? or users who rely on screen
  readers" [documented]. So Amazon documents that image text is invisible to
  EXTERNAL search engines and screen readers, and simultaneously vendors claim
  an internal AI reads it. Both can be true, and the design must serve both.

**Design consequence:** we can honestly claim "make your listing internally
consistent" and "make your A+ alt text genuinely descriptive for screen
readers", because Amazon documents both. We must NOT claim "image text is
indexed and will raise your rank", because no Amazon source confirms it.

### 1.2 Alt text / image keywords
- A+ Content: alt text is a REQUIRED field per image module, and submitting
  alt text that does not describe the image and would not be useful to a
  screen-reader user "can result in content rejection" [documented].
- Live PULL/Write path? The API already parses every Home Feed / house feed block
  with the correct ``line_card`` + ``alt_on_error`` behaviour [observed].
- **CRITICAL UNCERTAINTY**: a trade-press piece claims Amazon is REMOVING
  seller-written alt text from A+ Content modules in a phased rollout that began
  in 2025 and continues through 2026, with an AI generating image descriptions
  instead, and that Amazon has published nothing about it [inferred ? single
  source]. Building a full alt-text authoring workflow on this is a bet.
  **Open question for the operator.**

### 1.3 A+ copy, video titles, Brand Story, Storefront, social
- A+ Content can add images and text into five to seven content modules in the
  Product Description section; Brand Story appears in a dedicated "From the
  brand" slot and links to other products and the Brand Store [documented].
- A+ Content is "intended to showcase unique aspects of the product or brand"
  and images/text must be unique to A+ ? reusing gallery images is rejected
  [documented].
- Manage Your Experiments lets you A/B test product title, main images, bullet
  points, product description, A+ Content and Brand Story, with results
  reporting sales and conversion plus the probability that the winning content
  is better [documented]. This is Amazon's own measurement surface.
- Storefront: image tiles can link to a Store page or product detail page;
  embedded text is discouraged because external search engines and screen
  readers cannot read it [documented].
- Social posts driving external traffic: Amazon Attribution exists as the
  measurement mechanism (not covered in depth this pass ? flagged).

## 2. Mapping ranked keywords and ad search terms to creative briefs

### 2.1 What exists today
- **Helium 10 Listing Builder** is the closest existing implementation of
  keyword-to-listing: it combines keyword discovery, keyword bank management and
  AI listing generation in one workflow; accepts up to 5 product images (up from
  1) and up to 2 ASINs for Rufus insights; auto-strips brand names from keyword
  phrases; auto-moves unused root keywords (misspellings, non-English terms) to a
  Generic Keywords section to maximise indexing coverage; and lets you input a
  COMPETITOR ASIN to infer tone and positioning, or describe the tone manually,
  with the AI applying a consistent brand voice across the full listing
  [documented, help centre article dated 2026-05-13]. It also pushes content to
  the live listing. **It stops at text** ? it produces no images, no A+ layouts,
  no ad creative [documented by the tool taxonomy: 30+ tools, none an image or
  video editor].
- Amazon itself offers no keyword-to-creative path at all.
- None of the creative tools in Track A accept a keyword cluster as an input
  (verified across Canva, Figma, Creatify, Holo, Pebblely, Photoroom, Flair,
  Claid, Pacdora).

**This is the white space.** Every seller already has the keyword data; no tool
turns it into a creative brief.

### 2.2 What Northstar OS already has (from the codebase)
- `products` table (1,024 rows: 173 `data_kind='live'`, 851 `data_kind='demo'`)
- `keywords` table (10 rows, with source, search_volume, relevance_score)
- `keyword_performance` table (4 rows: organic_rank, sponsored_rank,
  impressions, clicks, spend, orders, revenue, acos, tier, movement)
- `search_query_performance` table (0 rows currently, but the schema carries
  impressions, clicks, cart_adds, purchases, impression_share, click_share,
  cart_share, purchase_share, search_frequency_rank)
- `campaigns` (4 rows) and `campaigns.campaign_name`
- `live_pulls` (3 rows, real chocodata pulls from 2026-09-23)
- The API already exposes `/api/products/finder` with filters for min_roi_per_unit,
  min_monthly_sales, max_fba_sellers, and a stock-first read path through
  `live_catalog.get_stocked()` which filters `data_kind='live'`
- The Design Studio backend (`ds_projects`, `ds_assets`, `ds_jobs`) now exists
  with a `metadata` JSON column and `source_record_id` / `source_record_type`
  / `pulled_at` columns specifically designed to carry this lineage

**The wiring is therefore short**: a keyword-cluster row ? a creative brief
record linked by `source_record_type='keyword_cluster'`.

### 2.3 The mapping we should build (proposed)
1. Take a keyword cluster (e.g. the `tier`/`movement` grouping already computed
   in `keyword_performance`, or the top N by `search_volume` from `keywords`).
2. Derive the *claim* the creative must make, from the cluster's head term plus
   the product's real attributes (from the `products` row).
3. Derive the *slot* the creative must fill, from the ranking position: a term
   with organic_rank present but no sponsored_rank is a hero-shot problem; a term
   with impressions and no clicks is a CTR/thumbnail problem; a term with clicks
   and no purchases is a conversion/A+ problem. This is derived from Amazon's own
   stated traffic-vs-conversion split in Manage Your Experiments [documented:
   title and image experiments drive traffic; images, A+ and Brand Story
   experiments drive conversion].
4. Write the brief with the source keywords attached, so the operator can see
   which search terms produced which asset.
5. Feed ad search terms (`search_query_performance`) into the hook/angle
   selection for the Video & UGC section.

## 3. Closed-loop measurement: which creative variant moved CTR/CVR/ranking?

### 3.1 Data sources that exist
| Source | What it gives | Status |
|---|---|---|
| Manage Your Experiments | Version A vs B on title/image/bullets/description/A+/Brand Story, with sales, conversion and probability-the-winner-is-better; auto-publish | Amazon-documented; requires Brand Registry + traffic-eligible ASIN |
| Ads API (via Amazon Ads console) | Impressions, clicks, spend, orders, ACOS per ad/creative | Documented specs; not yet wired in Northstar |
| SP-API | Listing, order and inventory data | Not wired in Northstar |
| Brand Analytics | Search terms and alternate purchase behaviour | Requires Brand Registry |
| Amazon Attribution | External traffic (social) measurement | Not covered in depth this pass |
| A+ Content experiments | Experiment on A+ specifically; both versions must be applied to the exact same ASIN set | Documented in the MYE best-practice guide |
| Amazon Search Query Performance report | Per-query impressions/clicks/cart-adds/purchases and share metrics | **Schema already exists in Northstar** (`search_query_performance`), 0 rows populated |

### 3.2 The closed loop Northstar can honestly offer
Because Manage Your Experiments is Amazon's own tool and it reports per-Version
outcomes, the honest loop is:
1. Produce Version A (current) and Version B (new) in Design Studio from the
   same brief and the same ASIN set (Amazon requires the exact same ASINs or
   the experiment cannot be set up) [documented].
2. Hand the pair to Manage Your Experiments (export/checklist, not auto-publish).
3. Record the outcome back against the project and the brief.
4. Promote the winner into the brand-kit / template so the next brief starts
   from what worked.

Northstar must NOT claim to measure ranking change from a creative, because
Northstar has no rank-history-per-creative data and Amazon does not expose one.

## 4. Where tools stop today
- Helium 10: keywords ? listing TEXT. Stops before any image, A+ layout, or ad
  creative [documented by tool taxonomy].
- Pacvue: ads/listing at the data layer; Helium 10 is part of the Pacvue family
  [documented]. No creative production.
- Canva/Figma: creative with no keyword input at all.
- Creatify/Holo: creative from a URL, no keyword input.
- Nobody maps ad search terms to a creative hook.
- Nobody pre-checks Amazon compliance before generation.
- Nobody records provenance per asset.
- Nobody ties creative variants back to Manage Your Experiments outcomes.

**Four of those seven gaps are cheap for Northstar to close, because it already
holds the keyword, product and (soon) creative data in one store.**

## 5. Open questions for the operator
1. Do we author A+ alt text, given the unverified claim that Amazon is removing
   seller-written alt text during 2026?
2. Do we build the search-term-report ingestion path first (the schema exists,
   it is empty) before or after the Design Studio write path?
3. Do we attempt Amazon Attribution measurement for social-driven external
   traffic, or scope that out for Phase 1?
4. Should a creative brief be allowed to reference `data_kind='demo'` product
   rows? Current decision: NO ? only live rows, per the zero-sample-data rule.
