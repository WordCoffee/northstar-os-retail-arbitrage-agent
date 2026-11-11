# sel-06b — the app can print a second packaging form

Job `sel-06b-second-brand`, rank 1. Rollback tag `rollback/pre-sel06b-20261111`.
Acceptance: `reports/ty/sel06b_acceptance.md`. Proof JSON: `reports/ty/sel06b_proof.json`.

## The defect, stated exactly

`mogra_label_art.design_for()` accepted one product and raised for every other
(`Northstar_backend/mogra_label_art.py:156-160`). `product_picture.build()` composed every
picture through `mogra_label_art.front_panel/back_panel` (`product_picture.py:154`), and its plate
briefs asked the image model for a **stand-up pouch** for every face
(`product_picture.py:42-55`). So the app could print

- one brand, and
- one packaging form (a supplement pouch with a Supplement Facts block).

Six of the twelve held-out prompt-only seller briefs are the other form: a slim pale-pink and
cream **Word Coffee gift box** (`ty/seller_briefs_heldout_modes.json` PO-002/004/006/008/010/012).
They were unreachable through the app at all — not a scoring problem, a product gap.

## What changed

| file | change |
|---|---|
| `Northstar_backend/package_art.py` | a `blush` theme, and the **folding-carton** renderers `render_front_box` / `render_back_box` (brand, script line, tagline, cream weight band, drawn beans, ingredients/brew/codes/UPC on the back). `render_front` (the bag form) is untouched. |
| `Northstar_backend/brand_art.py` *(new)* | the dispatch layer: `design_for`, `design_for_brief`, `form_of`, `face_mm`, `front_panel`, `back_panel`, `manifest`. A design declaring `supplement_facts` renders through `mogra_label_art` (byte-identical); anything else renders through the carton form on its declared face size. |
| `Northstar_backend/product_picture.py` | `FORM_PLATE_BRIEFS` (box plate briefs beside the pouch ones), `FORM_INSETS` (a carton has no weld or gusset to inset for), `plate_brief(face, form)`, `compose_face(..., form=)`, `build` records `product.form`. |
| `Northstar_backend/product_picture_api.py` | `GET /designs` lists **every** brand with its form, face size and the plate briefs for that form; `POST` validates faces and references against the design's own form. |
| `Northstar_backend/test_package_forms.py` *(new)* | 17 tests: A1–A9 plus the API surface. |
| `tools/box_form_proof.py` *(new)* | the proof run, kept (it is repeatable and it states its own plate caveat). |

A second brand is now **a data entry**: `Word Coffee` is a dict in `brand_art.py`, not a branch in
the renderer.

## Acceptance, measured

| id | result | evidence |
|---|---|---|
| A1 | pass | `design_for('word-coffee')` → `form=gift_box`, `brand=WORD COFFEE`, `script=For Mom`, no `supplement_facts` |
| A2 | **pass, and this is the safety property** | pouch `front`/`back` sha256 `e0160055bf0884c1` / `c719c7000ca57180` — identical to `mogra_label_art` output before and after |
| A3 | pass | OCR on the box front: `WORD`, `COFFEE`, `For Mom`, `12 COFFEE SACHETS`, `Empowering Moms, One Message at a Time`, `NET WT. 120 G (4.2 OZ)`; **no** "supplement" |
| A4 | pass | OCR on the box back: `NET WT. 120 G (4.2 OZ)`, `WHAT'S INSIDE`, `INGREDIENTS`, `Ground roasted coffee (100% arabica)`, `HOW TO BREW`, `LOT WC-0000`, `850000000004`; no Supplement Facts |
| A5 | pass | `product_picture.build(word-coffee, generator=<carton plate>)` → `ok: true`, `form: gift_box`, plate brief says "slim folding gift box", `product_front.png` 1.5 MB |
| A6 | pass | a flat plate → `ok: false`, `plate_face_not_found`, no `product_front.png` written |
| A7 | pass | `pytest test_product_picture.py test_mockup_product_picture.py test_product_picture_reference.py test_package_pipeline.py test_package_design.py test_package_designs_j.py` → **55 passed**; default build still asks for a pouch and still measures the pouch face |
| A8 | pass | `design_for('moon-dust')` raises naming `word-coffee, mogra-lions-mane` |
| A9 | pass | PO-002 → `gift_box`; PO-001 → `stand_up_pouch`; PO-099/`tea-tin` raises naming the brief and the line |
| A10 | pass | the composed front passes `assert_legible` on wordmark **and** net weight after the perspective warp; the back needed a real fix, not a bypass — the net weight was missing from the carton back, so it was added to the panel (the legal panel carries it, which is why the pouch back carries it too) |

`pytest Northstar_backend/test_package_forms.py -q` → **17 passed in 26.12s**.

## Vision verdict

`python tools/box_form_proof.py --judge` (local `gemma3:4b`, loopback only): front **95**, back
**95**, panel_front **95**, panel_back **95** — 4/4 pass against the brief's own constraint.
Honest caveat: this judge scored the **back** against a front-facing rubric and passed it, so it is
a *sanity* judge, not a discriminating one; it is recorded as weak evidence, not as proof of print
quality.

## What is proved, and what is not

- **Proved:** the app's real panel renderer, face measurement, homography warp and OCR gate now run
  for a second brand and a second form, and the pouch path is bit-for-bit unchanged.
- **Not proved:** the **plate** is synthetic. `studio_generation.engine_status()` reports
  `armed: False` — `reachable: False` at `http://127.0.0.1:8188`, i.e. **ComfyUI is not running**
  (the `MEDIA_GEN_LIVE=1` flag *is* set in `.env`; the status text was wrong until this cycle fixed
  `engine_status()` to load the repo `.env`, `Northstar_backend/studio_generation.py:_flag`). So a
  drawn carton stands in for the FLUX photograph. Everything after the plate is shipped code; the
  proof JSON says so in its `plate.source` field. A FLUX plate remains owed.
- **New limit found, and it is a refusal not a bug:** a *very* pale carton on a pale sweep
  (238,214,214 on 232,230,226) falls below the chroma threshold and is refused
  (`plate_face_not_found: … less than 2% of the plate`). The brief's pink reads at 240,196,202. If
  the first real FLUX plate comes back too pale, the fix is a higher-contrast plate brief, not a
  looser gate.

## Next

`sel-06-exercise-product-pipeline` (rank 2, D-011): point the Seller-Tester at
`product_picture.build` with `brand_art.design_for_brief`, so the seller numbers stop being
harness-pipeline numbers.
