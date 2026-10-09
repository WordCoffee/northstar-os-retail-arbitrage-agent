# SEO / AD LOOP — keyword → creative → feedback
Phase 5 deliverable · NorthstarOS Design Studio deep research
Author: SEO/ad-loop & feasibility subagent · Date: 2026-10-08 (all `accessed` dates UTC)

**Evidence labels (per RULES.md R0):** **VERIFIED** = directly observed on a public page/doc during this research.
**REPORTED** = vendor marketing, third-party article, or review claims it; not observed. **UNKNOWN** = not confirmed.

> Amazon-specific requirements are sourced only from Amazon properties where available
> (developer-docs.amazon.com SP-API, advertising.amazon.com Ads API, Seller Central help pages and
> Amazon PDFs on m.media-amazon.com). Third-party Amazon summaries are labelled REPORTED.
> Every Amazon requirement row carries an `accessed` date and is **date-sensitive**.

---

## 0. Method and reach

Public docs only. No logins, no trials, no API keys, no paid calls. Key technical note that shaped
everything below:

- Amazon Seller Central *help pages* (sellercentral.amazon.com/help/hub/...) render via JavaScript and
  returned only page chrome to `webfetch`. Content from those pages was therefore obtained through
  search-engine snippets that quote the page text, and is labelled **VERIFIED (snippet)**.
- Amazon **PDFs** hosted on `m.media-amazon.com` were downloaded directly and text-extracted
  (`pypdf`). These are full official documents and are labelled **VERIFIED**.
- Amazon Ads API docs are a client-side React app, but the docs publish an `llms.txt` index pointing
  at a raw-markdown CDN (`d3a0d0y2hgofx6.cloudfront.net/en-us/...`). Those pages fetched cleanly and
  are labelled **VERIFIED**. The full API table of contents (`toc2.json`) was retrieved and grepped.
- SP-API docs support appending `.md` to any page URL for markdown. Labelled **VERIFIED**.

---

## 1. How keyword-research tools expose data (and whether any expose it to a creative tool)

### 1.1 Amazon first-party (official)

**Brand Analytics Search Terms report** — `GET_BRAND_ANALYTICS_SEARCH_TERMS_REPORT`
(Reports API). VERIFIED. Fields, per the official SP-API Analytics Reports page:

- `dataByDepartmentAndSearchTerm`: `departmentName`, `searchTerm`, `searchFrequencyRank`,
  `clickedAsin`, `clickShareRank`, `clickShare`, `conversionShare`.
- Availability: sellers **and** vendors with the Brand Analytics SP-API role, registered in Brand
  Registry **and** a brand representative.
- `reportPeriod`: DAY / WEEK / MONTH / QUARTER; requests cannot span multiple periods.
- Output JSON. Report is **request-only** (not schedulable). Capped at approximately 12 million
  items.
- Covering 18 marketplaces incl. US, CA, MX, BR, ES, UK, FR, NL, DE, IT, SE, TR, SA, AE, IN, SG,
  AU, JP.

Important semantic: `searchFrequencyRank` is a **relative rank, not a volume**. Amazon publishes no
search volume number here. Third parties are explicit that the rank is relative and the gaps between
ranks are not disclosed (amalytix, sellersprite — REPORTED).

**Search Query Performance report** — `GET_BRAND_ANALYTICS_SEARCH_QUERY_PERFORMANCE_REPORT`.
VERIFIED. Fields:

- `dataByAsin` → `searchQueryData`: `searchQuery`, `searchQueryScore`, `searchQueryVolume`;
  `impressionData`: `totalQueryImpressionCount`, `asinImpressionCount`, `asinImpressionShare`;
  `clickData`: `totalClickCount`, `totalClickRate`, `asinClickCount`, `asinClickShare`,
  `totalMedianClickPrice`, `asinMedianClickPrice`, plus same/one/two-day shipping counts;
  `cartAddData`: counts, rates and shares;
  `purchaseData`: counts, rates and shares.

This is the strongest first-party query→ASIN performance join available programmatically, and it is
the single most important input for the target loop in §6. `searchQueryVolume` is Amazon's own
volume-ish field (it is labelled "search query volume", not exposed as raw monthly searches).

### 1.2 Keyword-data providers with public, documented APIs

