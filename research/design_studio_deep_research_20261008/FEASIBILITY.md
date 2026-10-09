# FEASIBILITY — product-faithful creative, video, 3D, brand kit, compliance
Phase 6 deliverable · NorthstarOS Design Studio deep research
Author: SEO/ad-loop & feasibility subagent · Date: 2026-10-08 (all `accessed` dates UTC)

**Labels:** VERIFIED = observed on a public doc during this research. REPORTED = vendor marketing /
third-party claim. UNKNOWN = not confirmed.
No paid calls, no API keys, no logins, no trials.

---

## 1. Product-faithful image generation

### 1.1 Approach and maturity

Four distinct techniques, at three different maturity levels:

| Technique | What it does | Maturity in 2026 (public docs) | Evidence |
|---|---|---|---|
| **Reference-image conditioning** | Supply N reference images; output preserves the referenced subject/style across new scenes | **Mature** | VERIFIED — Google Gemini image-generation docs: up to **14 reference images** total, of which up to 10 "objects with high-fidelity", up to 4 (Gemini 3.1 Flash Image) or 5 (Gemini 3 Pro Image) "characters to maintain character consistency", and up to 3 "images to be used as style references" (Pro only). BFL: FLUX.2 multi-reference editing references **up to 10 images**; FLUX 3 Image combines up to ten references. |
| **Masking / inpainting / outpainting** | Edit only inside a mask, or extend the canvas outside the mask | **Mature** | VERIFIED — OpenAI `Images.edit` ("Edit parts of an image by uploading an image and mask that identifies the areas to replace"). BFL `FLUX.1 Fill [pro]` (mask may be the alpha channel or a separate image), `FLUX.1 Expand [pro]` (add pixels to any side), `FLUX Erase` (mask-driven object removal). Ideogram `Edit` (mask: black=edit, white=keep, min 10% black, same dimensions as source), `Reframe` (outpainting), `Replace Background`. AWS Titan Image Generator v2 `INPAINTING` / `OUTPAINTING` with `maskPrompt` (text-described mask) **or** an image mask. |
| **Bounding-box / layout control** | Place elements at exact coordinates | **Emerging → maturing** | VERIFIED — BFL FLUX 3 Image: "Place every element of an image with bounding boxes, then recolor, move, replace, or remove elements box by box while the rest of the image stays unchanged." Kontext also documented to accept "bright colored boxes as annotations for targeted local editing". Ideogram 4.0: "JSON prompting for pixel-precise text placement with bounding boxes." |
| **Deterministic compositing (paste the real photo over a generated background)** | No model involved: cut out the seller's real product, place it on a generated plate | **Mature — and this is the only fully deterministic option** | VERIFIED as available primitives — Titan v2 `BACKGROUND_REMOVAL` returns a transparent-background cutout, auto-detecting multiple foreground objects; BFL FLUX Erase / Outpainting; Ideogram Background Remover app. Compositing itself is ordinary image processing. |

**Key structural finding:** BFL publishes an official use-case page titled **"Product Consistency —
Maintaining product consistency across image edits"** whose examples are explicitly packaging
scenarios: a logo applied to a perfume bottle, a bottle re-lit in a new scene, and "Place the LEGO
deer product image on a real LEGO retail box… glossy printed cardboard package with sharp edges,
folded seams". A second page, **"Product Mockups — creating product mockups with transparent
backgrounds and label integrity"**, states in its own summary that it covers label integrity.
VERIFIED (official docs). This is direct vendor acknowledgement that product-identity and
label-text fidelity are first-class, documented concerns — not an accident.

### 1.2 Cost drivers

- **BFL (VERIFIED, published rates).** Credit-based; **1 credit = $0.01**. FLUX.2 pricing is
  megapixel-scaled, "from" per image: klein 4B $0.014, klein 9B $0.015, pro $0.03 (t2i) / $0.045
  (edit), flex $0.05, max $0.07. FLUX 3 Image is per-image by resolution: 768sq $0.041, 1k $0.048,
  2k $0.100, 4k $0.607. Fine-tuned endpoints are billed at the base rate during public beta.
  Klein is billed as a flat first megapixel plus a per-additional-MP rate.
