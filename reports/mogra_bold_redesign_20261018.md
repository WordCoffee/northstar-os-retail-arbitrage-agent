# MOGRA bold redesign — 10 concepts × front + back (shelf mockups)

_2026-10-18 · design lane · benchmark: bulk-supplement brand grade (user reference)_

## What changed
The v1 concept set was judged "boring". The whole line was redesigned to the
information-dense, display-bold benchmark the operator supplied (huge condensed
headlines, value bar, seal, hero botanical, fully structured two-column backs).

### New shared blocks (`Northstar_backend/package_designs.py`)
- **Anton display font** (`assets/fonts/Anton.ttf`, Google Fonts OFL) for all
  headlines — condensed, stackable, shelf-bold. Playfair stays for the brand logo.
- `headline()` — fitted Anton stacks (auto-shrink to column width).
- `value_capsule()` — 3-cell fact bar: **5 g PER SERVING / 170 g WEIGHT / 34 SERVINGS**.
- `organic_seal()` — own-design "ORGANIC CERTIFIED" roundel (placeholder mark;
  actual certifier name/number required — see register).
- `frame()`, `dome()`, `monogram()`, `wordmark()`, `vtext()`, `rot_paste()`.

### 10 redesigned fronts (all use the real 4× logo master)
| # | key | treatment |
|---|-----|-----------|
| 01 | forest_bold | full forest ground, gold frame, cream band w/ wordmark, 15 mm Anton headline, gold capsule |
| 02 | sticker_fun | tilted forest sticker on cream, white logo disc, capsule inside sticker, motif cascade |
| 03 | midnight_luxe | near-black ground, double gold frame, gold-recoloured motif, gold capsule |
| 04 | kilim_arch | big forest arch w/ gold scallop foot, type inside arch, motif below |
| 05 | split_duo | forest/cream vertical split, rotated display type, side badge column |
| 06 | wall_of_type | kraft tube, stacked Anton wall, icon row, forest capsule |
| 07 | dome_gold | forest tube, gold dome w/ real monogram, cream motif, gold capsule |
| 08 | stamp_roll | perforated rotated stamp roundel, monogram + type inside |
| 09 | edge_stripe | forest+gold edge stripes at wrap-safe arc, cream centre column |
| 10 | concentric | forest disc w/ concentric rings, logo roundel centre |

### Backs — `render_back()` v3 (Bulk-grade regulatory layout, all filled)
- Top: real wordmark + organic seal.
- Huge 2-line Anton headline; net quantity `170 g (6.0 oz)`.
- Bags: **two columns** — left: complete Supplement Facts (white panel) +
  Other Ingredients: None + Color May Vary + WARNING/FDA block + lot/best;
  right: Free-of, Suggested Use (incl. mg-scale / sold-by-weight / settling),
  Storage, Distributed Exclusively by (full address), certifier line, then
  QR + real UPC-A + item code `X00MOGRA-LM` on a **white code panel** for dark grounds.
- Canisters (narrow half-wrap): single-column variant; text scale raised
  (H/150) so the tube face still reads; lot/best sits above the code panel
  (fixed overlap found in review).
- Bottom descriptor line: `NEW - Mogra Organics Organic Lion's Mane Mushroom Powder (170 g)`.
- Placeholder register expanded (Latin name, free-of, suggested use, storage,
  certifier, item code…) — regenerated as `BACK_LABEL_REQUIREMENTS.md` in the pack.

## Outputs (regenerated end-to-end, verified visually)
- Flat art 300 dpi: `exports/mogra-designs-20261018-bold/` (10 × front/back + wrap, contact sheet, requirements, logo master).
- Photoreal shelf mockups: `exports/mogra-shelf-mockups-20261018-bold/` (10 × front_shelf/back_shelf + contact sheet)
  — pouch homography quads, tube cylindrical warp, safe-arc wrap discipline.

## Verification
- `python export_mogra_designs.py` → 10 designs, 31 files, compile OK.
- `python export_mogra_shelf_mockups.py` → 10 mockups, compile OK.
- Visual pass on contact sheets + full-res spot checks (sticker front, tube back
  dark-ground, tube back narrow) — one collision found and fixed (lot/best vs barcode).

## Open (operator data, batched in the register)
Certifier name + number; final GTINs; QR target; origin; exact ingredient/serving
wording; facility allergens. Everything else is fully dressed for a refinish.
