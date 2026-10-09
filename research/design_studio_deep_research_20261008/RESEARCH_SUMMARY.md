# RESEARCH SUMMARY — NorthstarOS Design Studio competitive & market research

**Research date:** 2026-10-08 → 2026-10-09 (UTC) · **Folder:** `research/design_studio_deep_research_20261008/`
**Method:** public pages, official documentation, official Amazon PDFs, official API docs, public review sites and search-index retrieval. **No logins, no trials, no API keys, no paid calls, no provider calls.**

---

## Evidence ledger

| Metric | Value |
|---|---|
| Sources registered in `SOURCES.csv` | **224** |
| … labelled VERIFIED (directly observed) | 175 |
| … labelled REPORTED (vendor/third-party claim) | 46 |
| … labelled UNKNOWN (not confirmed) | 3 |
| Malformed rows / duplicate ids / unresolved references | **0 / 0 / 0** |
| Competitors in `COMPETITOR_MATRIX.csv` | 18 |
| Competitor-matrix cells honestly marked UNKNOWN | 58 |
| Workflows mapped end-to-end in `WORKFLOWS.md` | 8 |
| Amazon spec rows in `AMAZON_REQUIREMENTS.md` | ~60, all `date_sensitive: yes` |
| Seller pain-point themes (with sample sizes) | 5 |
| Differentiated feature concepts in `OPPORTUNITIES.md` | 22, all PROPOSED |

---

## Files in this folder

| File | What it is |
|---|---|
| `RULES.md` | The evidence rules the research was run under |
| `PHASE0_ENTITY_RESOLUTION.md` | Identity resolution for the 7 named competitors + 11 additions |
| `COMPETITOR_MATRIX.csv` | Consolidated matrix, 18 competitors × 20 columns |
| `PHASE1_COMPETITOR_MATRIX.csv` | Phase 1 source matrix, general-design competitors |
| `PHASE1_AMAZON_SELLER_MATRIX.csv` | Phase 1 source matrix, Amazon-seller competitors |
| `WORKFLOWS.md` | 8 end-to-end workflow teardowns + 13 cross-cutting patterns |
| `AMAZON_REQUIREMENTS.md` | Amazon requirements across 11 surfaces, with sources and dates |
| `SELLER_PAIN_POINTS.md` | 5 themes, clustered with explicit sample sizes |
| `SEO_AD_LOOP.md` | Keyword / rank / search-term data plumbing, and the loop definition |
| `FEASIBILITY.md` | Technical maturity, cost drivers, failure modes per technique |
| `OPPORTUNITIES.md` | 22 PROPOSED feature concepts with validation plans |
| `SYNTHESIS_NOTES.md` | Working notes from the mid-research synthesis |
| `MASTER_BLUEPRINT.md` | The recommended plan, phases, risks and open questions |
| `SOURCES.csv` | Master source register — every finding traces to a row here |
| `mockups/` | 9 concept renders + `index.html` + the generator |

---

## 1. Entity resolution — the operator's corrections, checked

