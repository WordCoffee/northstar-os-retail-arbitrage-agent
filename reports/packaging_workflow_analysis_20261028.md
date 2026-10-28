# 1.1 — LABEL COMPOSITING (TY CORE)
## Phase 2 research deliverable — REA program

**Date:** 2026-10-28
**Scope:** reverse-engineer best-in-class packaging mockup workflows, quantify the
gap against `pouch_label.py` + `mockup_compositor.py`, recommend the compositing
change with the best quality-per-line-of-code.
**Method:** code inventory (this repo) + published manual workflows + one local
ground-truth experiment run on this machine (`tools/rea_warp_probe.py`).
**Spend:** 0. **Amazon contact:** 0. **New dependencies:** 0.

All numbers below are reproduced by `python tools/rea_warp_probe.py`, which
writes `reports/rea_probe/warp_probe.json`.

---

## 1. Current pipeline, as built

Read from source. Every step names where it lives today.

| # | Step | Where | Automatic? |
|---|---|---|---|
| 1 | Background estimate: outer-ring median of the plate | `pouch_label.py:54 _background_colour` | auto |
| 2 | Foreground mask: colour distance from background, threshold 26, HSV saturation gate, morphological close/open, largest component by area, flood fill | `pouch_label.py:67 _foreground_mask` | auto |
| 3 | Per-side edge fit → trapezoid (least-squares), then inset off the weld | `pouch_label.py` (row extents + inset; see `_row_extents` at :167) | auto |
| 4 | Label panel artwork drawn at `PANEL_SIZE = 900×1200` with cream stock / pine ink / engraved gold, cert icons drawn as vectors | `pouch_label.py:42-46` | auto |
| 5 | **4-point homography** panel→quad, bilinear sampling, optional luminance displacement, soft-light shading, capped specular, grain sync, tonal match | `mockup_compositor.py:274 warp_panel`, `:263 _homography` | auto |
| 6 | Feathered erase of pre-existing glyph zones, then re-compose | `mockup_compositor.py:112 erase_circle`, `:137 erase_rect` | auto |
| 7 | OCR gate: any surviving text on the plate fails the render | `text_fidelity.py` | auto |
| 8 | Prepress check: max TAC vs 300, dE76 > 8 share | `prepress.py` | auto |

**The gap in one sentence:** steps 1–2 are strong (measurement from the plate),
step 5 is geometrically *first-order only*, and there is **no step that lets an
operator nudge the fit** — the only dial is `shading`.

---

## 2. What the manual workflow actually does

Harvested from published workflows (Sources §7). The professional sequence is
consistent across all four sources:

| # | Manual step | Observed detail | Our equivalent |
|---|---|---|---|
| A | Convert artwork to a **Smart Object** so the fit survives edits | Photoshop smart object / "Replace Content" | **partial** — compose presets are reusable per plate (`data/compose_presets.json`) but the panel is redrawn per run, not held as a swappable object |
| B | Place + scale the art over the object | free transform, measure width/height with the line tool | **have** — measured quad |
| C | **Warp** to the surface: `Arch` preset for a bottle/cylinder, grid warp for a bag | "drag the center handle until the curve matches" | **missing** — homography only (no curve) |
| D | Duplicate the product layer, **desaturate**, blend to pick up shading | multiply / soft-light; some use a gradient overlay | **have** — soft-light shading + specular + tonal match |
| E | Mask the art to the object edge | layer mask | **have** — measured mask, feathered |
| F | Manual adjustment: fill/opacity tweak while warping, then reset | "lower the layer fill … then press Enter and reset fill to 100%" | **have** — `shading` dial |
| G | If the surface is genuinely 3D, use a 3D model + material instead of a 2D warp | Adobe Dimension / Blender | **not needed yet** — see §4 |

Two things stand out:

1. **Curvature is the step every human performs and we skip.** Every source
   reaches for warp before shading, because a flat panel on a curved object
   reads as a sticker even when the lighting is perfect.
2. **The human's warp is also a hand-fit against the actual edge**, which is
   why their results do not show the fringe we measured in §5.

---

## 3. Hard measurement: how wrong is a 4-point homography?

Ground truth: a cylindrical pouch face (radius 300 px, 51.6° arc, f = 1000 px,
900×1100 px photo) rendered by exact inverse mapping, so the true mapping is
known analytically. 1,813 panel sample points, error measured in **destination
pixels** against that truth.

