# PACKAGING CAPABILITY BLUEPRINT — resolving the Design Studio blockers

**Date:** 2026-10-16
**Scope:** make the Design Studio capable of producing real Mogra Organics packaging artwork + print-ready dielines + mockups, resolving the three blockers found in `docs/mogra-organics-packaging/BRIEF_pouch_2sku_20261016.md`.
**Method:** GitHub + web survey, 2026-10-16. Every external component is licence-checked before it is recommended. Licences verified against the primary source (HF model card / repo LICENSE), not secondary write-ups.

---

## 0. THE FINDING THAT MATTERS MOST

The brief failed because packaging artwork was routed to a **diffusion model**. That is a category error.

Packaging artwork is not an image-generation problem. It is a **typesetting + vector geometry** problem. No professional packaging designer diffusion-generates a label — they open the dieline in Illustrator and set vector type on it. Everything the brief wanted (exact wordmark, exact product name, exact weight, legible Supplement Facts, 300 dpi, CMYK, 3 mm bleed, Pantone callouts) is *native* to vector and *impossible* for diffusion at any model size.

**Consequence:** the fix is not a bigger text-rendering model. The fix is to make the artwork **vector-first**, then use diffusion only for jobs vector genuinely cannot do — photographic environments and cutouts.

Reframed that way, five of the eight blockers dissolve into architecture. Two need external tools. One is an operator action.

| Blocker | Resolution | New work? |
|---|---|---|
| `kit-mogra` palette wrong | Local fix | ~5 min |
| `BOX_PRESETS.pouch` proportions wrong | Local fix + co-packer confirm | ~30 min |
| No back-view camera preset | Local fix | ~10 min |
| **Diffusion cannot render text/logos** | **Dissolves — artwork becomes vector** | Architecture change |
| **1216 px ceiling blocks print** | **Dissolves — SVG is resolution-free** | Architecture change |
| CMYK / Pantone / PDF-X-4 output | External chain (all free, all Windows) | Integration |
| **No doypack dieline generator** | **Must be built — nothing open-source exists** | Real engineering |
| Brand vector assets missing | Operator must supply | Blocked on operator |

---

## 1. THE ARCHITECTURE (six layers)

```
   LAYER 1  DIELINE          parametric SVG, millimetres          [BUILD]
            structural truth: cut / crease / seal / zipper / gusset / bleed
                 │
                 ▼
   LAYER 2  ARTWORK          SVG document, vector type            [UPGRADE]
            replaces Canvas2D-only doc.js with an SVG serializer
                 │
                 ├──────────────► LAYER 5  CUTOUTS     BiRefNet / Lucida (MIT)
                 │                                     Amazon MAIN compliance
                 ▼
   LAYER 3  PRINT            SVG → PDF → CMYK PDF/X             [ADD]
            pdf-io (BSD-3)  or  Inkscape → Ghostscript  or  Scribus
                 │
                 ▼
   LAYER 6  MOCKUPS          Blender (GPL) headless  /  render3d.js  [ADD]
            photoreal hero renders + in-app fast preview
                 │
   LAYER 4  TEXT-IN-IMAGE    Qwen-Image Apache-2.0   (marketing only, optional)
            NOT needed for packaging artwork
```

Layers 1–3 are the required path. Layers 4–6 are optional upgrades.

---

## 2. LAYER 1 — THE DIELINE GENERATOR (the real build)

### 2.1 Nothing open-source does doypacks. Verified.

Every open-source dieline project found generates **folding cartons**, not stand-up pouches:

