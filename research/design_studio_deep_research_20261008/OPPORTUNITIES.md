# OPPORTUNITIES — 22 differentiated feature concepts

**Date:** 2026-10-08 · **Phase 7 deliverable (items 5)** · **Status:** PROPOSED — nothing here is built or committed.

Every concept below is labelled **PROPOSED**. Each one is tested against the delivered evidence:
`COMPETITOR_MATRIX.csv` (18 competitors), `WORKFLOWS.md` (8 workflows, 13 patterns),
`SEO_AD_LOOP.md`, `FEASIBILITY.md`, `PHASE0_ENTITY_RESOLUTION.md`, plus the repo audit in
`reports/CREATIVE_DESIGN_INVENTORY_20261008.md`.

**Why there is room at all.** Amazon's own AI creative tools are free, ASIN-first and native to the ad
console (`PHASE0` §3, S221–S224). No keyword vendor exposes creative data, and no creative tool
exposes keyword data (`SEO_AD_LOOP.md` §1.3, VERIFIED). So the differentiation cannot be generation
quality or price. It has to be: the seller's *own* product photography, cross-surface consistency,
compliance as a hard gate, claims governance, and the loop.

---

## Scoring key

| Field | Meaning |
|---|---|
| **Seller problem** | the pain it removes, sourced where possible |
| **Mechanism** | how it works, concretely |
| **Master-brain dependency** | which data contract it reads or writes |
| **SEO / ROI hypothesis** | the expected effect, explicitly a hypothesis |
| **Amazon safety** | the compliance and account-safety consequence |
| **Validation** | the cheapest experiment that would prove or kill it |
| **Build now / later** | feasibility verdict from `FEASIBILITY.md` |

---

## A. The keyword-bound creative loop (the core thesis)

### O-01 · Keyword-bound asset binding — **PROPOSED**
- **Seller problem:** sellers produce images that look fine but are not tied to any search term, so they cannot tell which creative won which term.
- **Mechanism:** every asset record carries `bound_search_terms[]`, `tier`, and `historical_orders`. Shown in the inspector; used by O-02, O-05, O-14.
- **Dependency:** reads `keyword_performance` (searchTerm, impressions, clicks, spend, orders, sales, acos) already produced by `ads_api_importer.run_search_term_report()`; reads `ad_pilot.classify_keyword_tier()`.
- **SEO/ROI hypothesis:** binding makes the O-14 learning loop possible; without it there is nothing to learn.
- **Amazon safety:** neutral — metadata only, no claim risk.
- **Validation:** take 5 live search terms with ≥10 orders, bind 3 assets each, and check the binding survives a round-trip export. No provider call needed.
- **Build now.** Pure UI + existing contract.

### O-02 · Keyword-aware creative brief — **PROPOSED**
- **Seller problem:** briefs are written from intuition, so the creative and the ad copy optimise for different terms.
- **Mechanism:** brief generation pre-fills the target terms from `keyword_performance`, ranked by orders and tier, and the brief carries them into every generated variant.
- **Dependency:** reads keyword tiers + search-term performance; writes the brief record.
- **SEO/ROI hypothesis:** tighter term↔creative alignment improves click-through on the terms that already convert.
- **Amazon safety:** neutral.
- **Validation:** compare a keyword-prefilled brief against an operator-written one for 10 ASINs; measure whether the diff is worth the automation.
- **Build now.** The data already exists in the repo; only the brief UI is missing.

