# MOGRA ORGANICS — STAND-UP POUCH · NORTHSTAR DESIGN STUDIO BRIEF

**SKU 1** Organic Lion's Mane Mushroom Powder · 6 oz (170 g)
**SKU 2** Organic Shiitake Mushroom Powder · 8 oz (227 g)

Revised 2026-10-16 from the original concept brief. The original was written as a
brief to a human packaging designer. This version is written to the **Northstar OS
Product Design Studio** and routes every requirement to an engine that can actually
produce it.

---

## 0. ENGINE ROUTING — read this first

The original brief asked one worker for dielines, CMYK plates, a wordmark, and
photoreal mockups. The Design Studio is three lanes with hard, documented limits.
Every requirement below is assigned to exactly one lane.

| Lane | Engine | On this box | Produces | Cannot produce |
|---|---|---|---|---|
| **A** | Deterministic renderer — `studio/engine/doc.js` (Canvas2D), `render3d.js`, `mockups.js`, `presets.js` | Local, free, **always available** | Brand-exact artwork, vector type, exact-mm geometry, repeatable mockups at any raster size | Photo-realism |
| **B** | ComfyUI — FLUX.2 klein 4B Q8 | Local, free, **armed only when `MEDIA_GEN_LIVE=1` AND ComfyUI answers on `127.0.0.1:8199`** | Backdrops, lifestyle plates, texture, environments | **Any text, wordmark, logo or legible label copy.** Max 1216 px. Not print resolution |
| **C** | Prepress — Illustrator / Acrobat, human | Outside the studio | CMYK, Pantone, PDF/X-4, 3 mm bleed, outlined type, plates, die lines | — |

### Lane B's hard limits — plan around these, do not prompt against them

`Northstar_backend/studio_generation.py:30` appends this to **every** image prompt:

```
, professional commercial product photography, clean composition, no text, no watermark, no logos
```

That is not a suggestion to the model, it is a hard suffix. Consequences:

- Lane B **will not render** "MOGRA ORGANICS", the product name, the icon row, the
  weight, or the Supplement Facts panel. Asking for them produces mush or produces
  them as unreadable pseudo-glyphs. **Do not ask.**
- Resolution is clamped to **512–1216 px** (`_clamp`). Print needs 300 dpi.
  A 130 mm panel at 300 dpi is 1,535 px — **already past the engine's ceiling.**
- Steps are fixed at **4 (draft) / 8 (final)**. No high-step refinement available.
- One 16 GB GPU: each render **evicts the local brain** (`unload_brain()`, ~10 GB)
  and frees models after (`release_models()`). The brain reloads on next chat
  (~10–60 s). Budget for it; do not run a render burst during chat work.

**Therefore:** Lane B generates the *world the pouch sits in*. Lane A draws the
*pouch*. Lane C makes it printable. Nothing crosses over.

---

## 1. LANE A — brand kit correction (blocker, do first)

`presets.js` → `DEFAULT_BRAND_KITS` already carries a `kit-mogra` entry, but it is
an **honest placeholder from a local work brief and does not match the brand**:

```js
// CURRENT — presets.js:132-143  (WRONG PALETTE)
{ id: 'kit-mogra', name: 'Mogra Organics',
  palette: ['#f4f7f0', '#1f3320', '#4a7a4a', '#d8a13a', '#ffffff'],
  ink: '#1f3320', paper: '#f4f7f0', accent: '#4a7a4a',
  headingFont: 'Libre Baskerville', bodyFont: 'DM Sans',
  voice: 'Clean, botanical, plain-spoken.' }
```

```js
// REQUIRED — replaces the palette/ink/paper/accent only
{ id: 'kit-mogra', name: 'Mogra Organics',
  palette: ['#171717', '#D5A77A', '#9DBA8B', '#F5EEE2', '#9FA9A4', '#253628', '#D0C5AC'],
  ink: '#171717',
  paper: '#F5EEE2',
  accent: '#253628',
  headingFont: 'Libre Baskerville',   // keep — matches the canister wordmark
  bodyFont: 'DM Sans',                // keep
  voice: 'Clean, botanical, plain-spoken.' }
```

**Palette roles** (bind these, do not re-invent per asset):

| Role | Hex | Use |
|---|---|---|
| Ink | `#171717` | Body copy, rules, Supplement Facts |
| Kraft | `#D5A77A` | SKU 1 ground, mortar fill |
| Olive | `#9DBA8B` | SKU 1 secondary, botanical sprigs |
| Ivory | `#F5EEE2` | SKU 2 ground, all-sides stock |
| Sage | `#9FA9A4` | SKU 2 secondary, sage-swatch variant |
| Forest | `#253628` | SKU 2 ground alt, CTA fills, deep-green ink |
| Cream | `#D0C5AC` | Dividers, subtle panels |