- **Google Gemini (VERIFIED, published rates).** Image output is token-priced: Gemini 3.1 Flash Lite
  Image $30/M tokens → 1K image (1120 tokens) ≈ **$0.0336**; Nano Banana 2 (3.1 Flash Image)
  $60/M → 1K ≈ **$0.067**, 2K ≈ $0.101, 4K ≈ $0.151; Nano Banana 2.1 $30/M → 1K ≈ $0.0336,
  2K ≈ $0.0504; Gemini 3 Pro Image $120/M → 1K/2K ≈ **$0.134**, 4K ≈ **$0.24**. Batch halves
  image-output price (e.g. 3 Pro Image $60/M → $0.067 per 1K/2K image).
- **Cost driver summary:** resolution dominates (roughly 4× from 1K→2K→4K tiers), then model tier,
  then reference-image count (multiple references cost more input tokens/images), then iteration
  count. Draft/low-res exploration is cheap; final render is not.

### 1.3 Failure modes (documented or structurally implied)

| Failure mode | Mechanism | Mitigation | Evidence |
|---|---|---|---|
| **Product identity drift** | The model re-renders the product from its prior, not from the reference; shape, proportions, colour, logo placement shift | Deterministic compositing of the real cutout is the only guaranteed fix; reference images reduce but do not eliminate drift | REPORTED — the Listing Optimization AI blog states one model "sometimes modifies product details"; BFL docs acknowledge the need for "Product Consistency" as a discipline |
| **Label text corruption** | On-pack typography is regenerated, producing garbled or altered words | **Never generate label text.** Composite the label region from the real artwork; generate only the background/context | REPORTED (vendor docs call out "label integrity" as the goal) + UNKNOWN for actual per-generation fidelity |
| **Packaging warping** | Boxes bend, seams fold wrongly, shrink sleeves distort | Use real dieline-driven 3D renders (§4) instead of generative mockups for anything print-adjacent | Structural inference; UNKNOWN quantitatively |
| **Background/product boundary artefacts** | Halos, contact shadows that don't match the new plate, reflections that betray the composite | Generate background with matched lighting direction; generate shadow separately; keep lighting metadata in the brief | Structural inference |
| **Stale/irreproducible output** | Results change between calls | Store `seed`, `model`, `model_version`, `prompt_hash` per variant (BFL exposes `seed`; Ideogram exposes `seed` 0–2,147,483,647) | VERIFIED (documented params) |
| **Model lifecycle** | Endpoints retire | e.g. AWS Amazon Nova Reel **v1:0 model EOL date 2026-09-30**, legacy ≥6 months | VERIFIED (AWS model page) |

### 1.4 Buildable now vs later

**Now:** reference-locked generation for *context/lifestyle* imagery; deterministic cutout +
compositing for the product itself; mask-based background replacement and canvas extension for
aspect-ratio variants; bounding-box placement of decorative elements.
**Later / not yet:** trusting a model to reproduce the seller's actual packaging or label typography.
That should be composited, never generated.

---

## 2. Reliable on-image text

### 2.1 Approach and maturity

**Emerging → maturing, and materially better than it was, but still not a substitute for typeset
text.** Documented capability by family:

