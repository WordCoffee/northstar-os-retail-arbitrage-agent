# White Space: Competitor x Capability Matrix + 25+ Original Ideas

Track F of the Design Studio research corpus. Pulled at 2026-10-10.
`YES` = documented as present. `NO` = documented absent or absent from the
tool's own taxonomy. `?` = not captured in this pass (see coverage-report).
The flag column marks capabilities where **nobody in this set serves Amazon
sellers**.

## Competitor x Capability matrix

| Capability | Canva | Figma | Pacdora/Packify | Creatify | Holo | Firefly | Pebblely | Photoroom | Claid | Flair | Helium10 | Amazon native |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Amazon main-image spec validation | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES (rules only) |
| Amazon A+ module system | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES |
| Store tile sizes / safe zones | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES |
| Sponsored Brands video spec validation | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES |
| Product-fidelity contract (enforced) | NO | NO | NO | NO | NO | NO | NO | NO | partial (claims) | NO | NO | NO |
| Keyword cluster as creative input | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | **YES** | NO |
| Ad search-term to hook mapping | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO |
| Manage Your Experiments linkage | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES |
| Local/free generation | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES |
| Per-asset provenance (prompt/model/seed/base) | NO | NO | partial | NO | NO | Content Credentials | NO | NO | NO | NO | NO | NO |
| Brand kit with revision history | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO |
| AI-people disclosure metadata write | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | YES |
| Mockup + dieline + 3D from one record | NO | NO | **YES** | NO | NO | NO | NO | NO | NO | NO | NO | NO |
| Bulk variation sets from one product | NO | NO | NO | partial (50) | NO | NO | NO | YES (250/run) | partial (API) | NO | NO | YES (flat file) |
| Cross-section shared asset library | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | NO | partial |
| Dieline/file export for print | NO | NO | **YES** | NO | NO | NO | NO | NO | NO | NO | NO | NO |

### Where nobody serves Amazon sellers (the white space)
1. **Pre-flight compliance before generation.** Every competitor validates
   AFTER you produce (or never). Nobody tells you BEFORE you spend a credit
   whether the output will be suppressed.
2. **Product-fidelity as an enforced contract with a pass/fail result.** Claid
   markets a fidelity vocabulary (label preservation, packaging consistency,
   seam accuracy, fine detail retention); nobody turns it into a verdict.
3. **Keyword cluster ? creative brief.** Helium 10 goes keywords ? listing TEXT.
   Nobody goes keywords ? IMAGE.
4. **Ad search term ? hook/angle.** Nobody.
5. **MyE linkage.** Nobody connects creative production to Amazon's own A/B
   measurement tool.
6. **Local, free, unlimited generation.** Nobody in the set offers it; Northstar
   has a 5080 + ComfyUI already running.
7. **Per-asset provenance.** Nobody persists prompt/model/seed/base-asset lineage
   in a queryable store.
8. **Brand memory with confidence, provenance and unlearn.** Nobody.
9. **AI-people disclosure automation.** Amazon documents the requirement;
   no tool writes the IPTC metadata for you.
10. **One product record ? packaging + mockup + 3D + listing images.** Only
    Pacdora does the packaging half.

---

## 25+ original ideas for Amazon sellers

Effort: S = days, M = weeks, L = months. Feasibility: LOCAL = local GPU,
API = paid provider, DET = deterministic (no model).

### Tier 1 ? build now (deterministic, no credits, closes a documented gap)
1. **Compliance pre-check before generation.** DET. Runs the documented
   main-image rules (RGB 255/255/255, 85% fill, no text/logo/watermark, min
   1000px, format, 72 dpi) plus the A+ rules (RGB, <2MB, alt text present,
   uniqueness) and blocks export on failure. S. Risk: low. *This is the single
   highest-value feature in this document.*
2. **Format registry as the only source of export sizes.** DET. Every Amazon
   size in one place: main image, A+ basic/premium modules, Store tiles, SB
   video horizontal and vertical, DSP display sizes. S. Risk: low.
3. **Honest safe-zone overlays.** DET. Store hero 16%+18%, Store tile link-title
   19%/12%, SB video bottom-right no-text. S. Risk: low.
4. **Suppression triage board.** DET. Given a list of ASINs, show which main
   images fail which documented rule, mapped to Amazon's own "Listing Quality"
   reason strings, so the operator knows what to fix and why. M. Risk: low.
5. **AI-disclosure metadata writer.** DET/LOCAL. Writes IPTC
   `contains-synthetic-performer` to `dc:subject` when an asset contains
   photorealistic AI people. S. Risk: low.
