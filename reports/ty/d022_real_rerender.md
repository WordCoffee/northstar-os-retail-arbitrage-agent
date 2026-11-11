# D-022 real re-render — the composite's shadow is gone; the plate's shadow is not

Unit `d022-real-rerender`. Tag `ty-dir-d022-real-rerender`. Rollback point
`rollback/pre-d022-rerender-20261111` at `9d4568cd`.

## What was owed

D-022 closed on a test, not on a picture: `_generate_cut_and_compose` passes
`shadow=not flat(brief)`, so the composite no longer paints its own contact shadow under a
main image. The *published* artefacts were still the old ones, so the residue number that
found the defect (10.2 – 25.6 % across eight outputs) had no after-number. This unit runs
real lanes to produce one, twice: at the model's original seeds, and at fresh seeds.

## What ran (commands, exit codes, artefacts)

| run | command | result |
|---|---|---|
| fresh seeds | `python -m tools.seller_tester composite --catalog ty/_briefs_prompt_only.json --renderer comfy --layout deterministic --scene-size 768 --steps 20 --model sdxl --out-dir renders/heldout_prompt_only11 --summary-out reports/ty/d022_real_pass.json` | **3 selected, 3 scored, 3 passed, mean 100.0.** Seeds 2771967432 / 2726882844 / 2572653623. The 4th brief was refused by the lane: `budget: refused: 8.54 GB free - 8.2 GB needed = 0.34 GB < 1.0 GB reserve` |
| pinned seeds | `python tools/rerender_prompt_only.py --previous reports/ty/label_conform_pass.json --limit 3 --out-dir renders/d022_pinned --summary-out reports/ty/d022_pinned_pass.json` | **3 seeds reused, 0 random. 2 passed, 1 failed, mean 96.7** |

Every render records `lane.stopped.ok = true` in `state/gpu/comfy_lanes.jsonl`; the GPU lock
was free before each run and ComfyUI was not resident after (`nvidia-smi` 2040 MiB used, the
embedding model only).

## The number at an identical seed

| brief | seed | before (D-020 audit) | after (this unit) | verdict |
|---|---|---|---|---|
| PO-001 white main | 2747063199 | **25.647 %** residue, 1 025 874 px | **14.760 %**, 590 541 px (587 151 neutral) | still over the 0.5 % limit — **fails `matte_residue` at 90.0** |
| PO-002 lifestyle | 3952987930 | free background, not checked | **100.0**, free background kept | pass |
| PO-003 scale reference | 3268127863 | 11.922 % | **0.000 %**, 0 px | pass |

**The composite's shadow is measurably gone: −10.887 points, −435 333 px at the same seed,
same model, same steps, same size.** The single variable between the two pictures is the
`shadow=not flat(brief)` branch.

**And the main image is still not clean.** The contact sheet
`reports/ty/d022_pinned_diagnostic.png` draws the recorded silhouette in blue and every
off-white painted pixel outside it in red. PO-001 at the pinned seed still carries a wide
grey smear to the right of and under the pouch: it is the *plate's* own cast shadow, which
`generators._cut` (grabcut) keeps because it is opaque and attached to the product. Nothing
paints it — the model drew it and the cutout did not remove it.

## The second finding: the instrument can hide it

The same defect scores **0.00 % on a fresh seed** (`renders/heldout_prompt_only11/PO-001.png`)
and **14.76 % on the pinned seed**, on pictures produced by the same code path. The blue
contour in the contact sheet shows why: the silhouette the check is given is a coarse
rectangle over pouch **and** shadow on the fresh seed (1 280 943 px) and a tighter, offset
shape on the pinned seed (881 410 px). Whatever is inside the silhouette is never counted as
residue, so a picture with a visible smear can pass by being *masked* rather than by being
clean.

## Filed

* **D-025** — a full-generation cutout keeps the plate's own cast shadow; the real matte
  (`product_cutout.matte_alpha`, BiRefNet, the D-017 fix) is what removes it, and the
  generation route still uses grabcut. Queued `fix-fullgen-matte-cutout`, rank 1.
* **D-026** — `check_matte_residue` trusts the recorded silhouette, and that silhouette does
  not follow the product on the generation route (too big on one seed, offset on another).
  An instrument that can pass by masking is not an instrument. Queued
  `fix-fullgen-silhouette`, rank 2.

## Honest statement

D-022 is **partially retired**, not closed. What is proven: the composite's painted shadow
no longer ships. What is not: a white-background main image from the generation route is
still not a picture a seller can list, and the score that says otherwise is measuring a
mask. The two open defects are the next two units, in that order.

## Tests

Nothing in this unit changes code. The existing guards that this unit exercised and which
remain green:

```
python -m pytest Northstar_backend/test_matte_residue.py \
  Northstar_backend/test_fullgen_white_composite.py \
  Northstar_backend/test_seller_tester_composite.py -q
-> 39 passed in 8.04s   (exit 0)
```

## Correction, 2026-11-11 (independent verifier)

The run table above cites `reports/ty/d022_real_pass.json` for the **3-brief**
fresh-seed run. That file now holds a **12-brief** run at different seeds, because
the next session re-ran the full catalog to the same summary path. The 3-brief
numbers are therefore no longer reproducible from the file this report points at.

This is the director's editing error, recorded rather than smoothed: an evidence
file another report cites must not be overwritten in place. The 12-brief pass is
its own unit (`reports/ty/d022_real_pass.json`, 12 selected / 12 scored / 12 passed,
mean 100.0) and the pinned-seed run it belongs beside is
`reports/ty/d022_pinned_pass.json`.

*Correction appended by the director after `reports/ty/verify_20261111.md`.*
