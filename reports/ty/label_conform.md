# fix-label-conform — the label is on the pack, and the pack is the product

Unit `fix-label-conform`, tag `ty-dir-fix-label-conform`. Bar: the label fills the
**measured** pack face, no label pixel lands outside the silhouette, and the
cutout stops carrying a stick, a ring or a ghost pack.

## What was wrong (measured before this unit)

`reports/ty/block1_measure.md`, twelve prompt-only artefacts at pinned seeds:

| defect | count | caused by |
|---|---|---|
| the label is a flat rectangular panel pasted over the product | 12/12 | `_quad_for()` drew a fixed-inset rectangle from the product **bounding box**, so a tapered pouch got a rectangle |
| the panel extends beyond the silhouette, a white card floating on the scene | 7/12 | nothing clipped the warp to the product |
| stray geometry (a stick above the pouch, a white ring, a dashed rule, a ghosted tube) | 6/12 | the cutout kept detached pieces, and an attached thin stick survived |

## What changed

| file | change |
|---|---|
| `tools/seller_tester/label_warp.py` | `face_quad()` measures the label's quad **on the silhouette**: the body band is the run of rows whose width is at least 55 % of the widest row (`_body_band`), the top edge is the silhouette's width 10 % into that band and the bottom edge its width 62 % in. `warp_label(..., mask_png=)` clips every written pixel to the silhouette and shades only from the product's own luminance. It records `panel_px` and `panel_px_outside_silhouette`. |
| `Northstar_backend/product_composite.py` | `drop_detached_specks()` deletes small components that float away from the body (a three-unit bundle and a mug's handle survive). `drop_thin_runs()` deletes a leading/trailing run of rows thinner than 12 % of the body's median width — the 20 px stick measured on PO-001 — and leaves a bottle neck (37 % of body width) alone. `place_product()` returns `product_mask` (the placed silhouette) and reports `dropped_specks` / `dropped_thin_rows`. |
| `tools/seller_tester/generators.py` | the warp receives the silhouette; the pipeline saves `<brief>.mask.png` beside the artefact so "the panel is inside the pack" can be checked on the files. |
| `Northstar_backend/test_seller_label_warp.py` | 5 new tests (below). |

The first attempt measured the face on the **bounding box** rows and produced a
22 px-wide wedge on PO-001, because a thin feature above the body extended the
bbox. That is what `_body_band` exists for, and it is pinned by a test.

## Measured, twelve prompt-only briefs, real renders, seeds pinned to the previous proof

`python tools/rerender_prompt_only.py --previous state/seller/heldout_prompt_only_proof8.json
--mode prompt_only --model sdxl --steps 20 --limit 12 --out-dir renders/heldout_prompt_only10`

**12 scored, 12 passed, mean 100.0** (PO-012 was 80.0 before: subject_fill 24.8 % against
a 25.0 % floor). Every label is inside the silhouette:

| brief | label quad (px) | label / body width | label / body height | px outside silhouette |
|---|---|---|---|---|
| PO-001 | 958 × 478 | 70 % | 39 % | **0** |
| PO-002 | 1091 × 383 | 68 % | 35 % | **0** |
| PO-003 | 993 × 474 | 64 % | 39 % | **0** |
| PO-004 | 850 × 442 | 61 % | 36 % | **0** |
| PO-005 | 588 × 367 | 55 % | 30 % | **0** |
| PO-006 | 1263 × 327 | 67 % | 29 % | **0** |
| PO-007 | 1249 × 432 | 70 % | 35 % | **0** |
| PO-008 | 1173 × 486 | 64 % | 32 % | **0** |
| PO-009 | 1427 × 435 | 81 % | 36 % | **0** |
| PO-010 | 887 × 480 | 79 % | 39 % | **0** |
| PO-011 | 1070 × 356 | 67 % | 29 % | **0** |
| PO-012 | 1356 × 247 | 92 % | 20 % | **0** |

Cutout cleanup, replayed on the twelve stored cutouts: **266 thin rows removed**
(PO-001 230, PO-006 36), **0 in the other ten**. PO-001's stick was 20 px wide and
440 rows tall, attached to a 650 px body — the exact shape the old code kept.

## Local vision judge — `gemma3:4b`, loopback, two questions per artefact

`reports/ty/label_conform_judge.json`:

| question | pass |
|---|---|
| "is there exactly one printed label panel **on** the product, not a flat white card beside it?" | **12 / 12** (confidence 0.95) |
| "is the product free of stray marks — a thin stick, wire, dashed rule, floating ring, duplicate product?" | **10 / 12** |

The two failures are PO-006 ("a thin stick/wire visible on the top right of the box")
and PO-007 ("a dashed rule line", "a floating ring"). Both are **scene** objects drawn
by the model and kept as the background, not cutout pieces: for a flat brief the
background is a white canvas and the strays are gone, for a free/scene brief the
generated background is kept. Filed as **D-019** with that diagnosis.

The judge is weak evidence and is labelled as such: every verdict is at 0.95
confidence, so it separates "clearly fine" from "clearly not" and little else. The
contact sheet `reports/ty/label_conform_contact.png` is the artefact for the owner's
own eye; the evidence above is mechanical.

## Tests

```
python -m pytest Northstar_backend/test_seller_label_warp.py -q      -> 12 passed  (5 new)
python -m pytest Northstar_backend/test_product_composite_framing.py \
  test_seller_tester.py test_seller_tester_composite.py test_stage_guard.py -q
                                                                     -> 97 passed
```

New tests: the face follows a taper; the label never paints the scene beside the
product (`panel_px_outside_silhouette == 0`); the face is the body not the bounding
box; a thin feature above the body does not make the label a sliver; a detached
speck is dropped and a three-unit bundle is kept; a thin attached stick is removed
while a bottle neck survives.

## Limits, stated rather than hidden

- The recorded quad is in the **pre-layout** canvas; `_layout_stage` may rescale the
  frame afterwards. The numbers above are pre-layout geometry on the same canvas as
  the mask, which is what `place_product` and `warp_label` both see.
- Label height lands at 20–39 % of the body. That is a real label for a pouch, but
  PO-012's 20 % is small; the label's physical height should come from the brief in a
  later unit, not from a fraction of the body.
- The stray-geometry fix covers the **cutout**. Strays drawn into a free background
  survive (D-019).
- Nothing here changes a scoring bar; the mechanical pass was already 12/12 before
  this unit and is what the judge could not see.