| Project | Licence | What it actually generates |
|---|---|---|
| `BrownBear127/open-dieline` | **PolyForm Noncommercial 1.0.0** ❌ | Reverse-tuck-end + telescope boxes. **No pouches.** |
| `haku-d/pde` | not stated | `card-box-basic` folding carton only |
| `stoneproof-tech/PackagingWorkbench` | open source | FEFCO 0201 / 0301 / 0713 corrugated |
| `DDR68/Rhino_Packaging_Toolkit` | open source | ECMA A20.20 cartons (needs Rhino, paid) |
| `jangtrinh/design-os-origami` | **MIT** ✅ | 11 parametric cartons. **No pouches.** |
| `ahzs645/packcad` | not stated | rigid-origami mailer box |
| `MiquelRR/TeDraGen` | MIT ✅ | box/POS templates |

`open-dieline` is also **noncommercial-licensed**, so it is out on licence grounds as well as scope. Pouch dieline generation is a **commercial SaaS niche** (Packhelp Packaging Toolbox, Pacdora, DielineMaker, Sparal) — nobody has open-sourced it.

**So it must be built.** This is tractable: a stand-up pouch (doypack) dieline is a closed parametric polygon — body rectangle, top seal band, zipper keep-out, bottom gusset V-fold, side seals, optional hang hole, rounded corners, plus bleed and safe-area offsets. Roughly 300–500 lines of SVG path generation.

### 2.2 Steal the output contract from MIT code

`jangtrinh/design-os-origami` (**MIT**) already solves the *output* problem correctly, even though it only does cartons. Copy its **printer profile** pattern:

- five **named spot colours**
- 1 pt PDF strokes
- a printed legend on the sheet
- **3 mm default bleed**
- separate printer PDF + R2000 DXF per blank
- dimensioned in millimetres at 100 % scale

Its CLI is also the right shape:

```
python3 -m origami_cad.cli generate --type tuck-box --profile printer --output-dir output
```

**Our equivalent:**

```
python -m packaging.cli dieline --type standup-pouch --size 130x210+40 --profile printer
```

### 2.3 Adopt the SVG layer convention from `open-dieline` (idea only, not code)

Even though its licence bars reuse, its **layer model** is correct industry practice and should be matched:

- four independent layers: **cut / crease / half-cut / dimension**
- SVG export groups by line type into named `<g>` so Illustrator opens it already layered
- a "manufacturing mode" that emits only cut / crease / half-cut
- DXF R12-compatible, three layers `CUT` / `CREASE` / `HALFCUT`, so the die shop can read it

Match this convention exactly. It is what a die shop expects to receive.

### 2.4 Calibrate against real published dielines — and it exposes a spec error

Free, published, 1:1-scale stand-up pouch dielines exist. Use them as the calibration corpus:

- **Sparal Packaging** — 6 sizes in **SVG + 1:1 PDF**, drawn to 5 mm seal margins, fold lines, **zipper keep-out bands**, bleed notes. Also a browser generator for arbitrary W/H/gusset.
- **PackagingBest** — 20 stand-up pouch sizes with clear front, back, seal, zipper and bottom-gusset guides.
- **`intrepidjoe/hq-dielines`** — **GPL-3.0**, real production mylar-bag dielines from HQ Packaging, including `4x3 flat with zipper.pdf`, `3x5x2`, `4x6x2`, `5x8x3`. North-American inch conventions.
- **Packhelp Packaging Toolbox** — doypack template at `/tools/dielines/templates/doypack`.

### 2.5 ⚠ THE GUSSET IS WRONG — confirm before cutting plates

Calibrating against Sparal's published ladder produces a hard, factual mismatch:

| Fill weight | Published standard stand-up pouch | Gusset |
|---|---|---|
| 2 oz / 50 g | 100 × 150 **+60** | 60 mm |
| 4 oz / 100 g | 120 × 180 **+70** | 70 mm |
| **8 oz / 250 g** | **140 × 200 +80** | **80 mm** |
| 16 oz / 500 g | 160 × 240 +90 | 90 mm |
| 32 oz / 1 kg | 200 × 300 +100 | 100 mm |

Mogra's specs:

