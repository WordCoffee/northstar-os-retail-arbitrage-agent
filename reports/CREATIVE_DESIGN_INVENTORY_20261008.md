# CREATIVE DESIGN INVENTORY — what NorthstarOS already has for "all creatives"

**Date:** 2026-10-08 · **Branch:** `feature/product-designer-studio` · **Scope:** read-only audit of
every creative/design surface in this repo, before any research or design change.

This document answers the operator's first question — *what design do we have for all creatives?* —
with a straight inventory. It is deliberately blunt about what is real, what is a shell, and what is
dead code. Nothing here was changed.

---

## 0. Headline finding (read this first)

There are **two separate creative surfaces**, and they are not connected to each other:

| # | Surface | Where | State | Real? |
|---|---|---|---|---|
| 1 | **Creative Studio** room | `northstar-os-ui/src/pages/internal/CreativeStudio.jsx` (783 lines), route `/creative-studio` | **Live in the app**, listed in nav as `Concept` | Real *local workflow records*. No image or video is generated. No provider. |
| 2 | **Studio engine + components + CSS** | `northstar-os-ui/src/studio/**` (11 files, ~140 KB) | **Orphaned — nothing imports it, no git history** | Real, working, dependency-free renderers. Dead code today. |

Surface 1 is a records-and-approvals workspace with every preview deliberately blank.
Surface 2 is an actual design engine (Canvas 2D document renderer, format library, brand kits, 3D
packaging renderer, mockup renderer, interactive stage) that **has never been mounted**.

**The gap between them is the whole opportunity.** The engine that could render real creatives exists
and is uncommitted; the room that ships has no engine. The rest of this document is the evidence.

---

## 1. Surface 1 — the shipped Creative Studio room

**File:** `northstar-os-ui/src/pages/internal/CreativeStudio.jsx`
**Route:** `/creative-studio` (`App.jsx:89`)
**Nav status:** `Concept` (`src/data/nav-config.js:20`) — operator + platform_admin roles only.

### 1.1 Tab structure (8 tabs)

`Briefs` · `Image Composer` · `Video / Shorts` · `Production Queue` · `Variants & History` ·
`Assets` · `Exports` · `Library`

### 1.2 What is genuinely functional (local, browser-persisted)

Verified by reading the code — all state goes through a `useLocalRoom` helper over `localStorage`
with keys `ns-creative-briefs|requests|assets|variants|bundles`:

- **Briefs** — create / list / select / open; each carries objective, audience, brand, formats,
  deliverable count, status (`Draft`, `Active`, `In Review`, `Archived`).
- **Image Composer** — prompt/work-brief textarea, brand selector (Word Coffee, Mogra Organics,
  Neck Nirvana, Northstar OS), output format, aspect (`1:1, 4:5, 9:16, 16:9, 3:2`), resolution
  (`1024px, 1280×720, 1536px, 2048px`), staging tier (Draft / Final), reference-asset multi-select.
- **Production Queue** — real record list. Because no provider is connected, every request lands in
  the terminal state **`Blocked — provider required`** and stays there. There is a `Queue anyway`
  affordance and a `Simulate error` affordance to exercise those paths. **No request can ever reach a
  fake "Complete".**
- **Variants & History** — real state transitions `Draft → In Review → Changes Requested → Approved`,
  with state-appropriate actions only (an already-Approved variant does not offer Approve again).
  Merged history log of requests + variants.
- **Assets** — local asset metadata with type/collection/review state and brief-attachment state.
  Upload is an honest `ProviderBoundary`/toast — nothing is uploaded.
- **Exports** — bundle builder produces a **local manifest record** (references only). Download is
  rendered `disabled` with the reason "download unavailable — no asset store". Real handoff navigation
  to `/socialpulse` and `/listingforge`.
- **Library** — four collections with clearly-labeled **sample counts** (24/38/17/8 = 87 items).

### 1.3 The honesty contract it enforces (this is the house style and it is good)