| Model family | Documented text capability | Maturity | Label |
|---|---|---|---|
| **Ideogram** | Officially positioned on typography: "excels at integrating text into images for logos, branding, POD, or design layouts"; docs say it "excels in the generation and integration of text into an image" as overlay, typographic design, or integral element. **Ideogram 4.0 adds JSON prompting for pixel-precise text placement with bounding boxes.** Also: **Custom Models — "Train on-brand image models from your approved assets so generations follow your style, art direction, typography, and visual identity."** | **Mature-ish (specialist)** | VERIFIED (official docs) |
| **BFL FLUX.2 [flex]** | Model described in the API reference as "Specialized for **typography and text rendering**, and for preserving small details". Docs give a text-rendering recipe: put the text in quotation marks, specify placement, describe style, state font size, use hex codes for brand text. Kontext [max] is described as meeting "premium consistency" with "greatly improved prompt adherence and **typography generation**". | **Mature-ish** | VERIFIED |
| **Google Gemini (Nano Banana family)** | "**Advanced text rendering**: Capable of generating legible, stylized text for infographics, menus, diagrams, and marketing assets" (Gemini 3 image models). | **Mature-ish** | VERIFIED |
| **OpenAI GPT Image** | No typography-accuracy claim found in the public docs. Editing precision is the stated differentiator ("Sunburst for workflows where editing precision matters most"). | **UNKNOWN for typography** | UNKNOWN |

### 2.2 Known failure modes

Documented or vendor-acknowledged (all REPORTED unless noted):

- **Long-form text is out of scope.** Ideogram's own docs: "not designed to generate complete,
  text-heavy documents. It can insert titles or short blocks of text, but **long passages should be
  added afterward in a graphic editor**."
- **Non-Latin scripts fail.** Ideogram docs: "Text rendering is most accurate in English. Non-Latin
  scripts often produce unpredictable results." Marketing page adds support is "expanding".
- **Text accuracy is a marketing number, not a measurement.** Ideogram's FAQ claims 95% text-rendering
  accuracy versus 30–50% for other generators. REPORTED, vendor-supplied, no methodology. Treat as
  UNKNOWN.
- **Spelling/grammar inside pixels is unrecoverable** without regeneration — a single wrong glyph in
  a rendered headline is not editable.
- **Font fidelity.** Models choose an approximate font. Exact brand typeface cannot be guaranteed.

### 2.3 The recommended architecture (and why)

**Do not rely on generated text for anything that must be exactly right.** Generate the *scene*, then
**composite real typography deterministically** on top (vector text in a fixed slot, using the brand
font, with character limits enforced). This is:

- fully deterministic and therefore auditable;
- reversible (a typo is a 2-second fix, not a regeneration),
- testable in a pre-flight (§6),
- consistent across every variant and locale,
- aligned with Amazon's own guidance (§5.1 of SEO_AD_LOOP.md): keep embedded text limited and large
  enough to read on mobile.

Generative typography is useful for *exploration* — showing a designer what an infographic might look
like — not for production output.

---

## 3. Video generation

### 3.1 Maturity

**Emerging → maturing, with real per-second pricing and real latency.**