| Provider | Exposure | Documented endpoints / fields | Label |
|---|---|---|---|
| **DataForSEO** | Full REST API with public reference docs | `dataforseo_labs/amazon/bulk_search_volume` (up to **1,000 keywords per request**; returns `keyword`, `search_volume`); `amazon/related_keywords`; `amazon/ranked_keywords`; `amazon/product_rank_overview`; `amazon/product_competitors`; `amazon/product_keyword_intersections`. Locations supported: US, Egypt, Saudi Arabia, UAE (per docs). | **VERIFIED** (docs) |
| **Jungle Scout** | Public REST API, JSON-API 1.0 shape, header versioning (`application/vnd.junglescout.v1+json`), API key from a Developer page, `marketplace` query param (us, uk, de, in, ca, fr, it, es, mx, jp), 6 endpoints | **Keywords by ASIN** (up to 10 ASINs → up to 100 keywords with search volume, trends, PPC bids); **Keywords by Keyword** (1 keyword + filters → up to 100 related keywords with search volume + competition); **Historical Search Volume** (weekly, up to 1 year in 1 call); **Product Database**; **Sales Estimates** (daily, up to 1 year); **Share of Voice** (brand SOV, PPC bid, search volume, conversion rate for top 3 products). Also publishes a Postman collection, an open-source Python client, and a Zapier integration. | **VERIFIED** (docs + help centre) |
| **Helium 10** | MCP server (Model Context Protocol) + Claude/GPT/Cursor connectors; **no public REST API docs found** | Public page states **"40+ MCP tools: Keyword Research, Reverse ASIN lookup, Product Discovery …, Ads Intelligence, Commerce Analytics"**, cross-tool data chaining, standard MCP, works with Claude, GPT, Cursor and custom agents, multi-account. **Available to Diamond-plan customers at no additional cost.** Magnet/Cerebro metrics named on the keyword-tools page: Search Volume, # of Competing Products, Title Density, Keyword Sales, Magnet IQ Score, Search Volume Trend. | **VERIFIED that the page claims this**; the actual tool list/response schema is **UNKNOWN** (needs an account) |
| **SellerSprite** | Public marketing pages and blog only | Blog describes Amazon Search Volume and Search Frequency Rank interpretation. No API docs found. | **UNKNOWN** for API surface |
| **Pacvue** | Marketing pages only | Keyword Intelligence: keyword volume history, CPC trends, organic and sponsored rankings, keyword-to-ASIN mapping; organic + paid Share of Voice. States Amazon category intelligence is powered by Helium 10's dataset. | **REPORTED** |
| **Perpetua** | Public help centre (Intercom) | Keyword Harvesting; Organic Rank Optimization (ORO); Rules incl. "Adjust bids based on Organic Rank"; Search Insights reporting; DSP Creatives Builder. | **VERIFIED (help-centre article titles/descriptions)** |

### 1.3 The direct answer to "does any keyword tool expose data to a creative/asset tool?"

**No keyword-research vendor exposes a documented, native integration into a creative/asset tool.**
What exists instead:

1. **Helium 10 MCP** is the closest thing. It is a *generic AI-agent* surface, not a creative tool —
   any MCP-capable agent (including, in principle, a creative agent) can call keyword/reverse-ASIN/
   ads tools. It is a pipe, not a pipeline. VERIFIED that the connector is advertised; the actual
  tool inventory and schemas are UNKNOWN.
2. **Jungle Scout's public API + Zapier** is a generic automation pipe with the same property.
3. **Amazon's own Ads API** does the reverse of what a creative loop needs: it *accepts* creative
   assets (§4.2) but exposes **no keyword-to-creative join**. Grepping the complete Ads API table of
   contents (`toc2.json`) found **zero** occurrences of "experiment" and **zero** creative-generation
   endpoints — only `creative-asset` *library* pages (upload / register / manage).

So: keyword data is machine-readable and cheap to fetch. Nobody has wired it into asset production.

---

## 2. How rank tracking works in the tools inspected