The existing `kit-pine` and `kit-wordcoffee` kits are **not** to be used for Mogra
artwork. Every Mogra document must set `kitId: 'kit-mogra'`.

---

## 2. LANE A — pouch geometry (blocker, do second)

`BOX_PRESETS` already contains a pouch, but its proportions are wrong for **both**
SKUs, so an unmodified render is dimensionally false:

```js
// CURRENT — presets.js:238
{ id: 'pouch', name: 'Stand-up pouch', note: 'Wide, shallow, tall gusset.', size: [1.15, 1.5, 0.42] }
// normalised to width → 1 : 1.3043 : 0.3652
```

| SKU | Real mm (W × H × D) | Required normalised | vs. preset |
|---|---|---|---|
| 1 — Lion's Mane 6 oz | 130 × 210 × 40 | **1 : 1.6154 : 0.3077** | height **19.3 % too short**, gusset **18.7 % too deep** |
| 2 — Shiitake 8 oz | 150 × 210 × 40 | **1 : 1.4000 : 0.2667** | height **6.8 % too short**, gusset **37.0 % too deep** |

Two parameterised presets are required, sized by `[W, H, D]` in millimetres, not by
a single hardcoded triple:

```js
{ id: 'pouch-mogra-lm6',  name: "Mogra Pouch — Lion's Mane 6oz", size: [130, 210, 40], mm: true }
{ id: 'pouch-mogra-shi8', name: 'Mogra Pouch — Shiitake 8oz',    size: [150, 210, 40], mm: true }
```

Until these exist, **do not present any pouch render as dimensionally accurate.**

---

## 3. LANE A — the three required views

The requested views map onto existing `CAMERA_PRESETS`:

| Required view | Camera preset | Notes |
|---|---|---|
| Standing upright, front | `front` — yaw 0°, pitch 0° | Flat packshot. Pair with `LIGHTING.flat`. |
| Back | **no preset exists** | There is no yaw-180 preset. Either add `{ id: 'back', yaw: 180, pitch: 0 }`, or render `front` with the **back-panel artwork** mapped instead of the front. Do not ship a mirrored front and call it the back. |
| Side profile showing gusset | `profile` — yaw −90°, pitch 4° | Its own note reads "Side panel / dieline check". Correct preset. |

**Lighting rigs:**

- Dieline + packshot → `flat` ("Even light both sides. Print / dieline use.")
- Hero mockup → `three-point` (the default product look)
- Deep-green premium variant → `dramatic`

**Scenes** (for shelf/marketing context, Lane A composites, Lane B may supply the plate):

- `scene-studio-paper` — "Listing-safe." Use as the default.
- `scene-marble` — "Cool stone surface for beauty / supplement shots." Best fit for the apothecary register.
- `scene-warm-linen` / `scene-sage` — warm and botanical variants.
- `scene-deep-pine` — dark premium; pairs with the forest-green ground.

---

## 4. LANE A — front panel, authored as a document

The renderer's layer vocabulary is fixed: `KIND = { BG, SHAPE, IMAGE, TEXT, PRODUCT, BADGE }`,
in **normalised 0..1 coordinates** (`doc.js`). Author the front panel as a Mogra
document so it renders identically at 200×200 and 2000×2000.

| # | Layer kind | Content | Placement |
|---|---|---|---|
| 1 | `BG` | Ground fill — SKU 1 `#D5A77A`, SKU 2 `#F5EEE2` | full bleed |
| 2 | `IMAGE` | Logo lockup SVG — mortar-and-pestle mark, EST/2023 flank, wordmark, tagline | centred, top third |
| 3 | `TEXT` | `ORGANIC LION'S MANE` / `ORGANIC SHIITAKE` | large, centred |
| 4 | `TEXT` | `MUSHROOM POWDER` | beneath, smaller |
| 5 | `IMAGE` | Engraved mushroom line art SVG — lion's mane form / shiitake cluster | mid-panel |
| 6 | `IMAGE` | Icon row SVG — USDA Organic · Non-GMO · Gluten-Free · Fruiting Body | near bottom |
| 7 | `TEXT` | `6 oz (170g)` / `8 oz (227g)` | bottom |
| 8 | `TEXT` | `Healthy & Organic` footer | bottom |

**Rule:** every text element is a `TEXT` layer, never baked into a raster image. The
compliance register enforces this — rule `text-on-image-legibility`: *"On-image text
is rendered as vector."* A flattened PNG of the label will flag.

