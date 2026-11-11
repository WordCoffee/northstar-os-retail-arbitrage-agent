# D-025 — a generated plate's own cast shadow is cut by a real matte, not by colour

Unit `fix-fullgen-matte-cutout`. Tag `ty-dir-d025-fullgen-matte`. Rollback point
`rollback/pre-d025-20261111`.

## What was owed

D-022's real re-render (`reports/ty/d022_real_rerender.md`) left PO-001 at its original
seed 2747063199 still failing: **25.647 % → 14.760 %** residue, and the remaining 590 541 px
was not painted by the composite. It was painted by the model — a cast shadow, attached to
the product and opaque — and `generators._cut(..., method="grabcut")` kept it, because a
colour cut cannot separate a shadow from the object it touches. D-017 fixed exactly this
on the app's plate route with BiRefNet; the generation route still cut by colour.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/generators.py` | new `CompositeGenerator._matte_cut()`: the product's matte through `product_cutout.matte_alpha` inside the media lane (`comfy_lane.lane(needed_gb=3.0, role="scene:matte")`), or an already-resident lane. `pc.MatteUnavailable` is raised **with the lane's own reason** when it cannot run, and the generation route falls back to grabcut — recorded, never silent. `record["cutout_matte"] = {requested, method, reason}` and `cutout_method` are written for every artefact |
| `tools/seller_tester/scorers.py` | `_product_mask_from_cutout` now accepts the cutout's PNG **bytes**. Passing bytes used to make `np.asarray` produce a 1-D array, the helper returned `None`, and `check_matte_residue` was *skipped* — a silent skip is how a masked shadow passes as a clean picture |
| `Northstar_backend/test_fullgen_matte_cutout.py` | checks written before the code: the matte removes the drawn shadow; the control (grabcut) keeps it; the fallback is named; the shadow pixels are gone, not hidden |

## Measured

**Ground truth — a synthetic plate whose shadow is a known ellipse** (196 grey, attached to
the product, 768 px at this scale):

| route | `cutout_method` | shadow band px kept | residue check |
|---|---|---|---|
| real matte (BiRefNet stand-in alpha) | `birefnet` | **3** (0.0003 % of the frame — a resample seam on the product's own edge) | **0.00 %**, pass |
| grabcut fallback | `grabcut` | **768** | **0.00 %, blind** — D-026 |

The fallback also records `requested=birefnet`, `method=grabcut`,
`reason="the media lane is unreachable: no birefnet"`.

**Real lane — PO-001 at the pinned seed 2747063199** (`renders/d025/PO-001.png`,
`reports/ty/d025_pinned_pass.json`):

| | before (grabcut, `renders/d022_pinned`) | after (matte, `renders/d025`) |
|---|---|---|
| recorded matte | none (grabcut) | `{"requested":"birefnet","method":"birefnet"}` |
| score | 96.7 (1 of 3 failed) | **100.0**, every check ok |
| residue | 14.760 % measured by D-022's audit | **0.00 %**, 0 px |
| the picture | a dark smear to the left of and under the pouch | clean white on all four sides; label copy intact (`MOGRA ORGANICS`, `ORGANIC LION'S MANE MUSHROOM POWDER`, `6 oz (170 g)`) |

**The honest limit of the real-lane number:** the two artefacts are the same brief, model,
steps, size and seed, but not the same framing, so the comparison is *visual plus score*,
not a per-pixel ground truth. The per-pixel instrument with exact truth is the synthetic
plate above; the real lane confirms it transfers.

## Still open — D-026, unchanged

`check_matte_residue` counts pixels outside the **recorded** silhouette. On the generation
route with the grabcut fallback that silhouette *includes* the attached shadow, so the check
reads 0.00 % on a picture with a visible smear (proven by the control test above: 768 band px
kept, residue 0.00 %). The unit that fixes it is `fix-fullgen-silhouette`, rank 2. It is
recorded in the control test as an assertion, so the day it is fixed wrongly, the suite says
so.

## Tests

```
python -m pytest Northstar_backend/test_fullgen_matte_cutout.py -q
-> 4 passed, 1 skipped   (the skipped one is the lane-gated real-plate check, NS_MATTE_LANE=1)
```

Related groups re-run green: 39 in the residue / fullgen-white / composite group.
