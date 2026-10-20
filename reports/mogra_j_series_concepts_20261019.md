# MOGRA J-series — the operator's two concept directions, built

**Date:** 2026-10-19 · **Branch:** `feature/v4.1-mesh`
**Requested:** use the pipeline to generate product designs for Mogra Organics
Organic Lion's Mane Mushroom Powder from the two supplied concept sheets
(`C:\Users\T2Hol\Downloads\Image.jpg`, `Image (1).jpg`), with the real logo
(`exports/mogra_logo_master_v3_white.png`).

---

## 1. What was produced

Pack: `exports/mogra-lionsmane-6oz-j-series-20261019/` — 4 print panels at
**1535 × 2480 px (130 × 210 mm @ 300 dpi)** plus contact sheet and README.

| Design | Front | Back | Source concept |
|---|---|---|---|
| `j01_olive_kraft` | kraft stock, full lockup, tracked serif caps + italic binomial, Hericium plate, USDA roundel, olive net-weight band | cream plate on kraft, real Supplement Facts, cert badges, UPC + QR | concept 01 "Olive + Kraft" |
| `j02_botanical_luxe` | bone stock, oversized Playfair `lion's mane`, forest botanical sweep with the Hericium plate, botanical sprig, USDA + VEGAN/NON-GMO footer | cream panel, same regulated content | concept 02 "Botanical Luxe" |

Shelf mockups (design printed onto the studio packshot):
`exports/mogra-lionsmane-6oz-j-series-20261019-shelf/` — 2 designs × front + back
+ contact sheet.

## 2. Three real defects the concepts exposed — fixed, not worked around

**(a) The pipeline has been stamping the wrong species.** `motif_lionsmane.png`
in every pack since 2026-10-17 is a **button mushroom (Agaricus)** — cap, gills,
short stem — extracted from a raw render. Lion's Mane (*Hericium erinaceus*) is a
compact mass of long hanging spines with no cap or gills at all. The i-series
packaged Lion's Mane with a button mushroom on the front.

**(b) The back panels carried placeholder identity.** `render_back()` prints
"T2 Holdings LLC, 1234 Sample Ave, Springfield MO", a 5 g / 34-serving facts
panel and "Example Certifiers, Inc." The operator's live label (found on the
Desktop in `Mogra Organics\`) says: **Mogran Organics, 2442 S Collins St,
Ste 108 PMB 1157, Arlington TX 76014**, serving **~1000 mg**, **~170 servings**,
certs **HALAL / KOSHER / ISO 9001 / ISO 22000**.

**(c) The requested logo file has no alpha.** `mogra_logo_master_v3_white.png`
is a flattened **RGB** white-field companion — stamped as-is it paints a white
rectangle onto kraft. The exporter now detects a fully-opaque master and uses
the RGBA sibling of the same artwork (`mogra_logo_master_v3.png`, same 2920 ×
2510 build), logging the substitution in the pack README.

## 3. How the hero art was solved

The correct species now comes from the operator's own product photograph
(`Desktop\Mogra Organics\IMG20240320001655.jpg`, cropped to
`Northstar_backend/assets/brand/hericium_source.jpg`, 920 × 665). Two
deterministic treatments, both pure PIL/numpy:

- **`hericium_plate()`** (kraft): flat-field correction removes the label's own
  lighting gradient, then a ground→body→shadow luminance ramp pins the printed
  paper field *exactly onto the bag colour* so the art dissolves into the stock.
- **`hericium_plaque()`** (forest sweep): the same plate with a feathered
  elliptical matte, because a cream field cannot be ramped into a dark ground
  without showing a rectangle.

Both are cached per colour pair; a full re-export is ~40 s.

## 4. Verification

| Gate | Result |
|---|---|
| `pytest test_package_designs_j.py` | **5 passed** (spec wiring, full-panel render, back render, no placeholder distributor, species asset) |
| Panel geometry | 1535 × 2480 px = 130 × 210 mm @ 300 dpi, all four |
| Visual check | both fronts and both backs reviewed as images this session (the model **can** see images here — earlier sessions could not) |
| Re-export | `python export_mogra_designs.py --only j01_olive_kraft,j02_botanical_luxe --flat` reproduces the pack |
| Mockups | 2 × front/back through `mockup_engine.print_package` on the calibrated pouch plate |

## 5. Honest limits

1. **The hero art is a photographic plate, not an engraving.** The source is a
   photograph of a printed label (920 px of mushroom), so it reads as a printed
   tonal image. A hand-drawn Hericium line engraving would be sharper at print
   size; the procedural attempts made this session (strand-field and
   high-pass etch variants) were rejected on inspection.
2. **The facts panel is transcribed, not certified.** Values come from the photo
   of the live label; the running copy still needs sign-off before plate
   production (see `BACK_LABEL_REQUIREMENTS.md`).
3. **`Mogran` vs `Mogra`.** The live label prints "Distributed by **Mogran**
   Organics" while the brand is "MOGRA ORGANICS". Copied as printed — needs a
   decision.
4. **Bleed.** Panels are trim-size art; the 3 mm bleeds and dieline marks used by
   the print lane are not applied to these two (the `design_studio_print`
   doypack path does that when a die is supplied).

## 6. Wiring

- `Northstar_backend/package_designs.py` — new section *bag series J*
  (`hericium_plate`, `hericium_plaque`, `usda_roundel`, `leaf_branch`,
  `j01_olive_kraft`, `j02_botanical_luxe`, `render_back_j`), dispatched from
  `render_back()` via `spec["back"] == "j"`, registered in `design_specs()`.
- `Northstar_backend/export_mogra_designs.py` — `_load_logo_master()` alpha guard.
- `Northstar_backend/export_mogra_shelf_mockups.py` — j01/j02 added to
  `BAG_DESIGNS`.
- `Northstar_backend/assets/brand/hericium_source.jpg` — the cropped product photo.
