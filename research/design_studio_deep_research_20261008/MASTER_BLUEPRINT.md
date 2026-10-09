# MASTER BLUEPRINT — NorthstarOS Design Studio

**Date:** 2026-10-09 · **Status:** DRAFT FOR OPERATOR REVIEW — nothing in this document is built or committed.
**Evidence base:** 224 sourced findings (175 VERIFIED, 46 REPORTED, 3 UNKNOWN) across 18 competitors, 8 mapped workflows, ~60 verbatim Amazon spec rows, and 5 seller-pain-point themes. All in this folder.

---

## 1. Decision summary — five things, in order

| # | Decision | Why now |
|---|---|---|
| **1** | **Correct the repo's A+ format presets before building anything.** | `presets.js` declares A+ wide banner `970×600`, standard `300×300`, comparison `970×300`. Amazon's own module-guide PDFs specify Premium Full Image at **1464 × 600**, Basic Comparison Chart at **150 × 300**, Four Images & Text at **200 × 200** (`AMAZON_REQUIREMENTS.md` §4–§5). A studio built on the wrong numbers would enshrine the error in every asset it produces. **Pure data fix, zero provider cost, do it first.** |
| **2** | **Mount the orphaned studio engine.** | `northstar-os-ui/src/studio/**` (11 files, ~140 KB) already renders documents, 21 formats, brand kits, scenes, lighting, mockups and 3D packaging on a dependency-free Canvas 2D path. It has zero importers and zero git history. The work exists; it is simply not attached to a route. |
| **3** | **Ship compliance as a hard gate, not a document.** | Amazon states non-compliant images "can lead to product listing suppression from search results," and that content failing validation **will not start a Manage Your Experiments test as scheduled**. Two consequences from one gate. |
| **4** | **Bind every asset to its search terms — and do not claim ranking benefit.** | No competitor exposes a keyword→creative join (`SEO_AD_LOOP.md` §1.3, VERIFIED). But Amazon's own A+ guides say text inside images **is not read by search engines or screen readers** — so this is a *measurement and legibility* feature, not an SEO one. |
| **5** | **Render on-image text as vector, never generated.** | The most-repeated seller complaint is garbled on-image text (`SELLER_PAIN_POINTS.md` theme 2, and `FEASIBILITY.md` §2.3 recommends the same). `studio/engine/doc.js` already implements a real Canvas 2D text primitive. |

---

## 2. Where NorthstarOS can actually win

**The competitive floor is zero.** Amazon Ads ships a Creative Studio and Creative Agent — free, ASIN-first, native to Sponsored Brands / Display / DSP / Brand Store, built on Nova and Claude (`PHASE0_ENTITY_RESOLUTION.md` §3, S221–S224). Photoroom, Flair, Pebblely and Packify all have real, funded products. No price or model-quality advantage is available to us.

**So the value sits where a free native tool structurally cannot reach:**

1. **The seller's own product photography, reference-locked.** Amazon's generator starts from an ASIN and invents; ours composites the operator's real packshot. This is also the single most-repeated seller complaint (inaccurate rendering, 13 threads) — solved by *not* generating the product at all.
2. **Cross-surface consistency.** Nothing checks that an ad's claim matches the listing's claim. Sellers report brand fragmentation across detail page, Brand Store and ad creative as an *operational* risk, not an aesthetic one.
3. **Compliance as a gate.** Amazon's own generative tools do not pre-check output against listing rules.
4. **Claims governance.** No tool blocks an unsupported claim at compose time.
5. **The loop.** Nobody closes it, and the operator's repo already holds the data contracts.

---

## 3. Information architecture

One room, `/design-studio`, replacing the current `/creative-studio` and absorbing SocialPulse's creative surface.

```
/design-studio
├─ content-type selector  ── derives formats, templates, compliance profile and brief fields
│    Listing · Ads · Video · Social · Product · Brand
├─ left tool rail (62px)  ── Listing | Ads | Video | Social | Product | Brand
│                            ── Pre-flight · Keywords · Assets
├─ centre stage (dark)    ── document canvas, guides, zoom, variant row, cost ledger
├─ right inspector (300px) ── image set / campaign binding / clip plan / pack geometry
│                            ── Amazon pre-flight · bound search terms · claims guardrail
└─ stage footer           ── the always-visible pre-flight verdict
```

**Mode toggle: Simple / Advanced.** Simple exposes curated controls; Advanced unlocks layer geometry, guides and raw prompt fields — and is honest about what it hides (the orphaned `Chrome.jsx` already specifies this).

**What replaces the current 8 tabs:**

