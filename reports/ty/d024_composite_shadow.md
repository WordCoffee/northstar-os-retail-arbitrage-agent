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

## Measured, real lane

The GPU came free and the pass ran:

```
python -m tools.seller_tester composite --catalog ty/seller_briefs_heldout_modes.json \
    --limit 2 --renderer comfy --method birefnet --model sdxl \
    --out-dir renders/d024 --summary-out reports/ty/d024_sample_pass.json
-> PO-001 100.0 passed; SR-001 100.0 passed (was 93.3, failed)
```

| artefact | residue | residue px | of which neutral |
|---|---|---|---|
| SR-001 **before** (`renders/d022/SR-001.png`) | **11.473 %** | 458 901 | 458 900 |
| SR-001 **after** (`renders/d024/SR-001.png`) | **0.037 %** | 1 488 | 1 488 |

The score moved with it: **93.3 (failed) → 100.0 (passed)**. The remaining 0.037 % is the
product's own edge blend, under the 0.5 % limit and under the 5 × 5 dilation tolerance in
the wrong direction only where the cutout is 1–2 px tight. Record:
`reports/ty/d022_residue_before_after.json`.

## Tests

```
python -m pytest Northstar_backend/test_seller_tester_composite.py -q   -> 26 passed
python -m pytest Northstar_backend/test_fullgen_white_composite.py -q   -> 4 passed
```

## Honest limits

* **A lifestyle picture keeps its shadow by design.** The guard's job is the flat canvas;
  removing the shadow everywhere would break the mockup pictures that need it.
* **One brief, one seed.** SR-001 is the only composite white-main brief in the held-out
  catalog, so the after-number is one real render, not a distribution.