| Provider | Documented capability | Maturity | Cost driver evidence |
|---|---|---|---|
| **BFL FLUX 3 Video** | Text-to-video, image-to-video (pin a start frame, set start+end frame, interpolate keyframes), video continuation (`v2v`), video edit (remove/add/replace objects, change setting, restyle, change text or dialogue), video upscale 1080p/2K/4K, multi-shot films with directed cuts, synchronized audio and speech/dialogue/voiceover | **Emerging–maturing** | VERIFIED — **per-second pricing** by resolution class: t2v and i2v `$0.17/s` (hd), `$0.29/s` (fhd), `$0.40/s` (qhd), `$0.80/s` (uhd); `v2v` `$0.41–$0.95/s`; **draft mode `$0.06/s`** ("about a third of a full render, so you can explore variants freely and only pay full price for the shot you keep"). Video Upscale priced **per output megapixel-second**: $0.07 (Precise) / $0.10 (Creative) — worked example given: a 10s clip to 1080p = 19.8 MP·s = $1.39 / $1.98. Video Edit `$0.03/s`. |
| **Amazon Nova Reel** | Text-to-video and text+image-to-video with camera-motion controls. Videos generated in **6-second increments up to 2 minutes**, 1280×720, 24fps, async only (`StartAsyncInvoke`), writes `output.mp4` plus per-shot `shot_NN.mp4` files and `manifest.json` / `video-generation-status.json` to S3. Multi-shot storyboard: an image, a prompt, or both per 6-second interval. | **Emerging** | VERIFIED (docs). Latency is explicit: **~90 seconds for a 6-second video, ~14–17 minutes for a 2-minute video.** Model `amazon.nova-reel-v1:1`. Content provenance via Content Credentials (C2PA). English only. **`amazon.nova-reel-v1:0` EOL 2026-09-30.** |
| **Google Veo** | Documented in Gemini API pricing as video output billed by output token consumption, ~5,792 tokens/second of 720p video ≈ **$0.10 per second** (Standard). | **Emerging–maturing** | VERIFIED (pricing page) |
| **Amazon Ads Video Generator (Creative Studio)** | "Turn your products into ready-to-run video ads" from a product ASIN or a single product image. Stated available for Sponsored Brands video in AU, CA, FR, DE, IN, IT, JP, MX, ES, UK, US; in the US also reachable from Campaign Manager. | **Emerging** (login required) | REPORTED (Amazon Ads help/marketing pages) |

### 3.2 Cost drivers

**Duration × resolution × render mode**, with a cheap draft tier. A 15-second 1080p BFL t2v full render
is $0.29/s × 15 = $4.35; the same clip as a draft is $0.90. Upscaling is billed separately and
*megapixel-seconds* scale badly: a 10-second 1080p upscale is ~$1.39–1.98 on top. Realistic planning
number for a 15–30s product video at fhd is therefore **low single-digit dollars per finished
second** if you upscale, **~$0.17–0.29/s** if you render at final resolution directly.

### 3.3 Failure modes

- **Latency is architectural, not incidental.** 14–17 minutes for a 2-minute Nova Reel video; up to
  ~30 minutes in `PROCESSING` for video assets in the Ads asset library because of transcoding. Any
  UX that promises live video is not buildable.
- **Product identity drift across shots** — the same failure as §1.3, compounded by motion.
- **Aspect-ratio lock.** Nova Reel: 1280×720, 16:9 only. Vertical (9:16) creative needs a different
  provider or a re-render.
- **Shot and duration quantization.** 6-second increments; not every ad length is expressible.
- **Audio/voice drift and mispronunciation** in generated voiceover.
- **Regional/language limits** (Nova Reel English only).
- **Model EOL churn** (Nova Reel v1:0 already EOL 2026-09-30).

---

## 4. 3D / packaging mockups

### 4.1 Maturity: **mature, deterministic, and the correct tool for anything print-adjacent**

| Tool | What it does | Maturity | Label |
|---|---|---|---|
| **Esko Studio** | 3D packaging design inside Adobe Illustrator using **real production artwork**, syncing 3D models with printed packaging ("digital twin"); patented print modelling that simulates printing and finishing operations one by one, in order, on the right substrate (substrates, process/PANTONE/spot colours, spot UV, embossing/debossing, die-cutting, hot/cold foils, holographics); Shrink Sleeve toolkit; Store Visualizer for virtual shelves; packshot/movie export. Bundle tiers (Essentials vs Advanced) and a 30-day trial. Custom bespoke 3D shapes are a **paid modelling service** ("send the Shapes Request Form to shapes@esko.com to get a price quote"), with print areas definable per label/back/sleeve. | **Mature (professional desktop)** | VERIFIED (vendor pages) |
| **Adobe Substance 3D** | Dieline cut visualisation, print effects (emboss, logo), PBR materials, decals/patterns from Illustrator/Photoshop files, real-time path tracing, **integrated UV export that preserves the original dieline cuts and print requirements**, FBX/GBL/USDZ import incl. CAD conversion, Stager for substrate-based staging. | **Mature** | VERIFIED (vendor pages) |
| **Dieline template services / APIs** | Catalogues of tens of thousands of production-ready dielines with custom dimension/thickness editing; downloads in **PDF, DXF and SVG**; API endpoints for dieline generation, 3D mockups with custom dimensions, automatic nesting and imposition; Illustrator plug-ins. | **Mature (utilities)** | REPORTED (vendor site claims) |

