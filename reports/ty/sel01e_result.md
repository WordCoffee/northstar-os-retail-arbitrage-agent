# The checks can now fail, and two composites did

2026-11-08, sel-01e. Owner instruction: *mark current composite passes provisional until the
product-region check can verify them, or apply the cannot_verify=fail rule.*

## Applied: cannot_verify is a failure

`score_image` now grades a `product_region` check on the composite route and treats it as
critical. The harness loads `<artefact>.cutout.png` and its `product_box`; **a missing cutout is
a failure, not a skip.** `tools/composite_audit.py --run` rewrote the proof accordingly:

| brief | before | now | passed | provisional | failed on |
|---|---|---|---|---|---|
| MG-C01 white main | 60.0 | **48.0** | false | no | background, subject_fill, product_region |
| MG-C02 greenhouse | 75.0 | **57.1** | **false** | **yes** | subject_fill, product_region |
| MG-C03 forest mockup | 100.0 | **76.2** | **false** | **yes** | product_region |

The old numbers are kept as `provisional_score` (75.0 and 100.0) so the record shows exactly what
changed and why. Proof summary: **2 passed / mean 78.3 → 0 passed / mean 60.4.**

The reason is the same for all three and it is a real gap, not a formality: *the generator did not
save the cutout it used, so the product region cannot be compared.* `sel-01c` is rank 1 for
exactly that reason.

## What that does to the score — and a correction

Design-studio sits at **75.9**, with `seller` 22.1 from the **40-output stored pass**. That is the
honest reading in this checkout.

The builder's own run reported 75.9 → 73.0. That delta came from `seller_scores` rejecting a
**3-output composite sample** (the minimum is five), which zeroed the dimension — not from the
60.4 mean. Both numbers are real; they are samples of different sizes, and the five-output floor
is doing its job. The 40-output pass is preserved at `state/seller/last_run_stored_20261108.json`.

## OCR: rebuilt on hard real crops, and the answer changed shape

16 crops cut from the real pouch labels (brand lockups, product names, weights, the icon ring),
JPEG q72 to keep the compression artefacts, ground truth per crop, per-crop recall recorded:

| engine | mean recall | crops |
|---|---|---|
| **rapidocr @ 2×** | **0.906** | 13/16 |
| rapidocr | 0.875 | 12/16 |
| easyocr | 0.359 | 3/16 |

Hardest crops: `life_brand_left` 0.25, `main_brand_left` 0.75 / 0.50 / 0.00. **Decision: keep
rapidocr**, because the 2× variant's margin is 0.031 — under the 0.05 bar for a swap. The upscale
is now a documented option rather than a default.

This is the useful part: the old eval scored 1.000 and could not separate anything. On real crops
easyocr collapses to 0.36 and the incumbent's own weak spots are visible.

## The embedding is no longer null

`qwen2.5vl` descriptions now feed `qwen3-embedding:0.6b` through `reference_check.embed`:

| brief | cosine |
|---|---|
| MG-C01 | **0.9678** |
| MG-C02 | **0.9918** |
| MG-C03 | **0.9327** |

Descriptions are stored in the proof. A blank description and a raising describer both yield
`cannot_verify` — never 1.0, never null silently.

## Tests

```
python -m pytest test_composite_fidelity.py test_seller_tester.py test_reference_checks.py -q
72 passed in 17.57s
```

Still running: **sel-01d** (white-canvas main images, the GPU lane recording `nvidia-smi` and
`ollama ps`, unload/reload of Bojo and embeddings, a measured upscaler, and FLUX 3 fixed or
replaced).
