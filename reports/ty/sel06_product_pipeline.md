# sel-06 / D-011 — the Seller-Tester now renders through the app

Job `sel-06-exercise-product-pipeline` (rank 2). Rollback tag `rollback/pre-sel06b-20261111`
(shared with sel-06b, same session, same tree).

## The defect this closes

| path | entry | what it used |
|---|---|---|
| the app sells this | `product_picture_api.py` → `product_picture.build` | `brand_art` panels, `mockup_compositor` face warp, `mockup_quality.assert_legible` OCR gate |
| the Seller-Tester scored this | `tools/seller_tester/generators.py` → `CompositeGenerator._generate_cut_and_compose` | its **own** label composer (`label_warp.compose_label`), its **own** quad (`_quad_for`), no OCR gate |

A count of `product_picture|mockup_compositor|brand_art|mogra_label_art` in
`tools/seller_tester/*.py` was **0**. Every seller number therefore described the harness, not the
product. `reports/ty/d11_plan.md` wrote the shape of the fix down; this is it.

## What it moved

`tools/seller_scores.py` published the harness number and said so in its own `pipeline` block
(`same_pipeline: false`). It now reads the app-path pass:

| field | before | now |
|---|---|---|
| published seller mean (design-studio) | 22.1 — 40 **replayed** rows, 0 passed | **94.9 — 12 generated rows through `product_picture.build`, 11 passed** |
| `pipeline.same_pipeline` | `false` | `true` |
| `pipeline.plate_source` | absent | `drawn` |
| `pipeline.judged` | absent | `true` |
| **design-studio service score** | 75.9 | **89.3** |

The harness/composite pass is no longer averaged beside it: two pipelines over the same briefs are
two pipelines, not one population, and blending them hides which one a seller would receive. The
replay rows stay as context in `services[*].replay` (40 scored, mean 22.1, 0 passed) and never enter
the published mean. `ty/scorecards.json` is regenerated from that: **4 services at bar**
(`hub`, `prospector`, `keyword-tracker`, `profitability` 100), design-studio 89.3 with `correct`
still at 60 ("tests prove the code path; output quality is judged by the Seller-Tester") — the
per-dimension bar, not an average, is what keeps it out.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/generators.py` | `ProductPipelineGenerator`: resolves the brief to a brand design (`brand_art.design_for_brief`), supplies the plate, and calls `product_picture.build(faces=("front",), generator=<plate>)`. Returns the app's own artefact; records the build manifest per face. |
| `tools/seller_tester/scene_render.py` | `synthetic_plate` (a **drawn, labelled** blank package) and a `drawn` renderer; `stock_from_brief` reads the brief's own colour words so a stand-in plate cannot contradict the brief. |
| `tools/seller_tester/cli.py` | `python -m tools.seller_tester product` — the app path, scored, per-mode, with `--renderer comfy\|drawn` and optional local judge. |
| `tools/seller_scores.py` | the app-path pass is the published population; the harness pass is no longer averaged beside it; the `pipeline` block reports `same_pipeline`, `plate_source` and `judged` instead of a standing warning. |
| `Northstar_backend/test_seller_tester_product_pipeline.py` *(new)* | 8 tests pinning the seam. |
| `Northstar_backend/test_seller_scores.py` | 3 tests: the app pass is published, the harness pass is not averaged in, and the harness is named when there is no app pass. |

The refusals are the app's, not the harness's: a brief with an undesigned product line, a brief that
asks the model for lettering instead of `label_mode: warp`, and a plate the app cannot measure all
raise `GeneratorUnavailable` with the app's own words, and the record keeps the reason.

## Measured — prompt-only, 12 held-out briefs, labelled by pipeline

| pipeline | plate | scored | passed | mean | judged (`gemma3:4b`) |
|---|---|---|---|---|---|
| harness composite (before this) | generated / replayed | 12 | 12 | 98.3 | 12 passed, 98.7 |
| **app `product_picture.build` (now)** | **drawn (`synthetic_plate`)** | **12** | **12 mech / 11 judged** | **97.5 mech / 94.9 judged** | 11 passed, 94.9 |

Forms: 6 `stand_up_pouch` (Mogra), 6 `gift_box` (Word Coffee) — both brands now reach the scorers
through the app.

**The one judged failure is the plate, and it says so in its own words.** PO-002 is the *lifestyle*
brief ("on a light oak kitchen counter in morning light, shallow depth of field"); the judge's
reasons are "the counter is not a light oak kitchen counter", "the lighting is not morning light",
"the depth of field is not shallow" — a drawn flat sweep cannot be a lifestyle scene. The judge
passed the other five Word Coffee briefs, including PO-004, where it read the brand, the script line
and the tagline: "The image shows a pale-pink and cream gift box… 'Word Coffee' and 'For Mom' are
present in lilac script… 'Empowering Moms, One Message at a Time' is visible."

`PO-007` is the one soft miss: it is an **infographic** brief (`text_rule: text_expected`, minimum
0.20 % margin ink) and the product-picture path delivers a product picture, so it scores 70 on
`text_free` while still passing. That is a correct finding — an infographic is a different output
type, and it needs its own path rather than a product picture pretending to be one.

**The number is not a quality claim.** It says the app's pipeline runs end to end and can be scored.
The plate is drawn, so the app path is *easier* than the real one (no scene grain, no cutout edge).
The FLUX lane (`MEDIA_GEN_LIVE`) is still unarmed, and a real plate remains owed — but the seam is
now the *plate*, which is one argument in one adapter, not the whole picture path.

## Evidence

- `pytest Northstar_backend/test_seller_tester_product_pipeline.py -q` → **8 passed**
- `pytest Northstar_backend/test_seller_scores.py -q` → **16 passed**
- `pytest test_seller_tester.py test_seller_tester_composite.py test_seller_label_warp.py test_stage_guard.py -q` → **98 passed**
- `python -m tools.seller_tester product --limit 12 --mode prompt_only --renderer drawn` →
  `selected 12, scored 12, passed 12, mean 97.5`, by_mode `prompt_only {scored: 12, passed: 12, mean_score: 97.5}`
- the same pass with `--judge` → `scored 12, passed 11, mean 94.9` (PO-002 refused on the scene)
- Per-brief summary committed at `reports/ty/d11_product_pass.json`; the judged pass at
  `reports/ty/d11_product_pass_judged.json`. Artefacts in `renders/seller_product/<brief>/`.

## Next

1. Arm the render lane and run the same pass with `--renderer comfy`: that turns the drawn-plate
   number into a real one, and it is the only thing between this and a real lifestyle picture.
2. `sel-07-bundle-and-body-shape` (PO-012 measures one unit of three).
3. `sel-refs-designs` (reference depth: 21 stored rows are 2 designs).
