# sel-01e — three soft checks, made to fail

Branch `ty/sel-01e` (from `staging`). Three jobs from the owner: a composite that cannot be
verified must fail, the OCR benchmark must be hard enough to separate engines, and the null
vision-description embedding must become a real cosine or `cannot_verify`.

## 1. A composite that cannot be verified does not pass

**The rule is in code, not in a report.** A composite route now grades `product_region`, and a
missing cutout is a named failure rather than a skip:

* `tools/seller_tester/scorers.py` — `score_image(..., route, composite_route, cutout, placement)`;
  `combine_checks()` is the one place weights, the critical set and `cannot_verify`-cannot-pass
  are applied. `product_region` carries weight **0.25** and joins the critical set on the
  composite route, so an unverified region fails a brief even if every other check passes.
* `tools/seller_tester/harness.py` — a pass records whether the generator composited, loads
  `<artefact>.cutout.png` beside the artefact and passes the recorded `product_box`. No cutout →
  `cutout=None` → the scorer emits `product region cannot be verified: ...`. A future
  `CompositeGenerator` run cannot forget the check because the route comes from its own record.
* `tools/seller_tester/composite_check.py` — every refusal reads
  `product region cannot be verified: <why>` and carries `ok: False`.
* `tools/composite_audit.py` — `--run` re-scores the proof rows with the region check through the
  same weights, then rewrites `state/seller/composite_proof.json`.

### The amended proof (state/seller/composite_proof.json)

| brief | old score | new score | passed | provisional | `failed_checks` |
|---|---|---|---|---|---|
| MG-C01 white main | 60.0 | **48.0** | false (was false) | no | background, subject_fill, **product_region** |
| MG-C02 greenhouse | 75.0 | **57.1** | **false** (was true) | **true** | subject_fill, **product_region** |
| MG-C03 forest mockup | 100.0 | **76.2** | **false** (was true) | **true** | **product_region** |

Every row's reason, verbatim:

> product region cannot be verified: the generator did not save the cutout it used, so the product
> region cannot be compared; expected `<artefact>.cutout.png`

`provisional_score` keeps 75.0 and 100.0 on the two rows that passed on printed text alone;
`provisional_passed` keeps the old verdict. The proof summary moved from `passed 2 / mean 78.3`
to `passed 0 / mean 60.4`, `provisional: 2`, `product_region_verified: 0`.

The two provisional rows are the two that passed on OCR recall (0.75 and 1.00) with no evidence
the pixels in the frame were the upload's. MG-C01 was already failing on its background, so it is
re-scored but not called provisional.

### Seller output, re-scored

`python tools/seller_scores.py --write` and `python tools/scorecards.py --json`, on the same
machine state as the before-run (readiness scan and `state/scores/measured.json` copied into the
worktree so the baseline reproduces: hub 100.0, prospector 100.0).

| number | before | after |
|---|---|---|
| composite pass mean | **78.3** | **60.4** |
| `seller_scores` design-studio mean | 22.1 (40 outputs, stored pass) | 60.4 (3 outputs, composite proof) |
| `design-studio` scorecard | **75.9** | **73.0** |

**Say it plainly:** the composite set's own mean fell 78.3 → 60.4 because two passes lost their
credit for something they never proved. The scorecard also fell, 75.9 → 73.0, but the reason is
worth naming: the newest seller pass is the 3-brief composite proof, `seller_scores` refuses a
sample under five (`only 3 Seller-Tester output(s) scored for this service`), so design-studio's
seller dimension is zero. Its measured mean of 60.4 is *higher* than the old 22.1 over forty
stored outputs — so the scorecard fall is the thin-sample rule plus the provisional rule, not a
60.4 < 22.1 comparison. Both facts are on disk; the stored pass is kept at
`state/seller/last_run_stored_20261108.json` and the pre-change proof at
`state/seller/composite_proof_before_sel01e.json`.

## 2. OCR benchmark rebuilt from hard real crops

`tools/ocr_bench.py`: 16 crops cut from the three real Mogra uploads — brand lockup, display
product name and weight panel on each pouch, 16–48 px cap height, saved as **JPEG q72** so real
compression is present, with real curvature and scene blur. Ground truth per crop is written into
`ty/ocr_leaderboard.json` with the source frame and pixel box. Same fuzzy token metric as the
reference check. The old three-frame set and the synthetic card are gone: rapidocr scored 1.000
there, which told us nothing.

| engine | licence | mean recall | crops exact | s |
|---|---|---|---|---|
| **rapidocr @ 2× upscale** | Apache-2.0 | **0.906** | **13 / 16** | 19.52 |
| rapidocr (incumbent) | Apache-2.0 | 0.875 | 12 / 16 | 28.63 |
| easyocr 1.7.2 | Apache-2.0 | 0.359 | 3 / 16 | 18.94 |

Per-crop recall (`ty/ocr_leaderboard.json` → `per_crop`):