6. **Flat-file image manifest export.** DET. Exports `main_image_url`,
   `other_image_url1..8`, `swatch_image_url` rows per child ASIN, with a
   PartialUpdate-safe diff view so the operator can see what a feed would blank.
   M. Risk: medium (destructive-feed risk if wrong).
7. **Provenance record per asset.** DET. prompt, model, seed, base asset id,
   cost, timestamp, compliance verdict, into `ds_assets.metadata`. S. Risk: low.
8. **Empty-state discipline + Run cost preview.** DET. Every surface with no
   data shows a Run button with an explicit cost/quota preview and a confirm.
   S. Risk: low. *Already mandated by the master directive; the research
   confirms it is also the honest and competitor-rare pattern.*

### Tier 2 ? build next (local GPU, free, high differentiation)
9. **Keyword cluster ? creative brief.** LOCAL (deterministic mapping) + the
   data already in `keywords`, `keyword_performance`, `search_query_performance`.
   Maps rank position ? the slot that needs help (hero shot vs CTR vs
   conversion) using Amazon's own documented traffic/conversion split. M. Risk:
   low. *No competitor does this.*
10. **Ad search-term ? hook/angle generator.** LOCAL. Feeds the top converting
    search terms into the Video/UGC hook selection. M. Risk: low. *No competitor
    does this.*
11. **White-background main image as a deterministic check, not a generation.**
    LOCAL/DET. Mask + fill + verify 85% fill. Never spend a generation credit on
    something that is a colour fill. S. Risk: low.
12. **Product-fidelity composite mode.** LOCAL. The operator's real product
    image is an opaque masked base layer; generation happens around it. Enforced
    by construction, not by prompt. M. Risk: medium.
13. **Text overlay rendered in-engine, never by the diffusion model.** LOCAL/DET.
    Real layers, real fonts, real Amazon font-size rules. S. Risk: low.
14. **Per-ASIN creative scorecard.** LOCAL/API. Joins compliance verdicts,
    keyword links, MYE outcomes and ad performance per ASIN. M. Risk: low.
15. **Creative A/B experiment tracker mapped to MYE.** M. Produces the
    Version A / Version B pair against the exact same ASIN set (Amazon's stated
    requirement) and records the outcome. Risk: low.
16. **Review-mining to infographic claims.** LOCAL. Mine review text for
    recurring complaint themes, propose them as infographic callouts. M. Risk:
    medium (needs review data we do not have yet).
17. **Bulk variation sets from one product record.** LOCAL. One project ? N
    child-ASIN main images + additional images, with per-child labels. M. Risk:
    low.
18. **Master Brain brand memory as the brand kit.** LOCAL/DET. Brand facts live
    in `memory_entries` with confidence, provenance and unlearn; the Design
    Studio reads them rather than owning a second brand store. M. Risk: low.
19. **IP-Adapter reference conditioning instead of per-brand LoRA.**
    LOCAL. Minutes, reversible, no storage ceiling. M. Risk: medium.
20. **Seasonal creative calendar.** LOCAL/DET. Plan briefs against known retail
    events with a lead-time model. S. Risk: low.

### Tier 3 ? build later (bigger bets)
21. **Packaging + mockup + 3D + listing images from one product record.** L.
    Pacdora proves the packaging half. Risk: medium.
22. **Compliance pre-check as a service other rooms call** (ListingForge,
    SocialPulse). M. Risk: low.
23. **Top-10 competitor image gap analysis** (slot count, which slot carries
    text, which carries scale, which carries social proof) using manual + ad
    library collection. M. Risk: medium (ToS).
24. **Creative version history with regenerate-from-any-variant.** M. Risk: low.
25. **Shared asset library + generation queue across Product Designer,
    Creative Studio and Design Studio** (already specified in the master
    directive; the `ds_assets` / `ds_jobs` store exists). M. Risk: low.
26. **Hand-off buttons: Send to Product Designer / Send to Creative Studio.**
    S. Risk: low.
27. **Hand-off to ListingForge / SocialPulse / AdPilot.** M. Risk: low.
28. **Rufus/assistant content-consistency check.** LOCAL/DET. Compare infographic
    callout claims against the listing copy and flag claims present in the image
    but absent from the text (the "consistency gap" a vendor guide names). M.
    Risk: low. *Honest framing: we check internal consistency, not ranking.*
29. **Brand voice distillation from real listing copy + reviews.** LOCAL. M.
    Risk: medium.
30. **Local GPU job queue with VRAM state, per-job logs, cancel, retry.**
    LOCAL. M. Risk: low. *Already partially built as `ds_jobs`.*
