# D-023 — cartons carry their safe layer, and the packaging lane goes 6/8 to 8/8

Unit `fix-carton-safe-layer`. Tag `ty-dir-fix-carton-safe-layer`. Rollback point
`rollback/pre-d023-20261111` at `bfbd71a1`.

## What was wrong

`package_readiness.REQUIRED_LAYERS` is `("trim", "fold", "safe")` and `assess_dieline`
blocks any build missing one of them. `build_carton` emitted bleed, trim, fold and info —
never `safe`. So **the app refused every folding carton and sleeve it printed, by name**:
*"dieline is missing its 'safe' layer"*. The first packaging pass measured it as 6 of 8
briefs failing at 71.4 (`reports/ty/sel04_packaging.md`).

## What changed

| file | change |
|---|---|
| `Northstar_backend/design_studio_print.py` | `_panel_blank(..., safe_mm=)` writes one **safe rectangle per body face**, inset by the margin from the trim and from both folds; a face narrower than twice the margin gets no rectangle rather than an inverted one. The glue tab carries no print and gets none. `build_carton(..., safe_mm=)` and the three carton templates (`rsc_box`, `tuck_end`, `sleeve`) now declare `safe_mm` (default 3 mm) as an editable parameter, and `build_from_template` passes it through. `meta.safe_mm` is recorded so the margin a file was built with is readable. |
| `Northstar_backend/test_carton_safe_layer.py` | 13 checks. |

## Measured

```
python -m pytest Northstar_backend/test_carton_safe_layer.py -q     -> 13 passed
python -m tools.seller_tester packaging                            -> 8 scored, 8 passed, mean 100.0
```

Before → after on the packaging lane, same eight briefs, same engine:

| | before | after |
|---|---|---|
| passed | 2 / 8 | **8 / 8** |
| mean | 78.6 | **100.0** |
| failing checks | `layers` + `readiness` on six cartons | — |

`reports/ty/packaging_pass.json` is the after-run; `renders/packaging/` holds the eight
SVG/PDF pairs. `safe_mm` is now readable per artefact: 5 mm on the two doypacks, 3 mm on the
six cartons.

Regression groups, all green: `test_design_studio_print`, `test_package_readiness`,
`test_dieline_geometry`, `test_dieline_geometry_api`, `test_specialists`, `test_prepress`
(80 passed) and `test_seller_packaging`, `test_carton_safe_layer`,
`test_bojo_tools_publishing`, `test_creative_pipeline_chain`, `test_design_studio_re_ext`
(45 passed).

## The 13 checks, written before the code

* every carton template carries a `safe` layer and a positive margin;
* the margin is the brief's own number (`safe_mm=6` → `meta.safe_mm == 6`);
* each safe rectangle lies **inside the trim by that margin on all four sides**, measured
  against the trim polyline's own bounding box — not against an assumption;
* `package_readiness.assess_dieline` no longer lists a layer blocker for any carton;
* labels and doypacks keep their safe boundary (additive, not a rewrite).

## Honest limits

* **A safe margin is a layout rule, not a print proof.** The rectangle marks where copy may
  live; whether the artwork obeys it is checked when artwork is placed, not here.
* **The default 3 mm is a judgement.** The doypack uses 5 mm because its seals need it;
  cartons follow the commercial 3 mm default. It is a parameter per brief, so a converter
  who asks for 4 mm gets 4 mm.
* **The 100.0 is the engine's own verdict on eight briefs**, not a claim that every carton
  a seller could ask for is print-ready. The lane's job is to make the app's gate honest.