| Current tab | Fate |
|---|---|
| Briefs | becomes the brief panel inside the inspector, now keyword-prefilled |
| Image Composer | absorbed by the stage — the composer *is* the document |
| Video / Shorts | becomes the Video station's storyboard + cost ledger |
| Production Queue | stays, but backed by real jobs |
| Variants & History | becomes the variant row under the stage |
| Assets | absorbed by the rail's Assets item |
| Exports | stays, plus compliance handoff manifests |
| Library | absorbed into the asset store |

**Renders:** `mockups/out/02`–`07` (stations), `08` (loop), `09` (before/after), `00` (current state).

---

## 4. Module list

| Module | Contents | Data dependency | Build |
|---|---|---|---|
| **Listing** | main image, secondary set, lifestyle, A+ Basic + Premium modules, Brand Story, Storefront | format presets (corrected), Amazon rule profile | now |
| **Ads** | Sponsored Brands / Display / Products creative, off-Amazon static + video | `ad_pilot`, `ads_api_importer` → `keyword_performance` | now |
| **Video** | URL-to-video, UGC-style, 3D/animated product video, storyboard, cost ledger | provider + spend cap | **later — needs the operator's video budget decision** |
| **Social** | reels, posts, carousels, content calendar | `social_pulse.load_brand_voice()` | now (publishing stays disconnected) |
| **Product** | concepts, mockups, dielines, insert cards, manufacturer specs | `three.js` mesh + mockup renderer | now |
| **Brand** | brand kit, voice, claims library, approved/prohibited language | brand voice contract + new claims store | now |
| **Compliance** | rule store, pre-flight, content-type profiles, claims guardrail | Amazon spec rows (data, not code) | now — and first |
| **Loop** | keyword binding, brief prefill, performance write-back | all four repo contracts | read/write now; measurement link later |

---

## 5. The loop, concretely

```
search terms ──→ creative brief ──→ asset variants ──→ pre-flight ──→ publish/test
     ↑                                                                      │
     └──────────── learning written to the master brain ←── performance ←──┘
```

Each link's data requirement, and whether the repo already has it:

| Link | Needs | Repo status |
|---|---|---|
| search terms → brief | `searchTerm`, `impressions`, `clicks`, `spend`, `orders`, `sales`, `acos`, `tier` | **exists** — `ads_api_importer.run_search_term_report()` → `keyword_performance`; `ad_pilot.classify_keyword_tier()` |
| brief → variants | the bound terms carried into the doc record | new, but trivial |
| variants → pre-flight | deterministic spec checks | `FEASIBILITY.md` §6.1 — implementable as hard gates |
| pre-flight → publish | handoff manifest | new |
| publish → performance | Amazon's own search-term report | **exists as an importer** |
| performance → learning | write-back to the master brain | new; path is local and free |

**One honest gap:** Amazon's search-term reports aggregate at campaign / ad-group / keyword level and carry **no creative or asset identifier column** (`SEO_AD_LOOP.md` §1.3, VERIFIED). So creative-level attribution cannot be derived automatically. v1 must therefore record which variant was live in which date range and let the operator attribute — never infer it.

---

## 6. Compliance pre-flight — the differentiator

Rules are **data, versioned, sourced and dated**, never code. Each row carries source id, accessed date and `date_sensitive: yes`.

