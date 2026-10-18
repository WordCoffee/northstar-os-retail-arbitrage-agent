# MOGRA bag series 2 — the real logo ETCHED into the bag (5 new bag-only designs)

_2026-10-18 · bag-only series, all-new concepts, real logo on every view_

## Summary
Five brand-new bag concepts built around the operator's **real logo** (the 4×
refined master), rendered **etched into the material** — a tone-on-tone blind
deboss with a lit/shadow bevel cut from the logo's own silhouette, so it reads
as stamped into the bag, not printed on it. In the mockups the print-integration
engine bakes the pouch's folds and studio light straight through the etching.

## Concepts (bags only)
| Key | Ground | Treatment |
|---|---|---|
| b06_etched_heritage | ivory | double gold frame; the full real lockup (mortar + EST 2023 + MOGRA ORGANICS + tagline) etched large as the hero; Anton headline, engraved mushroom, cert row, forest capsule |
| b07_etched_noir | near-black | the real lockup ghost-etched into the matte black (tonal relief); cream wordmark + gold rule at the top; white Anton headline; gold capsule |
| b08_foil_monogram | cream | the real mortar-and-pestle mark as a **raised gold foil** (emboss: light upper-left, shadow lower-right); real wordmark beneath; capsule |
| b09_kraft_plate | kraft | printed cream label plate on the natural bag carrying the **etched lockup**; structured type, engraved mushroom, capsule, kraft footer line |
| b10_botanical_spine | deep sage | etched lockup at the head; vertical spine lettering both edges; Anton headline; engraved mushroom; capsule |

Backs (all five): the shared complete regulated back — real wordmark + organic
seal, big headline, Supplement Facts, free-of, suggested use, warning, lot/best,
QR + real UPC-A on the white code panel. Placeholder register unchanged.

## Implementation
- `package_designs.etch_logo(logo, base, rim_hi, rim_lo, tint, offset_mm, softness)` —
  a real **embossed stamp**: the logo's own artwork is remapped into a tone ramp
  (`base` = dark/light tones) so every internal detail — the mortar line work,
  the wordmark letterforms, the tagline, the leaf greens (via `tint`) — stays
  visible; the silhouette mask then drives an outer bevel (lit upper-left rim,
  shaded lower-right rim) plus inner-edge shading, so the mark reads raised.
  The ink mask is keyed from the flat logo file's darkness (and respects an
  existing alpha channel), so the operator file works as-is.
- `package_designs.paste_w()` — scale-and-centre helper for RGBA blocks.
- Both runners gained subset flags: `--only <keys>` + `--pack <name>`
  (mockups also `--designs <folder>`), so series can be exported alone.

## Sharpness pass (v2)
Reported as "blurry and grainy" on the first emboss renders — fixed at the
source:
- **2× compositing**: plates load through `mockup_engine.load_plate(scale=2)`
  (Lanczos + anchors scaled), so the printed artwork is drawn at 2048 and the
  mockups export at 2048 — print/typography crispness doubles.
- **Filtered art pre-scale** (`_prescale`): artwork is Lanczos-resized to ~the
  on-screen size before sampling, removing the softening of point-sampled
  bilinear downscaling (displacement stays physically constant).
- **Grain removed**: `apply_paper` noise cut to a barely-there 0.7/255 (was
  1.9) + mottle 0.05 (was 0.14).
- **Tighter bevels**: emboss softness 0.22-0.28 mm → 0.13-0.15 mm, with darker
  base ramps so the logo reads as a real, defined brand mark on the pack.

Run with sharpness: append `--scale 2` to the mockup runner.

## Outputs
- Flat art 300 dpi (+ paper grain): `exports/mogra-bags2-designs-20261018/designs/b06..b10/{front,back}.png`
- Shelf mockups 2048² (printed-into-the-bag engine): `exports/mogra-bags2-shelf-mockups-20261018/`
  (`contact_sheet.png` = all 5 × front + back)

## Commands
```
python export_mogra_designs.py --only b06_etched_heritage,... --pack mogra-bags2-designs-20261018
python export_mogra_shelf_mockups.py --only b06_etched_heritage,... --pack mogra-bags2-shelf-mockups-20261018 --designs ../exports/mogra-bags2-designs-20261018/designs
```