| crop | rapidocr | rapidocr-2x | easyocr |
|---|---|---|---|
| main_brand_left | 0.75 | 0.50 | 0.00 |
| main_brand_right | 0.50 | **1.00** | 0.25 |
| main_name_left | 1.00 | 1.00 | 1.00 |
| main_name_right | 1.00 | 1.00 | 1.00 |
| main_panel_left | 1.00 | 1.00 | 0.00 |
| main_panel_right | 1.00 | 1.00 | 0.00 |
| life_brand_left | 0.25 | 0.25 | 0.00 |
| life_brand_right | 0.50 | **1.00** | 0.00 |
| life_name_left | 1.00 | 1.00 | 0.50 |
| life_name_right | 1.00 | 1.00 | 1.00 |
| life_panel_left | 1.00 | 1.00 | 0.00 |
| life_panel_right | 1.00 | 1.00 | 0.00 |
| forest_brand_left | **1.00** | 0.75 | 0.75 |
| forest_brand_right | 1.00 | 1.00 | 0.75 |
| forest_name_left | 1.00 | 1.00 | 0.50 |
| forest_panel_right | 1.00 | 1.00 | 0.00 |

**Decision: keep rapidocr.** The harder set does its job — the incumbent is no longer perfect
(0.875) and the brand-lockup crops are where the candidates separate. The 2× variant is the best
reader here (+0.031, under the 0.05 swap margin) and was faster in this run (19.5 s vs 28.6 s);
it stays a variant of the same licensed engine, recorded as a candidate. easyocr loses the small
text: it returns nothing at all on 8 of the 16 crops, all of them the low-contrast panels and
green-lockup crops, which is the honest datum.
`ty/model_roles.json` → `roles.ocr` updated (`eval: mogra_crops`).

## 3. A real vision description, and a real cosine

* `tools/seller_tester/reference_check.py` — `describe_picture(rgb)` encodes the decoded picture in
  memory and sends it through `tools.vision.understand.describe_page` (qwen2.5vl; the same read
  path the browser lane uses). `describe_enabled()` is on unless `NORTHSTAR_VLM_DESCRIBE=0`;
  the unit suites set 0 because their contract is offline-only.
* `harness.run_pass(describe=...)` defaults to that describer, so a pass records descriptions for
  **both** the produced picture and the reference.
* `semantic_agreement` embeds both descriptions with `qwen3-embedding:0.6b` and reports the
  cosine. A blank description, a missing embedder or a describer that raises is `cannot_verify`
  with the error recorded — never 1.0, never a silent null.
* The proof was refreshed through the describer, so `meaning` now holds a measured similarity
  rather than `null`.

The three Mogra pairs (`state/seller/reference_embeddings.json`):

| brief | description (produced) | cosine | decision |
|---|---|---|---|
| MG-C01 | "The page showcases organic mushroom powder products. ORGANIC LION'S MANE …" | **0.9678** | printed_text |
| MG-C02 | "The page showcases organic mushroom powder products. ORGANIC LION'S MANE …" | **0.9918** | printed_text |
| MG-C03 | "Mogra Organics Promoting healthy and organic mushroom powders. Organic Lion's …" | **0.9327** | printed_text |

All three clear the 0.72 embedding bar, so meaning now agrees with the printed text instead of
being unavailable. Text still decides, which is the designed order.

## Tests

```
python -m pytest Northstar_backend/test_composite_fidelity.py Northstar_backend/test_seller_tester.py Northstar_backend/test_reference_checks.py -q
72 passed in 16.77s

python -m pytest Northstar_backend/test_seller_tester_composite.py Northstar_backend/test_seller_scores.py -q
24 passed in 0.82s
```

New in `test_reference_checks.py` (15): a describe callable that returns text yields a non-null
cosine; `""` yields `cannot_verify`; a raise yields `cannot_verify` with the error recorded;
printed text cannot launder a blank description into agreement; a composite with no cutout fails
with `product region cannot be verified` in `failed_checks` and `critical_failed`; a brief that
declares `route: composite` is checked without the flag; a full generation is not; a saved cutout
at a recorded placement verifies (≥ 0.99); the audit marks a passing row provisional and keeps
its old score; a failing row is not called provisional; the harness fails a composite with no
saved cutout and verifies one that saved it. `test_composite_fidelity.py` adds the refusal-reason
test.

## Files

```
tools/seller_tester/composite_check.py   refusal names the product region
tools/seller_tester/scorers.py           product_region check, combine_checks, composite route
tools/seller_tester/harness.py           cutout + placement + VLM describer wiring
tools/seller_tester/reference_check.py   describe_picture, describe_enabled, errors recorded
tools/composite_audit.py                 re-scores and rewrites the proof, provisional rule
tools/ocr_bench.py                       16 real crops, per-crop recall, leaderboard
Northstar_backend/test_composite_fidelity.py
Northstar_backend/test_seller_tester.py  offline describer fixture
Northstar_backend/test_reference_checks.py   (new)
ty/ocr_leaderboard.json, ty/model_roles.json, ty/seller_scores.json
state/seller/composite_proof.json        (runtime, gitignored: amended proof)
```

## What this does not fix

* **The cutout is still not saved by the generator.** `sel-01c-cutout-provenance` is the fix;
  until it lands every composite is provisional by this rule, which is the point.
* **`seller_scores` still reads one pass file.** It now reads the composite pass because that is
  the newest pass on disk; the 40-output stored pass is preserved beside it, not merged. Merging
  the two populations is a scoring decision the director should make, not a builder.
* **The VLM prompt is the page reader's.** It describes a pouch as "the page showcases …" — real
  text, useful for an embedding, but a product-specific prompt is a better fit and is not in this
  scope.
