# Brand Voice and Master Brain Learning Loop

Track D of the Design Studio research corpus. Pulled at 2026-10-10.
Tags: `[documented]`, `[observed]`, `[inferred]`.

## 1. How competitors implement brand kits / voice / style references

### 1.1 Canva Brand Kits ? the most complete brand-governance implementation found
- A Brand Kit stores official logos, colours, fonts and assets in one place;
  admins and brand designers can create multiple kits for different teams,
  clients or campaigns [documented].
- A kit's contents (from reviewer description of the UI): brand logo, colour
  palette, own fonts, own images, regularly-used graphics, icons, branded
  charts, and **brand voice** [documented ? "define your brand voice" is listed
  as a Brand Kit element].
- Hard limits: up to 1,000 kits per subscription; up to 2,000 brand assets per
  asset CATEGORY inside one kit; max 500 uploaded fonts per kit; 1 kit on Free,
  5 Pro, 100 Business, 1,000 Enterprise [documented].
- Font upload accepts OTF, TTF, WOFF [documented].
- **Brand Controls? + Design Approval** is the governance layer: a reviewer
  describes defining logos, colours, fonts and usage rules once, then using
  approval flows "instead of catching the same branding mistakes on every single
  asset". In their first review round they caught one adaptation using the wrong
  font and another with an outdated logo, and Brand Controls prevented both from
  moving forward [documented ? G2 review].
- **Access control for AI on-brand generation**: Magic Design controls the
  model used for generating designs, and Canva AI controls the entry points to AI
  experiences; some AI experiences can use Brand Kit and Brand Template context
  to create more on-brand results, toggled per team [documented].
- **Known failure**: brand templates created all end up in a general brand
  templates section rather than stored in individual brand kits with the other
  assets [documented ? reviewer complaint]. Also asset-upload reliability
  complaints on r/canva.

### 1.2 Style references (model-conditioning without training)
- Adobe Firefly documents **Style references** ("reusing a visual look") and
  **Composition references** ("layout and structure guidance") as distinct
  mechanisms, with text editing and model-dependent reference support
  [documented via third-party summary referencing Adobe help pages]. These are
  reference-conditioning features, not training.
- Claid's **Custom AI** "trains on your specific product photos to generate
  multiple lifestyle-scene variations" but operates within Claid's proprietary
  model architecture [documented].
- Flair.ai Pro+ includes "up to 8 standard or 2 fast custom models" [documented
  via third-party pricing capture].

### 1.3 "Brand DNA" from a URL (the inference approach)
- Holo's entire mechanic: input your website URL, the AI learns "your tone, your
  audience, and your style", and that becomes the Brand DNA applied to every
  generated asset. Multi-brand: 5+ brands, each with its own Brand DNA,
  templates and workspace [documented].
- Helium 10's variant: input a **competitor ASIN** to infer tone and
  positioning, or manually describe the desired tone, and the AI applies a
  consistent brand voice across the full listing [documented, help centre
  2026-05-13].
- **Critical weakness of the inference approach**: there is no way to inspect,
  correct, version or revoke what the model inferred. It is a black box with no
  revision history. This is precisely the weakness the Northstar Master Brain
  design avoids by making brand memory EXPLICIT and revisionable.

### 1.4 Custom model training (what it actually takes)
- **Adobe Firefly Custom Model (Firefly Foundry)** terms are the only
  vendor-published legal detail captured [documented]:
  - Access via the Custom Models module at firefly.adobe.com.
  - You may store up to the Quantity of Trained Custom Models per the Pricing
    Detail table.
  - **The Custom Model licence BY ITSELF does not include output generation** ?
    a separate Creative Cloud licence including output-generating products is
    required.
  - **Internal use only.**
  - Models are hosted, cannot be copied, only operate with Adobe Firefly
    foundational models, and if those become unsupported the customer must
    RETRAIN.
  - There is no additional separate Firefly Output indemnification for Custom
    Model outputs; any indemnity comes from the separate Creative Cloud licence,
    with Customer Training Data treated as Firefly Input.
- Pricing for Firefly Foundry was not captured in this pass (enterprise-only,
  contact sales).

## 2. Feasible local pipeline on a 16 GB 5080 (ComfyUI)

Northstar already runs ComfyUI locally. The 16 GB VRAM budget is the binding
constraint. Local paths by content type, with the honest feasibility note:

