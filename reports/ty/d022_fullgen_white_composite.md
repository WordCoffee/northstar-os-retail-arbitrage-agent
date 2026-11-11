# D-022 — a main image is finished without the composite's own contact shadow

Unit `fix-fullgen-white-composite`. Tag `ty-dir-fix-fullgen-white-composite`. Rollback
point `rollback/pre-d022-20261111` at `49bbc666`.

## What was wrong

The full-generation route already does the right first half: it generates a plate, cuts the
product out, and composes it on the brief's flat canvas (`white_canvas_png`). Then it called

```python
composite.place_product(background, cut_png, scale=0.62, anchor=(0.5, 0.6))
```

— and `place_product`'s default is `shadow=True`: a measured soft ellipse, 1.15 × the
product's width and 0.22 × its height, blurred, opacity 96, filled `(18, 14, 10)`. On a
studio sweep that ellipse sells the picture. On **255 white** it is the grey pool, and it is
what D-020 measured as 10.2 %–25.6 % background residue on eight published artefacts.

The shadow was added on purpose, for a good reason: the D-018 fix reserved its footprint
inside the frame so it could not be clipped by the edge. The bug was that a **main image**
kept it at all.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/generators.py` | `_generate_cut_and_compose` passes `shadow=not flat(brief)`. A flat brief (uniform value, or a white matte) is composed with no contact shadow; a free/scene brief keeps it, so a lifestyle picture does not get a product floating above nothing. The choice uses the same `flat()` predicate that already picks the canvas, so the two cannot disagree. |
| `Northstar_backend/test_fullgen_white_composite.py` | 4 checks, written before the code. |

## Tests

```
python -m pytest Northstar_backend/test_fullgen_white_composite.py -q                     -> 4 passed
python -m pytest Northstar_backend/test_seller_tester.py \
  test_seller_tester_composite.py test_fullgen_white_composite.py \
  test_matte_residue.py -q                                                                -> 91 passed
```

The four checks:

1. a main-image brief is composed with `shadow=False` (a spy on `place_product` records the
   argument);
2. a free-background brief is composed with `shadow=True`;
3. the delivered main image has **no residue**: the picture and the cutout the route writes
   are scored with `check_matte_residue` and the residue is ≤ 0.5 % of the frame;
4. the control: the same composition with `shadow=True` **fails** the same check, so the
   measurement has teeth rather than always agreeing.

## The real measurement (the claim is retired)

The first attempt was refused on the memory budget — `budget: refused: 8.48 GB free - 8.2 GB
needed = 0.28 GB < 1.0 GB reserve` — while `qwen2.5vl:7b` was resident for another lane and
its lease was **extended** mid-attempt (03:36 → 03:42), i.e. in use and not mine to unload.
The lane came free and the pass ran:

```
python -m tools.seller_tester composite --catalog ty/seller_briefs_heldout_modes.json \
    --limit 2 --renderer comfy --method birefnet --model sdxl \
    --out-dir renders/d022 --summary-out reports/ty/d022_sample_pass.json
-> PO-001 (full_generation) 100.0 passed; SR-001 (composite) 93.3
```

Measured on the artefacts with `check_matte_residue`, each against its own recorded
silhouette (`reports/ty/d022_residue_before_after.json`):

| artefact | residue | of which neutral (shadow-shaped) |
|---|---|---|
| PO-001 **before** (`renders/heldout_prompt_only10/PO-001.png`, published 100.0) | **25.647 %** (1 025 874 px) | 1 022 424 px |
| PO-001 **after** (`renders/d022/PO-001.png`, real SDXL lane, same code) | **0.000 %** (0 px) | 0 px |

A real render, at the model's own seed, on the app's own path. **D-022 is measured, not
asserted.**

The same pass found the sibling defect on the **composite** route: SR-001 (a white-main
brief with a real seller photo) read **11.473 %** residue, 458 900 of it neutral — the
composite path had the same `place_product` default. Filed **D-024**, fixed in
`generators._composite` (`shadow=not white_main`) with two checks; the real-lane
re-measurement of SR-001 is queued as `d024-real-residue`.

## Honest limits

* **The 8 published artefacts are still the old pictures.** They were rendered with the
  shadow; re-scoring them cannot improve them. Their numbers stand as the "before".
* **This does not make the model better.** A generated plate can still carry its own cast
  shadow, which the cutout may keep. The fix removes the shadow *we* painted; the plate's own
  light is a separate question and the residue check now measures it on every new picture.