| SKU | Spec | Nearest industry weight | Industry gusset | Delta |
|---|---|---|---|---|
| 1 — Lion's Mane 6 oz / 170 g | 130 × 210 **+40** | ~4–8 oz | 70–80 mm | **≈ half** |
| 2 — Shiitake 8 oz / 227 g | 150 × 210 **+40** | 8 oz / 250 g | **80 mm** | **≈ half** |

Width and height are in the right neighbourhood. **The gusset is roughly half the industry convention for that fill weight.** Either the 40 mm is measured on a different convention (single-ply gusset, or side-seal width rather than total bottom-gusset depth), or both bags are materially undersized for their fill.

This is the single largest commercial risk in the brief. **Resolve it with the co-packer and by physically measuring two or three competitor 8 oz pouches before any plate is cut.** A wrong gusset is a reprint.

---

## 3. LAYER 2 — ARTWORK: MAKE THE DOCUMENT MODEL EMIT SVG

### 3.1 The change

`northstar-os-ui/src/studio/engine/doc.js` is a **Canvas2D** renderer over a normalised 0..1 layer model. The model is already correct and already resolution-independent; only the *backend* is raster-bound. `mockupToDataUrl()` even defaults to 720 px (`mockups.js:209`) — far below the Amazon 2000 × 2000 MAIN requirement.

**Add an SVG serializer alongside the existing Canvas2D renderer.** One document, two backends:

- **Canvas2D** → interactive on-screen preview (unchanged, keep it fast)
- **SVG** → output: resolution-free, real `<text>`, real fonts, real kerning, diffable in git, and directly convertible to PDF → CMYK

Normalised coordinates map onto SVG's `viewBox` with no translation layer. This is a small, well-scoped change with a large payoff — it is the single highest-leverage edit in this blueprint.

### 3.2 Why this is what actually resolves the text blocker

Once artwork is SVG, "text rendering" stops being a model problem:

- the wordmark is a `<use href="#mogra-logo">` reference
- the product name is a `<text>` element with Libre Baskerville, exactly spelled
- the weight is `6 oz (170g)` — literal, always correct
- the Supplement Facts panel is a real table
- nothing can hallucinate, because nothing is inferred

**No diffusion model is required to produce correct packaging artwork, at any resolution, ever.** That entire blocker class disappears.

### 3.3 Still operator-gated

The SVG serializer cannot invent a wordmark. These vector assets must be supplied before Layer 2 produces anything real:

- `mogra-logo-lockup.svg` — mortar-and-pestle mark + EST 2023 + serif wordmark + tagline
- `mogra-mushroom-lionsmane.svg` — engraved line art
- `mogra-mushroom-shiitake.svg` — engraved line art
- `mogra-iconrow.svg` — USDA Organic · Non-GMO · Gluten-Free · Fruiting Body
- `mogra-sprig.svg`, `mogra-rule.svg` — ornaments

**This is the last true blocker and no amount of research resolves it.**

---

## 4. LAYER 3 — PRINT OUTPUT (CMYK / PDF-X)

### 4.1 Recommended: `pdf-io` — BSD-3-Clause, Python

**`pdf-io` (PyPI, BSD-3-Clause, Python ≥3.11)** is the cleanest fit by a wide margin:

- SVG → PDF, preserving shapes, paths, **text with embedded font subsets**, gradients, masks, clipping
- **CMYK output**
- **spot colours (Separation)**
- **ink limit**
- **ICC output intent**
- **PDF/A-2b / 2u / 3b**
- **zero dependencies** — bundled C library, prebuilt for Windows x86_64 and arm64, `pip` compiles nothing
- pure Python, so it drops straight into the existing backend

```python
import pdf_io
pdf_io.convert_file("mogra_lm6_front.svg")           # → .pdf
pdf_bytes = pdf_io.svg_to_pdf(svg_text)
```