| Tool | Mechanism | Fields / semantics | Label |
|---|---|---|---|
| **DataForSEO** | SERP-scrape index, refreshed on their schedule | `ranked_keywords` returns, per keyword: `keyword_data.keyword_info.search_volume` + `ranked_serp_element.serp_item.amazon_serp` / `.amazon_paid` with `rank_group`, `rank_absolute`, `position`, `title`, `asin`, `image_url`, `price_from`, `price_to`, `is_best_seller`, `is_amazon_choice`, `rating`, `delivery_info`, plus `related_searches` items carrying `image_alt`. `serp_item` also carries `last_updated_time` and `previous_updated_time`. | **VERIFIED** |
| **DataForSEO** | `product_rank_overview` returns aggregate rank buckets | `metrics.amazon_serp` / `amazon_paid`: `pos_1`, `pos_2_3`, `pos_4_10`, `pos_11_100`, `count`, `search_volume`. Accepts up to 1,000 ASINs per request. | **VERIFIED** |
| **Helium 10** | "Keyword Tracker — Track Keyword Ranking Over Time" (product page) | Metric names and cadence not published. | **REPORTED** (name only) |
| **Pacvue** | Proprietary keyword-tracking database; organic + paid Share of Voice | Keyword volume history, CPC trends, organic and sponsored rankings, keyword-to-ASIN mapping; benchmark by keyword/product/category. | **REPORTED** |
| **Perpetua** | Organic rank used as an *input to bidding* | Help centre lists "Organic Rank Optimization (ORO)" and "Rules – Adjust bids based on Organic Rank"; a bid-adjustment help article names "Improve Organic Rank" as a use case for Keyword Boost and cautions organic rank gains "can take some time to actualize". | **VERIFIED (help centre)** |
| **Amazon** | No first-party organic rank | Searched the complete SP-API doc index and the Ads API TOC: **no organic rank / rank-tracking endpoint exists.** Search *Query* Performance (impressions/shares per ASIN) is the nearest first-party proxy and is not a rank. | **VERIFIED (absence)** |

**Practical consequence for Design Studio:** organic rank is a third-party, modelled, paid signal
(DataForSEO is the only one with fully public field-level docs). It is not something Amazon will hand
us. Any rank-tracked creative correlation is therefore built on provider data with unknown refresh
cadence, unknown SERP-personalisation bias, and per-request cost.

---

## 3. How ad search-term reports are surfaced — actual fields

### 3.1 Amazon Ads API v3 (official; deprecated 2027-06-30 — migrate to ads-v1)

Source: Amazon Ads API "Search term reports" guide, fetched as raw markdown. VERIFIED.

Shared configuration:

| | Sponsored Products | Sponsored Brands |
|---|---|---|
| `reportTypeId` | `spSearchTerm` | `sbSearchTerm` |
| Max date range | 31 days | 31 days |
| Data retention | 65 days | 60 days |
| `timeUnit` | SUMMARY / DAILY | SUMMARY / DAILY |
| `groupBy` | `searchTerm` | `searchTerm` |
| `format` | GZIP_JSON | GZIP_JSON |

Behavioural notes stated on that page (these matter enormously for a creative loop):
- Search-term reports contain performance **broken down by targeting expressions and keywords**.
- They include **only impressions that resulted in at least one ad click**.
- `keywordType` filter selects targeting expressions vs keywords
  (`BROAD`, `PHRASE`, `EXACT`, `TARGETING_EXPRESSION`, `TARGETING_EXPRESSION_PREDEFINED`).
- If a placement has no associated search keyword on a product detail page, the search term is an
  asterisk `*`. (The AMALYZE glossary, REPORTED, adds that Amazon uses `*` when the underlying query
  is below a privacy threshold, and those rows still spend.)
- Sponsored Brands search-term reporting is in **preview** and, during preview, data for campaigns
  with `isMultiAdGroupsEnabled = FALSE` is unavailable.

**Sponsored Products base metrics available in `spSearchTerm`** (selected; the full list is long):
`impressions`, `clicks`, `cost`, `costPerClick`, `clickThroughRate`, `purchases1d/7d/14d/30d`,
`purchasesSameSku*`, `unitsSoldClicks*`, `sales1d/7d/14d/30d`, `attributedSalesSameSku*`,
`unitsSoldSameSku*`, `salesOtherSku7d`, `unitsSoldOtherSku7d`, `acosClicks7d/14d`,
`roasClicks7d/14d`, `campaignId`, `campaignName`, `adGroupId`, `adGroupName`, `portfolioId`, `date`,
`startDate`, `endDate`, `keywordId`, `keyword`, `keywordBid`, `keywordType`, `matchType`,
`targeting`, `searchTerm`, `adKeywordStatus`.

**Sponsored Brands base metrics:** `campaignId/Name/Status/Budget*`, `adGroupId/Name`, `costType`,
`impressions`, `clicks`, `cost`, `purchases`, `purchasesClicks`, `sales`, `salesClicks`,
`unitsSold`, `addToList`, `addToListFromClicks`, `qualifiedBorrows(+FromClicks)`,
`keywordId`, `keywordText`, `keywordBid`, `matchType`, `searchTerm`, `date`, `startDate`, `endDate`,
`video5SecondViews`, `video5SecondViewRate`, `videoCompleteViews`, `videoFirstQuartileViews`,
`videoMidpointViews`, `videoThirdQuartileViews`, `videoUnmutes`, `viewabilityRate`,
`viewableImpressions`, `viewClickThroughRate`.

