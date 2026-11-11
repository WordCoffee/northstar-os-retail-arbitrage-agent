# pack-02 — apparel is a form, and one of its two scoreable briefs passes

Unit `pack-02-apparel-flat-print`. Tag `ty-dir-pack-02-apparel`.

## What was missing

Six catalog briefs ask for apparel. `brand_art.design_for_brief` raises for a product line it
has no design for, and it knew a pouch, a folding carton and a cylinder — so every apparel
brief was refused by name. A tee is not a packaging form: it has no panel to discover, its
print area is a rectangle on a body, and the artwork must keep its aspect.

## What changed

| file | change |
|---|---|
| `Northstar_backend/brand_art.py` | a declared **apparel** form with a physical print area (`mogra-tee`: 280 × 350 mm on the front), `form_of` / `plate_kind` / `face_mm` answering for it |
| `Northstar_backend/product_picture.py` | the garment route: measure the body from its own silhouette, place the print at the declared size, keep the artwork's aspect, refuse a blank plate by name instead of printing on nothing |
| `tools/seller_tester/scene_render.py` | `synthetic_plate(kind="apparel")`: a garment silhouette — torso, two sleeves, a collar arc, a hem line — drawn, never called a photograph |
| `ty/seller_briefs.json` | ST-017 and ST-046 wired to the form (the other four apparel briefs wait on the form being proven, which it now is) |
| `Northstar_backend/test_apparel_form.py` | five checks written first: the form and its millimetres, the shadowless plate, the print inside the body, the blank plate refused by name, and the app path delivering a flat white main image |

## Measured

`python -m tools.seller_tester product --catalog … --skip-unavailable`
→ `reports/ty/d025_apparel_pass.json`, `renders/d025/ST-017/`

| brief | mode | score | verdict |
|---|---|---|---|
| ST-017 | prompt only, white-background main | **100.0** | passed — `renders/d025/ST-017/product_front.png`: cream tee on 255 white, the Mogra chest print inside the body, brand copy legible, no shadow |
| ST-046 | uploaded reference | **80.0** | **`reference_subject` cannot verify**: *"no local copy of the uploaded file (tee_charcoal-folded.jpg); the upload was not present in this checkout"* |

**The 1 of 2 is the honest number.** ST-046 is not a form failure — the garment rendered; it
cannot be scored without the owner's upload, and `cannot_verify` is a failure in this harness
by contract, not a skip. It is the same class as the twelve uploaded-reference briefs that
have been unscorable since cycle 9.

**Quality, stated plainly:** the tee is a **drawn schematic** — blocky sleeves, a thin collar
arc, a visible hem line. It is a correct flat-print mockup and it is labelled as drawn; it is
not a photograph and would not be listed as one.

## Tests

```
python -m pytest Northstar_backend/test_apparel_form.py -q
-> 5 passed, 1 skipped
```