### O-03 · On-image copy for humans, not for crawlers — **PROPOSED** (premise corrected)
- **Seller problem:** sellers write on-image copy for aesthetics, so it reads badly at thumbnail size and doesn't help a buyer decide.
- **Mechanism:** suggest headline/sub-head copy drawn from the bound terms, with the `COPY_ROLES` word budgets already in `presets.js`; flag when the headline shares no term with the bound set.
- **⚠ Premise correction from the research:** the operator's brief framed this as *image-text SEO* — on-image copy that matches indexed and ranked terms. **Amazon's own guidance says the opposite.** Amazon's A+ guides instruct sellers to "limit the amount of text embedded in images" and to use the descriptive text fields instead, *because text inside images is not read by search engines or screen readers* (`AMAZON_REQUIREMENTS.md` §3, S411, S412, S414). The Stores guidelines repeat it verbatim, and Amazon's KDP A+ examples page says "Don't add text to your background image. Add text to the overlay box" (S414).
- **Revised framing:** this is a **human-comprehension and conversion feature, not an SEO feature.** The value is legibility and decision speed at thumbnail size. Any claim that it improves ranking is **not supported by Amazon's own documentation** and must not be made in the UI or in marketing.
- **Dependency:** reads bound terms; no rank data needed (and `SEO_AD_LOOP.md` §2 notes organic rank is a third-party modelled signal anyway).
- **SEO/ROI hypothesis:** improved legibility may lift click-through. Ranking effect: **no evidence, and Amazon says text in images is not indexed.**
- **Amazon safety:** on-image text is **prohibited on the MAIN image** entirely; on secondary images the prohibition is ambiguous (`AMAZON_REQUIREMENTS.md` §2). Sellers on Amazon's own forums report Premium A+ images rejected for containing a brand logo with the reason "text is no longer allowed on images" (S471), and product images flagged over text that is part of the physical product itself (S473). **This must be gated per content-type and default to off on anything Amazon is tightening.**
- **Validation:** before building anything, re-verify Amazon's current secondary-image text rule and note the date. Then A/B the *legibility* of copy variants on thumbnails.
- **Build now for A+ text-overlay modules only** (where Amazon explicitly provides a text box beside the image), not as a general image-text renderer.

### O-14 · Creative performance-learning loop — **PROPOSED**
- **Seller problem:** results live in the ad account and never inform the next creative.
- **Mechanism:** the 7-step loop in `mockups/out/08-learning-loop.svg` — search terms → briefs → variants → pre-flight → publish → performance → learning, with winners written back to the master brain.
- **Dependency:** all four contracts in `SYNTHESIS_NOTES.md` §1.4, which already exist in the repo.
- **SEO/ROI hypothesis:** over time the winning term↔creative pairings get reused, raising effective conversion without extra spend.
- **Amazon safety:** only measured, sourced performance data is written back. No inferred results.
- **Validation:** run one full cycle on 3 ASINs offline with recorded data, and check the loop closes without inventing a number.
- **Build now (measurement link later).** The write-back and read paths are local and free; only the performance-ingest link needs a connected source. Until then it reads UNKNOWN rather than a placeholder.

---

## B. Compliance and account safety (the trust wedge)

### O-04 · Compliance pre-flight scan — **PROPOSED**
- **Seller problem:** a listing is suppressed or an experiment fails to start because the image broke a rule nobody checked.
- **Mechanism:** deterministic checks on raster size, file type, product fill, on-image text, file size, colour space — run before export, and blocking.
- **Dependency:** none. Rules are **data** (rows with source + accessed date), not code, so they can be corrected without a deploy.
- **Amazon safety:** this *is* the safety feature. `FEASIBILITY.md` §6 separates deterministic hard gates from heuristics that must only flag.
- **Validation:** encode ~20 rules from Amazon's own pages, then run them against the repo's existing 21 format presets and see how many already fail. That number is the evidence.
- **Build now.** `FEASIBILITY.md` §6.1 marks the deterministic checks as implementable hard gates.

### O-05 · Listing-to-ad consistency check — **PROPOSED**
- **Seller problem:** the ad says "no sugar" while the listing says "unsweetened"; the ad is suppressed or the seller is accused of a mismatch.
- **Mechanism:** compare claims, price, pack count and title terms between the listing doc and the ad doc; block export on a substantive mismatch.
- **Dependency:** reads the listing record (repo has `listing_forge`) and the ad record (`ad_pilot`).
- **Amazon safety:** directly protective.
- **Validation:** hand-check 10 real listing↔ad pairs for mismatches and see whether the check catches them.
- **Build now.** Pure string/spec comparison.

### O-06 · Claims guardrail with an evidence ledger — **PROPOSED**
- **Seller problem:** sellers paste marketing claims into images; some are prohibited, some need evidence, and the cost of getting it wrong is account health.
- **Mechanism:** a library of approved / blocked / needs-evidence phrases. A blocked phrase **cannot be typed into a text layer** — it is not a warning at export. Every claim requires an attached evidence source.
- **Dependency:** brand voice contract plus a new claims store; align with the repo's existing `PROMO_COMPLIANCE.md` and `LEGAL_REVIEW_PACKAGE.md`.
- **Amazon safety:** the highest-value safety feature in the set. Fewer claims, safer listing.
- **Validation:** draft the blocked list from Amazon's own prohibited-claims pages; have the operator review before it is enforced.
- **Build now.** It is a filter plus a lookup table.
- **Note:** who authors the lists is an open operator question (`SYNTHESIS_NOTES.md` §7.4).

