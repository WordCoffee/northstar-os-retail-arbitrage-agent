# D-018 — the fill instrument can see a white product on a white canvas

Half of unit `fix-shadow-and-white-fill`. D-018 is fixed; **D-017 is not** (see the end).

## What was wrong

ST-024 read **20.7 %** against a 24 % floor and ST-031 **19.8 %** against 20 %
(`reports/ty/white_main_pass.json`). The pictures were fine; the instrument was blind.
`check_subject_fill` measured the product as *the share of pixels that differ from the
corner colour*, and a white product on a 255 canvas differs by about 5 levels against a
distance of 20, so it found almost nothing.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/scorers.py` | `_product_mask_from_cutout()` maps the product's own silhouette (the saved cutout, trimmed to its alpha box) onto the frame inside the recorded product box. `check_subject_fill(..., subject_mask=)` uses it **only when the corner instrument is blind** (it found under 5 % on a flat background) and the mask finds at least 5 %. Every other picture keeps exactly the instrument it was scored with. The check reports `instrument: "cutout_mask"` and keeps the blind reading as `corner_fill_pct`. |
| `Northstar_backend/product_picture.py` | `_place_on_flat()` returns the cutout; `build()` records `product_box` (the same box it already wrote as `background.box`) and writes `<face>.cutout.png` beside `product_<face>.png`. Without that provenance the fallback cannot fire on a real picture — measured: ST-024 and ST-031 have `product_box: None` and no cutout in their records. |

**No published score changes.** Re-scoring all twelve prompt-only artefacts from
`renders/heldout_prompt_only10` with the new code: `instrument` is `corner_colour` on
**12 of 12**, i.e. the fallback never fires where the instrument works.

## Tests

```
python -m pytest Northstar_backend/test_subject_fill_instrument.py -q          -> 8 passed
python -m pytest Northstar_backend/test_product_picture_white_main.py -q      -> 8 passed
python -m pytest Northstar_backend/test_package_forms.py test_package_cylinder_form.py \
  test_product_composite_framing.py test_seller_label_warp.py -q             -> 74 passed
python -m pytest Northstar_backend/test_seller_tester.py \
  test_seller_tester_composite.py -q                                        -> 89 passed
```

New tests: a white product on white is measured by its cutout (36 % where the corner
instrument reads under 2 %); a visible product keeps the corner instrument even when a
cutout is supplied; `_place_on_flat` returns a cutout whose aspect is its box; `build`
records `product_box` and writes the `.cutout.png`.

## Honest limit

ST-024 and ST-031 were rendered **before** this provenance existed, so their records carry
no cutout and no box; their new number cannot be produced without re-rendering them. The
instrument is proven by test against a known 36 % product, not by a re-run of those two
briefs. A white-main pass at the pinned seeds is the measurement that closes it.

## D-017 is still open

A plate's opaque contact shadow survives `_place_on_flat`'s colour threshold, and the code
says so in its own comment: "removing it needs a real matte (BiRefNet in the lane)". That
was true before this unit and is true after it. Filed as its own job
(`fix-plate-shadow-matte`), not claimed as done.
