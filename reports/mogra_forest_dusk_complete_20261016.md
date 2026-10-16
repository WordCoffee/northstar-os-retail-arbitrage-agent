# MOGRA — complete front panel composited onto the studio render (2026-10-16)

## Deliverable

- **`renders/mogra-forest-dusk-mockup-complete.png`** — the complete package:
  both pouches fully dressed (1216×832)
- `renders/mogra-forest-dusk-mockup-complete.json` — machine record of the composite
- Base plate (letter-free): `renders/mogra-forest-dusk-mockup.png`
- Compositor: `scripts/compose_mogra_complete.py` (deterministic, re-runnable)

## Why (operator feedback)

The first deliverable was the text-safe plate — clean art with no lettering.
Operator: *"looks nothing like a complete package."* Correct — and the old
packaging (supplied in `C:\Users\T2Hol\Desktop\Mogra Organics`) is the bar: the
real logo, the real type, the full front panel. This build closes that gap.

## What's on the pouches now (brand-exact)

| Element | Source |
|---|---|
| Logo lockup printed directly — mortar & pestle, two leaves, EST 2023, wordmark, tagline (no disc, no sticker shadow) | **the real logo file** — mark band as raster (alpha fattened), wordmark set in Playfair Display 700 (matches the Didone), tagline from the real raster; all in one cream print (`Northstar_backend/assets/brand/mogra_logo.png`) |
| `ORGANIC LION'S MANE` / `ORGANIC SHIITAKE` | Playfair Display 700 (closest to the canister wordmark among available faces) |
| `MUSHROOM POWDER` | Inter, tracked caps |
| Engraved mushroom art (lion's mane / shiitake cluster) | **the model's own art, untouched** — kept at native resolution |
| 4 certification roundels (USDA Organic · Non-GMO · Gluten-Free · Fruiting Body) | drawn glyphs, discs seated exactly on the model's dot row with soft shadows |
| `6 oz (170 g)` / `8 oz (227 g)` + gold rules | typography; muted gold #C4A04A (LM) / warmer #D69E3E (SHI) |
| Palette | cream #F3EAD6, badge ivory #F5EEE2 on the matte grounds |

## How (deterministic compositor, same code path for any SKU)

1. **Heal** — only the model's old badge is removed: per-region median prefill
   → 420-iteration diffusion fill (boundary-exact) → native film-grain
   re-injection. Lesson: fewer iterations under-converge and leave visible
   patches; the face's shading gradient must be carried by the fill.
2. **Panel** — authored at 2.5× render scale in layered form (real logo bands,
   real fonts), soft-blurred once for the warp downsample.
3. **Warp** — exact 4-point homography per face; alpha composite.
4. **Lighting** — the print takes the face's own luminance falloff so the panel
   sits IN the photography, not on it.

## Iterations of note (kept honest)

- Re-pasting the model's art at scaled size destroyed its fine linework in the
  first builds → final design keeps the art 100% untouched; the text stack was
  re-fitted ABOVE it instead.
- The dot row is NOT healed — roundels are placed exactly on the model's dot
  centres (measured: bag1 x 307/346/386/425, bag2 x 790/830/870/910, y 655).

## Reproduce

```
python scripts/compose_mogra_complete.py            # writes the complete PNG
python scripts/render_mogra_forest_dusk.py          # re-renders the base plate
```

## P0 realism update — compositor v2 (2026-10-16, post deep-dive)

The compositor now runs the industry-standard realism passes
(`warp_panel` v2, constants recorded in the sidecar):

1. **Luminance displacement** — the print's sample point shifts with the
   surface's blurred luminance so ink rides the material (max 3 render px).
2. **Print-grain sync** — the pouch's own high-pass grain, keyed to ink alpha.
3. **Soft-light shading + specular** — the print takes the face's luminance
   falloff; the film's sheen screens over the ink on bright zones.

Deferred honestly: the printed-**patch** AO rim / seam (report step 4) — our
design is scattered type + art, and an edge rim would outline glyphs instead of
grounding a label patch. Displacement + shading are the grounding here.

**Evidence (in `renders/`):** `_ab_full.png` (before/after, full frame),
`_ab_crop.png` (100% print zone — the lion's mane art visibly sits in the light
now), baseline preserved as `mogra-forest-dusk-mockup-complete-v1.png`.
Parameters: DISP_K 3.0 px · soft-light 0.9 (floor 0.28) · specular cap 0.32 ·
grain ±measured.

## Next steps (to make this print-real)

- Back panel document (description, Supplement Facts reserved zone, QR/UPC
  reserved zone, storage/distributed-by) per BRIEF §5.
- `amz-main` 2000×2000 export of the dressed front (bare pouch, white bg) —
  the current hero is a secondary/A+ asset, not a MAIN image.
- Vector text layer for prepress handoff (Lane C) — this compositor is
  presentation-grade, not print-grade.