### 4.2 Cost drivers and failure modes

- **Cost drivers:** desktop licences (bundled tiers), bespoke shape modelling (quoted per shape),
  render time, and human designer time. This is the expensive, slow, deterministic end of the stack.
- **Failure modes:** wrong dieline for the actual supplier; print-area mis-registration between label
  panels; substrate/finish mismatch (a matte render used to sell a gloss pack); **dieline changes not
  propagating** to already-produced assets if the 3D asset isn't versioned against the artwork.
- **Failure mode unique to generative approaches:** a generated mockup has **no dieline truth** at
  all. If the pipeline generates a box, it has invented a structure. That is fine for a concept and
  unacceptable for a packshot.

### 4.3 Buildable now vs later

**Now:** use dieline-driven 3D renders as the *product reference* for §1's compositing. This gives
product-faithful, label-accurate, print-truthful imagery at any background/lighting — the exact
inverse of generative product generation.
**Later:** automated dieline→3D pipeline requires either the seller's 3D asset or a paid bespoke
shape model. That is a per-SKU data-acquisition problem, not a modelling problem, and should be
budgeted as such.

---

## 5. Brand-consistency enforcement

### 5.1 Deterministic (build these first — they are cheap and exact)

| Mechanism | Status |
|---|---|
| **Fixed template & slot system** — canvas size, safe area, text slots, logo placement, min font size, contrast floor | Fully deterministic. Ordinary layout code. |
| **Brand palette as hex, enforced in code** — reject any asset whose dominant colours fall outside the palette | Deterministic. Supported by the models themselves: BFL documents **HEX colour code prompting** explicitly as "ideal for brand consistency, design work, and exact color control"; Titan v2 accepts **1–10 hex codes** as a colour palette; Titan v2 also offers `COLOR_GUIDED_GENERATION`; Ideogram exposes a `color_palette` parameter. |
| **Font lock + vector text compositing** (§2.3) | Fully deterministic. |
| **Versioned brand kit** with an audit trail — every asset records `brand_kit_version` | Deterministic. |
| **Approved-asset registry** — only registered logos/packshots may be used as references | Deterministic policy enforcement. |

### 5.2 Probabilistic (reduce, never rely on)

| Mechanism | Documented status |
|---|---|
| **Fine-tuned / custom brand models** | Ideogram offers **Custom Models: "Train on-brand image models from your approved assets so generations follow your style, art direction, typography, and visual identity"** (VERIFIED, official docs). BFL offers fine-tuned endpoints on FLUX 1.1 [pro] ultra and FLUX.2 [klein] 9B, plus LoRA style training on klein (VERIFIED docs); Titan v2 supports fine-tuning for **subject consistency** (pet, shoe, handbag) and for style/personalisation. **Important documented limitation: with a fine-tuned Titan model you cannot use inpainting, outpainting or the colour-palette features.** |
| **Style-reference images** | Gemini 3 Pro Image: up to 3 style-reference images. BFL FLUX.2 style transfer. Ideogram `style_reference_images` / style presets. All probabilistic. |
| **Prompt-level brand language** | Works, unreliably. |

### 5.3 Verdict

Brand consistency must be **≥90% deterministic by construction** (templates, palette hex, font lock,
vector text, approved-asset registry, versioned kit) and only marginally probabilistic
(style reference / fine-tune as a *tie-breaker inside a template*). Any design that asks a generative
model to hold the brand together is asking for drift. This is the single highest-leverage architectural
decision for Design Studio, and it is also the cheapest.

---

## 6. Compliance pre-flight checks before export