| Method | mean px | p95 px | max px | mean % of photo width |
|---|---|---|---|---|
| **4-point homography (shipped today)** | **5.413** | **11.437** | **13.324** | 0.60 % |
| quad mesh 3×4 | 2.673 | 4.381 | 4.834 | 0.30 % |
| quad mesh 5×7 | 0.676 | 1.360 | 1.493 | 0.075 % |
| quad mesh 9×13 | 0.171 | 0.367 | 0.405 | 0.019 % |
| quad mesh 17×25 | 0.043 | 0.092 | 0.099 | 0.005 % |
| analytic cylinder (exact parameters) | 0.000 | 0.000 | 0.000 | 0 % |

Where the homography hurts: **inner 30 % of the panel 3.98 px mean, outer 30 %
6.73 px mean**. The error is not uniform — it is worst along the mid-edges,
which is exactly where a pouch face is most curved and where a weld seam sits.

Reading it operationally: at 5.4 px mean on a 900 px photo, a 2 px keyline
shifts by more than two of its own widths. That is the difference between "the
label is on the bag" and "the label is printed on the bag".

**A 5×7 mesh captures 87 % of the available improvement** (5.413 → 0.676 px) for
a small, dependency-free change: `cv2.remap` is already available (OpenCV 5.0.0
in the backend Python), and a quad mesh is just two float32 maps.

> Nuance: `warp_panel(..., maps=...)` already applies a *luminance displacement*
> pass (`compositor_realism.displacement_shift`, `mockup_compositor.py:302-314`).
> That moves ink with the surface's texture, but it does not correct geometry —
> the error in this table is measured on the geometric base warp, which is what
> decides whether the panel edge lands on the physical edge.

---

## 4. Technique comparison (what to adopt)

| Technique | Library / licence | GPU | Fits this box | Measured or stated quality | Verdict |
|---|---|---|---|---|---|
| 4-point homography | our own (`mockup_compositor._homography`), no dependency | no | yes | **5.41 px mean** (measured) | keep as the outer bound only |
| Piecewise-affine / bilinear **quad mesh** via `cv2.remap` | OpenCV (Apache-2.0), already installed | no | yes | **0.68 px mean at 5×7** (measured) | **adopt** |
| Analytic cylinder | our own math | no | yes | 0.00 px when parameters are exact; parameters need estimating | use only as a validation ceiling, not as the shipping path |
| Blender mesh deform + render | Blender (GPL), heavy | yes | possible, costly (RAM-bound box, `--cache-none` precedent) | unmeasured here | **defer** — no evidence it beats a 5×7 mesh for a 2D composite |
| Smart-object template (reusable per-plate preset) | our own | no | yes | n/a | adopt as a *workflow* improvement, not a warp change |

**Recommendation:** add a `mesh` warp mode to `warp_panel` — a `NxM` node grid
(5×7 default) with bilinear sampling through the same displacement/shading
chain. Keep the homography as the fallback when fewer than 4 reliable edge
points are found. Do **not** add Blender.

---

## 5. Where the halo actually comes from (the assumption was wrong)

The plan assumed the visible edge halo came from the feathered erase radius.
Measured on the same ground-truth face, sweeping **quad overshoot** and
**feather sigma** independently, sampling the 3 px band just outside the true
edge (scene background 40/255, panel 240/255, so panel contrast = 200):

| Quad overshoot | Feather σ | Bleed outside true edge | % of panel contrast |
|---|---|---|---|
| 0 px | 0 | 0.000 | 0 % |
| 0 px | 2 | 0.000 | 0 % |
| 0 px | 8 | 0.000 | 0 % |
| **1 px** | 0 | **57.013** | **28.5 %** |
| 1 px | 2 | 35.633 | 17.8 % |
| 1 px | 8 | 31.409 | 15.7 % |
| **3 px** | 0 | **190.492** | **95.3 %** |
| 3 px | 2 | 145.415 | 72.7 % |
| 3 px | 8 | 110.073 | 55.0 % |