**Deterministic hard gates (block export):**
- Raster size inside Amazon's published range; >1,000 px longest side for zoom
- File type accepted; animated GIF rejected (Amazon's servers do not support them)
- MAIN image: white background, ≥85% product fill, no text/logo/border/colour block/watermark, product out of packaging
- A+ global: JPG/BMP/PNG, ≤2 MB, ≥72 dpi, **RGB — CMYK not supported**
- A+ per-module minimum sizes and character limits (the full tables are in `AMAZON_REQUIREMENTS.md` §4–§5)
- Claims: blocked phrase present, or a claim with no attached evidence

**Heuristic (flag for a human, never auto-block):**
- "Amazon may reject text in A+ images" — sellers report Premium A+ rejections over a *brand logo* and over text that is part of the physical product (S471, S473)
- Soft-hide risk flags ("lack diverse images", "professional usage context")

**Date-sensitivity is a first-class concern.** Amazon states it "periodically updates our policies" and reserves the right to reject any ad "at its sole discretion, for any reason" (S403). Every rule row must be re-verifiable, and the UI needs a visible "verify against Seller Central" affordance.

**The strongest argument for a hard gate:** Amazon warns that content failing validation — e.g. a non-white background in a category that requires it — will not start a Manage Your Experiments test as scheduled. A gate protects the experiment, not just the listing.

---

## 7. Phased build

### Phase 0 — Spec correction (hours, no provider, no approval)
1. Correct `presets.js` A+ values to the verified Amazon figures; leave the rest alone.
2. Diff and record the change as a data fix with source ids.
3. Re-run the full test suite and `npm run build`; commit.

### Phase 1 — Mount the engine and the shell (no provider needed)
1. Import `studio/` into the app; add the `/design-studio` route.
2. Build the shell: content-type selector, tool rail, stage, inspector, mode toggle.
3. Wire the corrected format presets into the stage.
4. All previews remain honest placeholders — do **not** fake a provider.

### Phase 2 — Compliance and brand (no provider needed, highest value)
1. Rule store seeded from `AMAZON_REQUIREMENTS.md`.
2. Pre-flight panel + blocking export.
3. Claims library + evidence ledger, gating at compose time.
4. Brand kit as a first-class object with voice inheritance.

### Phase 3 — The loop (no new backend source needed)
1. Keyword binding in the inspector.
2. Brief prefill from `keyword_performance`.
3. Listing-to-ad consistency check.
4. Performance write-back to the master brain.

### Phase 4 — Provider wiring (needs the operator's provider decision)
1. Local ComfyUI behind `MEDIA_GEN_LIVE` (default off), or a metered cloud tier.
2. Real jobs for the production queue.
3. Asset store so export produces files, not manifests.
4. **Video only after the spend cap and approval gate are named.**

---

## 8. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Amazon's free native creative tool | High | Compete on seller-owned assets, cross-surface consistency, compliance gating and the loop — never on raw generation. |
| Encoded Amazon rules are wrong or out of date | High | Rules are data with source + accessed date; a failed check blocks rather than passes; re-verification affordance in the UI. |
| Product-fidelity drift across an asset set | Medium | Reference-lock to the operator's own packshot; product layer immutable by default; composite labels from real photos, never generate them. |
| On-image text garbled | Medium | Deterministic vector text layer, never model-rendered. |
| Credit burn / spend runaway | Medium | Visible cost ledger before commit, hard per-job cap, named approval. On failure: stop, persist, manifest, report. Never auto-retry. |
| Claiming SEO benefit that Amazon contradicts | Medium | Amazon says embedded image text is not indexed. UI and copy must not claim ranking lift. |
| Creative attribution inferred from campaign-level data | Medium | Amazon's search-term reports have no creative identifier. Record what was live and let the operator attribute. |
| Pricing/user counts copied from competitor marketing | Low | VERIFIED/REPORTED/UNKNOWN labels enforced; UNKNOWN is the default; 58 matrix cells are honestly UNKNOWN. |
| PicCopilot assumed to be a live competitor | Low | Resolved: it is shutting down (2026-12-08) and its pricing already renders `$0` / `"$NaN"`. |

---

## 9. Open questions for the operator

1. **Provider for the first real render** — local ComfyUI behind `MEDIA_GEN_LIVE`, or a metered cloud tier? The docs lean local-first; GPU provisioning is unconfirmed on the pilot machine.
2. **Video budget** — the per-job cap and the approval gate, before any video backend is armed. Recorded as unanswered in `CREATIVE_SOCIAL_LOCAL_STATUS.md` §4.
3. **Who authors the claims library**, and does the repo's `LEGAL_REVIEW_PACKAGE.md` / `PROMO_COMPLIANCE.md` review step gate enforcement?
4. **Audience** — Design Studio is currently a `Concept` room for operators only. Beta customers, or operator-only for now?
5. **Asset store** — local FS or object store? Export stays references-only until this is answered.
6. **`creator.fyi`** — no product exists at that domain (no A record, nothing served). If one is expected, a correct URL is needed.
7. **MYE handoff** — is a copy-paste manifest acceptable as v1, given no API exists?

---

## 10. Coverage limits

- Pixel specs, character limits and rule wording come from `AMAZON_REQUIREMENTS.md`, which is `accessed` 2026-10-09 and **date-sensitive**. Several canonical Amazon pages are JS-gated and were reached through Amazon's own summaries on official properties, not the pages themselves — flagged inline there.
- Seller pain-point sample sizes are **anecdote clusters, not trends**. G2, Capterra, Trustpilot and Product Hunt all returned HTTP 403; Reddit was reached only through a search index; no YouTube comment text was obtained. The largest vendor-specific cluster is 5 threads against Creatify and 4 against Photoroom — real, but not a statistic.
- Competitor pricing is UNKNOWN wherever a vendor rendered it dynamically (Canva, Adobe Firefly plan credits, Packify, AdCreative.ai). Helium 10 pricing is third-party REPORTED only and the sources disagree.
- Pacvue returns HTTP 403 to automated fetching; its evidence is REPORTED via search rendering and is the weakest in the set. Perpetua's help centre is ~14 articles with no creative-generation documentation.
- No generation was actually run, so **no failure-mode frequency is quantified**. Maturity calls describe documentation, not observed reliability.
- Nothing in this blueprint has been built. Renders in `mockups/out/` are layout and information-architecture concepts drawn in the repo's real tokens — they are not product imagery.