Amazon publishes enough hard numbers that most of this is trivially deterministic.

### 6.1 Deterministic (implement as hard gates)

| Check | Rule | Source | Label |
|---|---|---|---|
| Pixel dimensions | Listing images: **500–10,000 px** on the longest side; **1,600px+ recommended** for zoom; at least **1,000 px** to enable zoom | Seller Central forum stickies quoting the Product image guide; Amazon *General Guidance for Listing Optimization* PDF ("Images are required to be 1,600px or larger on the longest side") | VERIFIED (PDF) / VERIFIED (snippet) |
| File format | Listing images: JPEG (preferred), TIFF, PNG, non-animated GIF. **A+ images: .jpg, .bmp, .png only, RGB colourspace, CMYK not supported, animated GIF prohibited, individual files under 2 MB, minimum 72 dpi** | Amazon *A+ content guidelines* (GW8U76SSNTRTBX7) via snippet | VERIFIED (snippet) |
| File size | A+: <2 MB per file | same | VERIFIED (snippet) |
| Background is pure white (MAIN) | RGB 255,255,255; reject off-white/grey casts | Amazon *General Guidance for Listing Optimization* PDF; *Amazon Home Selection Image Guide* PDF ("Use a pure white background of 255 RGB") | VERIFIED |
| Product frame fill (MAIN) | Product occupies ≥85% of the frame; whole product in frame, not cropped | same PDFs | VERIFIED |
| MAIN-image content | No text, logos, borders, colour blocks, watermarks or other graphics over the product or in the background; no multiple views in one image; no Amazon logos/trademarks | same PDFs | VERIFIED |
| SU-supported image variants | Only `MAIN`, `PT01`–`PT08`, `SWCH` are programmatic | SP-API *Submit media attributes* doc | VERIFIED |
| A+ module canvas | e.g. Standard Four Images & Text 200×200; Single Left/Right Image 300×300; Comparison Chart 400×400; Image & Dark/Light Text Overlay 970×300; Premium Full Image desktop 1464×600 (min), mobile 600×450 (min); Premium background video 960×540 min, 200 MB max, 180 s max | Amazon official module-template PDFs (downloaded and text-extracted) | VERIFIED |
| Character limits | A+ module headline/body limits per module (e.g. Premium headline 80, body 300) | Amazon *Premium A+ Module Guide* PDF | VERIFIED |
| **AI-generated-people metadata** | If an image features people entirely generated by AI and photorealistic, add the keyword `contains-synthetic-performer` to the `dc:subject` (XMP) field via an IPTC-compatible metadata editor **before upload**. Do **not** tag when: only real people (even AI-altered); only characters from movies/games/expressive works; no people; people are not photorealistic. An "AI-generated" checkbox also exists in the A+ Creative Assets uploader. | Amazon *A+ content guidelines* (GW8U76SSNTRTBX7) via snippet | VERIFIED (snippet) |
| Video specs | Frame rate ∈ {23.98, 24.0, 25.0, 29.97}; duration ∈ {15.0, 30.0}s; ≥2 audio channels; aspect ratio per program (e.g. Stores intro splash requires 9:16) — **exactly the checks Amazon's own asset library returns in `failedSpecChecks`** | Amazon Ads *Creating assets* doc, response example | VERIFIED |

### 6.2 Heuristic (flag for human review, never auto-block)

| Check | Why it's heuristic |
|---|---|
| On-image text legibility on mobile | Requires rendering at mobile scale and measuring contrast/effective size; Amazon's rule is "small text that is unreadable when shown on mobile devices… is not allowed" — a judgement, not a number |
| Text/ink coverage ratio | No Amazon numeric limit found; a heuristic threshold (e.g. flag >X% of area covered by text) must be tuned |
| Prohibited-claim language | Requires lexicon + regex + LLM classification. Amazon's A+ guidelines prohibit (among others) mimicking Amazon logos/detail-page headings, adult-product and criminal-activity content, promotional content, prices and contact info in A+ images. Keyword matching catches the obvious; paraphrase does not |
| Blurry / low-quality / jagged edges | Measurable with sharpness metrics, but the threshold is a judgement |
| Colour accuracy vs the real product | Requires a reference sample and a perceptual delta; threshold is a judgement |
| Category-specific style-guide conformance | Amazon publishes category style guides; they are numerous and change. Needs a maintained rule set, not code |
| IP-rights / third-party logos | Needs a trademark list and human review |

