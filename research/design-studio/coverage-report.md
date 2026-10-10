# Coverage Report ? Design Studio Research

Honest accounting. Pulled at 2026-10-10. Every target the master directive set
is listed with the ACTUAL number achieved.

## Targets vs actual

| Target | Target | Actual | Status |
|---|---|---|---|
| Total vetted sources | 300+ | **149** | **SHORT by 151** |
| YouTube transcripts | 60+ | **0** | **NOT DONE ? zero transcript searches run** |
| Review / complaint sources | 40+ | **20** | **SHORT by 20** |
| Amazon-official docs | 30+ | **76** | **MET** (76 Amazon-sourced rows) |
| Competitor deep-dive files (min 20 sources + 8 transcripts each) | 7 named | **7 files written**, but 0 of the 8-transcripts-each requirement met | **STRUCTURE MET, TRANSCRIPT REQUIREMENT NOT MET** |

## Sources by track

| Track | Sources |
|---|---|
| B ? Amazon requirements | 76 (all Amazon-official) |
| A ? Competitors (incl. identity verification) | 69 |
| C ? SEO/keyword (Helium10/Pacvue) | 4 |

## Sources by type

- official_doc: 43
- vendor_blog: 23
- official_site: 19
- official_pdf: 10
- review_site: 9
- forum_thread: 8
- official_pricing: 8
- agency_blog: 4
- official_marketing: 3
- startup_db: 3
- official_blog: 3
- legal_terms: 3
- official_news: 3
- trade_press: 2
- forum_reddit: 2
- competitor_platform: 1
- vendor_doc: 1
- academic_paper: 1
- competitor_pricing: 1
- forum_figma: 1
- help_doc: 1

## Claim tags

Tags were applied per claim inside every track file, not counted as a separate
column. Distribution by the class of source the tag rests on:
- **[documented]**: Amazon Seller Central / Ads help and legal pages, vendor
  pricing and help pages, legal terms ? 88 rows of quality 4-5.
- **[observed]**: on-site patterns, forum threads from Amazon staff, App Store
  review mining with a stated methodology.
- **[inferred]**: agency/vendor blogs, third-party reviews, trade press, and
  startup databases ? explicitly labelled in every file.

## What was NOT verified (do not rely on these)

1. **Image text and ranking.** A vendor guide states plainly that Amazon has not
   published documentation on which image signals affect recommendations. Two
   vendors publish irreconcilable numbers (22% vs 63.9% non-overlap with
   page-one). Treat every percentage as vendor-measured.
2. **A+ alt-text removal.** One trade-press claim that Amazon is removing
   seller-written alt text from A+ modules 2025-2026. Single source, unverified.
3. **Creatify case-study percentages** (669% adoption growth, 47.6% CTR
   increase, 73% ROAS improvement) are vendor self-reported.
4. **Photoroom performance claims** (+93% lower editing cost, +56% sell-through,
   +77% basket value) are vendor self-reported.
5. **Pacdora/Packify testimonials** are vendor-published, with the one
   substantive complaint (no sheet-nesting for print assembly) also taken from
   that vendor surface.
6. **Holo's 4,268-customer / 4.9-5 rating and PicCopilot's "CTR +54.7%"** are
   vendor-reported.
7. **No pricing was captured** for Mokker, Pixelcut, Kling, Runway, Veo,
   Hailuo, HeyGen, Arcads, MakeUGC, Midjourney, Jasper Art, or Firefly Foundry
   (enterprise contact-sales).
8. **Non-US specs** (EU Store tiles, JP Brand Registry) were not captured.

## Known research errors avoided (recorded for audit)

- **Packify treated as separate**: resolved ? Packify is Pacdora's brand.
- **Canva Magic Studio benchmarked**: resolved ? the brand is retired; the
  replacement is Canva AI 2.0.
- **"Holo AI" conflated with Holo**: resolved ? holo-ai.dev is a different
  German company.
- **"Magic Studio" / "Magic Studios" collisions**: resolved and recorded in
  identity-verification.md.
- **PicoPilot features invented**: avoided ? no deep-dive written for an
  unresolved identity.

## Pre-existing corpus preserved

The operator's 325-source tree at
`research/design_studio_deep_research_20261008/` is a separate, earlier corpus.
Per rule 3 it was NOT deleted and was NOT merged; the two corpora have not been
de-duplicated against each other, so a combined unique count is not claimed.
This corpus's 149 sources are the Phase 1 deliverable.

## Deliverables produced

- `sources.db` and `sources.md` (index with quality scores and a query log)
- `CHECKPOINT.md`
- `competitors/canva.md`, `figma.md`, `pacdora-packify.md`, `creatify.md`,
  `holo.md`, `adobe-firefly.md`, `product-photo-tools.md`, `video-ugc-tools.md`,
  `amazon-native-tools.md`, `identity-verification.md` (10 files)
- `amazon-requirements.md`
- `seo-keyword-tiein.md`
- `brand-voice-learning-loop.md`
- `ux-teardown.md`
- `whitespace.md`
- `SYNTHESIS.md`
- `coverage-report.md` (this file)

Phase 0 build artifacts also delivered before this research phase:
`/design-studio` route + DesignStudio.jsx, merged rail (21 services), the
`ds_projects`/`ds_assets`/`ds_jobs` backend store and its API, and the
21/21 operator smoke verification.