| Content type | Local approach | Feasible on 16 GB | Notes |
|---|---|---|---|
| Product fidelity (preserve real pixels/labels) | **Composite, do not generate.** Put the operator's real product image as an opaque base layer, then generate background only, with the product masked. Inpaint around the product, never through it. | Yes | This is the single most important architectural decision, and it is cheap. No tool in Track A does it as an enforced contract. |
| Background replacement | IMG2IMG / inpainting with the product masked out | Yes | SDXL-class models fit in 16 GB; use tiled VAE for large output |
| Relighting | Inpainting with lighting control + shadow layer | Yes | Photoroom's "AI shadows and reflections" is the commercial equivalent |
| Text overlay | **Do it in-engine, never by the diffusion model.** Render text as a real layer with a real font after generation. | Yes | Text rendering by diffusion models is the category's most reliable failure mode |
| White-background main image | Mask + fill RGB 255,255,255 + verify frame fill | Yes | Deterministic, no model needed. Must be a *check*, not a generation |
| Product video / UGC clips | Image-to-video, short clips | Marginal | 16 GB limits resolution and length; AnimateDiff/SVD-class, not Veo-class |
| Custom LoRA / brand style training | Train a LoRA on brand imagery | Yes, slowly | Kohya/ai-tooling on a 5080 16 GB is the standard path; hours not minutes |
| IP-Adapter / ControlNet conditioning | Reference-image conditioning | Yes | The cheap alternative to training: no retraining, no storage limit |
| Full fine-tune | Not feasible | No | Needs more VRAM than 16 GB for brand-grade results |

**Design rule that follows**: for text-on-image and white-background compliance,
the local pipeline must be DETERMINISTIC (engine-rendered layers and colour
fills), not generative. Generation is reserved for the parts of an image that
actually benefit from it (background, scene, lighting, ambience). That is both
cheaper and more compliant.

## 3. Learning-loop design: what signals exist to rank creative winners

| Signal | Source | Available in Northstar |
|---|---|---|
| CTR by creative | Manage Your Experiments (title/image experiments) | Indirect ? Amazon measures, we record the outcome |
| CVR by creative | Manage Your Experiments (image/A+/Brand Story experiments) | Indirect |
| ACOS by creative | Ads API | Schema for `campaigns` exists; not per-creative |
| Search-term-to-creative match | Amazon Search Query Performance report | **Schema exists** (`search_query_performance`), 0 rows |
| Review language mining | Reviews | Not wired |
| Competitor creative scans | Manual/ToS-safe collection | Not built |
| Compliance pass/fail | Our own checker | Buildable now, deterministic |

**The loop that is actually buildable**: every generated asset gets (a)
provenance, (b) a compliance verdict, (c) a link to the keyword cluster that
justified it, and (d) a slot to record the MYE outcome. Then a per-ASIN
creative scorecard is a query, not a model.

## 4. Competitor creative surveillance ? ToS-safe approaches

Amazon's ToS and copyright law constrain scraping competitor imagery. The
defensible approaches:
1. **Manual, human-collected samples** for pattern analysis (a human browses and
   saves). This is what agencies actually do and it is not a ToS problem.
2. **Publicly advertised competitor ads**: Amazon's own **Meta Top Ads Library**
   (10M+ ads) is documented as accessible on Creatify's Pro tier, and Creatify
   ships an Ad Clone and competitor ad tracker built on it [documented]. Using
   a platform's own public ad library is the commercial precedent.
3. **Photoroom-style competitive teardown** of listing gallery structure (slot
   count, which slot carries text, which carries scale) ? observable facts, not
   copyrighted images, and the output is a gap analysis not a copy.
4. **Brand Registry Report a Violation** is Amazon's own tool for violation
   reporting, not surveillance ? do not conflate.

**Explicitly out of scope as a ToS risk**: automated scraping of competitor
detail pages or gallery images at volume. Recommend the operator authorise the
manual+ad-library path only.

## 5. Master Brain tie-in

The Master Brain memory bank (23 entries already in `memory_entries`) holds
facts, preferences, experiences and AI-derived learnings with confidence,
provenance and a `retired_at` column (revisions and unlearn are already
supported). The Design Studio should store brand facts there rather than in a
new silo, so that:
- a brand fact has confidence, provenance and a revision history by default;
- the operator can unlearn a bad brand fact and it propagates;
- creative briefs can cite which memory entries generated them.

Competitors all fail this: Canva's Brand Kit has no confidence or provenance,
Holo's Brand DNA is an undocumented inference, and Adobe's Custom Models must be
retrained rather than revised.

## 6. Open questions for the operator
1. Do we train a LoRA per brand, or rely on IP-Adapter reference
   conditioning? LoRA is stronger but needs hours of 5080 time per brand and a
   storage-management story; IP-Adapter is minutes and reversible.
2. Should brand facts live in `memory_entries` (Master Brain) or in
   `ds_assets`-adjacent brand records? Recommendation: Master Brain, with the
   Design Studio reading it.
3. Authorise the manual + Meta Top Ads Library competitor-scan path only, or
   none at all for now?
4. Is the 5080's 16 GB the ceiling, or is a second GPU possible later? That
   decides whether custom LoRA training is a headline feature or a footnote.