### 6.3 Architecture recommendation

Run the deterministic set as a **hard pre-export gate** (fail = no export, no upload). Run the
heuristic set as a **soft gate** that produces a review queue with reasons. Mirror Amazon's own
`failedSpecChecks` shape — `{program, specProgramName, specification, actualValue, arguments,
failureReason, isPassed, stringId}` — because it is a proven, machine-readable contract and it makes
the pre-flight output directly comparable to Amazon's post-upload rejection report. Add a
**PROCESSING→ACTIVE polling** step and treat `failedSpecChecks` from Amazon as a *post-flight*
correction signal that feeds back into the pre-flight rule set.

---

## 7. Amazon "Manage Your Experiments" — confirmed, and programmatic creation is NOT possible

### 7.1 It exists (VERIFIED — multiple official Amazon sources)

- **Seller Central help page** (VP453K5XRBJS7Y9 / GVP453K5XRBJS7Y9), corroborated by the official
  *Manage Your Experiments* 1-pager and *Best Practice Guide* PDFs (downloaded and text-extracted;
  versions dated 2022-11-01 and 2023-10-03).
- **What it supports:** A/B split tests on **product title, main image(s), bullet points, product
  description, and A+ Content** — the sell.amazon.com page adds "including Brand Story", and the FAQ
  confirms **multi-attribute experiments** ("test multiple page elements at the same time, like title,
  images, and bullet points").
- **Who can use it:** professional selling account + Brand Representative for a brand enrolled in
  Amazon Brand Registry; available in US, CA, MX, UK, DE, FR, ES, IT, NL, PL, SE, IN, JP. An ASIN is
  eligible only if it belongs to your brand **and has received enough traffic in recent weeks** to
  produce valid results.
- **How it decides:** a **Bayesian** approach; results updated **weekly**; the confidence of a winning
  treatment is the percentage of posterior outcomes showing a positive unit-sales impact; conclusion
  at **66% or better** significance. Reported per version: units, sales, conversion rate, units sold
  per unique visitor, and sample size, plus a projected one-year impact (completed experiments only,
  explicitly not accounting for seasonality or price changes).
- **Auto-publish** of the winning content (opt-in at creation, toggleable mid-flight) and
  **"run to significance"** duration are available; the Amazon FAQ states the auto-publish capability
  and the "to significance" feature are **in beta and currently available for title and image
  experiments**.
- **Similarity guard:** Amazon warns at creation when the two versions are too similar and may not
  deliver conclusive results; content that fails validation (e.g. non-white background in a category
  that requires it) will not start as scheduled, and the failure is reported with an error code.
- Amazon's own stated benefit numbers (internal data, vendor claims): conversion improved by 15% and
  up to 25% sales increase reported by brands using MYE.

### 7.2 Programmatic creation: **not possible** (VERIFIED by absence, from two independent indexes)

- **SP-API:** the complete documentation index (`developer-docs.amazon.com/sp-api/llms.txt`, 1,122
  lines of every documented page) contains **zero** occurrences of "experiment", "split test", or
  "A/B". The Reports API, Listings Items API, A+ Content API, Feeds, Notifications and Catalog APIs
  are all indexed; none manages experiments.
- **Amazon Ads API:** the complete table of contents (`advertising.amazon.com` docs `toc2.json`,
  170 KB of every page path and OpenAPI spec) contains **zero** occurrences of "experiment" or
  "experiments". It also contains **no creative-generation endpoint** — only `creative-asset`
  library pages (upload / register / manage).

**Stated plainly:** no third-party tool can create a Manage Your Experiments experiment
programmatically, and none found claims to. The closest programmatic surfaces for *content* are the
SP-API Listings Items API (MAIN/PT01–PT08/SWCH image locators), the A+ Content API
(create/update/publish A+ documents), and the Ads creative asset library API (register image/video
assets). All three **publish** content; none **experiments** on it.

### 7.3 Consequence for variant testing — align, don't replicate

Design Studio should treat MYE as the measurement authority for listing variants and design around
its constraints:

1. **One material change per experiment** — MYE's own guidance warns that too many changes at once
   yield unclear findings (and multi-attribute is a separate mode, not a licence to change everything).
2. **Version A and B must be substantively different** or Amazon warns you the result may be
   inconclusive. Briefs should target a real hypothesis with an expected delta, not a cosmetic tweak.
3. **Never end early.** MYE's own docs: ending early increases the chance of overestimating impact or
   selecting the wrong version. The pipeline's auto-promotion must inherit this rule.
4. **Traffic-gated.** Low-traffic ASINs cannot be tested. The pipeline must skip or queue them, and
   must say so rather than fabricating a result.
5. **Content validation is Amazon's.** A variant that fails validation will not start. Pre-flight (§6)
   must therefore be *stricter* than Amazon's, not equal to it.
6. **Human-in-the-loop for scheduling.** Because there is no API, the operator creates the experiment
   in Seller Central. The product's job is to hand the operator a ready-to-upload Version B plus the
   hypothesis, then **ingest the reported result** into the learning store. That ingestion is the
   only manual link in the loop and it is the one Amazon gives us no automation for.

---

## 8. What I could not inspect (R7)

- **No account interiors.** Amazon Ads console, Seller Central (incl. Manage Your Experiments UI and
  Image Manager), Helium 10, Jungle Scout, Pacvue, Perpetua, SellerSprite, Amazon Creative Studio /
  Creative Agent, Ideogram/BFL/Gemini/OpenAI playgrounds and dashboards. Every capability inside those
  products is REPORTED at best.
- **No generation was actually run.** Every image/video capability here is from documentation.
  Nothing in this file is an observed output; therefore **no failure-mode frequency is quantified**.
  All maturity calls describe what the *documentation* supports, not observed reliability.
- **No pricing page for AWS Bedrock / Nova Canvas per-image cost was captured** — the AWS pricing page
  rendered without extractable figures. Third-party planning heuristics (~$0.06–0.08/image Canvas,
  ~$0.80/6s Reel shot) exist but are REPORTED and were deliberately not used as facts.
- **OpenAI GPT Image pricing** was not captured (docs page didn't expose the rate table in fetched
  output); only model names (`gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`) and the
  generations/edits/multi-turn capability are VERIFIED.
- **Third-party 3D/dieline vendors** (diecuttemplates.com etc.) were assessed from marketing pages
  only — REPORTED. Esko and Adobe were assessed from their own product pages — VERIFIED.
- **Amazon Ads API v1 (ads-v1)** report shapes were not fetched; v3 deprecates 2027-06-30 so those
  shapes must be re-verified before build.
- **Field-level schemas** for Helium 10 MCP, Jungle Scout JSON, Pacvue, Perpetua APIs: UNKNOWN.
- **Seller Central help pages** were not machine-readable; their content here is from quoted snippets
  (**VERIFIED (snippet)**) and official Amazon PDFs. Any "snippet"-labelled requirement could be stale
  or region-specific.
- **The claim that Amazon removed A+ alt-text** (§5.7 of SEO_AD_LOOP.md) is unverified against any
  Amazon announcement and should be re-checked before any SEO feature depends on it.
- **No real ad or sales data.** No report was ever pulled; every field description is documentary.