### O-07 · Content-type compliance profiles — **PROPOSED**
- **Seller problem:** one rule set applied to everything. The main image forbids text; A+ content *requires* structured modules.
- **Mechanism:** selecting the content type loads that type's rule profile, so the main image can't accidentally get a badge and A+ can't ship without its modules.
- **Dependency:** driven by the O-04 rule store, seeded from `AMAZON_REQUIREMENTS.md`.
- **Verified rules now available to encode:** main image (white bg, ≥85% product fill, no text/logo/border/colour block, out of packaging, 500–10,000 px, >1,000 px preferred for zoom, PNG/JPG/TIFF/non-animated GIF); A+ Basic and Premium per-module minimum sizes and character limits; A+ global file rules (JPG/BMP/PNG, ≤2 MB, ≥72 dpi, **RGB — CMYK not supported**); background-video tile (1,280 × 640 min, 2–20 s, MP4 H.264).
- **Amazon safety:** removes an entire class of silent error.
- **Validation:** encode the ~60 verbatim spec rows from `AMAZON_REQUIREMENTS.md`, then run them against the repo's existing 21 format presets and count how many already fail. **That count is the deliverable's own headline metric.**
- **Build now.**

### O-04b · Audit the repo's existing format presets against Amazon's published specs — **PROPOSED, do this first**
- **Seller problem:** the repo already ships 21 format presets, several of which do not match Amazon's published specs. Building a studio on top of them would enshrine the error.
- **Finding (verified):** `northstar-os-ui/src/studio/engine/presets.js` declares `aplus-a: A+ wide banner 970×600`, `aplus-b: A+ standard 300×300`, `aplus-c: A+ comparison 970×300`, and `amz-main 1600×1600`. Amazon's own module-guide PDFs specify **Premium Full Image at 1464 × 600** (desktop min), **Basic Comparison Chart images at 150 × 300**, and **Four Images & Text at 200 × 200** (`AMAZON_REQUIREMENTS.md` §4–§5, S410, S413). `1600 × 1600` for the main image is compliant (Amazon's range is 500–10,000 px with >1,000 px preferred) — that one is fine.
- **Mechanism:** a spec-correction table, shipped as data with source + accessed date, replacing the wrong values and leaving the rest untouched.
- **Validation:** the diff is the evidence. Reproduce it before writing any new format.
- **Build now, before anything else.** This is a data fix with zero provider cost and it prevents an entire category of downstream non-compliance.

### O-08 · Experiment-ready pair generation — **PROPOSED**
- **Seller problem:** A/B testing listings is the highest-leverage conversion lever, and Amazon's own Manage Your Experiments does it — but **there is no API** (`FEASIBILITY.md` §7.2, VERIFIED by absence from the SP-API index and the Ads API TOC).
- **Mechanism:** generate *two sufficiently different, individually compliant* variants plus a handoff manifest the operator pastes into MYE. Never claim to create an experiment.
- **Verified MYE parameters to respect:** A/B on title, main image(s), bullet points, product description, A+ Content and Brand Story; professional seller + Brand Representative + Brand Registry; ASIN must belong to the brand **and have had enough recent traffic**; Bayesian, weekly updates, concludes at **≥66% significance**; reports units, sales, conversion rate, units sold per unique visitor, sample size and a projected one-year impact; auto-publish and "run to significance" are **beta, title and image only**; a similarity guard warns when versions are too similar.
- **Dependency:** reads the compliance profile (O-04/O-07) and the doc engine.
- **Amazon safety:** Amazon states that content failing validation — **e.g. a non-white background in a category that requires it** — will not start as scheduled, reported with an error code. So compliance gating protects the experiment, not just the listing. This is the single strongest argument for making pre-flight a hard gate.
- **Validation:** produce a pair set for 3 ASINs, confirm both pass pre-flight and differ substantively enough to clear Amazon's similarity guard.
- **Build now (v1 as manifest export).**