**Notable for a creative loop: the SB set includes video-completion metrics but no creative-asset
identifier.** There is no `adId`/`assetId` column in the search-term report, so you cannot, from this
report alone, tell which creative produced a given search term's clicks.

### 3.2 Console search-term reports (Seller Central)

**Sponsored Products** (Amazon Ads help, updated 2026-05-18) — VERIFIED (snippet). Lookback window
**65 days**; 2 time units (summary / daily); only terms with ≥1 click. Columns include
Customer Search Term, Portfolio name, Start/End Date, Currency, Spend, CPC, CTR, Sales (promoted /
halo), Units sold (promoted / halo), Purchases, Purchase rate, Match Type. Amazon notes that
alphanumeric entries in the Customer Search Term column correspond to ASINs and the PDP on which the
ad displayed, and that these appear for Sponsored Products **auto-targeted** campaigns and
product-attribute-targeted ad groups.

**Sponsored Brands** (Amazon Ads help, updated 2026-02-24) — VERIFIED (snippet). Contains Campaign
Name, Clicks, CTR, Cost Type (vCPM or CPC), Currency, Customer Search Term, Cost, CPC, VCPM,
Impressions, Start/End Date.

### 3.3 Search Term Impression Share (SIS) report — VERIFIED (snippet)

Contains `Customer Search Term`, `Search Term Impression Rank` ("the numeric rank of your
account-wide impression share relative to all the other advertisers generating impressions on the
same term"), `Search Term Impression Share`, Total ROAS, 14-day sales, clicks, CTR, CPC, impressions,
cost. **This is the only Amazon-sourced report that exposes a per-search-term competitive rank.**

### 3.4 Bulksheets search-term report — VERIFIED (Ads API docs, raw markdown)

Accessible via Sponsored ads → Bulk operations for Sponsored Brands and Sponsored Products only;
fixed **7-day lookback**; deliberately **excludes** some seller/vendor-specific lookback metrics
(e.g. 7-day advertised SKU sales, 14-day advertised ASIN sales). Columns:
`Product` (campaign type), `Campaign Id`, `Ad Group Id`, `Keyword Id` (read-only),
`Product Targeting Id` (read-only), `Campaign Name`, `Ad Group Name`, `Portfolio Name`, `State`,
`Bid`, `Keyword Text`, `Match Type`, `Product Targeting Expression`, `Customer Search Term`.

### 3.5 Console vs API gaps (official, VERIFIED)

Amazon's own "Advertising console vs. API reports" page states:
- The console search-term report contains **both keyword and targeting data broken out by search
  term**; to recreate it via API you must request **both** a target report and a keyword report
  segmented by `query`, then aggregate.
- Search terms appear in the API report **only if they have at least one click**, while the console
  report includes terms without clicks.
- The API **does not support segmenting Sponsored Brands target reports by `query`**.
- Search-term reports are **not available for Sponsored Display campaigns**.
- **Console report types not available via API at all:** Sponsored Products Performance Over Time;
  Sponsored Products and Sponsored Brands Search Term Impression Share; Sponsored Products Budget.

**Net:** the creative loop's feedback link can be built, but it must aggregate two report families,
accept a 65-day retention ceiling, and never assume it can see zero-click search terms. SIS — the
single most useful competitive field — is console-only.

---

## 4. Does ANY tool connect search-term data → brief → assets → performance → learning?

**Operator's belief tested: the loop gap is CONFIRMED, with one important partial from Amazon itself.**

### 4.1 The six links, and who (if anyone) closes each

| Link | What it requires | Who closes it today | Label |
|---|---|---|---|
| **L1** Search terms + ad performance → ranked insight | Search-term report × SIS × rank × query-performance join | Pacvue (Query-ASIN graph), Perpetua (keyword harvesting), Helium 10, DataForSEO, Jungle Scout | **REPORTED** |
| **L2** Insight → **creative brief** | A structured artifact: audience, objection, claim hierarchy, on-image copy candidates, module list | **Listing Optimization AI** (reviews → "Create Brief" → main-image recs, infographic concepts, lifestyle images, A+ modules, video screenplay). Amazon **Creative Agent** (product+audience research → storyboard). | **REPORTED** (vendor blog / Amazon page) |
| **L3** Brief → **asset variants** | Deterministic template + generative fill, brand kit enforcement | Amazon Creative Studio Image/Video Generator; Ideogram; FLUX; Gemini. Generic AI creative tools. | **REPORTED** (capability), **VERIFIED** (docs for the pipe) |
| **L4** Variants → **live** | Push to Amazon programmatically | **Amazon Ads creative asset library API** (`POST /assets/upload` → `PUT` → `POST /assets/register`); **SP-API Listings Items API** media attributes (`main_product_image_locator`, `other_product_image_locator_1..8`, `swatch_product_image_locator`); A+ Content API. | **VERIFIED** |
| **L5** Live → **measured performance** | Variant-level attribution | **Amazon Manage Your Experiments** (title, main image, bullets, description, A+) — console only. Ad-side: search-term report at campaign/ad-group level, **not** at creative level. | **VERIFIED (docs)** / **VERIFIED (absence of creative-level attribution)** |
| **L6** Performance → **learning** (feeds the next brief) | A store that updates brief generation from measured outcomes | **None found.** | **UNKNOWN → treated as absent** |

### 4.2 The closest verified partial: Amazon's own stack

- **Creative Studio / Creative Agent** (Amazon Ads pages, VERIFIED that these pages exist and
  describe the flow; the product requires a login so the capability is REPORTED). Officially
  described as: conducts product and audience research, brainstorms, develops concepts in storyboard
  format, generates ads across display, Sponsored Brands video, online video, audio, STV, and saves
  assets to the Creative Asset library for use in campaigns. Creative Agent is stated to be in **open
  beta, US advertisers only**. Image generation is stated available in CA, FR, DE, IN, IT, MX, ES,
  UK, US; video generation in the same list; Creative Agent **US only**. Advertiser-facing
  availability by ad product differs per feature (e.g. Image generation not available for Amazon DSP;
  Video generation not available for Sponsored Products or Sponsored Display).
- **Creative asset library API** — fully public, VERIFIED. Three calls: create an upload URL, PUT the
  bytes, register. `POST /assets/register` accepts `url`, `name`, `asinList`, `assetType`
  (`IMAGE`/`VIDEO`), `assetSubTypeList`, `versionInfo`, `tags`, `registrationContext`,
  `associatedSubEntityList` (brand entity ID via `GET /brands`), and
  `skipAssetSubTypesDetection`. The response returns `assetId` **and a machine-readable
  `failedSpecChecks` array** naming the program, the spec, the actual value, the expected values, a
  human-readable failure reason, and a stable `stringId` (e.g. `al-spec-video-frame-rate`,
  `al-spec-video-duration`, `al-spec-video-aspect-ratio`, `al-spec-min-audio-channel-count`).
  Assets go to `PROCESSING` then `ACTIVE`; video can take up to ~30 minutes because of transcoding.

  **This is the most important single finding for the loop:** Amazon already publishes a
  machine-readable creative-spec validation contract. It is a *rejection* report, not a pre-flight,
  but it proves the contract is expressible and shows the exact shape to imitate.
- **What Amazon does not provide:** any API to *generate* creative (no generation endpoint exists in
  the Ads API TOC), any join from search-term report to creative asset, and any programmatic
  experiment creation (see §6.7 in FEASIBILITY.md).

### 4.3 Third-party partials (all REPORTED, vendor or blog sources)

- **Listing Optimization AI** (listingoptimization.ai, described by an agency blog, 2025-10-13):
  market-intelligence report from reviews (by keyword or by ASIN) → "Create Brief" → brief with
  main-image recommendations, infographic concepts, lifestyle images, A+ content modules and video
  screenplay ideas → in-platform AI image generation with model choice (OpenAI or Google Gemini) →
  annotation/comments/regeneration for designer collaboration. **Two of six links, at most.** The
  input is *customer reviews*, not ad search-term performance, and there is no measured outcome fed
  back. The blog also notes a real product-identity risk in its own model comparison: one model
  "brings more creativity but sometimes modifies product details".
- **SalesDuo AI Creative Studio** (vendor blog, 2026-09-25): draft detail-page images, A+ images,
  titles, bullets, descriptions in one workflow, framed around COSMO / Rufus / Alexa for Shopping
  intent signals. **Link 2 + 3, no 5 or 6.**
- **Pacvue Query-ASIN Graph** (press release, 2019): aggregates ad performance + Amazon search-query
  data into a graph of query↔ASIN relationships and recommends that brands "improve the content and
  SEO of their product detail pages" where they lack click/conversion share. **Link 1 only, and the
  recommendation is manual.**
- **Perpetua / Pacvue / Helium 10 Ads**: search-term → bid, budget, negative-keyword and targeting
  actions. This is the industry-standard loop and it terminates at the *auction*, never at the
  *creative*.
- **Splitly** (Tracxn, REPORTED): the historical Amazon listing split-testing specialist is listed
  as **Deadpooled**. There is no incumbent dedicated listing-image testing vendor left.

### 4.4 Verdict

The loop as the operator framed it — search terms and ad performance → creative briefs → on-image and
copy variants → performance feedback → learning — is **not closed by any tool found**. Confidence:
**high**. The strongest evidence is not the absence of a competitor but the presence of two verifiable
structural blockers:

1. **Amazon publishes no creative-level performance attribution.** Search-term reports aggregate at
   campaign/ad-group/keyword/targeting. Amazon's own console-vs-API page confirms the API report
   cannot be made equivalent to the console report. Variant-level creative measurement exists only
   inside Manage Your Experiments, which is console-only and has no API.
2. **Amazon publishes no creative generation API and no keyword→creative join.** The Ads API TOC
   contains no generation endpoint and zero occurrences of "experiment".

---

## 5. Amazon indexing of text and imagery — claim-by-claim with confidence

| # | Claim | Source | Label | Confidence |
|---|---|---|---|---|
| 5.1 | Amazon's own A+ best-practice guidance is to **use text fields across modules, limit the amount of text embedded in images, and use descriptive Image Keywords (alt-text) for each uploaded image**. | Amazon *A+ Content Best Practice Guide* PDF, p.11 (downloaded and text-extracted) | **VERIFIED** | High |
| 5.2 | Alt-text is required-ish and policed: submitting image alt-text that "does not describe the image and that would not be useful for a customer using a screen reader application can result in content rejection". | Amazon Seller Central *A+ content guidelines* (GW8U76SSNTRTBX7), via quoted snippet | **VERIFIED (snippet)** | High |
| 5.3 | An Amazon employee on the official Seller Central seller forums states alt-text "does not show on the product detail page, but is used by visually impaired customers and screen reader apps, and helps your products in search results", and points at the Create A+ content help page. | sellercentral.amazon.com seller-forums thread, Amazon-staff reply | **VERIFIED** (official property; informal register) | Medium — authoritative-ish but a forum reply, not a spec |
| 5.4 | Amazon has **never** officially confirmed how heavily alt-text is weighted, or that A+ text is indexed. | myamazonguy (2025) and marissaputtagio (2026) both state this explicitly | **REPORTED** | Medium — but consistent across independent third parties and *not contradicted* by any Amazon doc found |
| 5.5 | **Text inside an image is not indexed by Amazon's internal search.** No Amazon document states on-image text is indexed; the strongest official signal is 5.1 (Amazon tells you to *limit* embedded text and to use text fields instead). | Absence + inference from 5.1 | **UNKNOWN (as a direct Amazon statement)**; the inference is **REPORTED**-strength | Low-Medium. **Do not build SEO strategy on this either way** |
| 5.6 | A+ **body text** is not indexed by Amazon but is crawled by Google; image alt-text is the highest-value indexed zone; comparison-chart headers partially. | keywords.am (2026), marissaputtagio (2026) | **REPORTED** | Low — directly contested between vendors |
| 5.7 | Amazon has **removed seller-managed alt text** in A+ Content and Brand Story and now auto-generates it with AI, cutting a former keyword-indexing path. | myamazonguy news post, 2026-04-15, citing Marketplace Valet and eStore Factory | **REPORTED** | **Low — unverified against any Amazon announcement.** Treat as a live risk, not a fact. Note the *A+ content guidelines* page as retrieved still describes alt-text rules (5.2), which is either a stale snippet or a partial/regional rollout |
| 5.8 | A+ alt-text has a character limit per image (third parties cite 100 characters). | keywords.am | **REPORTED** | Low — no Amazon page found confirming the number |
| 5.9 | Main-image content rules: pure white background (RGB 255,255,255), no text, logos, borders, colour blocks or watermarks, no multiple views, product fully in frame. Images 1,600px+ on the longest side for zoom; must not exceed 10,000px. | Amazon *General Guidance for Listing Optimization* PDF (official, text-extracted); *Amazon Home Selection Image Guide* PDF (official, text-extracted); Seller Central forum stickies quoting the Product image guide | **VERIFIED** | High |
| 5.10 | Search terms (backend keywords) guidance: generic words/synonyms only, no competitor brand names, don't repeat a word, single-space separated, no punctuation. | Amazon *General Guidance for Listing Optimization* PDF | **VERIFIED** | High |
| 5.11 | Amazon now requires `contains-synthetic-performer` in the `dc:subject` XMP field of image files containing photorealistic AI-generated people, and will display a disclosure "where applicable". An "AI-generated" checkbox also exists in the A+ Creative Assets uploader. | Amazon Seller Central *A+ content guidelines* (GW8U76SSNTRTBX7), via quoted snippet; corroborated by CNBC 2026-07-23 and an Amazon seller-forum announcement thread | **VERIFIED (snippet + official PDF style guide context)** | High |
| 5.12 | On images being generally AI-indexed for relevance: nothing official. | — | **UNKNOWN** | — |

**Design implication.** The SEO story for on-image creative is weak-to-unverified on the Amazon side,
and the strongest *official* guidance actively discourages heavy embedded text in A+ images. Amazon's
own recommendation is to put keywords in text fields and alt-text, and to keep on-image text large
enough to be readable on mobile. For Design Studio this means: **on-image text must be justified on
conversion/CTR grounds (and A/B-testable), not on indexing grounds** — and alt-text should be treated
as a first-class, per-image output of the creative pipeline rather than an afterthought, with the
caveat in 5.7 flagged as a live risk.

---

## 6. The target closed loop — definition and per-link data contract

**Definition.** For a given ASIN and marketplace, continuously:

```
[search terms + ad performance]  →  [creative brief]  →  [on-image + copy variants]
        ↑                                                          ↓
        └────────────[ learning store ]  ←  [ measured performance ] ┘
```

### Link 1 — Search terms + ad performance → Ranked Insight

Inputs: `spSearchTerm` / `sbSearchTerm` reports (aggregated), SIS report (console), Brand Analytics
Search Query Performance, third-party organic rank, listing snapshot.

Required data contract:

| Field | Source | Notes |
|---|---|---|
| `search_term` | Ads search-term report | `*` rows must be bucketed, not dropped |
| `clicks`, `impressions`, `cost`, `ctr`, `cpc`, `acos7d`, `roas7d`, `sales7d` | Ads API v3 | ≥1-click threshold means impressions are censored |
| `search_term_impression_share`, `search_term_impression_rank` | Console SIS report | Console-only → manual/periodic export |
| `search_query_volume`, `search_query_score`, `asin_impression_share`, `asin_click_share`, `asin_purchase_share` | SP-API Brand Analytics | Amazon's own query-level funnel |
| `organic_rank_group`, `organic_rank_absolute`, `rank_last_updated_at` | DataForSEO `ranked_keywords` | Provider freshness is not guaranteed |
| `query_family` (clustered terms) | Derived | Terms must be clustered before they mean anything for a brief |
| `marketplace_id`, `asin`, `captured_at`, `lookback_days` | — | 65-day retention ceiling is hard |

### Link 2 — Ranked Insight → Creative Brief

A **brief** must be a first-class, versioned, machine-readable artifact, not prose:

```
brief_id, asin, marketplace, generated_at, generator_version
hypothesis: {change, variable, expected_metric, expected_delta}
target_query_family[], primary_objection[], claim_hierarchy[{claim, evidence, source}]
audience: {segment, intent_stage, price_sensitivity}
on_image_copy: [{slot, char_limit, copy, source_query_id}]
module_plan: [{placement: MAIN|PT01..PT08|A+|SB, module_type, asset_count}]
brand_constraints: {palette[], font_lock, logo_placement_rules, prohibited_claims[]}
experiment_plan: {variant_count, success_metric, min_detectable_effect}
provenance: {query_ids[], review_ids[], rank_provider, rank_captured_at}
```

Every `on_image_copy` element must carry `source_query_id` so the loop can be audited and so the
learning store can score *which query produced which copy that produced which lift*.

### Link 3 — Brief → On-image and copy variants

Requires: a **reference-locked** product image (see FEASIBILITY §1), a **deterministic template**
that owns text placement (see §5), a brand kit, and a **compliance pre-flight gate** (see §6).
Output per variant:

```
variant_id, brief_id, template_id, prompt_hash, seed, model, model_version,
product_reference_asset_id, background_asset_id, text_layers[{slot,text,font,size,color,bbox}],
canvas: {w,h,dpi,format,bytes,color_space}, brand_kit_version,
preflight: {passed, checks[{check, result, deterministic|heuristic, detail}]}
```

Deterministic parameters (template, palette hex, font, size, bbox) must be **stored explicitly**, not
inferred back out of the pixels, or the learning store cannot attribute.

### Link 4 — Variants → Live

Two verified programmatic routes:

- **Listing images:** SP-API Listings Items API — `main_product_image_locator`,
  `other_product_image_locator_1..8`, `swatch_product_image_locator` via `putListingsItem` or
  `JSON_LISTINGS_FEED`; media must be reachable at a public HTTP(S) URL, a CloudFront URL, or a
  private S3 URL (private S3 needs a bucket policy granting `Media-Download-Role` `GetObject` and
  `ListBucket`). Note: **only MAIN, PT01–PT08 and SWCH are programmatic**; Seller Central's Image
  Manager supports additional variants that are not.
- **Ad creative:** Ads API `POST /assets/upload` → `PUT` → `POST /assets/register`, then reference
  the returned `assetId` when creating/editing a campaign. Budget for `PROCESSING` → `ACTIVE` polling
  (up to ~30 min for video).

Contract needs: `variant_id ↔ amazon_media_locator ↔ asin ↔ submitted_at ↔ submission_status`, plus
idempotency keys (private S3 objects are immutable — new content requires a new object key).

### Link 5 — Live → Measured performance

The hard link. Two very different measurement surfaces:

- **Listing-level (Amazon-owned, no API):** Manage Your Experiments. Bayesian, results updated
  weekly, significance threshold 66%, version-A vs version-B on a single ASIN with the same ASIN set,
  "run to significance" and "auto-publish" options. It measures units, sales, conversion rate,
  units-per-unique-visitor and sample size per version. **Variant testing must be aligned to this.**
- **Ad-level (API):** search-term report aggregated to campaign/ad-group. **No creative dimension.**

To attribute a creative variant, the pipeline must therefore **split by time or by ad group** — i.e.
one variant per ad group, or sequential flights — and accept that Amazon's own ad reports will never
tell you which asset drove a click. Any tool that claims creative-level Amazon attribution is
over-claiming (UNKNOWN/RISKY unless it uses MYE).

### Link 6 — Measured performance → Learning

Contract: an outcome record joined back to the brief and variant:

```
outcome_id, variant_id, brief_id, experiment_id, metric, value, baseline_value,
sample_size, significance, window_start, window_end, decision: WINNER|LOSER|INCONCLUSIVE,
confounders: [{type: price_change|promotion|competitor_launch|seasonality, note}]
```

Learning rules must be **reviewable and versioned**, and must reject conclusions where
`sample_size` is below MYE's minimum threshold or where a confounder overlaps the window. The MYE
guide is explicit that ending early risks over-estimating impact or picking the wrong version — the
same rule should govern the loop's own auto-promotion.

---

## 7. Coverage limits (R7) — what I did NOT inspect

- **No account surfaces.** Anything behind a login: Amazon Ads console, Seller Central dashboards,
  Helium 10, Jungle Scout, Pacvue, Perpetua, SellerSprite, Amazon Creative Studio, Amazon Ads MCP
  server, Ideogram/BFL/Gemini playgrounds. Capabilities inside those products are REPORTED at best.
- **Seller Central help pages** could not be rendered (JS-only). Their content here comes from
  search-engine snippets quoting them (**VERIFIED (snippet)**) and from official Amazon PDFs. Any
  requirement in this file marked "snippet" could be stale or region-specific.
- **Field-level schemas** for Helium 10 MCP, Jungle Scout's actual JSON responses, Pacvue and
  Perpetua APIs: UNKNOWN. Only endpoint names/descriptions were observable.
- **No live ad data.** No search-term report was ever pulled. All report-field descriptions are from
  documentation.
- **Cost figures** for Helium 10, Jungle Scout, Pacvue, Perpetua, SellerSprite: not gathered in this
  phase (pricing pages were outside this deliverable's scope).
- **Amazon internal ranking mechanics:** no Amazon document explains ranking weights, alt-text
  weighting, or whether on-image text is indexed. Every claim in §5 beyond 5.1/5.2/5.3/5.9/5.10/5.11
  is third-party and contested.
- **The "Amazon removed alt text" report (§5.7)** was not confirmed against any Amazon
  announcement. It is recorded as a risk to re-check, not as fact.
- **Ads API v1 (ads-v1) migration docs** were not fetched; v3 deprecates 2027-06-30, so the migration
  target's report shapes should be re-verified before build.