- A `Thumb` component renders a **dashed, hatched placeholder** with the label
  `no preview · local record`. It never renders a fabricated image.
- Two `ProviderBoundary` components declare, verbatim in the UI: expected engine `ComfyUI`, env
  `COMFYUI_URL`, gate `MEDIA_GEN_LIVE`, models `FLUX.2 klein / FLUX.1 dev (weights must be installed)`;
  and for video: `fal (Kling / Wan / Veo)`, `No local video pipeline exists in this build`.
- A 4-item **Provider Readiness** checklist shows `0 / 4 ready` and never claims otherwise.
- `DataNotice` banners state plainly: *"No image or video is generated or depicted — there is no wired
  creative provider in this build."*
- Every state-changing action is labelled "internal review state — not publishing authorization."

### 1.4 What it does NOT have

No canvas. No layers. No design document. No content-type selector. No Amazon compliance concept.
No keyword or search-term awareness. No brand-kit object (brands are a 4-item string list). No
template library. No pixel-accurate format presets. No performance data of any kind.

**Verdict:** a complete, honest *workflow shell* with a hollow middle.

---

## 2. Surface 2 — the orphaned studio engine

**Root:** `northstar-os-ui/src/studio/` — **zero importers anywhere in `src/`** (verified by grep),
**zero commits under that path** (verified with `git log -- northstar-os-ui/src/studio`, empty). It is
untracked work-in-progress on the current branch.

### 2.1 File map

| File | Bytes | What it is |
|---|---|---|
| `engine/doc.js` | 15.8 K | **Document model + Canvas 2D renderer.** The core. |
| `engine/presets.js` | 18.2 K | Format library, brand kits, scenes, lighting rigs, box presets, mockup surfaces, camera presets, copy roles, templates. |
| `engine/three.js` | 10.2 K | **Real 3D packaging renderer on a plain Canvas 2D context** — no WebGL, no three.js. |
| `engine/assets.js` | 8.3 K | **IndexedDB asset store** for operator-uploaded images, with honest degradation to a memory map. |
| `engine/mockups.js` | 6.8 K | Vector mockup surfaces (tee, hoodie, tote, mug, jar label, box face) with the operator's own artwork blend-mapped into the print area. |
| `engine/sceneDoc.js` | 3.4 K | Scene document model (Product Designer backdrop recipes). |
| `engine/store.js` | 2.6 K | Room store (`ns-studio-*`), uid, time/byte formatting, doc hash. |
| `components/Stage.jsx` | 7.3 K | **Interactive editing surface** — renders a doc, hit-test selection, drag-to-move, drag-resize, zoom rail, checkered backdrop, optional guides. |
| `components/Fields.jsx` | 5.3 K | Inspector field primitives. |
| `components/Chrome.jsx` | 5.5 K | ModeToggle (Simple/Advanced), ToolRail, ProviderBoundary, AssetThumb, FormatGrid. |
| `styles/studio.css` | 18.3 K | ~40 `sp-*` / `stage-*` / `sp3d-*` / `sp-tpl-*` / `sp-scene-*` / `sp-mock-*` classes. |

Combined with `styles/tokens.css` and `styles/app.css`, this is a **complete design system for
creatives** — it just isn't mounted on a route.

### 2.2 The engine's key architectural decision (worth preserving)

> A design document is a **flat layer list in normalised coordinates (0..1 of the canvas)**. That is
> the whole trick that lets one master render correctly at 300×300 and 1920×640: geometry is relative,
> only raster size changes.

Layer kinds: `bg`, `shape`, `image`, `text`, `product`, `badge`. Renderer is pure, synchronous,
deterministic, never fetches; images arrive pre-decoded in an `assets` map; a missing asset renders
`ASSET NOT LOADED` / `NO IMAGE SELECTED` — never a silently dropped layer.

