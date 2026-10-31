# Phase 1 & 3 — creative engine + operating-loop bindings

**Date:** 2026-10-30
**Model policy:** DeepSeek V4.1 Flash (OpenCode Go) for all code and reasoning; local lanes stopped.
FLUX 3 untouched this pass (no render was requested that needed one).
**Verification:** `pytest` **62 passed** (5 new modules) · `npm test` **63 assertions + 11 contrast pairs** · `npm run build` **0 errors (1.43 s)**

---

## Phase 1

### 1.1 A+ module generator — geometry, not prose

`specialists/image_aplus.py` already owned the *verified* canvas sizes and the copy rules. The
missing half was geometry. `aplus_layout.py` now produces **exact integer rectangles**:

| Module | Geometry produced |
|---|---|
| header / banner | safe inset 24, copy band = 44% of width (even-px), side-selectable |
| three_tiles | 3 × 300×300, 20px gaps, centred → x = **15, 335, 655** |
| four_tiles | 4 × 220×220, 30px gaps → x = **0, 250, 500, 750** (fills 970 exactly) |
| comparison | header 90, label column 250, two 360 columns, 4 rows |
| all | `crop_rect()` for `object-fit: cover`, `responsive_rules()` scale 1.0 / 728-wide / 344-wide |

`validate()` rejects overflow, negative origins and zero sizes; `pixel_plan()` refuses to return
broken geometry at all.

**UI:** `src/studio/aplus/` — `HeaderModule`, `ThreeFeature`, `ComparisonChart` render at the exact
canvas size, then scale **as one block** (Amazon scales A+ inside a fixed column; it never reflows).
Scale is measured with a `ResizeObserver`, not guessed.

**Anti-drift:** `src/lib/aplusMetrics.test.js` parses `aplus_layout.py` and fails if any canvas,
tile or scalar constant differs. Five assertions, and they are the reason a duplicated constant is
acceptable here.

### 1.3 Hero isolation with contact shadow

`listing_image.py`: cutout → **pure white** hero (RGB 255,255,255 at every sampled corner), subject
scaled to the requested fill, deterministic ellipse contact shadow blurred beneath the footprint.

The shadow is the trap: a blurred ellipse has tails, so the mask is **clipped off the frame border**
— a corner can never pick up grey. `audit_white()` returns the corner values and the pure-white
ratio, so compliance is *measured*, and an empty subject raises `empty_subject` rather than shipping
a white square as a product photo.

## Phase 3

### 3.1 Render init binding

`render_bind.bind(product, pricing=…, keywords=…, buyer=…)` → a `RenderBrief` where the **margin
decides the material**:

| margin | tier | substrate / finish |
|---|---|---|
| ≥ 55% | premium | matte kraft + soft-touch, embossed foil, spot UV |
| 35–55% | standard | coated white board, satin varnish, single-hit foil |
| < 35% | value | uncoated kraft, one-colour flexo |

Missing cost or price → `tier="unknown"` + `pricing_unknown` blocker (**never a zero**). Lifestyle on
a value-margin product is refused as `lifestyle_over_budget`. `prompt_suffix()` appends the
substrate/finish/lighting clause to every render prompt, so a value product cannot silently get a
foil finish. Keywords are normalised, de-duplicated and capped at 20.

### 3.2 Listing Forge hand-off

`asset_handoff.handoff(brief, assets)` → hero URL, hero aspect, secondary images ordered by role,
keywords, alt text. It **refuses** a hero that is not pure-white (`hero_not_pure_white`) or not
square (`hero_not_square`), drops assets without a URL, caps secondary at 6, and propagates the
brief's blockers so a pricing-unknown product cannot become a listing draft.

### 3.3 Brand memory — proposals only

`brand_memory.extract()` pulls validated hex colours, heading/body fonts, logo ref + placement and up
to 10 winning prompts. `propose()` returns a document whose status is **always `"proposed"`**; it
writes nothing unless an operator-approved `store` is injected, and a failing store is reported
(`persisted: false`, reason) rather than swallowed. There is no code path that returns `"applied"` —
the revision gate is intact.

## Verification

| Suite | Assertions |
|---|---|
| `test_aplus_layout.py` | 13 |
| `test_listing_image.py` | 7 |
| `test_render_bind.py` | 18 |
| `test_asset_handoff.py` | 11 |
| `test_brand_memory.py` | 13 |
| **pytest total** | **62 passed** |
| `aplusMetrics.test.js` (parity) | 5 |
| **UI total** | **63 passed** + 11 contrast pairs |

## Honest limits

1. **Nothing is mounted in a route yet.** The A+ components exist, are parity-tested and build
   clean, but no Design Studio page imports them. Wiring them into a page is an Import away and a
   review of that page's layout — not done here.
2. **Dieline and 3D projection (Phase 1.2) not advanced.** `design_studio_print.py` already emits
   SVG/PDF dielines with fold lines and bleed; mapping renders onto 3D geometry templates is a
   separate build (projection matrices + a mesh path) and was not attempted.
3. **Lifestyle ingestion (Phase 1.3, second half) is only the environment selector.** `bind()` maps a
   buyer room to `lifestyle-kitchen` etc.; the prompt composition and the Memory Bank read are
   wired at the function level, not in a live render call.
4. **No render was produced.** These modules are pure; the first FLUX 3 pass still needs
   `tools/start_comfyui.ps1 --cache-none` and the gateway on `:8190`.
5. **`hardware_guard` is not called by these modules.** Batch rendering is where it belongs; the
   A+ and hero paths are single-image and have no batch to step down.