**Finding (contradicts the plan's assumption):** feathering creates **zero**
bleed on its own. Feathering only *smears* a bleed that the geometry already
created — it lowers the peak (57 → 31 lum) while widening it into a soft halo,
which is why a feathered overshoot reads as a haze rather than a hard edge.
The single-pixel geometric overshoot is worth **28 % of the panel's contrast**.

Therefore the fix is not a smaller feather. It is **sub-pixel edge fit**:
the measured quad must land inside the physical face by a fraction of a pixel,
and the feather should be *derived* from the measured edge confidence, not a
constant.

---

## 6. OCR legibility floor (clean synthetic art)

`rapidocr` (the engine behind `text_fidelity.py`) on clean rendered art:

| Font size | Detected | Recognised |
|---|---|---|
| 10 px | yes | `ORGANIC LIONS MANE` (correct) |
| 12–18 px | yes | `ORGANICLIONSMANE` (spaces merged) |
| 20–24 px | yes | `ORGANIC LIONS MANE` (correct) |
| 28–32 px | yes | truncated — **artefact of the 760 px test canvas, not an OCR failure** |

**Reading:** on clean, high-contrast art the OCR gate is not the binding
constraint even at 10 px cap height. The gate fails on *photographic* panels
because the text has been resampled onto a curved, lit surface — which is the
same geometry problem measured in §3. So the OCR gate will improve as a
side-effect of the mesh fix, without touching `text_fidelity.py`.

`UNVERIFIED`: OCR on a real composited plate at final print size was not
re-measured in this run (needs a live render; the last recorded plate check is
`creative_readiness_20261022`).

---

## 7. Sources

| Source | What it gave | Pulled |
|---|---|---|
| [Photoshop Training Channel — place a logo onto a bottle](https://photoshoptrainingchannel.com/place-a-logo-onto-a-bottle-in-photoshop) | smart object → warp Arch → drag centre handle → duplicate/desaturate product for shading | 2026-10-28 |
| [Mockey — packaging mockup in Photoshop, 7 steps](https://mockey.ai/blog/how-to-make-packaging-mockup-in-photoshop/) | measure with line tool → rectangle → smart object → warp to match → mask → dupe product layer → effects | 2026-10-28 |
| [Adobe Help — warp a layer with cylindrical transform](https://helpx.adobe.com/photoshop/desktop/effects-filters/artistic-stylize-filters/warp-a-layer-wth-cylindrical-transform.html) | cylindrical warp is the packaging-specific tool; states its purpose is labels on bottles/cans | 2026-10-28 |
| [Adobe Help — print mockup walkthrough](https://helpx.adobe.com/th_th/photoshop/how-to/make-print-mockup.html) | Transform→Distort to corners, then Gradient Overlay for the surface shadow | 2026-10-28 |
| [Adobe Community — perspective mockup](https://community.adobe.com/questions-712/how-to-mockup-perspective-magazine-1085322) | the 2D path is warp + multiply; the 3D path needs a model and a material | 2026-10-28 |
| [OpenCV 4.13 — geometric transformations](https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html) | `remap` with `INTER_CUBIC` and `BORDER_TRANSPARENT`; confirms mesh resampling is a first-class primitive | 2026-10-28 |
| `tools/rea_warp_probe.py` (this repo) | every number in §3, §5, §6 | 2026-10-28 |

---

## 8. BUILD CANDIDATES

| id | component | change | evidence (report §) | effort | risk | gate |
|---|---|---|---|---|---|---|
| L1 | `mockup_compositor.warp_panel` | add `mode="mesh"` 5×7 quad mesh via `cv2.remap` (cubic, border-transparent), keep homography fallback | §3: 5.413 → 0.676 px mean | 1–2 h | low; additive, existing callers unaffected | none |
| L2 | `pouch_label` edge fit | sub-pixel refinement of the four side fits; report per-side residual px, refuse to compose when residual > 1.5 px | §5: 1 px overshoot = 28 % contrast bleed | 3–4 h | medium; needs the residual threshold tuned on real plates | none |
| L3 | `mockup_compositor` erase/compose | derive feather σ from measured edge residual instead of the constant (26.0 in `erase_rect`, similar in the panel mask) | §5: feather does not create bleed, it only smears it | 1 h | low | none |
| L4 | Compose presets | store the measured quad *and* its residual so a reprocess reuses a sub-pixel fit ("smart object" equivalent) | §2 step A/D | 2 h | low | none |
| L5 | `text_fidelity` | after L1, re-baseline the OCR gate on composited plates (expected improvement; do not weaken the gate) | §6 | 1 h | low | none |

**Rejected:** Blender mesh deform (no measured advantage, heavy on a RAM-bound
box); any commercial mockup API (spend gate, and the geometry problem is solved
locally).

## 9. UNVERIFIED

- Blender mesh deform quality on this box — not run (deliberate: no evidence it
  beats a mesh at this arc angle).
- Real-plate behaviour of the 5×7 mesh: the probe uses a synthetic cylinder. A
  pouch face is not a perfect cylinder (gussets, weld, taper), so the first
  build step must re-run this probe's metric on an operator plate with a known
  quad.
- Edge confidence → feather mapping: the 1 px/3 px sweep is two points, not a
  fitted curve.
