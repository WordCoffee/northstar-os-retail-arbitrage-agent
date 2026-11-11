# sel-08 — the catalog's prompt-only briefs, measured, and six forms the app cannot print

New job (no id in the queue; filed as `sel-08-prompt-only-coverage`). Rollback tag
`rollback/pre-sel06b-20261111` (same session and tree).

## What this closes

`seller_scores.py` could only ever count **12** outputs, because only the held-out modes catalog
(PO-xxx) had the fields the app path needs. The main catalog's 32 prompt-only briefs carried no
`label_mode`, no `product_line` and no `body_prompt`, so `product_picture.build` could not serve any
of them — and the seller dimension that feeds the scorecard was a 12-output sample.

## What changed

| file | change |
|---|---|
| `ty/seller_briefs.json` | the **8** prompt-only briefs whose category has a packaging form in the app (`supplement_pouch` → Mogra pouch, `food_jar` → Word Coffee carton) get `label_mode: warp`, `product_line`, `label{…}` and a `body_prompt` built from their own situation and copy. 24 were left alone — see below. |
| `tools/seller_tester/generators.py` | `skip_unavailable`: a catalog pass records a refused brief and continues instead of dying on the first one. `refusals` is the evidence. |
| `tools/seller_tester/cli.py` | `--skip-unavailable`; every refusal is printed with its brief id, category and reason, and saved in the summary under `refused`. |
| `tools/seller_scores.py` | the published app population is the **merge of every app-path pass** on disk, deduped by brief (judged wins, then mechanical, then the catalog pass). |

## Measured

`python -m tools.seller_tester product --catalog ty/seller_briefs.json --limit 56 --mode prompt_only --renderer drawn --skip-unavailable`

- `selected 32, scored 8, passed 8, mean 97.5`, **`refused: 24`**.
- The 8: ST-001, ST-008, ST-015, ST-016, ST-022, ST-023, ST-029, ST-030 — seven at 100, ST-029 at 80
  on `subject_fill` (a bundle situation with one drawn unit).
- The 24 refusals are all one reason, and it is true: **"brief ST-xxx declares no product_line"** —
  categories `ceramic_mug`, `apparel`, `skincare_bottle`, `small_appliance`, `pet_product`, `tool`.
  **The app can print two packaging forms. The catalog asks for eight product categories.**

## Published seller dimension

| | before this unit | after |
|---|---|---|
| outputs in the published population | 12 | **20** |
| mean | 98.3 | **98.0** |
| passed | 12 | **20** |
| design-studio service score | 89.8 | **89.7** |
| sources | held-out judged pass | judged + mechanical held-out **+ catalog pass** |

The service number moved down by 0.1 because the sample got larger and one row scored 80 — which is
the correct direction for an honest measurement.

## Filed as a gap, not papered over

`reports/ty/seller_gaps.json` now has a measured statement of the product-capability hole:

> The branding lane renders `stand_up_pouch` and `gift_box`. Six catalog categories —
> ceramic mug, apparel, skincare bottle, small appliance, pet product, tool — have no packaging form
> in the app at all, so 24 of 32 prompt-only briefs cannot be produced by any pipeline.

The fix is not a brief edit; it is new forms (a rigid-cylinder label for jars/bottles/tubes, a
flat-print form for apparel, a box-art form for appliances). That is the next packaging bundle.

## Tests

- `pytest Northstar_backend/test_seller_scores.py Northstar_backend/test_reference_scout.py -q` →
  **24 passed** (the merged app population dedupes by brief, and the harness pass is still excluded).
- `pytest Northstar_backend/test_seller_tester_product_pipeline.py -q` → **8 passed** (unchanged).
