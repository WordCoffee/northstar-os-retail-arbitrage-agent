# D-024 — the composite route had the same shadow, and the same blind guard

Unit `fix-composite-white-shadow`. Tag `ty-dir-fix-composite-white-shadow`. Rollback point
`rollback/pre-d024-20261111` at `475d52e3`.

## What was wrong

Found by the D-022 lane pass, on the **same run** that proved D-022. SR-001 is a white-main
brief with a real seller photo (composite route). Its artefact measured **11.473 %**
background residue — 458 901 px — of which **458 900** were neutral, the shadow's signature
(`reports/ty/d022_residue_before_after.json`).

The composite path already had a white-main guard, and it looked right:

```python
placed = composite.place_product(scene, cut, scale=..., anchor=...)
if white_main:
    measured = _measure_white(placed["bytes"], placed["product_box"], canvas_level)
    if not measured["corners_exact"]:
        placed = composite.place_product(..., shadow=False)
```

The guard measures the four **corners**. A contact shadow lives under the product, so the
corners stay exact and the shadow survives — the same blind spot D-020 closed in the
scorer, one layer down. A main image has no shadow, so the question should never be "did
the corners survive it".

## What changed

| file | change |
|---|---|
| `tools/seller_tester/generators.py` | `_composite` places with `shadow=not white_main`: a white-main composite never gets a contact shadow, a lifestyle composite always does. The corner measurement stays as a second gate, but it is no longer the only one. |
| `Northstar_backend/test_seller_tester_composite.py` | two checks: a white-main composite calls `place_product` with `shadow=False`; a lifestyle composite calls it with `shadow=True` (a spy records the argument). |

## Tests

```
python -m pytest Northstar_backend/test_seller_tester_composite.py -q   -> 26 passed
python -m pytest Northstar_backend/test_fullgen_white_composite.py -q   -> 4 passed
```

## Honest limits

* **The after-number needs a lane.** The before is measured on a real artefact (11.473 %);
  the after is proven by test on the argument and by the identical fix on the sibling route,
  which measured **25.647 % → 0.000 %** on a real render. A real-lane re-render of SR-001 is
  queued as `d024-real-residue` — the GPU lock was held by another lane
  (`role: seller_composite`, pid 2144) at the moment this unit closed, and the standing rule
  is one heavy lane at a time.
* **A lifestyle picture keeps its shadow by design.** The guard's job is the flat canvas;
  removing the shadow everywhere would break the mockup pictures that need it.
