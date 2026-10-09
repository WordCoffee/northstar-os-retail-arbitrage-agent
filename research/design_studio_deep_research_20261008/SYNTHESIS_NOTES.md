# SYNTHESIS NOTES — Phase 7 working file

**Date:** 2026-10-08 · **Status:** DRAFT — Phase 3/4 (Amazon requirements + seller pain points) still in flight. This file records only conclusions already supported by delivered evidence; it will be reconciled against `AMAZON_REQUIREMENTS.md` and `SELLER_PAIN_POINTS.md` when they land.

---

## 1. The four facts that decide everything

### 1.1 Amazon's own AI creative tools are free — that is the competitive floor
`PHASE0_ENTITY_RESOLUTION.md` §3 (S221–S224, VERIFIED): Amazon Ads ships a Creative Studio and a Creative Agent, ASIN-first, native to Sponsored Brands / Sponsored Display / DSP / Brand Store, built on Amazon Nova and Anthropic Claude.

**Consequence:** NorthstarOS cannot win on "AI image generation for Amazon." The value has to sit somewhere a free native tool structurally cannot: (a) the seller's *own* product photography, reference-locked and reusable; (b) cross-channel consistency between listing, A+, ads and social; (c) compliance pre-flight that blocks rather than warns; (d) the keyword→creative→performance loop, which nobody has built (§1.3); (e) brand voice, claims governance and account safety, which are seller-specific rather than channel-specific.

### 1.2 PicCopilot is shutting down — it is a source of orphaned users, not a live target
`PHASE0` §2.6 (S208, S209 VERIFIED; S211 REPORTED): closure banner on every page, service ends 2026-12-08 UTC+8, new-user payments stopped 2026-09-27, pricing already renders `$0` and the literal string `"$NaN"`. The operator's description of it (Amazon A+/EBC layouts, chat-to-edit) was **not** confirmed — no such module exists.

**Consequence:** remove PicCopilot from the competitor set for design purposes. Treat it as an inbound-user signal: its users are Amazon sellers who want listing imagery with no canvas to learn.

### 1.3 The keyword → creative loop is genuinely unbuilt — and the research confirmed it rather than assuming it
`SEO_AD_LOOP.md` §1.3 (VERIFIED): **no keyword-research vendor exposes a documented, native integration into a creative/asset tool.** Helium 10's MCP server is a generic agent pipe, not a creative pipeline. Jungle Scout's API + Zapier is the same. The Amazon Ads API does the reverse — it *accepts* creative assets but exposes **no keyword-to-creative join**; grepping the complete Ads API TOC found zero "experiment" occurrences and zero creative-generation endpoints.

**Consequence:** this is the real differentiation, and it is *narrowly* available because the operator's own repo already holds the contracts (§1.4).

### 1.4 The repo already holds three of the four data contracts the loop needs
Verified by code read in `reports/CREATIVE_DESIGN_INVENTORY_20261008.md` §4:

| Contract | Symbol | Status |
|---|---|---|
| Brand voice | `social_pulse.load_brand_voice()`; `listing_forge` `brand_voice` dict | exists |
| Keyword tiers | `ad_pilot.classify_keyword_tier()` | exists |
| Search-term data | `ads_api_importer.run_search_term_report()` → `keyword_performance` | exists |
| Org scoping | `foundation.repositories.for_keyword()` | exists |

**Consequence:** the loop needs **no new backend data source**. It needs the Design Studio to read these and write back. That reframes the build from "build a data pipeline" to "wire an existing pipeline to a UI."

---

## 2. What to adopt from competitors (patterns, not designs)

From `WORKFLOWS.md` (8 mapped workflows, 13 cross-cutting patterns). The five that matter most:

1. **Listing-as-entry-point, not blank canvas.** The Amazon-native tools converge on starting from an ASIN or the seller's own photo. This is also the cheapest way to avoid the "generic AI render" failure mode.
2. **On-pack text verification *before* generation.** Only Pebblely does this — auto-extract visible label text, let the seller confirm or correct with position and styling hints. Cheapest high-value gap to close.
3. **Product layer as an explicit, immutable-by-default object.** Pebblely's two-layer output, Flair's regenerate-product, Photoroom's cutout-then-composite.
4. **Compliance as an executable preset, not a document.** Photoroom generates at exactly RGB 255,255,255 because near-white still fails an automated check.
5. **Dual metering + visible cost.** Flair charges 4× for instant/ad generation; Pebblely shows bulk credit cost *before* commit.

**Also adopt:** honest-limits disclosure as a trust feature. Figma states it cannot use your own design system; Amazon states negative prompts are typically ignored. NorthstarOS already does this (the `Blocked — provider required` terminal state) — this is an existing strength to preserve, not a gap to close.

---

## 3. What no competitor does well