Caveats to respect: no complex-script shaping or bidi; WOFF2 and CFF2 fonts unsupported (use TTF/OTF for Libre Baskerville and DM Sans); filters are rasterized so keep the artwork filter-free — which the design bar already requires ("no gradients").

### 4.2 Fallback chain: Inkscape → Ghostscript (both free, both Windows)

If `pdf-io` disappoints:

```powershell
# 1. SVG → PDF, text converted to outlines
inkscape --export-type=pdf --export-pdf-version=1.5 `
         --export-text-to-path "panel.svg"

# 2. RGB PDF → CMYK PDF
gswin64c -q -sDEVICE=pdfwrite `
         -sColorConversionStrategy=CMYK `
         -sOutputICCProfile=CoatedFOGRA39.icc `
         -dNOSAFER -o "panel_cmyk.pdf" "panel.pdf"
```

Both are scriptable from Python. Note `--export-text-to-path` deliberately converts type to outlines — correct for a plate file, and it makes the "all type outlined" requirement in the brief automatic.

### 4.3 For true PDF/X-3 with an embedded profile: Scribus

**Inkscape cannot export PDF/X-3 and cannot embed colour profiles.** If the co-packer demands PDF/X-3 with an embedded ICC profile, the workflow requires **Scribus** (free, open source, proper CMYK + PDF/X-3 export, scriptable via its Python API). Verified constraint, not a preference.

### 4.4 JS option

`@imprint-pdf/print` — **Apache-2.0** core, ships PDF/X-4, **CMYK, ICC via lcms2 compiled to WASM**. Use this only if the print path should live in the UI rather than the backend. `pdf-io` is simpler for a Python backend.

### 4.5 Do not use

- **`freebug62/we2print`** — SVG-native web-to-print, zero deps, but its own milestone table lists **"SVG → PDF export (CMYK, bleeds): Not started"**. Unusable today.
- **Inkscape's `ExportPDFCMYK` extension** — its own wiki says it "doesn't yet run on Windows".

---

## 5. LAYER 4 — TEXT-IN-IMAGE MODELS: LICENCE-GATED

Only relevant for **marketing imagery** (A+/social), never for packaging artwork. Included because it was an obvious candidate and the licence outcome is decisive.

### 5.1 ⛔ Qwen-Image 2.1 — NON-COMMERCIAL. Do not use.

The best-looking option is blocked. `Qwen/Qwen-Image-2.1` is **7B, native 2K, RGBA VAE, professional typography with "packaging designs" named as a use case**, and there is a **verified 16 GB deployment** (`quitedob/qwenimage2.1`, RTX 5060 Ti 16 GB, INT8 ConvRot, 18.5 s @ 1024², peak VRAM 15,806/16,311 MiB). It would have been an excellent fit.

**It is licensed under the Qwen RESEARCH LICENSE AGREEMENT (Release Date: September 20, 2026)**, which states verbatim:

> *"Non-Commercial" shall mean for research or evaluation purposes only.*
> *… FOR NON-COMMERCIAL PURPOSES ONLY.*
> *You shall not use the Materials for any commercial purpose without obtaining a separate commercial license from us.*

Confirmed on the upstream repo (`QwenLM/Qwen-Image-2.1/LICENSE`) and on every GGUF mirror (`molbal`, `Abiray`, `abenzerps` — all `license: qwen-research`). Commercial licensing would require a request to `model-business@notice.qwencloud.com`.

**Cannot touch Mogra Organics packaging or marketing.**

### 5.2 ✅ Qwen-Image (original) — Apache-2.0. Commercial OK.

`Qwen/Qwen-Image` is **Apache-2.0, Copyright 2024 Alibaba Cloud**. 20B MMDiT, text encoder Qwen2.5-VL-7B. Recognised as the strongest open text-rendering model; ranks first on the reported Alignment and Text categories and second on LongText-Bench English. GGUF builds exist (`city96/Qwen-Image-gguf`, `license: apache-2.0`) at ~12 GB, which fits the 16 GB card with the text encoder offloaded to system RAM.

