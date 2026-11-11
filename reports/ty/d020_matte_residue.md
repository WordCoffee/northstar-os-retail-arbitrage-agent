# D-020 — the background is measured on the whole frame, and the published 100.0s do not survive it

Unit `fix-matte-residue-check`. Tag `ty-dir-fix-matte-residue-check`. Rollback point
`rollback/pre-d020-20261111` at `11973d05`.

## The blind spot, stated as a measurement

| instrument | what it samples | a main image with a grey pool under the product |
|---|---|---|
| `check_background` | four 24 px **corner** patches | **passes** — corners are 255 |
| `check_alpha_matte` (`white_matte`) | an outer **ring** 1 % of the side | **passes** — ring mean 255.0, std 0.00 |
| `check_matte_residue` (new) | the whole frame **outside the product's silhouette** | **fails** — 10.2 % to 25.6 % of the frame |

The first two are held under test (`test_the_corner_and_ring_instruments_both_pass_a_shadowed_main_image`)
so a future widening of either shows up as a failing test, not as silence.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/scorers.py` | `check_matte_residue(rgb, spec, subject_mask=)`: every pixel that differs from the asked value by more than the tolerance and is not inside the product's silhouette is residue. A 5 × 5 dilation of the silhouette tolerates the cut edge's blend; blobs under 0.02 % of the frame are dropped as sparkle. Limit **0.5 %** of the frame. Reports `residue_pct`, `residue_px`, `shadow_px` (the neutral ones) and the tolerance it used. No silhouette → **skipped with the reason**, never passed. Weights: `background` 0.20 → **0.10**, `matte_residue` **0.10** — the denominator is unchanged, so a picture with no residue keeps exactly the score it had. Where the check is graded it is **critical**. |
| `tools/seller_tester/harness.py` | three provenance defects fixed, each of which had been silently disabling the D-018 silhouette: (1) the cutout was loaded **only** on the composite route, so 0 of 20 `product_picture` artefacts ever reached the scorers; (2) `generation.product_box` is null on that route (measured 4 of 4); (3) the app's own `product_picture_manifest.json` beside the picture carries `product_box`, and `_product_box_from_manifest` reads it. New `audit_matte_residue(summary)` re-scores a recorded pass on the residue property alone, reusing every recorded check and re-judging nothing. |
| `Northstar_backend/test_matte_residue.py` | 9 checks, written before the code. |

## Measured on the published artefacts

`python state/director/_d020_audit.py` → `reports/ty/d020_residue_audit.json`

| pass | artefacts | checked | unchecked | newly failed | mean before → after |
|---|---|---|---|---|---|
| `label_conform_pass.json` (full generations) | 12 | **8** | 4 (free background) | **8** | **100.0 → 90.0** |
| `pack01_catalog_pass.json` (drawn plates) | 20 | **0** | 20 | 0 | 95.0 → not measurable (D-021) |
| `d020_sample_pass.json` (drawn plates, re-rendered today) | 4 | 3 | 1 | 0 | 100.0 → 100.0 |

Residue on the eight: PO-001 **25.6 %**, PO-006 19.9 %, PO-004 15.1 %, PO-012 14.3 %,
PO-011 12.7 %, PO-003 11.9 %, PO-009 11.7 %, PO-005 10.2 %. Every one of them was a
published 100.0. The picture is a product on a grey-pooled white field, and `renders/
heldout_prompt_only10/PO-001.png` shows it plainly. **The published seller mean of 96.2 is
provisional from now on**, and `ty/seller_scores.json` carries that statement next to the
number rather than a quietly rewritten mean.

`d020_sample_pass.json` is the control: a fresh drawn-plate pass *with* the new wiring
reads 0.00 % residue and still scores 100.0 — the check does not fire on a clean picture,
and the weight split costs a clean picture nothing.

## Where the check is still blind, stated as D-021

The 20 drawn-plate outputs cannot be checked, and re-rendering them would not help. The
drawn plate **draws** a base shadow (`scene_render.py:431`, ellipse `(206,204,200)`), the
colour cut keeps it, and the silhouette therefore *includes* it — so "outside the
silhouette" is empty and the check reads 0.00 % on a picture that visibly has a shadow.
Measured on the three artefacts of today's drawn pass that could be graded: 0.00 %, 0.00 %,
0.00 %. A check cannot police the instrument it is calibrated against; the fix is in the
plate (D-021, queued rank 1) and in the full-generation route (D-022, queued rank 2), not in
another threshold.

## Tests

```
python -m pytest Northstar_backend/test_matte_residue.py -q                       -> 9 passed
python -m pytest Northstar_backend/test_seller_tester.py \
  test_seller_tester_composite.py test_matte_residue.py \
  test_subject_fill_instrument.py -q                                              -> 95 passed
python -m pytest Northstar_backend/test_plate_shadow_matte.py \
  test_product_picture_white_main.py -q                                           -> 15 passed, 1 skipped
```

The nine new checks: the two old instruments pass a shadowed main image while the new one
fails it; a clean picture has no residue; a 2 px edge blend is tolerated; one speck is not a
shadow; no silhouette → skipped with the reason; a free background → skipped; `background` +
`matte_residue` still sum to 0.20 and a clean picture scores 100.0; a shadowed picture fails
even with every old check green; a clean picture still passes.

## Honest limits

* **One pass re-scored, not re-rendered.** The 8 failures are the same artefacts the 100.0
  was measured on, re-scored through their recorded checks — no new picture, no new judge.
* **The drawn-plate route is unmeasured, not clean.** 0.00 % there is the check being blind
  (D-021), not the picture being right.
* **The 0.5 % limit is a judgement, not a marketplace number.** The briefs ask for a
  uniform value with a tolerance of 6 levels; 0.5 % of a 2000² frame is 20 000 px, about
  the size of a coin at the product's base. A shadow is orders of magnitude bigger (10–26 %).
  The limit is a parameter (`MATTE_RESIDUE_MAX`), and the measurement prints the number so
  a later calibration has something to compare against.