| Name given | Verdict |
|---|---|
| **Canva / Figma / Adobe Firefly** | All three confirmed as named. Figma has repositioned to a full-stack creative canvas with an AI agent. Firefly is Adobe's. |
| **Packify AI** | **Operator correct in full.** Packify.ai, built by **Pacdora** (confirmed by `cdn.pacdora.com` and the billing contact). All five scope claims verified: text-to-3D concepts, dieline editor, AI photoshoots, API, manufacturer connection. |
| **Creator.fyi / Creatify AI** | **Half right — and the other half matters.** Creatify (creatify.ai, Creatify Lab) is real and matches the described URL-to-video scope. **`creator.fyi` is not a product at all:** DNS returns an SOA authority section with **no A record**, transport fails, and searches surface only unrelated "Creator FYI" Meta/Threads posts. Not an alias, not a second product. If one is expected, a correct URL is needed. |
| **PicoPilot** | Spelling confirmed: **PicCopilot**, `piccopilot.com`. But **the operator's scope is wrong** — no A+ / EBC / listing-layout module exists, and chat-to-edit could not be confirmed. **The product is shutting down:** closure banner on every page, service ends 2026-12-08 (UTC+8), new-user payments stopped 2026-09-27, and the pricing page already renders `$0` and the literal string `"$NaN"`. Treat as a former competitor. |
| **tryholo.ai** | **Resolved — the UNVERIFIED flag was justified.** It is **Holo**, a live Lithuanian autonomous marketing platform ($6M claimed, LinkedIn `holoai`). It plans/writes/publishes ads, social, email and SEO on autopilot with tap-approve, and explicitly positions *against* templates. It is **not** a design or packaging tool. Legal entity undisclosed → UNKNOWN. |
| **8 Amazon-seller additions** | Amazon Ads AI creative tools, Helium 10, Jungle Scout, Pacvue, Perpetua, Flair, Photoroom, Pebblely — all verified before inclusion. AdCreative.ai and Claid were added beyond the operator's list. **Jungle Scout and Perpetua were verified but excluded from workflow mapping** — neither exposes any asset-generation, editing or export surface in public pages. |

---

## 2. The three findings that change the plan

### 2.1 Amazon's own AI creative tools are free
Amazon Ads ships a Creative Studio and Creative Agent — free, ASIN-first, native to Sponsored Brands / Display / DSP / Brand Store, built on Amazon Nova and Anthropic Claude, with documented export dimensions (display 300×250 … 1800×1000; video minimum frame 1920×1080 at 24fps).

**Consequence:** NorthstarOS cannot win on "AI image generation for Amazon." Value must sit where a free native tool structurally cannot reach: the seller's *own* photography, cross-surface consistency, compliance gating, claims governance, and the loop.

### 2.2 The keyword→creative loop is genuinely unbuilt — for a structural reason
No keyword vendor exposes creative data; no creative tool exposes keyword data; the Amazon Ads API exposes **no keyword-to-creative join** and **zero** creative-generation endpoints (only a creative-asset *library*).

But here is the sharper constraint: **Amazon's search-term reports aggregate at campaign / ad-group / keyword level and carry no creative or asset identifier column.** So creative-level attribution cannot be derived automatically. v1 must record which variant was live in which date range and let the operator attribute — never infer it.

### 2.3 Amazon says on-image text is **not** indexed — which reverses one of the operator's premises
The brief proposed "image-text SEO: on-image copy that matches indexed and ranked terms." Amazon's own A+ guides say the opposite: limit text embedded in images *because text inside images is not read by search engines or screen readers*. The Stores guidelines repeat it verbatim; Amazon's KDP examples page says "Don't add text to your background image. Add text to the overlay box."

**Revised framing:** on-image copy is a **human-comprehension and conversion** feature, not an SEO one. Any ranking claim would contradict Amazon's own documentation. This correction is recorded against O-03 in `OPPORTUNITIES.md`.

---

## 3. Amazon compliance — the spec that matters most