1. **Keyword-bound creative.** No tool binds an asset to the search term it targets.
2. **Cross-surface consistency.** Nothing checks that an ad's claim matches the listing's claim.
3. **Compliance as a hard gate.** Amazon's own generative tools do not pre-check output against listing rules; Photoroom only does the background.
4. **Claims governance.** No tool blocks an unsupported claim at compose time. This is the account-safety play.
5. **Write-back learning.** Winners are captured in ad accounts but not in the seller's own brand memory.

---

## 4. Amazon Manage Your Experiments — the finding that constrains the variant-testing feature

`FEASIBILITY.md` §7 (VERIFIED by absence from two Amazon indexes):

- MYE **exists**: A/B tests on product title, main image(s), bullet points, product description, A+ Content and Brand Story. Requires professional seller + Brand Representative + Brand Registry. ASIN must have recent sufficient traffic. Bayesian, weekly updates, concludes at ≥66% significance. Auto-publish and "run to significance" are **beta, title and image only**. A similarity guard warns when versions are too similar.
- **Programmatic creation is NOT possible.** The SP-API doc index (1,122 lines of every documented page) contains zero occurrences of "experiment", "split test" or "A/B". The Ads API TOC likewise.
- Amazon warns that content failing validation — **e.g. a non-white background in a category that requires it** — will not start as scheduled.

**Design consequence — align, don't replicate:** the studio should produce an *experiment-ready pair set* (two sufficiently-different, individually-compliant variants) plus a handoff manifest the operator pastes into MYE. It must never claim to create an experiment. This is also a second, independent reason the compliance pre-flight must be a hard gate: a non-compliant image doesn't just risk suppression, it silently kills the experiment.

---

## 5. Cost and safety posture

From `FEASIBILITY.md` §1–3 and the repo's own `docs/CREATIVE_MEDIA_STACK.md`:

- Reference-image conditioning and inpainting are **mature** (Gemini: up to 14 reference images, 10 high-fidelity objects; FLUX.2 multi-ref up to 10).
- On-image text is the known weak point. `FEASIBILITY.md` §2.3 recommends rendering text as a **deterministic vector layer composited after generation** rather than asking a diffusion model to spell. **This is exactly what the existing `studio/engine/doc.js` already does** — its text layer is a real Canvas 2D text primitive with wrapping and measurement. The orphaned engine is the right architecture by luck.
- Video is metered per second; `docs/CREATIVE_SOCIAL_LOCAL_STATUS.md` §4 records the video budget as an **unanswered owner decision**.
- 3D/packaging is mature and **deterministic** — the correct tool for anything print-adjacent.

**Safety rule to carry into the build:** per the constitution, any hard failure of a live render stops immediately, persists what succeeded, records a scrubbed manifest, and reports. Never auto-retry.

---

## 6. Risks for the master plan

| Risk | Severity | Mitigation |
|---|---|---|
| Amazon's free native creative tool set | High | Compete on seller-owned assets, cross-surface consistency, compliance gating and the loop — never on raw generation. |
| Compliance pre-flight encodes wrong/outdated rules | High | Every rule carries source + accessed date; rules are data, not code; a failed check blocks rather than silently passes. |
| Product-fidelity drift across a set | Medium | Reference-lock to the operator's own packshot; product layer immutable by default. |
| On-image text garbled by a diffusion model | Medium | Deterministic text layer, never model-rendered. |
| Video spend runs away | Medium | Hard per-job cap + named approval; video is opt-in, never default. |
| MYE assumption wrong (assume an API) | Medium | Handoff manifest only; never claim to create an experiment. |
| Pricing/counts fabricated from competitor marketing | Low | VERIFIED/REPORTED/UNKNOWN labels enforced in every CSV; UNKNOWN is the default. |

---

## 7. Open questions for the operator

1. **Which provider for the first real image render?** Local ComfyUI (repo has the CLI, gated by `MEDIA_GEN_LIVE`) vs a metered cloud tier. The docs lean local-first but the GPU is unconfirmed.
2. **Studio is currently a `Concept` room for operators only.** Is the Design Studio intended for beta customers, or operator-only until Phase 1?
3. **Video: confirm the spend cap and the approval gate** before any video backend is armed.
4. **Claims library: who authors the approved/prohibited lists**, and is there a legal review step (the repo has `LEGAL_REVIEW_PACKAGE.md` and `PROMO_COMPLIANCE.md` to align with)?
5. **Asset store:** bundles are references-only today. Local FS or object store, and does that gate export?
6. **Does the loop write back to the existing `MemoryBank` room**, or a new master-brain store?
7. **`creator.fyi`** — the research found no product at that domain (no A record, nothing served). If one is expected, a correct URL is needed.
8. **MYE import:** is a handoff manifest (copy-paste pair set) acceptable as v1, given no API exists?

---

*To be completed once `AMAZON_REQUIREMENTS.md` and `SELLER_PAIN_POINTS.md` land: the compliance matrix rows and the pain-point frequency table.*