**If text-in-image is wanted for marketing, this is the model.** Note the Qwen-Image-2512 refresh has not been licence-verified for this document — verify before adopting that specific checkpoint.

### 5.3 VRAM reality on this box

The repo already documents the constraint: one 16 GB GPU, the local brain resident at ~10.4 GB, `unload_brain()` evicting it per render. Any of these models stacks with that rule, not around it:

- diffusion model must stay in VRAM (speed-critical during sampling)
- text encoder goes to **system RAM** (runs once per prompt, ~zero speed impact)
- check RAM headroom — the repo already flags a pending 64 GB upgrade

---

## 6. LAYER 5 — CUTOUTS FOR AMAZON MAIN COMPLIANCE

This layer automatically satisfies two **BLOCK** rules from the compliance register — `main-white-bg` and `main-fill` (≥85 % frame). It is the highest-value small addition in the blueprint.

| Model | Licence | Verdict |
|---|---|---|
| **BiRefNet** | **MIT** ✅ | Native in ComfyUI core (`Load Background Removal Model` + `Remove Background`), weights in `models/background_removal/`, RGBA + mask output |
| **BiRefNet-HR** | **MIT** ✅ | **Up to 2560 × 2560** — clears the 2000 × 2000 MAIN requirement outright |
| **Lucida** | **MIT** ✅ | BiRefNet fine-tune by `egeorcun`, purpose-built for **text, logos and line art** — exactly right for extracting the Mogra wordmark. In ComfyUI core. |
| **ComfyUI-RMBG** (`1038lab`, v3.2.0) | node pack | Adds `refine_foreground` (kills the background-colour halo on edges) and `unload_model` (instant VRAM release — pairs with the existing GPU handshake). Runs BiRefNet at 2048. |
| **RMBG-2.0** | **CC BY-NC 4.0** ❌ | **Non-commercial.** Do not use — despite being the most commonly recommended option. |

**Pipeline:** cut out the pouch with BiRefNet-HR → composite onto pure white → auto-scale to ≥85 % frame → MAIN-compliant by construction. Use **Lucida** when the goal is extracting the logo or line art from a flat design rather than the whole object.

---

## 7. LAYER 6 — PHOTOREAL MOCKUPS

The repo's `render3d.js` is a dependency-free Canvas 3D packaging renderer — good for fast in-app preview, not for hero photography.

- **Blender** (GPL, free, commercial output fine) + Python API, fully headless:
  `blender -b scene.blend -P render.py -- args`
  Run as a backend job beside the existing ComfyUI runner. Output is not licence-encumbered.
- **PACKFOLD** — **$46 one-time**, Blender add-on that rigs a flat dieline so it folds inside Blender. Cheap, no subscription. Its known limit is that it rotates panels on a rig rather than simulating physics — for a simple doypack that is acceptable.
- **PackCAD Mockup** — commercial ($29/mo, $240/yr), browser-based, **physics-based folding including gussets**, exports glTF/GLB → Blender. There is a published Blender workflow. Only genuinely needed if gusset-accurate cloth deformation is required.

**Recommendation:** `render3d.js` for the fast loop → Blender headless for hero renders → buy PACKFOLD once if dieline-driven folding is wanted. Skip PackCAD's subscription unless its gusset simulation proves necessary.

---

## 8. COMPONENT SCORECARD

