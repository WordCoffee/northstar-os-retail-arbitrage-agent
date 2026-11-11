# sel-07 — a bundle is three units, and it is measured as three

Job `sel-07-bundle-and-body-shape` (rank 3). Rollback tag `rollback/pre-sel06b-20261111`
(same session, same tree).

## The defect, in two halves

**The brief contradicted itself.** PO-004 and PO-012 are `bundle_multipack` briefs whose
`prompt` says "three identical units arran[ged]" and whose `body_prompt` said "**one unit
shown**". The plate prompt asked for one box, so one box is what came back, and the fill check
(25–85 %) measured a single unit at 20.3 %.

**The measurement could only see one package.** `mockup_compositor.find_panel_quad` calls
`pouch_label.measure_face`, which asks `_foreground_mask` for **the tallest coloured object**.
That is right for one pouch and wrong for three: measured on a drawn three-unit plate, the mask
held **1 component of 343,596 px at x 531–811** — exactly the first box — because the mask's
whole design is "pick one pouch".

## What changed

| file | change |
|---|---|
| `Northstar_backend/pouch_label.py` | `package_components()` — every package-sized component, labelled, instead of collapsing to the tallest. `_foreground_mask` is untouched: single-product measurement is unchanged. |
| `Northstar_backend/mockup_compositor.py` | `find_panel_quads(count=…)` — components sorted by height, taken left to right, and **each measured on its own crop with the other units flattened to the plate's background**, so one unit's silhouette cannot bleed into another's insets. |
| `Northstar_backend/product_picture.py` | `build(units=…)` and `compose_face(…, units=…)`: one panel warped per measured face; fewer faces than requested is `ValueError: units_not_found: measured N of M`, recorded as a refusal. The manifest carries `product.units`, `checks.units` and `checks.units_complete`. |
| `ty/seller_briefs_heldout_modes.json` | PO-004/PO-012: `units: 3` and a `body_prompt` that asks for three blank units. The stored-reference bundle rows were left alone — they are not body-prompt briefs, and a blanket edit had already touched them; that was reverted. |
| `tools/seller_tester/scene_render.py` | the drawn plate draws N units; **and** `stock_from_brief` now matches colour words on word boundaries — "One Message at a Time" contains "sage", so every Word Coffee box had been painted sage-green. |

## Measured

- `pytest Northstar_backend/test_package_forms.py -q` → **21 passed** (4 new: three units measured
  left to right, a three-unit build writes three panels and says so, a one-unit plate with
  `units=3` is refused with `units_not_found: measured 1 of 3`, and `units=1` is unchanged).
- `pytest test_product_picture.py test_mockup_product_picture.py test_pouch_label.py
  test_pouch_label_geometry.py test_pouch_label_placement.py test_mockup_compositor.py
  test_seller_tester_product_pipeline.py -q` → **68 passed** (the single-unit path is intact).
- `python -m tools.seller_tester product --limit 12 --mode prompt_only --renderer drawn` →
  **12/12, mean 97.5**. PO-004 and PO-012 now report `units requested 3 / found [3]`,
  `subject fill 25.9 %` (was 20.3 % on one unit), score **100**, and their manifests say
  `units_complete: true` with **three distinct quads**.

## What is still true

The plate is `synthetic_plate` (`MEDIA_GEN_LIVE` is not 1): three drawn boxes, not a photograph of
three boxes. The measurement, the three panel warps and the OCR gate are the app's.
