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
- `package_designs.etch_logo(logo, tone, hi, lo, offset_mm, softness, mode)` —
  keys the ink mask from the flat logo file's darkness (and respects existing
  alpha), stacks shadow/highlight copies of the silhouette offset ~0.45 mm
  (deboss) or reversed (emboss), then the base tone on top.
- `package_designs.paste_w()` — scale-and-centre helper for RGBA blocks.
- Both runners gained subset flags: `--only <keys>` + `--pack <name>`
  (mockups also `--designs <folder>`), so series can be exported alone.

## Outputs
- Flat art 300 dpi (+ paper grain): `exports/mogra-bags2-designs-20261018/designs/b06..b10/{front,back}.png`
- Shelf mockups (printed-into-the-bag engine): `exports/mogra-bags2-shelf-mockups-20261018/`
  (`contact_sheet.png` = all 5 × front + back)

## Commands
```
python export_mogra_designs.py --only b06_etched_heritage,... --pack mogra-bags2-designs-20261018
python export_mogra_shelf_mockups.py --only b06_etched_heritage,... --pack mogra-bags2-shelf-mockups-20261018 --designs ../exports/mogra-bags2-designs-20261018/designs
```
