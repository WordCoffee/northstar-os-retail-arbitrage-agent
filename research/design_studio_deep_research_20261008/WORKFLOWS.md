# WORKFLOWS — end-to-end mapping of the competitor set

Phase 2 deliverable, NorthstarOS Design Studio deep research (2026-10-08).
Companion files: `PHASE1_AMAZON_SELLER_MATRIX.csv`, `SOURCES.csv` (source ids S300+ are this
document's own register range).

Every capability below carries one of three labels, per `RULES.md`:

- **VERIFIED** — observed directly on a public page, doc or free surface during this research.
- **REPORTED** — a vendor marketing page, third-party article, review or video says so.
- **UNKNOWN** — not confirmed. Never guessed, never inferred, never filled in from memory.

---

## 1. Method and coverage

### 1.1 What was inspected

Public, no-login surfaces only. No trials, no accounts, no API keys, no paid provider calls.

| Surface type | Count | Notes |
|---|---|---|
| Vendor product / tool pages | 21 | Helium 10, Jungle Scout, Pacvue, Perpetua, Flair, Photoroom, Pebblely |
| Vendor pricing pages | 6 | Flair, Photoroom, Pebblely, Helium 10. Canva and Pacvue pricing pages were not captured |
| Vendor help-centre / KB articles | 20 | Canva Help Center, Figma Help Center, Helium 10 KB, Perpetua Help Center, Pacvue Support |
| Amazon Ads official pages | 11 | Creative Solutions hub, Support Center "Understand Creative Studio", image-generation guide, three launch announcements, two API developer guides, two supported-creative spec pages, one About Amazon press release |
| Official Amazon PDF | 1 | A+ Content Best Practices guide (sellercentral-hosted media URL) |
| Developer / API docs | 3 | Amazon Ads asset library + DSP creative management, Pebblely API, Canva MCP |
| Public YouTube videos | 14 | Titles, channels and dates recorded below; transcripts used where public |

Sources for every row are registered in `SOURCES.csv` as S300–S380 and are cited inline as
`[S3xx]`.

### 1.2 What was NOT inspected — plain statement of limits

1. **No product was used.** Every step count and every friction point in this document is
   reconstructed from documentation, help-centre procedure lists and public walkthroughs. No
   generation was run, so no measured time-to-first-asset exists unless a vendor published a
   number, and every such number is a vendor claim, not a benchmark.
2. **No logged-in surface was reached.** Amazon Ads Creative Studio, Helium 10 Listing Builder,
   Pacvue, Perpetua and Canva's editor are all behind authentication. Their internal flows are
   known only from the procedure lists their vendors publish.
3. **Pacvue's site blocks automated fetching.** `pacvue.com` and `www.pacvue.com` returned HTTP 403
   on repeated attempts. Content attributed to Pacvue was read through search-engine rendering of
   the same public URLs and is labelled REPORTED for that reason [S328, S329, S330]. Its support
   knowledge base did load [S331]. Treat Pacvue rows as the weakest evidence in the set.
4. **Pricing pages that did not render.** Canva's pricing page and Pacvue's pricing page were not
   captured. Canva plan gating is therefore described from its help centre, not its price list.
5. **Perpetua's help centre is near-empty.** The publisher states fourteen articles and surfaced no
   product documentation on creative generation, brand kits, approvals or export [S333]. Perpetua's
   workflow rows are consequently the thinnest in this document and several cells are UNKNOWN.
6. **Jungle Scout and Perpetua were inspected for Part A but excluded from Part B workflow
   mapping.** Neither exposes an asset-generation, asset-editing or asset-export surface in their
   public pages. Mapping a design workflow for them would be fabrication. They are recorded in
   `PHASE1_AMAZON_SELLER_MATRIX.csv` with UNKNOWN workflow cells.
7. **Transcripts.** Three YouTube sources returned no transcript and are recorded with the
   limitation "no transcript observed" [S372, S376, S379]. Auto-generated transcripts were used for
   the rest and are diet-level evidence only — they are third-party narration, not vendor specs.
8. **No competitor prose is reproduced.** Descriptions below are original wording. No screenshots,
   no template text, no taglines.
9. **Time claims are vendor claims.** Where a time is quoted it is because a vendor published it.
   The one thing this research can say with confidence about speed is which vendors publish a number
   at all — see §3.
10. **Not exhaustive.** The competitor set is the operator's named list plus the general design
    tools. AdCreative.ai, Claid, Creatopy, PixTeller, Booth.ai, ProductScope, CapShout and similar
    tools are being covered by other agents in this research folder and are out of scope here.

### 1.3 The eight mapped competitors, and why these eight

The eight most relevant to an Amazon seller's design studio, chosen for having an observable
asset-generation or asset-editing workflow:

| # | Competitor | Tier | Why included |
|---|---|---|---|
| 1 | Amazon Ads Creative Studio (image + video generator) | Amazon-seller-specific | The platform owner's own studio; ASIN-first entry; publishes back into campaigns |
| 2 | Photoroom | Amazon-seller-specific | The most complete marketplace-image operation surface: compliance, batch, brand kit, API |
| 3 | Flair | Amazon-seller-specific | The closest thing to a real design studio: canvas, layers, props, real-time collaboration |
| 4 | Pebblely | Amazon-seller-specific | Shortest published path to a first asset (3 steps) and the strongest on-pack text handling |
| 5 | Helium 10 (AI Listing Builder + AI image generation) | Amazon-seller-specific | The listing specialist: copy and image generation inside one keyword-driven tool |
| 6 | Pacvue | Amazon-seller-specific | Included deliberately. It is the largest enterprise Amazon-seller platform on the operator's list and it has **no generation layer at all** — that absence is a finding, not a gap in the research |
| 7 | Canva | General design | The default general-purpose studio; the most mature brand-kit and approval surface in the set |
| 8 | Figma | General design | The most mature version-history and handoff surface in the set; the contrast case for canvas depth |

Five of the eight are Amazon-seller-specific tools from Part A, satisfying the minimum of three.

---

## 2. Workflow comparison table

Cell text is abbreviated; the full reasoning is in §3. "UNK" = UNKNOWN per the label rules.

| Competitor | Entry (how you start) | Input | Brief step | Generation | Iteration | Editing | Review / approvals | Export | Publish |
|---|---|---|---|---|---|---|---|---|---|
| **Amazon Ads Creative Studio** | Log in to the ad console → Creative Tools → Creative Studio → "generate image" (documented as a six-step procedure) [S302] | Pick an existing **ASIN**; or upload your own product image; or a free-text prompt with pre-set styles and themes [S302] | No structured brief. Creative Agent does product and audience research conversationally, then produces storyboards [S300, S301] | Amazon auto-generates "enhanced product images" from the chosen ASIN, then prompt/theme variations. Video generator turns one product image into a multi-scene video with **six** options and text animations [S305, S306] | Re-prompt with themes; the vendor's own prompt guidance says to rewrite the whole scene description rather than appending "now add a tree" [S302] | UNK — no layer editor documented; refinement is prompt-and-theme only | All AI output passes Amazon Ads moderation review before it can be used [S301] | Saved to the Creative Assets library and attached to a campaign. Display sizes and video specs documented [S310] | **Yes — publishes directly into campaigns.** This is the only tool in the set that closes the loop itself |
| **Photoroom** | Upload a product photo from the homepage, the app, or a catalogue import [S345] | Upload / camera capture; Brand Kit seeded from a website URL or PDF [S341] | No brief step | Background removed automatically, then a scene, staging, fashion model, video or logo is generated. Claims background generation in under a second [S346] | Regenerate background; swap scenes; re-run a batch | Full layer editor: text incl. curved text, AI backgrounds, instant shadows, remove objects, retouch, recolour, expand/resize, product staging [S341, S342] | Team workspaces with roles and permissions; an enterprise **Visual QA** layer checks visuals before they reach the catalogue [S342, S346] | PNG / JPG / WebP; platform presets incl. Amazon; batch export; exact RGB 255,255,255; 4K gated to Ultra+ [S340, S345] | **No publish.** Exports for manual upload to Seller Central [S344] |
| **Flair** | Open the app and start from a photoshoot template or a blank canvas [S335] | Upload a clean product-only image; drag-and-drop props and 3D elements; optional custom model trained on your products | No brief step | Scene composition from the drag-and-drop canvas; on-model photography; video; ad generation. Marketing claims "seconds" [S339] | Per-element regeneration: regenerate product, regenerate human, variations, extend, magic erase/paint [S339] | Drag-and-drop canvas with lighting and camera-angle controls; 3D props; reusable templates at scale [S335] | Real-time team collaboration is advertised [S335]. **Approval workflow UNK** | Export dimensions UNK on the inspected pages | **No publish.** Download and hand off |
| **Pebblely** | Click "Add product" on the home screen [S348] | Upload a product image and crop it; name and tag it; **confirm extracted on-pack text**; pick a style image or brand colour | No brief step | Choose a template (40+ themes) or a custom prompt, a count (1/2/4) and a size. **~10 seconds per image**; high-resolution mode **~30 seconds at 2 credits** [S348] | Edit any result by describing the change; toggle resize/high-res during the edit; reposition, resize, rotate the product [S348] | Two-layer output (product + background) with layer ordering; reposition/resize/rotate [S347, S352] | UNK | Fixed size presets chosen *before* generation: 1080×1080, 1080×1350, 1080×1920, 1920×1080, 1200×628; canvas up to 2048×2048 [S347, S348] | **No publish.** Bulk download |
| **Helium 10 (AI Listing Builder)** | Listing Builder → Add Listing → create from scratch, or optimise an existing listing via Seller Central [S318] | Keyword bank from Cerebro reverse-ASIN, Magnet, My List or manual; product characteristics ≤500 chars; tone; audience; brand name; excluded words. 2026 builder also takes an uploaded image or a reference ASIN [S319, S323] | **Yes — the closest thing to a real brief in the Amazon-seller tier.** Captures product characteristics, tone, audience, brand name, marketplace/language, bullet structure and character limits [S319, S323] | Per-field AI generation ("write it for me") for title, bullets, description. AI image generation takes size, product scale and style then a prompt [S319, S322] | Accept suggestion or rewrite; the keyword bank visibly crosses off used terms and tracks root words; every field stays manually editable [S319] | Manual text editing only. **No image canvas documented** | UNK | Copy syncs to Amazon Seller Central. Image dimensions UNK | **Yes — listing copy syncs back to Seller Central** [S318] |
| **Pacvue** | Ingest SKUs, keyword lists and competitor lists into the platform [S330] | SKU/ASIN ingestion; keyword lists; competitor lists; rules and alert configuration [S330] | No brief step. Configuration is a rules-and-standards exercise | **No generation surface observed.** Outputs are content-health audits, alerts and auto-generated retailer tickets [S329, S330] | UNK — nothing to iterate on | **None** — no canvas or asset editor [S330] | Auto-ticketing routes content exceptions to owners [S329]. Approval workflow UNK | UNK | **No publish of creative.** It audits and tickets against whatever the seller published elsewhere |
| **Canva** | Homepage → Canva AI search box, or open the editor → Templates tab [S353] | Text prompt; upload; Add from Canva; Import; **Apply Brand Kit** [S353] | **Partly.** Magic Design infers a brief from the prompt plus attached media; Brand Kit + Brand Templates act as a standing brief [S353, S358] | Magic Design returns template candidates matched to the prompt/media; Magic Media makes images and 4-second silent clips; Canva AI Video makes 8-second clips with sound [S353] | Regenerate templates; Magic Edit / Expand / Eraser / Grab; Magic Morph re-styles elements; Magic Resize and Switch re-format [S354] | Full canvas: layers, locking, alignment guides, text panel, elements, draw tool, apps [S377, S378] | **Strongest in the set.** Brand Controls restrict approved colours and fonts **and can require design approval before publishing**; roles are owner / admin / brand designer / member; comments and real-time multiplayer [S359] | PNG / JPG / SVG / PDF standard; platform presets; Magic Resize for multi-format; Bulk Create [S354, S377] | Publishes to social platforms directly; not to Amazon. No Amazon-native features observed |
| **Figma** | Create a file in drafts → Make, or Actions → First Draft [S361, S362] | Text prompt; attach Figma frames, designs, community content, PDFs, images and text files; web search or a URL fetch for grounding [S362, S363] | **Partly, and the most developer-shaped.** A library choice plus a prompt; Make kits and npm packages carry design-system context [S363, S368] | First Draft builds editable wireframes/designs from Figma's own libraries; **the vendor states "a couple of minutes"** [S362]. Make builds interactive prototypes | Prompt a selected region to refine; style controls for colour, radius, spacing, typography; duplicate-and-edit; copy the preview as design layers [S362, S363, S368] | Full Figma Design editing; the properties panel, draw tool and annotations are available inside Make [S363] | **Strongest version control in the set.** Named versions with descriptions, restore, duplicate, viewer history; comments persist across restores; Dev Mode statuses (Ready for dev / Completed / Changed) with change reasons recorded in version history; notifications by email, desktop, push, Slack, Teams [S365, S366, S367] | PNG / JPG / SVG / PDF with export settings; GIF and MP4 nodes downloadable in Dev Mode [S364] | Publishes websites and prototypes via Figma Sites / Make. No Amazon-native features |

---

## 3. Per-competitor narrative teardowns

### 3.1 Amazon Ads Creative Studio — the platform owner's own studio

**The path.** The published procedure is six steps and it is the only fully documented end-to-end
flow in the Amazon-seller tier: open Creative Studio from the ad console's Creative Tools menu,
select a product by ASIN, save and continue, let the console auto-generate enhanced product images
from that listing, refine with prompts and themes, then save to the Creative Assets library or
attach the image directly to a campaign [S302].

**Entry is a listing, not a blank canvas.** That single design decision drives everything else.
Because the entry point is an ASIN, Amazon already holds the product imagery, the title, the
category and the price, so no upload step is needed for the common case. An upload path also
exists for sellers who want to enhance a different image [S304]. A second entry point opens through
Amazon DSP's Responsive eCommerce Creative, so the same generation can be reached from the
buy-side console as well as the sponsored-ads console [S302].

**There is no brief step.** What sits in its place is Creative Agent, a conversational surface
documented as performing product and audience research, brainstorming ideas and turning concepts
into storyboards before generating display, Sponsored Brands video, online video, audio and
streaming-TV ads [S300, S301]. That is a brief by conversation rather than a brief by form. For a
seller who wants structure — tone, audience, do-not-include list — there is no documented field to
put it in.

**Generation.** Amazon auto-generates enhanced product images from the selected ASIN before the
seller types anything, which means the first output is a cleaned-up version of their own listing
photo rather than a random scene. The video generator takes a single product image and produces a
multi-scene video with text animations and background music, and the seller receives six options to
choose from [S305, S306]. Amazon's own launch coverage is explicit that the six-option output exists
to raise creative experimentation [S306].

**Iteration is re-prompting, and Amazon documents the failure mode.** The image-generation guide
gives prompt guidance that is unusually candid for a vendor: describe the whole scene in one go,
use positive language, and expect negative phrasing such as "do not include" to be ignored
[S302]. The guide's worked example shows a seller moving from "a sandal on a beach" to "a sandal on
a beach with a tree next to it" as a full rewrite, and explicitly warns against the incremental
"now add a tree next to it" form [S302]. That is a vendor acknowledging that iteration in this tool
is coarse.

**Review is a gate, not a conversation.** All AI-generated content passes Amazon Ads moderation
review before it can be used [S301]. There is no comment thread, no approver role and no version
history documented anywhere in the inspected pages — the review is an automated platform gate that
either passes or rejects the asset.

**Export and publish are the same action.** Assets are saved to the Creative Assets library, which
is the same library Campaign Manager reads from, so an asset can be reused across multiple ad types
and campaigns [S301]. Amazon's launch coverage describes the studio as directly connected to the
creative assets library so that thousands of iterations can be saved and the best one selected for
the next campaign [S303]. Display sizes are documented in the supported-creatives spec
(300×250, 320×50, 728×90, 160×600, 1200×600, 300×600, 468×60, 800×250, 1800×1000) and video
specs are documented as a minimum 1920×1080 frame at 24fps in H.264, MPEG-2 or MPEG-4 with MP3 or
AAC audio [S310]. A separate support article describes a genuinely useful automation: on standard
display ads, the generative layer automatically derives additional sizes from a single upload — a
480×400 upload is upscaled and also used to produce a 300×250 for Twitch inventory — with over
sixty sizes supported and a 500kb maximum file weight [S311].

**There is also a programmatic path.** Three AI image-generation endpoints were announced for
closed-beta onboarding — list themes, submit generation tasks in batch, and poll task status
[S304] — and the asset library has a documented three-call API for uploading and registering
assets, with an optional ASIN list used for search and categorisation [S308]. The DSP side has a
full creative-management API including component-level moderation feedback, which tells a seller
which component caused a rejection [S309].

**Adjacent Amazon-owned surface, for contrast.** Amazon's own A+ Content Manager — reached from
Seller Central under the Advertising tab — is the closest thing to a design studio that Amazon ships
to sellers directly. Its documented flow is search by ASIN or product name, choose Basic or Brand
Story, name the content and select a language, add modules one at a time, then either type text or
drag and drop images or pull them from the same creative Asset Library the ad console uses,
associate ASINs, and review and submit [S369]. It shares the ad console's asset library but has no
generation layer at all, and its language-per-content model means a German page only shows German
content [S369]. For the Design Studio this is the handoff target that matters most: a generated A+
module has to land inside that module-and-Asset-Library structure.

**Teardown summary**
- **Discrete steps to a usable first asset: 6** (vendor-documented procedure) [S302].
- **Friction points:** login is mandatory and the tool is unavailable outside it; feature
  availability is country-gated and ad-type-gated through a matrix [S301]; video generation has
  asset limits whose value is not published; no brief fields, no brand kit, no approval workflow,
  no layer editor; iteration is coarse re-prompting; negative prompts are documented as unreliable
  [S302].
- **Time to first usable asset:** image generation is described as taking seconds and the video
  generator is described as producing assets in five minutes or less at no cost [S307]. Both are
  vendor claims on marketing/launch pages, not measured benchmarks.
- **Product fidelity:** strongest structural position in the set. The generator starts from the
  seller's own ASIN listing imagery and auto-enhances it, so the product is never invented from
  scratch; an upload path exists for images the seller supplies themselves [S302, S304]; the DSP
  path derives additional sizes from the seller's own uploaded asset rather than re-generating it
  [S311]. How faithfully the enhanced image preserves the physical product is **UNKNOWN** — no
  fidelity claim or scoring mechanism was found on the inspected pages.
- **Text accuracy:** the video generator adds text animations [S305, S306], but there is no
  documented control over on-image typography, no font selection, and no guarantee about rendered
  text. The prompt guidance about positive phrasing implies text-in-image is not reliably
  controllable. **UNKNOWN** for on-image typography fidelity.

### 3.2 Photoroom — the marketplace image operation

**The path.** The vendor publishes a three-step flow for the Amazon case: upload product photos,
apply predefined or brand templates for Amazon compliance, then batch-export for product pages, A+
modules or storefront banners [S343]. A second three-step version exists for the specific
white-background case: select an image, let the tool remove the background and pick a colour,
download [S345].

**Input is the seller's own photo, and the tool is built to standardise it.** The industry page
frames the whole product as standardising seller images at scale, preserving SKU-level product
fidelity and removing manual clean-up from onboarding [S342]. Batch mode is sized at up to 250
images in one pass on the published Amazon flow [S344].

**There is no brief step.** What replaces it is a template/preset layer that encodes the rules the
seller would otherwise have to hold in their head: white background, framing, padding, centring,
shadows, dimensions [S344, S345]. That is a compliance preset rather than a creative brief.

**Generation** is background and scene generation, staging, fashion models, ghost mannequin, flat
lay, product beautifier and video. The marketing claim is backgrounds generated in under a second
[S346] and the Amazon page claims automated compliance by cleaning edges, removing distractions and
producing Amazon-ready exports [S343].

**Iteration is re-generation plus a batch re-run.** Because the operation is cutout-and-replace,
iterating means regenerating the background or staging and re-running the batch, not editing a
canvas history.

**Editing** is a real editor: text including curved text, AI backgrounds, instant shadows, remove
objects, retouch, recolour clothing, expand and resize, enhance [S341]. The homepage claims Brand
Kit locks backgrounds, padding, colours, logos and formats and applies them automatically with
role-based access [S346].

**Review** has two layers. Team workspaces carry roles and permissions and the brand kit can be
shared with view or edit permissions [S341]. Separately, an enterprise **Visual QA** layer is
described as checking every visual before it reaches the catalogue, and a **Fidelity Raters**
product is described as product-fidelity scoring for generated visuals [S343]. Those two are the
only quality-gating surfaces in the entire competitor set that are aimed at catching a bad
generation before a customer does.

**Export** is PNG / JPG / WebP with platform resize presets and batch export [S340]. The
white-background page makes a specific and unusually precise claim: the tool generates the
background at exactly RGB 255,255,255 rather than an approximation, on the grounds that a
near-white can still fail an automated check [S345]. That is a vendor designing for a machine
reader, which is exactly right for a marketplace main image.

**Publish does not happen.** The vendor's own flow ends at "export your compliant images and upload
them to Amazon's Seller Central" [S344]. The handoff is manual.

**Teardown summary**
- **Discrete steps to a usable first asset: 3** published (upload → apply compliance template →
  export), realistically 5–6 once brand kit setup, secondary-image styling and batching are
  counted [S343, S345].
- **Friction points:** two separate meters — AI credits and exports — both capped per plan
  [S340]; the video generator is gated to Max and above and 4K to Ultra and above; adjustable AI
  shadows are Enterprise-only; the brand kit is a separate setup task with its own permissions
  model; no Amazon console integration means the last mile is always manual; fidelity scoring and
  visual QA are Enterprise-tier, so the quality gate disappears exactly where a small seller needs
  it most.
- **Time to first usable asset:** background generation claimed at under a second and background
  separation at two to five seconds [S346]. Vendor claims, not measured.
- **Product fidelity:** the strongest explicit position in the set. The seller's own photo is the
  subject and the background is replaced, so the product itself is not re-invented. The industry
  page claims the tool flags quality issues and fixes lighting and framing while preserving
  colours, textures and condition without misrepresenting the product [S342]; the Amazon page
  claims 99% image accuracy at upload [S343]; an API-based Fidelity Raters product exists for
  scoring generated visuals [S343]; Visual QA catches problems pre-catalogue [S342]. Mechanism, not
  just claim: cutout-then-composite plus a machine-readable colour target.
- **Text accuracy:** handled as an editing concern rather than a generation concern. Text overlays
  including curved text sit in the editor and brand-kit fonts are applied by the designer
  [S341]. No claim about AI-rendered on-image text was found. **UNKNOWN** for generated-text
  fidelity; the tool deliberately pushes typography into the human-editable layer.

### 3.3 Flair — the closest thing to an actual design studio

**The path.** Start from a photoshoot template or a blank canvas, upload a clean product-only image,
drag props and 3D elements onto the canvas, adjust lighting and camera angle, generate, then
iterate per element. The bulk path is shorter and explicitly three steps: upload clean product
images, select the content types you want (images, videos, text), generate [S338].

**Input is a product image plus a spatial composition.** Flair's entry is the only one in the
Amazon-seller tier that treats scene construction as a design act: the canvas takes drag-and-drop
props and 3D elements, and lighting and camera angle are adjustable controls rather than prompt
words [S335].

**There is no brief step.** Brand consistency is handled by a brand asset area described as keeping
brand assets in one place [S339], and custom models trained on the seller's own products act as a
de facto brand lock [S335, S336].

**Generation** covers product photography, on-model fashion and jewellery imagery with patterns and
logos advertised as preserved, product videos, ad generation with a template library, and AI human
models built from attributes such as hair colour and body type [S335].

**Iteration is the most granular in the Amazon-seller tier.** The editing catalogue includes
regenerate product, regenerate human, magic erase, magic paint, upscale, virtual try-on, generate
variations, extend image dimensions, recolour, change camera angle and change pose [S339].
"Regenerate product" is the important one: it swaps the product inside an existing generated image
without rebuilding the scene. That is product-locking as a user-facing feature rather than an
implementation detail.

**Editing** is a canvas with layers, props, 3D elements, lighting and camera angle, and reusable
templates that can be built at scale [S335].

**Review** is advertised as real-time team collaboration [S335]. No approval workflow, role model or
commenting surface was documented. **UNKNOWN.**

**Export dimensions are UNKNOWN** on every inspected page. Publish does not happen.

**Teardown summary**
- **Discrete steps to a usable first asset: 6** on the design path (open → upload product → compose
  props/lighting → optionally train or select a model → generate → iterate), or **3** on the bulk
  path [S338].
- **Friction points:** the free tier is 5 images and 1 video, which is a demo not a plan; instant
  image generation and ad generation cost four times the standard image quota, so the fast path is
  the expensive path [S336]; API access is early-access on Scale and unlimited only on Enterprise
  [S336]; no Amazon console integration; export dimensions are undocumented, which is a real gap for
  a seller who needs exact listing sizes; brand asset management is advertised but no permission
  model is documented.
- **Time to first usable asset:** UNKNOWN as a number. The editing-tool pages claim results "in
  seconds" [S339], which is marketing, not a measurement.
- **Product fidelity:** two mechanisms. First, an explicit regenerate-product operation so the
  product inside a scene can be swapped or re-rolled independently of the background [S339].
  Second, custom models trained on the seller's own products [S335]. The on-model feature advertises
  that patterns and logos are preserved [S335], and the editing pages market full product accuracy
  [S339]. Whether the composited product is pixel-true to the seller's photo is **UNKNOWN**.
- **Text accuracy:** UNKNOWN. No on-image typography control, font selection or text-fidelity claim
  was found on any inspected page.

### 3.4 Pebblely — the shortest path and the best text handling

**The path.** The vendor publishes a three-step flow and repeats it in its own changelog: add a
product (upload, crop, name, tag, confirm extracted text), generate (custom prompt or template,
count, size, style image or colour), download from the recent images list [S348, S350].

**Entry is a product object, not a project.** You "add a product" once — upload, crop, name, tag —
and then generate many images against it. That is the structural difference from every other tool
here: the product is a first-class entity and the image is an output of it. It is also what makes
bulk generation natural: select multiple products, choose settings once, generate.

**There is no brief step**, but there is something better for this problem: an on-pack text
confirmation step. When the product is first saved, the tool extracts all visible text from the
product image — brand names, ingredients, dosage information — and uses that text during generation
so labels and packaging copy survive. The seller can review, edit or manually add text items with
position and styling hints so the generator knows where and how to render them [S348].

**Generation** is either a template from 40+ themes (Basic, Studio, Cafe, Water, Kitchen and more)
or a free-text custom prompt, with a choice of 1, 2 or 4 images, a size, and optionally a style
reference image or a brand colour [S348]. The size is chosen *before* generation, not after — the
vendor is explicit that it generates at the target dimensions from the start rather than cropping
or extending a square [S350].

**Iteration is edit-by-description.** Any result can be edited by describing the change, with the
size and high-resolution mode toggleable during the edit [S348].

**Editing is deliberately thin, and that is the design.** Every generated image has exactly two
layers, the product and the background, with layer ordering, and the product can be repositioned,
resized and rotated [S347]. There is no general canvas. The trade is explicit: you give up design
control to get speed and product integrity.

**Review does not exist.** No collaboration, roles, comments or approvals were documented.

**Export** uses fixed presets chosen before generation: 1080×1080, 1080×1350, 1080×1920,
1920×1080 and 1200×628, with a canvas up to 2048×2048 and an API that accepts height and width
[S347, S348, S351]. Results can be filtered by resolution and searched by theme or prompt [S348].

**Teardown summary**
- **Discrete steps to a usable first asset: 3** — the shortest published count in the entire
  competitor set [S348, S350]. The pre-2026 flow was six steps including a separate background
  removal and canvas positioning step [S352], so the vendor has deliberately collapsed its own
  workflow.
- **Friction points:** no collaboration or review surface at all; no brand kit beyond colours and
  style references; the free tier is thin; bulk generate starts at the Basic tier [S349];
  high-resolution mode doubles the credit cost; custom prompts are described as paid-only in the
  older vendor blog [S352]; no Amazon integration.
- **Time to first usable asset:** **~10 seconds per image, and ~30 seconds in high-resolution mode
  at 2 credits** [S348]. This is the only competitor in the set that publishes a per-image time on
  a help page rather than a marketing adjective.
- **Product fidelity:** structurally the cleanest. The product is isolated as its own layer and the
  background is generated around it, so the seller's photo is composited rather than re-imagined;
  the product can be repositioned, resized and rotated and the two layers can be re-ordered
  [S347, S352]; the API takes explicit transforms (scale x/y, translate x/y, rotate) and an
  autoresize flag that centres the input in the canvas [S351]; up to five products can be composed
  in a group shot [S348]. The 2026 redesign removed the background-removal step entirely on the
  grounds that the model understands what the product is [S350] — a meaningful fidelity claim, and
  a risk, since it removes the seller's own control over the cutout.
- **Text accuracy:** **the strongest in the set and the single most adoptable pattern in this
  research.** On-pack text is auto-extracted at product-save time and fed into generation so labels
  and packaging copy are preserved; the seller reviews, edits or manually adds text with position
  and styling hints; the vendor publishes a dedicated help article on why AI product photos get text
  wrong and how to fix it [S348]. Two other tools in this set attempt on-image text; this is the
  only one that builds an explicit verification loop around it.

### 3.5 Helium 10 — the listing specialist, with a generation layer bolted on

**The path.** Open Listing Builder, choose create-from-scratch or optimise-an-existing, select a
marketplace, build a keyword bank, describe the product, pick tone and audience, then generate per
field and sync to Seller Central [S318, S319]. The vendor's own walkthrough describes it as a
handful of steps and is explicit that optimise-an-existing requires a Seller Central connection so
the listing can be pulled in and pushed back [S318].

**Entry is a listing, and the brief is real.** This is the only tool in the Amazon-seller tier with
a documented brief-like step: product characteristics capped at 500 characters, tone selection
matched to a target audience, brand name to inject into the title, excluded characters and words,
marketplace and language selection [S318, S319]. The 2026 rebuild adds an uploaded product image
for auto-fill, a reference ASIN, brand voice, category, and bullet structure with character limits
[S323].

**The keyword bank is the actual differentiator.** Keywords are imported from Cerebro's reverse-ASIN
lookup, Magnet's seed phrases, an existing My List or typed manually, and then — this is the part
worth copying — the bank visibly crosses off each term as it is used and tracks root words, so a
seller can see coverage accumulating while they write. Hovering a keyword shows the top ten ranked
products for it, and the tool reminds the seller that title and first bullet carry the most weight
[S319]. Generation happens per field with an accept-or-rewrite choice, so nothing is generated as a
single opaque block [S319].

**The image generator is a separate, thinner flow.** The vendor blog documents five steps: open a
listing and choose generate-AI-images, set size / product scale / style, write a prompt describing
the scene (and what to avoid), generate several options and review, then download and apply
[S322]. The same blog claims the image generator covers main listing images, Amazon Posts visuals,
A+ content images including logos and headers, and mobile-optimised images, and claims an exclusive
Amazon API partnership for image generation [S322]. Those are vendor blog claims and are REPORTED,
not verified.

**Iteration** is per-field regeneration plus manual editing. On the image side there is no canvas,
no layers and no documented history — you regenerate and pick.

**Review does not exist.** No collaboration, roles, comments or approvals were documented. **UNKNOWN.**

**Export and publish** are the strongest in the Amazon-seller tier for copy: the listing syncs back
to Amazon Seller Central, and the tool explicitly supports backend subject-matter fields that are
invisible to customers [S318]. Image dimensions are **UNKNOWN**.

**Teardown summary**
- **Discrete steps to a usable first asset: 6** (add listing → marketplace → keyword bank → product
  characteristics + tone + audience → per-field generation → review and sync). The image-only path
  is **5** [S322].
- **Friction points:** the advanced AI listing builder is Diamond-gated, and one AI surface is
  capped at 250 messages per month [S320]; meaningful keyword pre-work in Cerebro or Magnet is
  effectively mandatory to get value, so the real path is longer than six steps; generated copy
  still needs manual review for compliance; the image generator has no canvas, no brand kit and no
  documented dimensions; AI features are paid-tier only.
- **Time to first usable asset:** UNKNOWN as a measurement. Vendor blogs say listings can be
  produced "in minutes" and image options are produced after clicking generate [S322, S321].
- **Product fidelity:** handled by input rather than by mechanism. The 2026 builder takes an
  uploaded product image for auto-fill and a reference ASIN for guidance [S323], and the image
  generator takes a product-scale setting [S322]. There is no product-locking feature, no cutout
  layer model and no fidelity scoring. **UNKNOWN** for how faithfully the generated image preserves
  the physical product.
- **Text accuracy:** listing copy is fully editable text, which is the right answer for a listing.
  For images there is no documented typography control or on-image text claim. **UNKNOWN.**

### 3.6 Pacvue — the control point with no generation layer

This teardown is short because there is almost nothing to tear down, and that absence is the
finding.

**Pacvue has no design studio.** Across the inspected pages there is no asset generation, no canvas,
no image editor, no template library, no brand kit and no export surface. What exists instead is a
digital-shelf operation: brand and product auditing that flags detail-page gaps against standards
(title length, image count, videos, bullet count, description, enhanced content), Buy Box
monitoring, ratings and review monitoring, keyword tracking and share-of-voice measurement, and
automations that either alert a human or auto-generate a ticket to a retailer to correct a content
change [S329, S330]. One page explicitly describes automatically replacing poor-performing SKUs
with SKUs that have better detail-page content or ratings [S330].

**The workflow is a control loop, not a creation loop.** Ingest SKUs, keywords and competitor
lists; configure rules and content-health standards; the platform audits continuously; exceptions
raise alerts or tickets; reports are scheduled across retailers [S330]. Nothing here produces an
image. The seller or their agency makes the image somewhere else and Pacvue tells them whether the
listing that carries it is healthy.

**Why it is included in the top eight anyway.** It is the largest enterprise Amazon-seller platform
on the operator's named list, and it represents a whole class of tool that a seller's design studio
has to interoperate with. The finding is that the enterprise tier of Amazon tooling has invested
heavily in *measuring* content and not at all in *making* it. The gap between "this SKU's detail
page fails our image standard" and "here is a compliant image" is exactly the gap the NorthstarOS
Design Studio sits in.

**Teardown summary**
- **Discrete steps to a usable first asset: not applicable.** There is no asset-generation
  workflow. The nearest analogue is ingest → configure rules → audit → alert or ticket, which
  produces a work item, not an asset.
- **Friction points:** no generation surface, so every remediation requires leaving the platform;
  no public pricing page was reachable and no credit mechanics exist; the site blocks automated
  fetching so all evidence here is REPORTED via search-engine rendering of public URLs [S328,
  S329, S330]; an auto-ticketing route implies an approval or routing layer whose detail is UNKNOWN.
- **Time to first usable asset:** UNKNOWN.
- **Product fidelity:** not applicable to generation. The relevant behaviour is that audits check
  whether a published image exists and meets a count/format standard, not whether the image is
  faithful to the product [S330].
- **Text accuracy:** not applicable to generation. Content-health checks cover title length and
  description presence, not on-image typography [S330].

### 3.7 Canva — the general-purpose studio with the most mature governance

**The path.** From the homepage, select Canva AI, type a short description, optionally attach
uploads, existing designs or a Brand Kit, choose Design / Create an image / Video clip plus filters,
submit, then pick a template from the results [S353]. From inside the editor, open the Templates
tab, enter a descriptive prompt, optionally upload a photo, and either search existing templates or
tap Generate to create new ones [S353].

**Input is text plus media plus brand.** The distinctive feature of the input step is the explicit
"Apply Brand Kit" option inside the generation flow [S353], which means brand is an input to
generation rather than a constraint applied afterwards. Canva's brand surface is documented across
several articles — the Brand Kit and assets index, the setup article, the builder, the on-brand
generation article and the brand-assets and Brand Controls article [S355, S356, S357, S358, S359] —
and the same surface is reachable programmatically, with a documented MCP tool that creates design
candidates from a natural-language brief [S360].

**The brief is distributed.** There is no single brief form. Instead Magic Design infers intent from
the prompt and attached media, and a standing brief lives in the Brand Kit plus Brand Templates.
The vendor is candid about the limits of that: applying a Brand Kit brings in colours and fonts but
does not impose a template layout, so structure has to come from a Brand Template [S358]. It also
publishes authoring guidance for those templates — use placeholder text to guide the model, add
notes and annotations, use placeholder images instead of empty frames, keep the design simple and
structured, and apply editing locks to elements that must survive generation [S358].

**Generation** is layout-first: Magic Design returns template candidates matched to the content,
and it does not generate video itself. Video comes from Magic Media (4-second silent clips) or Canva
AI Video (8-second clips with sound) [S353]. Magic Background returns four options per generate
[S353].

**Iteration** is the deepest in the set: Magic Edit, Magic Expand, Magic Eraser, Magic Grab, Magic
Morph to re-style elements, Magic Animate, Magic Resize and Magic Switch to re-format across
channels, and Magic Write for copy [S354].

**Editing** is a full canvas with layers, locking, alignment guides, a text panel, elements, a draw
tool and an apps marketplace [S377, S378].

**Review is the most mature surface in the entire competitor set.** Brand Controls let admins
restrict designs to approved colours and fonts *and require design approval before publishing*
[S359]. Roles are owner, admin, brand designer and member, with brand designers creating templates
and guardrails and members designing inside them [S356, S359]. Multiple Brand Kits can exist for
different teams, clients or campaigns [S356]. Real-time multiplayer and comments are standard.

**Brand kit setup is itself automated.** Brand Kit Builder extracts logos, colours, fonts, graphics,
photography, brand voice and guidelines from a website URL or a PDF brand-guidelines document, with
the vendor warning that results vary and must be reviewed [S357].

**Export** is the standard set — PNG, JPG, SVG, PDF — with platform presets, Magic Resize for
multi-format output and Bulk Create for templated volume [S354, S377].

**Publish** goes to social platforms directly. **No Amazon-native features were observed** on any
inspected page.

**Teardown summary**
- **Discrete steps to a usable first asset: 6** (open Canva AI → describe → optionally attach media
  or Brand Kit → choose type and filters → submit → pick a template), then editing and export on
  top [S353].
- **Friction points:** the approval-publish workflow is a paid-team feature, not available to a solo
  seller; Magic Design for Video pulls free and Pro content and a free account must upgrade or
  strip Pro elements before download [S353]; applying a Brand Kit does not impose layout, so brand
  consistency still depends on a well-authored Brand Template [S358]; AI usage limits are described
  as having changed with per-tool specifics not published on the inspected pages; the pricing page
  was not captured so plan gating is known only from help-centre statements; nothing connects to
  Amazon.
- **Time to first usable asset:** UNKNOWN as a number. Marketing language says "in an instant"
  [S354], which is not a measurement.
- **Product fidelity:** no product-locking or compositing mechanism was found. Fidelity depends on
  the seller uploading their own product image and the tool treating it as an ordinary layer. Text
  and images are freely editable after generation, so a generated layout is a starting draft rather
  than a product-accurate render.
- **Text accuracy:** handled as a first-class editing concern. Typography, font pairing and sizes
  are set in the Brand Kit and applied by the designer; Magic Write generates copy that is then
  edited in place [S354, S356]. This is the right model for a tool whose output is a layout, and it
  is the opposite of Pebblely's approach.

### 3.8 Figma — the version-control and handoff benchmark

**The path.** Create a file in drafts, then either use Actions → First Draft or start a Make file
[S361, S362]. First Draft: optionally choose a library, enter a prompt, click Make it, preview
themes, close the menu or click Make changes [S362]. Make: click Make in the file browser, add
context by pasting a design URL or dragging in images and text files, prompt, then iterate in the
chat while editing the preview [S363].

**Input is a prompt plus design-system context.** First Draft uses Figma's own wireframing and
design libraries, each a set of component stacks, to assemble output from the prompt [S362]. Make
lets you attach existing designs, components, community content and other files to a prompt, add
styling context from a Figma library, set custom rules or paste in a frame, and can search the web
or fetch a URL to ground the output in real data [S363, S368].

**There is no brief form, and the vendor states the hard limitation plainly:** you cannot generate
designs using your own design system in First Draft [S362]. That is a remarkable admission and it is
the single most important sentence in the Figma evidence for this research.

**Generation** produces editable wireframes or designs from library components. Make produces
interactive prototypes that can be published as a website with a dedicated URL [S363].

**Iteration** is prompt-based on a selection — you can select one or more parts of the design and
apply the prompt only to those — plus style controls for colour, border radius, spacing and
typography, plus a duplicate-and-edit path [S362]. In Make you select the region you want to keep
refining and prompt it, or directly rewrite copy, replace images and change padding and margins, or
copy the preview as design layers to continue in Figma Design [S368].

**Review and version control are the best in the set.** Named versions with descriptions, version
restore, version duplication and viewer history [S365]. A compare-changes view lists edited, added
and deleted layers between versions with side-by-side or overlay display plus code and property
diffs [S366]. Dev Mode adds handoff statuses — Ready for dev, Completed, and an automatic Changed
state — with a change reason recorded into version history and notifications across email, desktop,
push, Slack and Teams [S367]. Comments persist across version restores [S365].

**Export** is PNG, JPG, SVG and PDF with per-layer export settings, and in Dev Mode GIF and MP4
nodes plus full-resolution source files are downloadable [S364].

**Publish** happens through Figma Sites and Make's website publishing [S363]. No Amazon-native
features.

**Teardown summary**
- **Discrete steps to a usable first asset: 6** (create file → choose First Draft or Make →
  optionally choose library or add context → enter prompt → Make it → preview themes and accept, or
  Make changes) [S362, S363].
- **Friction points:** First Draft cannot use your own design system [S362]; once you close the
  Actions menu you cannot make further First Draft edits and must fall back to ordinary property
  editing [S362]; Figma's own libraries excel at common web and mobile app patterns and struggle
  outside those frameworks [S362]; AI tools are gated to paid plans and the agent to Full seats on
  Professional, Organization and Enterprise, with drafts as the only free surface [S361]; AI was
  free while in beta with a pricing update promised later [S361]; nothing connects to Amazon.
- **Time to first usable asset:** the vendor states First Draft transforms an idea into editable
  designs "in a couple of minutes" [S362] — a documented figure rather than an adjective, and the
  only Amazon-adjacent competitor other than Pebblely to publish one.
- **Product fidelity:** not a product-photography tool. The analogue is component and library
  fidelity — output is assembled from Figma's own component stacks, and the documented limitation is
  that your own system cannot be used [S362]. There is no compositing of a seller's photograph.
- **Text accuracy:** handled as text. Rewrite, translate, shorten, adjust tone and text suggestions
  are per-product AI tools, and generated copy is directly editable as ordinary text layers
  [S361, S368]. On-image typography is a designer-controlled property, never a generated artefact.

---

## 4. Cross-cutting patterns worth adopting

Original wording throughout. No competitor copy, taglines or template text is reproduced.

### 4.1 Make the listing the entry point, not the canvas
Four of the eight tools begin from something the seller already owns: an ASIN (Amazon Ads), a
product photo (Photoroom, Flair, Pebblely) or an existing listing (Helium 10). Only the two general
design tools begin from a blank canvas or a bare prompt. The Amazon-native tools have converged on
"start from the asset you already have" because it removes the hardest step — getting an accurate
product into the frame. NorthstarOS should make the SKU the primary object and the design a
projection of it, never the reverse.

### 4.2 Separate the product layer from everything else
Pebblely emits exactly two layers — product and background — and lets the seller reposition, resize
and rotate the product independently [S347]. Flair exposes regenerate-product as a first-class
operation so the product inside a finished scene can be swapped without rebuilding the scene [S339].
Photoroom composites the seller's own cutout onto a generated background [S342]. Every one of these
protects the same invariant: the thing being sold is the seller's photograph, not a model's guess.
NorthstarOS should treat the product layer as immutable-by-default and require an explicit action
to regenerate it.

### 4.3 Verify on-pack text before you generate anything
This is the clearest single gap in the market and the cheapest to copy. Pebblely extracts visible
text from the product image at product-save time, feeds it into generation so labels and packaging
copy survive, and lets the seller review, edit or manually add text with position and styling hints
[S348]. Amazon's own prompt guidance admits negative instructions are ignored [S302]. Photoroom and
Flair have no equivalent. NorthstarOS should make a text-verification step mandatory between upload
and generation, and should surface it as a confirmed artefact rather than a silent preprocessing
step.

### 4.4 Publish a number, not an adjective
The competitors split cleanly. Pebblely publishes roughly ten seconds per image and roughly thirty
seconds for high-resolution on a help page [S348]. Figma's help centre says First Draft takes a
couple of minutes [S362]. Amazon publishes "five minutes or less" and "in seconds" on launch and
marketing pages [S307]. Canva, Flair, Photoroom and Helium 10 publish only adjectives — "instantly",
"in seconds", "in minutes". A vendor that publishes a per-image time on a help page is telling you
it has instrumented the thing. NorthstarOS should publish a measured time-to-first-asset as a
first-class product metric, not a marketing claim.

### 4.5 Make the expensive operations visibly expensive
Flair's pricing page states that instant image generation and ad generation cost four times the
standard image quota [S336]. Pebblely states that high-resolution mode costs two credits instead of
one and takes about thirty seconds instead of ten [S348]. Both turn an invisible cost into a
decision the user makes. NorthstarOS should expose a cost preview on the generate button — Pebblely
shows the total credit cost before the user commits on a bulk run [S350] — and should never hide a
quality upgrade behind a silent surcharge.

### 4.6 Meter generation and export separately
Photoroom runs two independent caps — AI credits and exports — with published values per tier
[S340]. This catches a real failure mode that single-meter tools miss: a user with plenty of
generation budget and no export budget is stuck, and vice versa. It also forces the vendor to say
which operations are cheap. NorthstarOS should separate generation cost from delivery cost, because
they are genuinely different resources.

### 4.7 Give the tool a compliance preset, not a compliance document
Photoroom does not hand the seller a spec sheet; it encodes the rule as a preset and generates the
background at exactly RGB 255,255,255 on the stated grounds that a near-white still fails an
automated check [S345]. Pacvue does the opposite — it audits against a standard and raises a ticket
[S330]. Both are useful, but only one produces a usable asset. NorthstarOS should ship
marketplace rules as executable presets that produce a compliant file on the first pass, and should
treat compliance as an output property rather than a checklist.

### 4.8 Batch against the product object, not the canvas
Pebblely generates across multiple products with one settings choice and shows the total credit cost
before committing [S350]. Photoroom applies one edit set across up to 250 images [S344]. Flair
generates multiple content types from one upload [S338]. The pattern is that volume lives at the
catalogue level. NorthstarOS should let a seller select SKUs and generate, rather than opening one
canvas at a time.

### 4.9 Seed the brand kit from something the seller already has
Canva's Brand Kit Builder extracts logos, colours, fonts, graphics, photography, voice and
guidelines from a website URL or a PDF, while warning that results vary and must be reviewed [S357].
Photoroom can pull brand elements directly from the seller's website [S341]. Both reduce brand-kit
setup from a project to a confirmation. NorthstarOS should do the same and should carry Canva's
honest caveat forward — auto-extraction is a draft, never a decision.

### 4.10 Lock what the model must not change
Canva's guidance for on-brand AI generation is to apply editing locks to elements that must survive
generation before publishing a template into the Brand Kit [S358], and it notes that locked elements
are kept unchanged and logos are maintained by default [S358]. Flair's regenerate-product and
Pebblely's two-layer output achieve the same thing structurally. The principle generalises: the
brand kit should contain both assets and *immutability rules*, and the generator should respect them
by construction.

### 4.11 Close the loop where the asset will be used
Only two tools in the set publish anywhere. Amazon Ads writes assets straight into the Creative
Assets library that Campaign Manager reads [S301, S303], and Helium 10 syncs listing copy back to
Seller Central [S318]. Everyone else ends at a download. NorthstarOS should treat publish-back as a
first-class integration target — first to the seller's own asset library, then to Amazon where
Amazon's own APIs permit — because a manual upload at the end of an otherwise-automated pipeline is
where the pipeline actually breaks.

### 4.12 Put a quality gate in front of the customer
Photoroom is the only competitor with an explicit pre-publication quality surface: Visual QA, which
checks every visual before it reaches the catalogue, and Fidelity Raters, which scores generated
visuals for product fidelity [S343]. Both are Enterprise-tier, which means the gate disappears
exactly where a small seller needs it most. NorthstarOS should make automated fidelity checking a
core feature rather than an upgrade, because for an arbitrage seller a mis-represented product is a
return and a policy problem, not a cosmetic issue.

### 4.13 State your limits out loud
Three vendors publish limitations that cost them nothing and buy real trust: Figma states you
cannot use your own design system in First Draft [S362]; Amazon states that negative prompts are
typically ignored [S302]; Canva states that applying a Brand Kit does not impose template layout
and that Magic Design does not generate video itself [S353, S358]. NorthstarOS should publish an
equivalent honest-limits surface for every generation mode. The research in this folder is bound by
the same rule, which is why so many cells above read UNKNOWN.

---

## 5. Reconciliation against Part A

| Competitor | Part A role | Mapped in Part B | Reason |
|---|---|---|---|
| Amazon Ads Creative Studio | Amazon-seller-specific | Yes | — |
| Photoroom | Amazon-seller-specific | Yes | — |
| Flair | Amazon-seller-specific | Yes | — |
| Pebblely | Amazon-seller-specific | Yes | — |
| Helium 10 | Amazon-seller-specific | Yes | — |
| Pacvue | Amazon-seller-specific | Yes | Included for the absence-of-generation finding |
| Canva | General design | Yes | — |
| Figma | General design | Yes | — |
| Jungle Scout | Amazon-seller-specific | **No** | No asset generation, editing or export surface in public pages [S326, S327] |
| Perpetua | Amazon-seller-specific | **No** | No asset generation, editing or export surface in public pages; help centre near-empty [S332, S333] |

Both excluded competitors are recorded in `PHASE1_AMAZON_SELLER_MATRIX.csv` with UNKNOWN workflow
cells rather than inferred ones. Nine competitors were verified for Part A; eight were mapped for
Part B; two of the eight have no creation workflow at all.

## 6. YouTube walkthrough register

| Competitor | Video title (shortened) | Channel | Date | Transcript | Source id |
|---|---|---|---|---|---|
| Amazon Ads Creative Studio | Amazon Creative Studio: Free AI Video and Image Generator for Amazon Ads (Full Tutorial) | third-party creator | 2026-02-04 | auto-generated | S313 |
| Amazon Ads Creative Studio | Unlocking Amazon Ads' Creative Studio: AI-Powered Ad Creation | The Ad Project | 2025-09-17 | auto-generated | S314 |
| Amazon Ads Creative Studio | Amazon's New Creative Studio: Full Walkthrough | third-party creator | 2025-11-22 | **no transcript observed** | S315 |
| Amazon Ads Creative Studio | How to Create Amazon Video Ads Using AI (Creative Studio Tutorial) | third-party creator | 2025-11-06 | **no transcript observed** | S316 |
| Helium 10 | Helium 10 Listing Builder Tutorial: Write Titles and Bullets That Rank on Amazon | Ecom Mastery | 2026-01-29 | auto-generated | S324 |
| Helium 10 | Helium 10's AI-Enhanced Listing Builder Tool | Helium 10 (vendor) | 2024-12-13 | **no transcript read** | S325 |
| Flair | Flair AI Tutorial — Create Stunning Product Images in Minutes | AI Agents, AI Influencers and More | 2025-03-04 | auto-generated | S373 |
| Flair | Create Product-Ready Images with AI In Seconds (Flair AI Review) | AI Mitch | 2025-10-31 | auto-generated | S374 |
| Flair | Drag and drop to build design with Flair AI | Flair (vendor) | date not captured | **no transcript read** | S375 |
| Photoroom | How to use Photoroom? | Photoroom (vendor) | 2024-06-07 | auto-generated | S370 |
| Photoroom | How to use Photoroom in 2025 | Photoroom (vendor) | 2025-07-21 | auto-generated | S371 |
| Photoroom | This AI App is Changing Product Photography Forever (Photoroom Walkthrough) | The 1994 Candle Co. | 2024-02-14 | **no transcript observed** | S372 |
| Pebblely | What is Pebblely? | third-party creator | 2025-11-12 | **no transcript observed** | S376 |
| Canva | How To Use Canva AI To Design Anything With Text Prompts | Aurelius Tjin | 2025-09-24 | auto-generated | S377 |
| Canva | Canva Full Tutorial 2026: New AI Tools Walkthrough | Bring Your Own Laptop | 2026-05-27 | auto-generated | S378 |
| Canva | How to Use Magic Design in Canva 2026? | third-party creator | 2026-01-17 | **no transcript observed** | S379 |
| Figma | Figma tutorial: Collaboration and handoff in Dev Mode | Figma (vendor) | date not captured | **no transcript read** | S380 |

Walkthroughs were used as corroboration only. No workflow conclusion in this document rests on a
video alone; where a video is the only evidence for a claim, the claim is not made.
