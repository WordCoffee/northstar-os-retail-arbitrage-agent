# MOGRA Lion's Mane 6 oz — brand-new design series (manufacturer bag #2)

_2026-10-18 · 10 designs · 100% new elements except the logo · one folder_

## Manufacturer fit check (their size sheet, image 1)
| Product | Mfr size | Face | Usable bulk (filled) | Needed @ ~0.5 g/cm3 | Verdict |
|---|---|---|---|---|---|
| Lion's Mane 6 oz (170 g) | ② **130×210+40** | 130×210 mm | ≈ 740 cm³ | ≈ 340 cm³ (~46% fill) | **fits comfortably** — and it is exactly the canvas our artwork is built on (130×210 mm printed face; +40 = bottom gusset, outside the print) |
| Shiitake 8 oz (227 g) | ③ **140×200+40** | 140×200 mm | ≈ 750 cm³ | ≈ 455 cm³ (~60% fill) | **fits**; if the powder is extra fluffy or the co-packer wants more headroom, size ④ 150×210+40 gives the same 1,764-class order flexibility |

MOQ counts (1,764 / 441) are ordering quantities, not design constraints.

## What was built
Ten **completely new** bag designs for Lion's Mane 6 oz on the 130×210 mm face.
No element of any previous series is reused — new type system (Cormorant
Garamond + Jost), new palettes, new ornaments, new facts presentation
(hairline colophon instead of the capsule bar), new print-lockup usage.
**Only the brand logo carries over**, and it now lives on the back with a new
**ABOUT LION'S MANE** section (replacing About Us), per instruction.

| Key | Ground | Device |
|---|---|---|
| f01_porcelain_type | porcelain | Cormorant title-case + one small engraving |
| f02_cedar_seal | deep cedar | circular seal hero: arc-text ring + "170 g" centre + inner arc |
| f03_linen_ledger | oat | spec ledger — hairline rows (ingredient / part / texture / serving / origin) |
| f04_wheat_minimal | wheat | one enormous Cormorant italic line + negative space |
| f05_pistachio_contour | pistachio | topographic contour field |
| f06_porcelain_tile | porcelain | single deep tile block carrying the content |
| f07_rose_wreath | dusty rose | drawn wreath ring with sprigs at the gaps |
| f08_granite_stack | granite | huge three-line display stack |
| f09_plum_prescription | deep plum | single-hairline label box + ruled utility rows |
| f10_ice_botanical | porcelain | engraved botanical at hero scale |

## Backs
Complete regulated label (Supplement Facts with values, free-of, suggested use
with milligram-scale note, storage, warning/FDA block, lot/best, distributed by,
certifier line, item code, QR + real UPC-A) **plus ABOUT LION'S MANE with the
real logo directly above the copy** — tinted to each back's ink so it reads on
dark grounds.

## One folder
`exports/mogra-lionsmane-6oz-20261018/`
- `<name>_front.png` / `<name>_back.png` — print art 300 dpi
- `<name>_shelf_front.png` / `<name>_shelf_back.png` — photoreal mockups 2048²
- `contact_sheet.png` · `contact_sheet_mockups.png` · `BACK_LABEL_REQUIREMENTS.md` · `logo/`

## Fixed / hardened during this build
- `arc_text` seal: radians/degrees bug (glyphs stacked) and the bottom arc
  (flip) now moves position as well as rotation — bottom text reads upright.
- `dome()` base-edge semantics corrected for the e-series arch (earlier).
- Print engine made memory-lean (float32, row-chunked sampling + compositing)
  after transient allocation failures under system memory pressure.