**Required assets (supplied by the operator, vector, SVG):**

- `mogra-logo-lockup.svg` — mortar-and-pestle mark + EST 2023 + MOGRA ORGANICS serif wordmark + "Healthy & Organic" tagline
- `mogra-mushroom-lionsmane.svg` — engraved line art, single colour, no cartoon, no photo
- `mogra-mushroom-shiitake.svg` — engraved line art, shiitake cluster
- `mogra-iconrow.svg` — 4-icon certification row, canister-matched style
- `mogra-sprig.svg`, `mogra-rule.svg` — botanical ornaments and divider rules

> **Blocker:** none of these SVGs exist on disk yet. The studio cannot invent a
> wordmark. Until the operator supplies the vector logo, Lane A renders
> `NO ARTWORK` placeholders — which is the correct, honest behaviour.

---

## 5. LANE A — back panel

Authored as a second document on the same 130 × 210 / 150 × 210 geometry.

1. `TEXT` — description block, 2–3 sentences, DM Sans
2. **RESERVED ZONE** — Supplement Facts, ~65 × 110 mm, black rules on white. Operator supplies final panel; use a *marked* placeholder, never a fabricated one
3. **RESERVED ZONE** — QR + UPC barcode. Operator supplies both
4. `TEXT` — suggested use · storage ("Store in a cool dry place") · country of origin · "Distributed by T2 Holdings LLC"
5. `IMAGE` — zipper icon + reseal note

The renderer's contract is explicit: *"Never fabricates content. Placeholder text is
text the operator typed."* Leave the reserved zones visibly reserved.

---

## 6. LANE B — generation requests (the diffusion engine)

Lane B is asked for **backdrops and environments only**. Use the `GEN_PURPOSES`
vocabulary:

| Purpose id | Label | Priority |
|---|---|---|
| `background` | "Backdrop only — Scene without the product for compositing." | **Primary.** Generate the plate; Lane A composites the packshot onto it. |
| `product-scene` | "Pack shot in a generated environment." | Marketing imagery, A+ |
| `lifestyle` | "Product in use, human context." | A+ / social |

**Prompt shape for Lane B.** Describe surface, light, mood, botanical context —
nothing else:

> *Warm linen cloth on a dark walnut table, soft directional daylight from the left,
> dried botanical sprigs and a scattering of loose dried mushroom pieces out of
> focus in the background, deep forest-green shadows, calm apothecary mood, shallow
> depth of field*

**Forbidden in every Lane B prompt:** the brand name, any product name, any weight,
any certification word, the word "label", "text", "packaging artwork", or any request
for typography. The `no text, no watermark, no logos` suffix will fight it and the
output will be unusable.

Tier: `draft` (4 steps) to explore, `final` (8 steps) only for a chosen composition.

---

## 7. OUTPUT FORMATS — from the spec registry

Real raster sizes the deterministic renderer hits (`presets.js` → `FORMAT_GROUPS`):

| Asset | Format id | Size | Lane |
|---|---|---|---|
| Amazon MAIN | `amz-main` | 2000 × 2000 | A |
| Amazon secondary / A+ | `amz-alt` | 1600 × 1600 | A |
| A+ Premium full image | `aplus-premium-full` | 1464 × 600 | A |
| A+ single image & sidebar | `aplus-sidebar-main` | 300 × 400 | A |
| A+ four images & text | `aplus-four-text` | 200 × 200 | A |
| Brand Story desktop | `brand-story-desktop` | 1464 × 625 | A |
| Storefront hero | `storefront` | 1920 × 640 | A |
| Meta feed / IG carousel | `meta-feed` | 1080 × 1080 | A |
| TikTok / Reels story | `tiktok` | 1080 × 1920 | A |
| Print label | `print-label` | 1275 × 1650 | A → C |

> **Gap to know:** `mockupToDataUrl()` defaults to **720 px** (`mockups.js:209`).
> `amz-main` needs **2000 × 2000**. Pass an explicit size — at the default, the
> MAIN image fails the zoom rule below.

---

## 8. COMPLIANCE PRE-FLIGHT — BLOCK rules that constrain this brief

The studio runs a 50-rule register. These are `level: 'block'` — export refuses.

