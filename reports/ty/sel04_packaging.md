# sel-04 — packaging deliverables are built by the app and scored, and six of eight fail

Unit `sel-04-packaging`. Tag `ty-dir-sel-04-packaging`. Rollback point
`rollback/pre-sel04-20261111` at `e25bc051`.

## What this means

A picture can be retouched until it passes. A **dieline** either folds into the package the
brief describes or it does not, so packaging is the one seller deliverable that can be
scored without a judge. The app already owns the engine — `design_studio_print`
(`build_from_template` behind a geometry gate, `render_svg`, `render_pdf`) and
`package_readiness.assess_dieline`. Nothing exercised it end to end, and no seller brief
asked for packaging at all.

## What was added

| piece | what it does |
|---|---|
| `ty/seller_briefs_packaging.json` | **8 briefs across 4 real templates** (`doypack`, `tuck_end`, `rsc_box`, `sleeve`), each naming a product, a brand, the parameters a manufacturer would receive, and the panels the manufactured package has |
| `tools/seller_tester/packaging.py` | `build_packaging` (build → SVG + PDF + record, or `PackagingRefused` with the engine's own words), seven checks, `run_pass` with a summary and a gap file |
| `tools/seller_tester/cli.py` | `python -m tools.seller_tester packaging [--limit N]` |
| `Northstar_backend/test_seller_packaging.py` | 9 checks |

The seven checks, each a property a print shop would reject the file for:

1. **sheet** — the SVG declares the same millimetre sheet the build measured;
2. **panels** — doypack: named faces (`front`, `back`, `gusset`) with positive size;
   carton/sleeve: the body-face widths **plus the glue tab plus both bleeds span the
   sheet** (measured: 4 × 45 + 15 + 2 × 3 = 201 mm), which is what proves no face was
   dropped from the layout;
3. **bleed** — at least what the brief asks;
4. **safe** — at least what the brief asks, or skipped with the reason when the template
   declares none;
5. **layers** — trim, fold, safe and bleed are separate SVG layers, the difference between
   an editable file and a flattened picture;
6. **pdf** — the PDF opens and its page is the sheet in points;
7. **readiness** — the app's own `assess_dieline`: assessed, and no blockers. Warnings
   (the doypack proportion ladder, "planning dieline, not a die") are reported and do not
   fail, which is `package_readiness`'s own rule.

## The pass, measured

```
python -m tools.seller_tester packaging
-> selected 8, scored 8, passed 2, failed 6, refused 0, pass_rate 25.0, mean 78.6
```

`reports/ty/packaging_pass.json`, gaps in `state/seller/packaging_gaps.json`, artefacts in
`renders/packaging/PK-00N.svg|pdf`.

| brief | template | score | failed |
|---|---|---|---|
| PK-001 MOGRA lion's mane 170 g | doypack | **100.0** | — |
| PK-005 MOGRA travel sachet 4 g | doypack | **100.0** | — |
| PK-002 Harbor body oil carton | tuck_end | 71.4 | `layers`, `readiness` |
| PK-003 Pine Paws joint chews | rsc_box | 71.4 | `layers`, `readiness` |
| PK-004 Word Coffee sleeve 250 g | sleeve | 71.4 | `layers`, `readiness` |
| PK-006 Harbor retinol carton | tuck_end | 71.4 | `layers`, `readiness` |
| PK-007 Pine Paws dental sticks | rsc_box | 71.4 | `layers`, `readiness` |
| PK-008 Word Coffee sleeve 500 g | sleeve | 71.4 | `layers`, `readiness` |

**This is a product defect, not a brief problem.** Both doypacks carry a `safe` layer;
every carton and sleeve does not — measured layers `['bleed', 'fold', 'info', 'trim']`
against the doypack's `['bleed', 'fold', 'info', 'marks', 'safe', 'trim']`. `build_carton`
never emits one, and `package_readiness.REQUIRED_LAYERS` is
`("trim", "fold", "safe")`, so **the app's own readiness gate refuses every folding carton
and sleeve it prints**, quoting itself: *"dieline is missing its 'safe' layer"*. Filed as
**D-023** and queued as `fix-carton-safe-layer`.

The other five checks pass on all eight briefs: sheets, panels, bleed, PDF pages, and the
`safe` field where the template has one.

## Tests

```
python -m pytest Northstar_backend/test_seller_packaging.py -q          -> 9 passed
```

* a doypack brief builds a layered SVG and a PDF, with `front`/`back`/`gusset` measured;
* a freshly built doypack scores 100.0;
* the geometry gate refuses a `rsc_box` whose flaps are deeper than its body, **by name**
  (`tab_deeper_than_body`), and writes no file;
* a missing `fold` layer fails `layers`;
* the PDF page is the sheet in points, and a 20 mm lie about the sheet is caught;
* a bleed below the brief fails;
* `run_pass` records a refusal, files the gap with the engine's reason, and counts it;
* the shipped catalog is 8 briefs across 4 templates;
* a carton's body widths span its sheet (with the bleed), and dropping a face breaks it.

## Honest limits

* **The dieline is geometry, not artwork.** A print-ready *file* needs the label art
  placed on the panels; this lane scores the die, the panels, the bleed and the layers, and
  says nothing about the printed copy. That is the next packaging step (`pack-*` jobs
  already in the queue cover artwork forms).
* **The proportion ladder is advisory.** PK-001's 40 mm gusset is "far below the published
  70 mm for a 100 g pouch" — a warning from the app's own ladder, reported in the summary
  and not hidden, but it does not fail the brief. Changing it would be inventing a
  measurement the owner has not supplied.
* **Six failures are the honest number.** The lane is not tuned to make its own catalog
  pass: the bar is the app's readiness gate, and the app does not meet it for cartons.
