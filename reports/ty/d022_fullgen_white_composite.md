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

## Honest limits

* **No real re-render yet.** The lane refused the sample pass on the memory budget, quoting
  its own numbers: `budget: refused: 8.48 GB free - 8.2 GB needed = 0.28 GB < 1.0 GB
  reserve`. `qwen2.5vl:7b` (5.7 GB VRAM) was resident for another lane, and its lease was
  *extended* while the pass was attempted (03:36 → 03:42), i.e. it is in use — not idle, so
  it is not mine to unload. The fix is proven by test on a real composition of a real plate
  through the same code path; a two-brief lane pass at the model's own seeds is the number
  that retires D-022, and it is queued as `d022-real-rerender` rather than claimed.
* **The 8 published artefacts are still the old pictures.** They were rendered with the
  shadow; re-scoring them cannot improve them. Their numbers stand as the "before".
* **This does not make the model better.** A generated plate can still carry its own cast
  shadow, which the cutout may keep. The fix removes the shadow *we* painted; the plate's own
  light is a separate question and the residue check now measures it on every new picture.