Other honesty properties already built in:
- `drawProduct` always uses `contain` and draws a separate radial contact shadow so the asset is
  never distorted; `squash` is an explicit 2D tilt **never labelled as a 3D render**.
- `three.js` is described in its own header as *"honest geometry… not a photoreal render and is never
  labelled as one."*
- `assets.js` reports `persistent: false` when IndexedDB is unavailable, *"so the UI never implies
  durability it does not have."*

### 2.3 The creative vocabulary already defined (`engine/presets.js`)

This is the "design for all creatives" in data form:

- **21 output formats in 4 groups**, each with real raster dimensions:
  - `Paid ads` (6): Meta feed 1080², Meta/Reels story 1080×1920, Google display 1200×628, Google
    square 1200², TikTok/Shorts 1080×1920, Sponsored brand 1200×628.
  - `Social content` (6): IG post 1080×1350, IG carousel 1080², Pinterest pin 1000×1500, X post
    1600×900, LinkedIn 1200×627, YouTube thumbnail 1280×720.
  - `Listing & A+` (6): Amazon main 1600², Amazon secondary 1300², A+ wide banner 970×600,
    A+ standard 300², A+ comparison 970×300, Storefront hero 1920×640.
  - `Video frames` (3): reel frame 9:16, landscape 1920×1080, square 1080².
- **3 brand kits** (`Pine & Bone` house default, `Word Coffee`, `Mogra Organics`) — each with palette,
  ink, paper, accent, heading font (Libre Baskerville), body font (DM Sans), and a **voice string**.
- **6 scene recipes** (Paper studio, Warm linen, Deep pine, Ochre flat, Marble top, Sage gradient) —
  deterministic gradient/geometry with key angle/intensity/spread, rim, ambient, backdrop type.
- **5 lighting rigs** (Three point, Softbox, Dramatic rim, Golden hour, Flat packshot).
- **5 box presets** (Carton, Stand-up pouch, Bottle, Mailer box, Gift cube) with sizes.
- **6 mockup surfaces** with print-area rectangles and tints.
- **5 camera presets** (Hero 3/4 yaw −28°, Front on, Top down, Low angle, Profile) + `describeAngle()`.
- **Copy ladder** — 5 roles with word budgets: Headline ≤12, Sub-head ≤20, Bullet ≤14, CTA ≤5,
  Legal ≤40. **Legal copy is explicitly marked "Never auto-hidden."**
- **5 templates** (Hero—paper, Split—bold claim, Feature grid, A+ banner, Reel cover), each a layer
  list in normalised coords, grouped by family: `Ad creative`, `Social post`, `Listing Image`,
  `A+ content`, `Vertical video`.
- **Generation vocabulary** — 7 purposes (product-scene, lifestyle, background, variant-style,
  ugc-clip, motion, hook-clip) across Image and Video families, and 2 cost tiers (Draft = 1, Final = 4).
- **`PROVIDER_BOUNDARY`** — the same honest engine/env/gate/models contract the room uses.

### 2.4 What the engine does NOT have

No Amazon compliance rules. No keyword/search-term binding. No claims library. No A+ module model
(only banner/standard/comparison rasters). No Brand Story module. No Sponsored Display/SB-video
specs. No variant-testing concept. No performance feedback path. No master-brain wiring. No
multi-asset batch. No export presets per channel (only `safeFileName` + `downloadDataUrl`).

---

## 3. Design system (shared by both surfaces)

`src/styles/tokens.css` — the Northstar identity, already consistent:

- **Surfaces:** paper `#f5f0e8`, paper-warm `#f0ebe1`, bone `#e8e2d8`, surface `#ffffff`,
  raised `#faf8f4`.
- **Ink:** pine-deep `#1a2e1a`, pine `#1d4a1d`, ink `#1a1a1a`, ink-mid `#5a5a4a`, ink-soft `#8a8a7a`,
  ink-faint `#b0afa0`.