| Rule id | Level | Label | What it means here |
|---|---|---|---|
| `main-no-overlay` | **BLOCK** | "No text, logo, badge, border, colour block or watermark on MAIN" | The `amz-main` shot must be the bare pouch on white. **No added icon row, no border, no colour block.** The icons live *on the pouch*, which is fine — they must not be an added graphic layer over the image. |
| `main-white-bg` | **BLOCK** | "MAIN image background is white" | The shelf / marble / linen hero **cannot be the MAIN image.** Those are secondary + A+ assets. |
| `main-fill` | **BLOCK** | "Product fills at least 85% of the frame" | Frame the pouch tight. Do not leave scene padding on the MAIN. |
| `raster-range` | **BLOCK** | Longest side within Amazon's published range | — |
| `raster-zoom` | FLAG | "Longest side above 1,000 px for zoom" | 720 px default fails this. Ship ≥ 1,600 px. |
| `superiority` | **BLOCK** | "No unsubstantiated superiority claim" | See the brand-bar note below. |
| `competitor-named` | **BLOCK** | "No competitor named" | Same. |
| `caps-headline` | **BLOCK** | "Headline is not ALL CAPS" (scope: ads) | The all-caps package lockup is *package artwork* and is fine. Do **not** reuse it as a paid-ad headline — it will block. |

> **On the original brief's brand bar.** "Looks at home on a natural-foods shelf next
> to Gaia Herbs and Om Mushroom" is an **internal design standard only**. It must
> never appear on artwork, in a comparison chart, or in listing copy — `superiority`
> and `competitor-named` will block it, and it is a real Amazon policy exposure.

---

## 9. OPEN FLAG — pouch fill ratio (verify before cutting plates)

Not a studio issue, but this dieline is about to become a print plate, and the
volume math does not look right.

Available fill height on a 210 mm doypack is roughly 210 − 40 mm for zipper, seals
and headspace ≈ **170 mm**. Geometric fill volume ≈ W × 170 × D:

| SKU | Geometric fill volume | Product at 0.45–0.55 g/mL | Fill ratio |
|---|---|---|---|
| 1 — 170 g | 130 × 170 × 40 = **884 mL** | 309–378 mL | **≈ 35–43 %** |
| 2 — 227 g | 150 × 170 × 40 = **1,020 mL** | 413–504 mL | **≈ 40–49 %** |

Both bags land **roughly half full**. For comparison, a 130 × 200 mm pouch is a
common size for a **227 g** competitor bag — so SKU 1 would be a *larger bag holding
less product* than its direct competition, which is a perceived-value problem on a
shelf and a complaint driver on Amazon.

**Action:** confirm the co-packer's rated fill volume for both formats, and physically
measure 2–3 competitor pouches (Micro Ingredients 8 oz, Nutriclean/Nutricost 8 oz,
Food to Live 8 oz) before the plates are cut. Likely fixes: reduce height, reduce
gusset, or go narrower-and-taller. **Re-cutting print plates is expensive; measure first.**

---

## 10. DELIVERABLES — restated by lane

### Lane A — deterministic, in-studio, available now
1. `kit-mogra` corrected to the real palette (§1)
2. Two mm-true pouch presets (§2) and a `back` camera preset (§3)
3. Front + back panel documents per SKU, authored in normalised layers (§4, §5)
4. Mockups: front, back, side-profile-with-gusset — at **explicit sizes**, not the 720 px default
5. Both SKUs side by side at `amz-main` and `amz-alt`, plus a presentation sheet
6. A `print-label` (1275 × 1650) export of each panel as the handoff to Lane C

### Lane B — local diffusion, requires arming
7. Environment plates per §6, `draft` tier first
8. Composited hero images for secondary / A+ only — never MAIN (§8)

### Lane C — human prepress, outside the studio
9. True 100 %-scale dieline with **3 mm bleed**, safe margins, zipper line and gusset fold marked
10. Layered vector source — AI or PDF/X-4, type outlined or licensed, **CMYK with Pantone equivalents**
11. Plate-ready files for the co-packer

**Lane C is not optional and cannot be substituted.** The studio's own brief already
says this — this revision promotes it from a footnote to a named lane: *if artwork
is produced with an AI tool, the print dieline must be manually rebuilt and verified
in vector software at true scale.* Lane B outputs at 1216 px; the print panel needs
1,535 px at 300 dpi. **No LANE B RENDER MAY GO TO PLATES.**

---

## 11. DESIGN BAR

Premium organic apothecary: calm, botanical, confident. Two tests:

1. Legible and distinct at Amazon thumbnail scale (~150 px) — the wordmark must read
   at `aplus-four-text` (200 × 200) without the tagline.
2. Sits at home on a natural-foods shelf — **as an internal standard, not artwork.**

No gradients. No photo-realism of powder piles. No generic wellness stock iconography.
No cartoon characters. Engraved botanical line art only, matching the approved
canister "Botanical Modern" treatment.