---

## C. Product fidelity and the seller's own assets

### O-09 · Reference-locked product layer — **PROPOSED**
- **Seller problem:** generated product imagery drifts from the real product — wrong label, warped packaging, invented details.
- **Mechanism:** the product is an explicit layer, immutable by default, sourced from the operator's own packshot; regeneration changes the scene, never the product.
- **Dependency:** reads the asset store; no model needed.
- **Evidence:** the three most-adopted competitor patterns are all product-layer-centric (`WORKFLOWS.md` §patterns — Pebblely two-layer output, Flair regenerate-product, Photoroom cutout-then-composite). Reference-image conditioning is mature (`FEASIBILITY.md` §1.1 — Gemini up to 14 references, FLUX.2 multi-ref up to 10).
- **Build now, and it is free.** The engine's `product` layer kind already exists in `studio/engine/doc.js` and already uses `contain` with a separate contact shadow so the asset is never distorted.

### O-10 · On-pack text verification before generation — **PROPOSED**
- **Seller problem:** garbled or invented on-pack text is the single most common complaint about generated product imagery.
- **Mechanism:** extract visible label text from the operator's own product photo, let them confirm or correct it with position and styling hints, *then* composite.
- **Evidence:** only Pebblely does this (`WORKFLOWS.md` pattern 2) — described there as "the cheapest high-value gap to copy."
- **Build now.** Deterministic, local, no provider.

### O-11 · Deterministic text layer (never model-rendered) — **PROPOSED**
- **Seller problem:** diffusion models misspell, so copy-heavy ads are unreliable.
- **Mechanism:** on-image copy is a vector text layer composited *after* generation.
- **Evidence:** `FEASIBILITY.md` §2.3 recommends exactly this architecture.
- **Repo note:** `studio/engine/doc.js` **already implements it** — a real Canvas 2D text primitive with wrapping, measurement, alignment, letter-spacing and valign. The orphaned engine is the right architecture already.
- **Build now.** Nothing to build; just mount it.

### O-12 · Scene + lighting preset library — **PROPOSED**
- **Seller problem:** no design vocabulary, so every product shot is a one-off prompt.
- **Mechanism:** deterministic scene recipes and lighting rigs, applied to the reference-locked product.
- **Repo note:** `studio/engine/presets.js` already defines 6 scenes and 5 lighting rigs with real parameters.
- **Build now.** Already exists, uncommitted.

### O-13 · Compliance as an executable preset — **PROPOSED**
- **Seller problem:** rules live in a help page the seller never reads.
- **Mechanism:** Photoroom generates at exactly RGB 255,255,255 *because* near-white fails an automated check (`WORKFLOWS.md` pattern 4). Bake the rule into the export preset.
- **Build now.**

---

## D. Brand governance

### O-15 · Brand kit as a first-class object — **PROPOSED**
- **Seller problem:** off-brand output; no shared kit across listing, ads and social.
- **Mechanism:** palette, ink, accent, fonts and voice in one kit object, inherited by every asset; `studio/engine/doc.js` `applyKit()` already substitutes kit colours into text and badge layers.
- **Dependency:** brand voice contract (`social_pulse.load_brand_voice()`, `listing_forge` brand_voice dict) already exists.
- **Evidence:** Packify makes Brand Kits a shared Business/Enterprise object (`PHASE0` §2.4); Figma's honest limit is that it *cannot* use your own design system (`WORKFLOWS.md` pattern 7) — which is a gap NorthstarOS can close.
- **Build now.**

### O-16 · Voice inheritance into copy layers — **PROPOSED**
- **Seller problem:** the ad sounds like a different company from the listing.
- **Mechanism:** the kit's voice string constrains copy suggestions in every text layer, including the `COPY_ROLES` word budgets already in `presets.js` (Headline ≤12, Legal ≤40, and Legal is explicitly never auto-hidden).
- **Build now.**

### O-17 · Claims vocabulary shared across surfaces — **PROPOSED**
- **Seller problem:** a claim approved for a listing shows up in an ad where it is not allowed.
- **Mechanism:** one claims library governs listing, A+, ads and social; the O-05 consistency check reads it.
- **Build now.** Depends on O-06.