The repo's own `presets.js` declares A+ wide banner `970×600`, standard `300×300`, comparison `970×300`. Amazon's official module-guide PDFs specify **Premium Full Image at 1464 × 600**, **Basic Comparison Chart images at 150 × 300**, and **Four Images & Text at 200 × 200**. (`1600 × 1600` for the main image *is* compliant — Amazon's range is 500–10,000 px with >1,000 px preferred for zoom.)

**This is why the master blueprint puts "correct the format presets" as Phase 0.** A studio built on the wrong numbers would enshrine the error in every asset.

Other verified constraints now encoded: MAIN image must be white background with the product filling **≥85%** and **no text, logos, borders, colour blocks or watermarks**; A+ is JPG/BMP/PNG, ≤2 MB, ≥72 dpi, **RGB — CMYK not supported**; Premium A+ has 19 module shapes each with their own minimum dimensions and character limits; and **Manage Your Experiments has no programmatic API** (verified by absence from the 1,122-line SP-API doc index and the Ads API TOC), so variant testing must ship as a handoff manifest.

---

## 4. Seller voice — what they actually complain about

Sample sizes are **anecdote clusters, not trends**, and the retrieval reality is stated plainly: G2, Capterra, Trustpilot and Product Hunt all returned HTTP 403; Reddit was reachable only through a search index; **no YouTube comment text was obtained at all.**

| Theme | Sample | Signal |
|---|---|---|
| Inaccurate product rendering | 13 threads | **Strong and consistent** — the most repeated complaint, corroborated from the buyer side (Vine reviewers calling it "deceptive advertising") |
| Credit burn / failed renders / billing lock-in | 11 threads | Strong, specific: Photoroom (4) and Creatify (5) |
| Garbled or altered on-image text | 5 threads | Consistent but smaller — a two-sided trap: tools damage it *and* Amazon increasingly rejects it |
| Off-brand output / template drift | 5 threads | Present but small and mostly **non-Amazon** — should not be read as an Amazon-seller finding |
| Rejected / suppressed listings | crossed into themes 1–2 | Sellers report Premium A+ rejected over a *brand logo*, and over text that is part of the product itself |

**Design consequence:** the product must be the operator's own photograph, reference-locked and never generated. That is simultaneously the fix for the #1 complaint and the cheapest architectural decision available.

---

## 5. Feasibility — build now vs later

| Technique | Maturity | Verdict |
|---|---|---|
| Reference-image conditioning / inpainting | Mature | Use it — but **never generate the product itself**; composite labels and packaging from real photos |
| On-image text | Emerging, unreliable in diffusion models | **Render as deterministic vector type.** `studio/engine/doc.js` already implements exactly this |
| Video generation | Emerging | Later. Real per-second pricing, but ~90 s latency for a 6 s clip, and video is metered spend needing an operator-named cap |
| 3D / packaging | **Mature and deterministic** | Build now. The correct tool for anything print-adjacent. `three.js` already does it dependency-free |
| Brand consistency | Make it **≥90% deterministic** | Locked palette, type scale, logo lockup, versioned kit. Fine-tuned brand models are probabilistic and have documented limits |
| Compliance pre-flight | **Mostly deterministic** | Implement as hard gates. Amazon's own asset library returns machine-readable `failedSpecChecks` — copy that shape |
| Manage Your Experiments | Exists; **no API** | Align, don't replicate. Ship an experiment-ready pair set + handoff manifest |

---

## 6. What this research could not do

Stated plainly, per the rules:

- **No logged-in surface was reached.** Amazon Ads console, MYE UI, Helium 10, Pacvue, Perpetua, Canva editor — all capabilities behind a login are REPORTED at best.
- **Seller Central help pages are JS-gated.** Their content came from Amazon's own summaries on official properties (labelled VERIFIED) or from official Amazon PDFs on `m.media-amazon.com`.
- **G2 / Capterra / Trustpilot / Product Hunt returned 403.** No review text from those sites was read, with one REPORTED exception.
- **No YouTube comments.** Comment data is client-rendered and absent from static HTML.
- **`pacvue.com` returns HTTP 403** to automated fetching — its evidence is the weakest in the set.
- **Generation was never actually run**, so no failure-mode frequency is quantified. Maturity calls describe documentation, not observed reliability.
- **The claim that Amazon removed A+ alt-text** could not be confirmed from any Amazon announcement — recorded as an unverified live risk, not fact.
- **Ads API v1 (`ads-v1`) report shapes were not fetched.** v3 deprecates 2027-06-30, so this must be re-verified before any build depends on it.
- **Canva, Adobe Firefly, Packify and AdCreative.ai pricing are UNKNOWN** — every one renders dynamically. Helium 10 pricing is third-party REPORTED only and the sources disagree.

---

## 7. Recommended next step

Read `MASTER_BLUEPRINT.md`, then decide the seven open questions it lists — chiefly the image provider, the video spend cap, who authors the claims library, and whether the Design Studio is operator-only or beta-facing.

**Phase 0 needs no decision and no provider:** correcting the A+ format presets in `presets.js` to Amazon's verified figures is a data fix that prevents an entire category of downstream non-compliance, and it can be done immediately.
