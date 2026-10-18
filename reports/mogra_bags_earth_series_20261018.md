# MOGRA earth-tone bag collection — 10 designs, one folder

_2026-10-18 · bags only · new front logo/print · About Us + real logo on every back_

## What was built
Ten new, distinctly styled bag designs in natural, earth-focused tones (premium,
restrained — no novelty effects), each with:
- the **new MOGRA ORGANICS front logo/print** (drawn fresh: Playfair serif
  MOGRA + tracked ORGANICS + hand-drawn two-leaf sprig; three variants —
  stacked, single-line, ringed badge — placed per design),
- product title + tracked descriptor + engraved lion's mane motif,
- the 3-cell value capsule (5 g per serving / 170 g / 34 servings),
- a complete rear label (Supplement Facts with values, free-of, suggested use
  with scale/settling note, storage, warning/FDA block, lot/best, distributed-by,
  certifier line, QR + real UPC-A + item code) — **plus a new ABOUT US section
  with the real MOGRA ORGANICS logo above it** (tinted to each ground so it
  reads on dark bags).

## The 10 styles
| Key | Ground | Character |
|---|---|---|
| e01_stone_heritage | warm stone | hairline double frame, classic symmetry |
| e02_moss_arc | deep moss | linen half-moon arch carrying the lockup |
| e03_clay_bands | soft clay | linen top band + deep moss footer band |
| e04_sand_hero | pale sand | oversized lockup as the hero |
| e05_bark_editorial | soft charcoal | left-aligned editorial grid, copper rules |
| e06_olive_badge | deep olive | ringed badge lockup |
| e07_oat_split | creamy oat | moss footer block, espresso type |
| e08_slate_formal | blue slate | fine cream frame, copper capsule |
| e09_taupe_watermark | mushroom taupe | tonal engraved watermark behind the type |
| e10_kelp_luxe | deep kelp | copper hairline frame, generous whitespace |

## One folder (fast review)
`exports/mogra-bags-earth-20261018/` — flat, no per-design subfolders:
- `<key>_front.png` / `<key>_back.png` — print art, 300 dpi
- `<key>_shelf_front.png` / `<key>_shelf_back.png` — photoreal mockups, 2048²
- `contact_sheet.png` (flat art, 10 × front + back) · `contact_sheet_mockups.png`
- `BACK_LABEL_REQUIREMENTS.md` (placeholder values to certify), `README.md`, `logo/`

## Commands
```
python export_mogra_designs.py --only e01_...,e10_... --pack mogra-bags-earth-20261018 --flat
python export_mogra_shelf_mockups.py --only e01_...,e10_... --pack mogra-bags-earth-20261018 \
    --designs ../exports/mogra-bags-earth-20261018 --scale 2 --flat
```

## Fixed during review
`dome()` semantics (flat edge sits at `base_y - r`): e02's arch originally landed
at the bag top; corrected to the upper-third half-moon.