---

## E. Packaging and production

### O-18 · Dieline and print-spec export — **PROPOSED**
- **Seller problem:** packaging concepts can't actually be manufactured.
- **Mechanism:** dieline with cut, fold, bleed and safe marked; PDF/X-1a CMYK export; a manufacturer handoff checklist.
- **Evidence:** Packify does text-to-3D concepts, dielines and manufacturer connection (`PHASE0` §2.4, all verified). `FEASIBILITY.md` §4 marks 3D/packaging **mature and deterministic** and the correct tool for anything print-adjacent.
- **Repo note:** `studio/engine/three.js` is a real mesh renderer on a Canvas 2D context — no WebGL, no three.js, no dependency.
- **Build now.**

### O-19 · Insert-card and label proof generator — **PROPOSED**
- **Seller problem:** inserts and labels are separate, unversioned one-offs.
- **Mechanism:** reuse the same doc and kit for insert cards, labels and mailer bands; `MOCKUP_SURFACES` already defines label, box-face, tee, tote and mug print areas.
- **Build now.**

---

## F. Cross-surface workflow

### O-20 · One content-type selector driving all formats — **PROPOSED**
- **Seller problem:** today the repo has two disagreeing creative surfaces (`CreativeStudio` with 8 flat tabs, and the orphaned `studio/` engine with 21 formats) and nothing that says what a "creative" *is*.
- **Mechanism:** a 6-station selector (Listing / Ads / Video / Social / Product / Brand) that derives formats, templates, compliance profile and brief fields from the selection.
- **Dependency:** reads the format and template presets.
- **Build now.** This is the structural change; the formats already exist.
- **Renders:** `mockups/out/02`–`07`, `09`.

### O-21 · Visible cost ledger and hard per-job caps — **PROPOSED**
- **Seller problem:** credit burn on expensive operations.
- **Mechanism:** show cost per render and per variant *before* committing; enforce a per-job cap; require named approval above it.
- **Evidence:** `WORKFLOWS.md` pattern 5 (Pebblely shows bulk credit cost before commit; Flair charges 4× for instant generation) and pattern 6 (dual metering). The repo's `docs/CREATIVE_MEDIA_STACK.md` already prices every tier.
- **Amazon safety:** protects real money. Per the constitution, any hard failure stops immediately, persists what succeeded, records a scrubbed manifest, reports — never auto-retries.
- **Build now.**

### O-22 · Experiment read-out write-back — **PROPOSED**
- **Seller problem:** MYE results are read in Seller Central and forgotten.
- **Mechanism:** the operator records the MYE outcome (units, sales, conversion, units-per-visitor, sample size, projected one-year impact — all fields Amazon itself reports), and it is written back into the master brain next to the variant that produced it.
- **Evidence:** `FEASIBILITY.md` §7.1 lists the exact MYE metrics and the ≥66% significance conclusion. Manual entry is *required* because no API exists (§7.2).
- **Build now.** Local, free, honest.

---

## Explicitly rejected (and why)

| Idea | Why not |
|---|---|
| **A better AI image generator** | Amazon's is free and ASIN-first. No price or quality advantage is available. |
| **Another general canvas editor** | Canva, Figma and Firefly own this and have distribution. |
| **Replicate MYE programmatically** | Verified impossible — no API exists (`FEASIBILITY.md` §7.2). Building it would mean automating a UI against Amazon's terms. |
| **Auto-publish to Amazon or social** | Any Amazon purchase/listing/transaction or real-money action requires fresh explicit operator approval per the constitution; and no social OAuth/publisher exists in this build. |
| **Copy competitor templates or layouts** | Explicitly prohibited by the research rules (R3). All patterns above are described in original words. |

---

## Coverage limits

- This file synthesises **delivered** evidence. `AMAZON_REQUIREMENTS.md` and `SELLER_PAIN_POINTS.md` were still in flight when this was written; the compliance concepts (O-04, O-07, O-08, O-13) will be reconciled against them.
- Pain-point frequencies are **not** cited here because Phase 4 has not landed. Once it does, the "Seller problem" lines should be annotated with sample sizes.
- No competitor pricing, user count or benchmark is asserted anywhere in this file.
- Nothing here is a commitment. All 22 are PROPOSED pending operator review.
