# D-011 execution plan — make the Seller-Tester render what the product sells

Filed 2026-11-11. Job `sel-06-exercise-product-pipeline` (rank 1). This note exists so the session
that runs it does not have to rediscover the shape of the problem.

## The measured fact

| path | entry | uses |
|---|---|---|
| the app sells this | `Northstar_backend/product_picture_api.py:115` → `product_picture.build` (`product_picture.py:191`) | `mockup_compositor`, `mogra_label_art`, `text_fidelity` |
| the Seller-Tester scores this | `tools/seller_tester/generators.py:766` | `product_composite.place_product`, `label_warp` |

A count of `product_picture|mockup_compositor|mogra_label_art` in `tools/seller_tester/*.py`: **0**.

## What makes this tractable

`product_picture.build` already takes an **injectable generator**
(`product_picture.py:196, 223-229`): `generator(brief, width=, height=, tier=, seed=) -> {bytes: ...}`.
So the harness can drive the app's real composition, real label art and real gate while supplying the
plate from the same ComfyUI lane the harness already owns. Nothing needs to be reimplemented.

## The steps, in order

1. **A `ProductPipelineGenerator` in `tools/seller_tester/generators.py`** with the same
   `generate`/`pair`/`route`/`record_for` contract as `CompositeGenerator`, which:
   - maps a seller brief to a `design` dict (`art.design_for(product)` or a brief-declared design);
   - calls `product_picture.build(design, faces=("front",), generator=<plate from ComfySceneRenderer>)`;
   - returns the front plate's artefact path and records the build's manifest (per-face ok, OCR
     report, refusal reason) in `record_for` so the summary can show *why* a face was refused.
2. **A refusal must stay a refusal.** If `build` returns `ok: False`, the generator raises
   `GeneratorUnavailable` with the face's own reason — the harness's circuit breaker already treats
   that as a stopped pass, not a skipped brief.
3. **Score the app's output with the same scorers.** No scorer changes: the checks are about the
   delivered picture, and this change is about *which* picture.
4. **Prove parity on one brief before scaling.** Run one prompt-only brief through both paths and
   compare: dimensions, background, fill, matte, file size, plus the judge. If the app's path fails
   where the harness passed, that is the finding — the harness was flattering.
5. **Re-measure the twelve.** Publish both numbers side by side, labelled by pipeline, and only then
   let the seller dimension read from the app's path (`tools/seller_scores.py`'s `pipeline` block
   exists to be deleted at that point).

## What NOT to do

- Do not "fix" `product_picture` to match the harness. If the app's label art, fold shadows or text
  gate disagree with the harness, the app is the product and the harness is the thing that is wrong.
- Do not average the two pipelines into one number.
- Do not claim the app path is exercised until a run has produced an artefact through
  `product_picture.build` and the summary names it.