- **Accents:** forest `#1d5a1d`, ochre `#c4941a`, clay `#a04020`, sage `#5a7a5a`.
- **Status:** ok `#2d6a2d`, warn `#b8860b`, error `#a04020`, unknown `#8a8a7a`,
  unavailable `#b0afa0` — **five distinct statuses, matching the VERIFIED/REPORTED/PROPOSED/UNKNOWN
  discipline in the constitution.**
- **Type:** Libre Baskerville (serif, editorial), DM Sans (UI), JetBrains Mono (data).
- Radius/shadow/spacing/gap scales, `--nav-w: 260px`, `--content-max: 1120px`, `--sidebar-w: 320px`.

`src/styles/studio.css` adds the creative-specific chrome: a **dark stage pane**
(`#1b2a1c → #131f14` gradient, ochre selection outline, checkered transparency backdrop) floating
inside the **paper/bone app chrome**. Room shell is `62px | 1fr | 300px` (tool rail · stage ·
inspector), collapsing at 1180px and 860px. Responsive + `prefers-reduced-motion` respected.

---

## 4. Data contracts the studio could be wired to (audited, as required)

Per the research rules, the repo was audited for brand-voice, keyword, and ad-search-term data
before designing around them. All of the following **exist today**:

| Contract | Location | Shape |
|---|---|---|
| **Brand voice (social)** | `Northstar_backend/social_pulse.py` → `load_brand_voice(brand)` | `{tone, style, hashtags_per_post, emoji_usage, call_to_action}` with a `_DEFAULT_VOICE` |
| **Brand voice (listing)** | `Northstar_backend/listing_forge.py` → `_build_title_prompt/_build_bullets_prompt/_build_description_prompt(..., brand_voice, ...)` | brand_voice dict threaded into every prompt builder |
| **Keyword tiers** | `Northstar_backend/ad_pilot.py` → `classify_keyword_tier()`, `detect_negative_keyword_candidates()` | tier classification + negative candidates |
| **Search-term generation** | `Northstar_backend/listing_forge.py` → `generate_search_terms()` | generated listing search terms |
| **Keyword store** | `Northstar_backend/data_layer.py` → `keywords.upsert()` | `{keyword, search_volume, ...}` |
| **Keyword performance** | `Northstar_backend/importers/ads_api_importer.py` → `import_keywords()`, `run_search_term_report()` | `keyword_performance(id, keyword_id, campaign_id, asin, impressions, clicks, spend, orders, revenue, acos, tier, recorded_at)` |
| **Search-term report fields** | same file → `_parse_search_term_report()` | `searchTerm, impressions, clicks, spend, orders, sales` (with Amazon's own column aliases: `Search Term`, `Impressions`, `Clicks`, `Spend`, `7 Day Total Orders (#)`, `7 Day Total Sales`) |
| **SP-API search terms** | `Northstar_backend/adapters/amazon_api.py` → `get_search_terms(days_back=30)` | provider-wrapped search-term read |
| **Org-scoped keyword read** | `Northstar_backend/foundation/repositories.py` → `for_keyword(org_id, keyword_id)` | tenant-scoped access |

**Conclusion: the master-brain data the Design Studio needs — brand voice, keyword tiers, and ad
search-term performance — already exists as code.** No new backend data source is required to build
keyword-aware creative briefs. That is a decisive finding for the design work.

## 5. Provider posture (what a connected studio would call)

Documented in `docs/CREATIVE_MEDIA_STACK.md` and `docs/CREATIVE_SOCIAL_LOCAL_STATUS.md`:

- **Image (local):** ComfyUI at `COMFYUI_URL`, gated by `MEDIA_GEN_LIVE=1`.
  `Northstar_backend/model_router.resolve_vision()` resolves local generation to `comfyui`.
- **Image (cloud, not wired):** FLUX.2 pro $0.03/1MP, klein 9B $0.015 draft; GPT Image 2 via
  OpenRouter for text-heavy ad finals; Nano Banana 2 via fal at $0.08 (carries Google SynthID).
- **Video (cloud, not wired, no local pipeline):** Wan 2.5 $0.05/s, Kling 2.6 Pro $0.07–0.14/s,
  Veo 3.1 fast $0.10/s.
- `Northstar_backend/foundation/data_rights.py` still lists `image_generation` as **"(planned)"**.
- **No route exists** from the UI to any creative backend: the foundation router exposes no creative
  route, and the room harness stubs `fetch` to foundation routes only. Six unanswered integration
  decisions are logged in `CREATIVE_SOCIAL_LOCAL_STATUS.md` §4 (provider strategy, router shape, async
  model, asset storage, approval semantics, video budget) — all still open.

## 6. Verdict — the five gaps to design against

1. **The engine is orphaned.** A working Canvas2D/3D renderer, 21 formats, 3 brand kits, 6 scenes,
   5 templates exist and are mounted on nothing. Mounting it is the single highest-leverage change.
2. **No content-type selector.** Two rooms (Creative Studio, SocialPulse) plus a dead engine disagree
   about what a "creative" is. There is no single selector covering listing / A+ / ads / social /
   packaging / brand / video.
3. **No Amazon layer.** Nothing in either surface knows Amazon's main-image, A+, or ad-creative rules.
   Compliance is not a feature anywhere in this repo.
4. **No keyword or performance data.** The contracts in §4 exist in the backend but no creative
   surface reads them. The brief→asset→performance→learning loop does not exist.
5. **No master-brain binding.** `MasterBrain.jsx` and `MemoryBank.jsx` are separate rooms with no
   creative connection.

---

## 7. Coverage limits of this inventory

- Read-only. No files modified, no build run, no tests executed, no provider contacted.
- Inspected: `northstar-os-ui/src/**` (all creative paths), `styles/tokens.css`, `styles/app.css`
  (class usage only), `App.jsx` route table, `src/data/nav-config.js`, the named backend modules in
  §4, and the three creative docs (`CREATIVE_MEDIA_STACK.md`, `CREATIVE_SOCIAL_LOCAL_STATUS.md`,
  `LOCAL_IMAGE_GEN_SETUP.md` header).
- Not inspected: `SocialPulse.jsx` internals in depth (only its role in the creative split), the
  `foundation/` router tree beyond `repositories.py` and `jobs_handlers.py`, the `legacy/` and
  `northstar-os-retail-arbitrage-agent/` trees, and `docs/PRODUCTION_BLUEPRINT.md` (to be read
  targeted when the build spec is written).
- `src/studio/**` has no git history, so the original intent of its author could not be recovered
  from commits — only from the in-file headers, which are unusually explicit.
- The 21 format raster sizes in `presets.js` are **the repo's own declared values**. They have not
  been checked against Amazon's or any platform's current published specs. That check is Phase 3 of
  the research, and several of them (e.g. `A+ standard 300×300`, `A+ comparison 970×300`) look
  plausible but unverified.

---

## 8. Addendum 2026-10-09 — the format presets are now CHECKED, and three A+ values are wrong

The Phase 3 research (`research/design_studio_deep_research_20261008/AMAZON_REQUIREMENTS.md`,
§4–§5, sources S410 and S413 — Amazon's own module-guide PDFs) provides published figures for the
A+ module images. Three of the repo's declared presets do not match:

| Repo preset (`presets.js`) | Declared | Amazon's published figure | Verdict |
|---|---|---|---|
| `aplus-a` "A+ wide banner" | 970 × 600 | **Premium Full Image: 1464 × 600** (desktop min) | **WRONG — 970 × 600 is not a current published spec** |
| `aplus-b` "A+ standard" | 300 × 300 | Basic **Four Images & Text: 200 × 200** (up to 4 images) | **WRONG for the module it most resembles** |
| `aplus-c` "A+ comparison" | 970 × 300 | Basic **Comparison Chart: 150 × 300** (up to 6 images) | **WRONG** |
| `amz-main` | 1600 × 1600 | Range 500–10,000 px; >1,000 px preferred for zoom | **OK — compliant** |
| `amz-alt` | 1300 × 1300 | same range | OK |
| `storefront` | 1920 × 640 | Stores tiles: full width 1,500 × 750 min; gallery 1,500 × 750 | **WRONG — 1,920 × 640 is not a published Stores spec** |

**Also now known and worth acting on:** A+ images must be JPG / BMP / PNG (no animated GIFs),
**≤ 2 MB** each, **≥ 72 dpi**, and **RGB — CMYK is not supported**. Amazon's Stores guidance
discourages embedded image text entirely, stating it is not readable by search engines or screen
readers. Premium A+ has 19 distinct module shapes, each with their own minimum dimensions and
character limits; the full tables are in `AMAZON_REQUIREMENTS.md` §5.

**Recommendation:** this is a data-only correction with zero provider cost, and it should happen
*before* the studio engine is mounted — otherwise every asset the studio produces inherits the wrong
raster size. It is Phase 0 of `MASTER_BLUEPRINT.md`. No file has been changed yet; this is a finding,
not a fix.

---

## 9. Addendum 2026-10-09 (second) — the repo moved under this research

Written while the research was running, a parallel session committed three implementation commits on
`feature/product-designer-studio`:

| Commit | What it did |
|---|---|
| `f232ef8` | Product Designer service — local scene designer, real 3D packaging view, mockups, provider-gated generation queue |
| `6bfafcb` | Design Studio — one room for ads, social, A+ content, image and clip requests; rewrote `CreativeStudio.jsx` (+1532 lines); added `northstar-os-ui/audit-imports.cjs` and `verify-studio.cjs` |
| `d67e83a` | ListingForge, SocialPulse and AdPilot gained real creative capability; added `studio/engine/adDoc.js` and `studio/engine/socialDoc.js` |

**§1's headline finding is now historical.** The studio engine is no longer orphaned: all 12 files
under `northstar-os-ui/src/studio/` are git-tracked, and `CreativeStudio.jsx` now imports
`Stage`, `Chrome`, `Fields`, `doc.js`, `assets.js` and `store.js` directly. The engine was committed
while this inventory was being written — which is why §1 recorded "zero git history" at the time it
was checked.

**§8's Phase 0 correction has been actioned.** `presets.js` now carries the verified Amazon figures,
with `VERIFIED from Amazon's asset-creation guide` and `VERIFIED from Amazon's Premium A+ module
guide` comments on the A+ blocks. Spot-checked against the research: `aplus-premium-full` 1464×600,
`aplus-comparison` 150×300, `aplus-four-text` 200×200, `aplus-premium-cmp3` 488×700, and the full
19-module Premium table. `amz-main` moved from 1600×1600 to 2000×2000, which is still inside Amazon's
500–10,000 px range.

**Two items still open, both from the research:**

1. **`storefront` is still 1920×640.** Amazon's published Stores specs give a hero at 3,000×600 and
   full-width image tiles at 1,500×750 minimum (3,000 px wide recommended). `1920×640` is not a
   published Stores spec — it is a generic web-hero size. Still a data fix.
2. **No compliance rule module exists.** `git ls-files northstar-os-ui/src/studio` returns 12 files,
   none of which is a rules or pre-flight module. The research (`OPPORTUNITIES.md` O-04/O-07) ranks
   this as the single highest-value feature: none of the ten competitors inspected enforces Amazon's
   main-image rules, and the ~60 verified spec rows in `AMAZON_REQUIREMENTS.md` are ready to encode as
   data. The dimensions were adopted; the gate that checks them was not built.

**Verification status of the implementation is unknown to this report.** `northstar-os-ui` has both
`verify-studio.cjs` and `audit-imports.cjs`, and `npm run build` must pass with 0 errors per the
project's standing rule — but neither was run as part of this research, and this addendum makes no
claim about their result.


