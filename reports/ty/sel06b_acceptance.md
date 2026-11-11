# sel-06b acceptance checks — written before the change

Job: `sel-06b-second-brand` (rank 1). Rollback tag `rollback/pre-sel06b-20261111`.

The defect: `mogra_label_art.design_for('word-coffee')` raises `ValueError: unknown
label design 'word-coffee'` (line 159), so the app can print exactly one packaging form for one
brand. The six Word Coffee prompt-only briefs (`PO-002/004/006/008/010/012`) are a slim pale-pink
and cream **gift box** — a form with no Supplement Facts panel at all.

A check is met only by command output or `file:line`, never by narration.

| id | check | how it is measured |
|---|---|---|
| A1 | `brand_art.design_for('word-coffee')` returns a `gift_box` design with `brand == "WORD COFFEE"`, `script_line == "For Mom"`, the tagline, and **no** `supplement_facts` key | `python -c ...` printing the dict keys, then the test |
| A2 | The pouch design renders byte-identically to `mogra_label_art.front_panel()` / `back_panel()` — the shipping Mogra path is not touched | sha256 of both images equal |
| A3 | The box front panel carries the brand, the script line, the tagline and the weight line, in the declared face aspect, and contains **no** "Supplement Facts" | OCR of the panel + `assert_legible` |
| A4 | The box back panel carries ingredients, the roast line, brew text, lot/best-by and a drawn UPC — and no Supplement Facts | OCR of the panel |
| A5 | `product_picture.build(design=word-coffee, generator=plain box plate)` returns `ok: True`, writes `product_front.png`, and its manifest records `form: gift_box` and a box plate brief (not a pouch brief) | build result + manifest JSON |
| A6 | A plate with no box in it is **refused**, `plate_face_not_found`, and no `product_front.png` is written | build result |
| A7 | The default `product_picture.build()` (no design) still uses the pouch brief and the Mogra panels, and the existing product-picture tests still pass | `pytest Northstar_backend/test_product_picture.py` |
| A8 | An unknown design id raises a `ValueError` that names the known ids | `pytest` |
| A9 | A seller brief reaches the app path by `product_line`: `design_for_brief(PO-002)["form"] == "gift_box"`, `design_for_brief(PO-001)["form"] == "stand_up_pouch"`. An unknown product line raises with the brief id — never silently falls back to Mogra | `pytest` |
| A10 | The OCR gate reads the wordmark **and** the net weight on the real composed box picture; if it cannot, the refusal reason is reported, not bypassed | `assert_legible` on the composed front, reason printed |

Evidence goes to `reports/ty/sel06b_second_brand.md`.
