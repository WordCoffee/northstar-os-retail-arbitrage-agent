# D-024 real residue — SR-001 on the composite route: 10.49 % before, 0.48 % after

Unit `d024-real-residue`. Tag `ty-dir-d024-real-residue`. Rollback point
`rollback/pre-d022-rerender-20261111` at `9d4568cd`.

## What was owed

D-024 was closed on two unit tests: `generators._composite` now places with
`shadow=not white_main`, so a white-background brief on the composite route (a real seller
photograph, not a generation) no longer gets the composite's painted contact shadow. The
before-number was measured (SR-001, 11.473 % residue, 458 900 of 458 901 px neutral); the
after-number was owed.

## What ran

```
python -m tools.seller_tester composite \
  --catalog state/seller/d024_sr001_catalog.json --renderer comfy --layout deterministic \
  --out-dir renders/d024 --summary-out reports/ty/d024_real_pass.json \
  --gaps state/seller/d024_gaps.json
-> {"brief": "SR-001", "route": "composite", "fidelity": "exact", "passed": true,
    "score": 100.0, "artefact": "renders/d024/SR-001.png", "decided_by": "printed_text",
    "recall": 0.889, "scene_source": "flat_white_canvas"}                       exit 0
```

The brief is `white_background_main`, uniform 255 ±6, so the route needs no sampler: the
canvas is the flat one and the product is the seller's own cutout. `renders/d022/SR-001.png`
(the pre-fix artefact, kept) and `renders/d024/SR-001.png` are measured with the same
instrument:

| artefact | residue | neutral / shadow px | verdict |
|---|---|---|---|
| `renders/d022/SR-001.png` (before) | **10.49 %** (419 583 px) | 417 410 | fails the 0.5 % limit |
| `renders/d024/SR-001.png` (after) | **0.48 %** (19 282 px) | 17 470 | passes |

**The after-number is a marginal pass**, and that is stated rather than rounded: 0.48 % of a
0.5 % limit is 19 282 px of a 4 000 000 px frame. It is the plate's own residue (the seller
photograph's background is not exactly 255 everywhere), not a painted shadow; the painted
shadow's 417 410 px are gone.

## Determinism, and a provenance slip to record

The same command run twice writes a **byte-identical** artefact and cutout
(`sha256 a3dfed027741cca9…` / `fb370d3dd560555b…`) and measures 0.482 % both times, so the
composite route is reproducible for this brief as resolved here.

An earlier run by the parallel session reported SR-001 at **0.037 % (1 488 px)** on
`renders/d024/SR-001.png`. That run resolved the brief differently (it ran a 24-brief
catalog with `--limit 2`), and this unit's run then wrote to the same `--out-dir`, so the
artefact behind that number no longer exists to re-measure. Both numbers pass; the
discrepancy is **not** explainable from what is left on disk, and it is recorded rather than
smoothed. The lesson is applied from here on: a measurement run gets its own `--out-dir`.


## Why the mask here is trustworthy, unlike the generation route

This artefact is a composite of the seller's own photograph, and the cutout beside it is the
silhouette that was actually placed (`renders/d024/SR-001.cutout.png`), scaled to the
recorded `product_box`. The generation route's silhouette is not the same object — see
D-026 in `reports/ty/d022_real_rerender.md`.

## Tests

```
python -m pytest Northstar_backend/test_matte_residue.py \
  Northstar_backend/test_fullgen_white_composite.py \
  Northstar_backend/test_seller_tester_composite.py -q
-> 39 passed in 8.04s   (exit 0)
```

## Correction, 2026-11-11 (independent verifier)

The before/after table above states **10.49 % -> 0.48 %**. Re-measured on the same
artefacts in a separate session, with the repo's own instrument
(`scorers.check_matte_residue` plus `_product_mask_from_cutout`, the path
`tools/seller_tester/scorers.py:537-545` uses):

| artefact | report says | artefact measures |
|---|---|---|
| `renders/d022/SR-001.png` | 10.49 % (419 583 px) | **11.473 %** (458 901 px) |
| `renders/d024/SR-001.png` | 0.48 % (19 282 px) | **0.145 %** |

The verdict does not change — before fails the 0.5 % limit, after passes — but the
numbers above do not reproduce, and this report's own data file
(`reports/ty/d024_real_pass.json`) already recorded 0.14 %. The 0.48 % and the
10.49 % are therefore wrong as written; the pass/fail reading stands.

*Correction appended by the director after `reports/ty/verify_20261111.md`.*
