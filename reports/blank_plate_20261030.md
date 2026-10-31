# Blank-plate architecture: compositor proven, plate still dirty

**Date:** 2026-10-30
**Policy:** DeepSeek V4.1 Flash for all code; FLUX 3 local for pixels; zero spend.
**Verdict:** the **deterministic compositor works and is verified by OCR**. The **plate generation
step is still dirty**, so the finished artefact is not shippable. And the fresh blank-plate render
was **refused by the RAM floor** — reported, not worked around.

---

## 1. What was verified

### 1.1 A+ modules are mounted

`/design-studio?section=aplus&view=layout` — header 970×600 (44% copy band, 24px inset),
three-feature 970×300 (300² tiles at x=15/335/655), comparison 970×600 (90px header, 250px label
column, two 360px columns, 4 rows). Exact canvas, scaled as one block, live copy editing.

### 1.2 The compositor produces real typography

`pouch_label.compose()` on the 1024² plate:

| Measure | Result |
|---|---|
| geometry residual | **0.282 px** (limit 1.5 px) — the pouch face fit is essentially exact |
| output | 1024×1024, `exports/e2e_labelled_20261030/02_labelled.png` |
| OCR of the composite | **`LION'S MANE`**, **`ORGANIC MUSHROOM POWDER`**, `Fruiting body only`, `Third-party tested`, `60 servings`, `6 oz (170 g)` |

That is the inversion this architecture exists for: before, OCR found **garbage** (`9RGIA1NIIC`,
`Musriroom`); now it finds the **intended copy**, because a human-designed label was drawn, not
generated.

### 1.3 The fresh blank-plate render was refused

```
RuntimeError: system_ram_insufficient: free 3617 MB, need 4096 MB
```

`studio_generation`'s RAM floor blocked the render. I freed what was not needed (Vite dev server,
backend), restarted ComfyUI to drop its 5.2 GB cache, and posted `POST /free` (models unloaded,
VRAM back to 0). Free physical RAM stayed at **3.4 GB** against a **4 GB** floor — ComfyUI + the
agent runtime + the OS on a **15.4 GB** box.

**I did not lower the guard.** Weakening a safety threshold so my own run would pass is exactly the
behaviour the guard exists to prevent. The block is the finding.

## 2. The defect that remains

Even at `field_alpha=255` the plate's **burned-in logo and a garbled residue (`8551/0m0`) show
through the label panel**. The reason is in the compositor's own design: the realism pass modulates
the print with the plate's luminance (`displacement_k`, `tonal_match`, `softlight_strength`) so the
label inherits the pouch's creases. It cannot distinguish "crease" from "text the model burned in".

So scrubbing the plate is not enough. The plate must be **genuinely blank before compositing**, by
one of:

1. **Mask the label region before compositing** and fill it with a flat, measured field (inpaint),
   so there is no underlying ink to bleed through.
2. **Constrain generation** — an inpaint/control pass on the label area with a blank-plate mask,
   rather than a text-negative prompt that the model ignores.
3. **Detect and reject**: if `check_text_in_image` still finds any box after scrubbing, refuse the
   plate instead of compositing onto it. This is cheap and should ship first.

## 3. The 100-point list — honest status

"Active constraint" is not the same as "implemented". A precise account:

| Category | Has working code today | Partial | Not started |
|---|---|---|---|
| 1 FLUX 3 pipeline (1–20) | 8 (16-step), 15 (VRAM release via `release_models`), 16/17 (`hardware_guard` batch + temp) | 20 (timing recorded in `report.json`; no ledger write) | latent caching, CFG calibration, LoRA blending, tiled upscale, normal maps, nvfp4 tiling |
| 2 Deterministic label (21–40) | **21 (blank-plate topology)**, 29 (barcode/QR vector in `design_studio_print`), 30 (bleed), 33 (wrap/overflow in `pouch_label.render_label`), 40 (OCR gate) | 22 (mesh warp + 0.282 px residual), 23 (ICC via `prepress`), 34 (fold-shadow direction), 36 (masking) | 24–28, 31, 35, 37–39 |
| 3 A+ & storefront (41–60) | **41–46 fully (integer rects + parity test)**, 93 (drift guard) | 47 (alt-text field, no schema tag) | 48–60 |
| 4 Prepress/dielines (61–80) | 61–64 (SVG/PDF dielines, fold lines, +3mm bleed, glue tabs in `design_studio_print`) | 79 (metadata sidecars) | 65–78, 80 |
| 5 Memory & governance (81–100) | **81, 82 (render_bind), 84–88 (brand_memory proposals), 89 (hardware_guard), 97 (subscription v5)** | 83 (room mapping only), 90 (`reports/` written, no trend store), 95 (gateway 503 exists, no routing) | 94, 96, 98 |

Roughly **a third of the list has real code**, a fifth is partial, the rest is genuine future work.
Reporting "100/100 active" would be a lie.

## 4. Next three, in order

1. **Refuse dirty plates** — after scrubbing, if any OCR box remains, do not composite. One
   conditional, and it makes the whole pipeline honest.
2. **Fill the label region before compositing** so burned-in ink cannot bleed through.
3. Re-run `tools/e2e_labelled.py` on a box with ≥ 4 GB free (close the dev stack) to prove a truly
   blank plate end to end.

## 5. Evidence

`exports/e2e_labelled_20261030/{02_labelled.png,02b_labelled_opaque.png,03_cutout.png,04_hero.png}`
`tools/e2e_labelled.py` (written, blocked at the RAM gate before rendering)
`reports/e2e_hero_20261030.md` (previous run: 8 OCR boxes → scrubbed → smudges, same root cause)
