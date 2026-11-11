# white-cutout-main — the product alone on white (D-015)

Unit: `white-cutout-main` (queue rank 1). Rollback tag: `rollback/pre-pack01-20261111`.

## The defect this closes

A **main-image** brief (uniform background, or a white matte) is not a photograph
of a product on a sweep: it is the product alone on the brief's background value.
The app composited the label onto the photograph and stopped there, so on the
first real plate ST-001 failed `background` and `alpha_matte` and scored **70**.

## What changed

| layer | change |
|---|---|
| `product_picture._place_on_flat` | cut the product out of the **plate**, keep the largest solid component (so a soft alpha does not lose the product's own bright edge), feather it, and stand it on the brief's value at a share of the frame's **area** |
| `product_picture.build(..., background=, background_value=, fill=)` | opt-in: `background="white"` applies the step; `fill` is the share of the canvas area the product should occupy |
| the cutout runs on the PLATE | cutting the finished picture punched the label's own light panel out and took the wordmark with it — the first attempt scored `wordmark_not_read: MOGRA` for exactly that reason |
| `fill` is an **area**, not a linear size | the briefs state fill as an area percentage, and Amazon's 85 % linear guidance is ~72 % area for a square subject. A fixed 0.85 linear fill overshot every brief with an upper bound (ST-008 51.5 % vs 20–50 %) |
| harness decides from the brief | `generators.ProductPipelineGenerator` reads `constraints.background.mode` and `constraints.matte.mode`, takes the band midpoint of `constraints.fill_pct` (clamped to 2–72 %), and passes it through. A free (scene) background keeps the photograph |

## Measured

**Real plate, `ST-001` (Mogra pouch, white-background main brief):**

| | score | passed | failed checks |
|---|---|---|---|
| before this unit (`renders/comfy_plate2`) | 70 | no | `background`, `alpha_matte` |
| after (`renders/comfy_plate6`) | **100** | **yes** | — |

`renders/comfy_plate6/ST-001/product_front.png`: a kraft stand-up pouch with its
real wrinkles, the designed label warped onto the front panel, standing on 255
white, every corner at ≥ 250 with a border std ≤ 4.

**Drawn catalog pass (20 briefs, 5 categories):** 20 scored, 20 passed,
**mean 95.0**; by category ceramic_mug 90 · food_jar 100 · pet_product 92.5 ·
skincare_bottle 92.5 · supplement_pouch 100. Published seller dimension:
**96.2 over 32 outputs, 32 passed**.

Checks that still fail inside passing pictures: `ST-011`/`ST-027` are infographic
briefs needing margin ink (D-013); `ST-024`/`ST-031` are **white mugs on a white
canvas**, and the fill instrument measures the subject by difference from the
corner colour, which a white product on white defeats (D-018).

## Tests

`Northstar_backend/test_product_picture_white_main.py` — **7 passed**:

- a flat-background brief gets the product on the requested value (corners ≥ 250, border std ≤ 4);
- the label survives the cutout (regression: the wordmark was punched out when the cut ran on the finished picture);
- the product's share follows the band it is given (0.20 → 0.18–0.22, 0.60 → 0.55–0.65);
- a blank plate is refused as `cutout_empty` and writes no picture;
- a scene background is left as the photograph;
- the harness cuts a `uniform` brief onto white and leaves a `free` brief alone.

One existing test changed: `test_the_apps_own_refusal_is_carried_out` accepted only
`plate_face_not_found`; on a flat-background brief the cutout now notices first, so
it accepts `cutout_empty` too. Both are the app refusing by name with no artefact.

Related suites green: `test_seller_tester_product_pipeline.py`,
`test_seller_tester.py`, `test_package_cylinder_form.py`, `test_package_forms.py`,
`test_product_picture.py` — **119 passed**.

## Filed

- **D-017** a plate's contact shadow survives the cutout when it is opaque enough
  to pass the solid-alpha threshold (visible as a wedge right of the pouch).
  Removing it needs a real matte — BiRefNet in the lane — not a colour threshold.
- **D-018** a white product on a white canvas defeats the fill instrument, which
  measures the subject by difference from the corner colour. `ST-024`/`ST-031`
  read 20.7 % / 19.8 % against bands starting at 24 / 20.
