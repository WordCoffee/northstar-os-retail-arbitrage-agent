# sel-05 — the label is composed, not spelled

Queue job `sel-05-label-fidelity` (rank 1), 2026-11-11. Rollback tag
`rollback/pre-rerender-prompt-only-20261111` (the batch's tag). Commit `d1de2d1d` + this one.

## The gap, measured before the fix

The local judge (`gemma3:4b`, loopback, ~15 s a picture) read the twelve prompt-only artefacts
produced at v6 and named the defect in one sentence per brief:

| brief | judge, before |
|---|---|
| PO-003 | "label reads **MOGGARA**", not MOGRA ORGANICS |
| PO-008 | "the box reads **AOW**", not Word Coffee |
| PO-004 | "brand name 'Word Coffee' is not visible" |
| PO-012 | box shows "Mom / Nonna / I love you", not the branding |
| PO-001/005/009/011 | label text missing, no weight, mushroom art not gold, not matte |

A diffusion model cannot spell. The briefs were handing it exact copy — brand, product, weight,
tagline — and asking for it in pixels.

## The fix

`tools/seller_tester/label_warp.py` already composed a label deterministically and warped it onto the
drawn body. Nothing used it, because **0 of 12 briefs set `label_mode`**. Now:

1. each brief declares `label_mode: "warp"`, a `label` block (brand, product, weight, lines) taken
   **verbatim from its own prompt**, and a `body_prompt` that asks for an unlettered body;
2. `scene_render.full_prompt()` returns the body prompt for a warp brief and **raises** if a warp
   brief has no body prompt — otherwise the model would letter the body and the warp would paste a
   second copy over it;
3. `label_warp.compose_label()` wraps and fits the copy instead of cutting it at 28 characters
   ("ORGANIC LION'S MANE MUSHROOM P" was on PO-009's label; the judge read the missing word);
4. nine tests in `Northstar_backend/test_label_mode.py`.

## Result, same seeds throughout

| version | what changed | mechanical | judged |
|---|---|---|---|
| v6 | labels asked of the model | 12/12, **100.0** | 11/12, **83.5** |
| v7 | labels composed + warped | 12/12, 98.3 | 12/12, **93.7** |
| **v8** | **+ the copy wraps instead of truncating** | 12/12, 98.3 | 12/12, **98.7** |

Render seeds were pinned to the previous proof each time (`seeds_reused: 12, seeds_random: 0`), so the
only variable between rows is the pipeline.

Mechanical and judged disagree in opposite directions, and both are useful: the mechanical scorer
cannot see lettering at all (it checks dimensions, background, fill, matte, file size), which is why
v6 scored a perfect 100.0 while a human would call every label wrong. That is the argument for the
judge existing.

## What is still not right — stated, not hidden

1. **PO-012 at 84.0**: the bundle brief asks for three identical units; the pipeline places one, and
   `subject_fill` measures 50.3 % of the frame. A real gap in the bundle situation.
2. **The judge is a 4B model.** "12 of 12" means *a small local vision model found no fault it could
   name*, not that a seller would accept the pictures. The rubric it checks against is the brief's
   own prompt text, which is the best available but is not a human review.
3. **D-011 stands.** These artefacts come from `tools/seller_tester` + `product_composite` +
   `label_warp`. The app renders through `product_picture.build` + `mogra_label_art` +
   `mockup_compositor`, and a count of those names in `tools/seller_tester/*.py` is **0**. The number
   above is a harness number. `tools/seller_scores.py` now says so in its own output.
   `mogra_label_art._wrap` already measures text width properly, which is the same drift seen from
   the other side: the app's path did not have the truncation bug the harness had.
4. **The body shape drifts on the pouch briefs.** PO-005 and PO-011 were judged "a green box, not a
   stand-up pouch" at v7; v8's pictures passed, but the prompt says "pouch" and the model produced a
   box twice in a row — a body-shape problem the label work does not touch.

## Held-out record

`state/seller/heldout_proof.json` after merging the v8 mechanical rows: prompt-only 12 scored /
12 passed / **98.3**; stored 12 / 11 / 91.8; uploaded 21 / 16 / 90.0 — **45 scored, 39 passed, 92.7**.
Judged prompt-only is kept beside it (`..._proof8_judged.json`), not merged, because the other two
modes were not judged and averaging judged with unjudged would inflate the set.