| Component | Licence | Commercial OK | Role | Priority |
|---|---|---|---|---|
| `pdf-io` | BSD-3-Clause | ✅ | SVG → CMYK PDF, spots, ICC | **P0** |
| Inkscape CLI | GPL | ✅ | SVG → PDF, text-to-path | **P0** |
| Ghostscript | AGPL | ✅ | → CMYK | **P0** |
| `jangtrinh/design-os-origami` | **MIT** | ✅ | printer-profile pattern (cartons only) | **P1** |
| BiRefNet / BiRefNet-HR | **MIT** | ✅ | cutouts → MAIN compliance | **P1** |
| Lucida | **MIT** | ✅ | logo / line-art extraction | **P1** |
| ComfyUI-RMBG | node pack | ✅ | halo removal, VRAM release | **P1** |
| Blender | GPL | ✅ | photoreal mockups | **P2** |
| Qwen-Image (original) | **Apache-2.0** | ✅ | text-in-image, marketing only | **P2** |
| Scribus | GPL | ✅ | PDF/X-3 + embedded ICC | **P2** |
| PACKFOLD | $46 one-time | ✅ | dieline folding in Blender | **P3** |
| `intrepidjoe/hq-dielines` | GPL-3.0 | ⚠ reference only | real mylar dielines, calibration | **P1** |
| `haku-d/pde` | not stated | ⚠ pattern only | dieline→3D architecture | P3 |
| **`open-dieline`** | **PolyForm Noncommercial** | ❌ | — | **excluded** |
| **RMBG-2.0** | **CC BY-NC 4.0** | ❌ | — | **excluded** |
| **Qwen-Image 2.1** | **Qwen Research** | ❌ | — | **excluded** |
| **`freebug62/we2print`** | — | ❌ | PDF export not started | **excluded** |

Three components that look like obvious wins — `open-dieline`, RMBG-2.0 and Qwen-Image 2.1 — are all **licence-blocked for commercial use**. All three are the natural first result when searching. **Nothing gets adopted in this studio without a licence check against the primary source.**

---

## 9. BUILD ORDER

**P0 — unblock the print path (no new models, no GPU)**
1. Fix the three local blockers: `kit-mogra` palette, mm-true pouch presets, `back` camera preset
2. Add the **SVG serializer** to `doc.js` (Layer 2) — one document, two backends
3. Wire **SVG → `pdf-io` → CMYK PDF**; verify `ink limit` and `ICC output intent` against the co-packer's spec

**P1 — the real engineering**
4. Build the **parametric stand-up-pouch dieline generator** (Layer 1): mm-true, cut/crease/half-cut/dimension layers, 3 mm bleed, named-spot printer profile, SVG + DXF R12 out. Calibrate against Sparal, PackagingBest and `hq-dielines`.
5. **Resolve the gusset question with the co-packer** — before any plate. §2.5.
6. Add **BiRefNet-HR + Lucida** cutout path → automates `main-white-bg` and `main-fill`

**P2 — upgrade the mockup + marketing lanes**
7. **Blender headless** render job beside the ComfyUI runner
8. **Qwen-Image (Apache-2.0)** for text-in-image, if and when marketing imagery needs it — *not* Qwen-Image 2.1
9. Extend the compliance register with the new BLOCK rules the dieline introduces (bleed present, safe area respected, seal zones clear of type)

**Operator action, blocking P0 step 2 in practice**
10. **Supply the vector brand assets.** Nothing in this blueprint can generate a wordmark.

---

## 10. WHAT THIS DOES NOT FIX

Be explicit about the ceiling:

- **No open-source component generates doypack dielines.** Layer 1 is custom engineering. Every alternative found is a commercial web tool whose geometry cannot be reused.
- **A generated dieline is a design proof, not a die.** Every source surveyed carries the same caveat — *verify with your die shop before production*. `open-dieline` states it outright; `design-os-origami` qualifies it the same way. Treat the output as a calibrated planning dieline, not a manufacturing master.
- **The gusset discrepancy is a physical question, not a software one.** §2.5 must be answered with a tape measure and a conversation with the co-packer.
- **Licences can change.** Qwen-Image 2.1's terms were set 2026-09-20 and already block commercial use. Re-verify before each new model adoption.
- **Nothing here was installed or run.** This is a survey + blueprint. Every claim about a component's capability is sourced; nothing has been verified on this machine.
