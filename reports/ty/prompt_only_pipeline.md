# Prompt-only: what the pipeline change did, and what it did not

Owner ask (2026-11-10): *build prompt-only as generate, cut out, deterministic stages; give a
per-check failure table for the twelve; separate product body from label; rescore and report. Do not
loosen the bar.*

## The result

| version | pipeline | scored | passed | mean |
|---|---|---|---|---|
| v1 | generate only | 12 | 0 | 37.5 |
| v2 | generate → cut → compose → layout | 12 | 0 | 34.5 |
| v3 | + the canvas at the brief's size | 12 | 0 | 41.5 |
| v4 | + the compose step actually running | **12** | **9** | **86.4** |

Nine of twelve now pass, against twelve of twelve failing before. **No rule was loosened**: the
briefs, the constraints and the scorer are the same files they were at v1.

## Why v2 and v3 scored 0: the compose step never ran

`_generate_cut_and_compose` used `np.asarray` without importing numpy. The `except Exception` around
the whole stage caught the `NameError` and returned the raw plate with a record entry saying
`method: "refused"` — so every artefact stayed at the lane's **768×768**, and:

- `dimensions` failed **12 of 12** (`768x768 vs min 2000x2000`);
- `background`, `alpha_matte` and `subject_fill` failed on the un-composed plate;
- the deterministic layout stages never ran either, because they sit after the compose call.

A refusal that is indistinguishable from a fallback is a lie with a timestamp on it. The fix is two
lines — import numpy, and re-raise programmer errors (`NameError`, `AttributeError`, `TypeError`,
`ImportError`) as `GeneratorUnavailable` so a stage that *cannot* run never looks like a stage that
*declined* to. A `ValueError` (an empty cutout) is still a refusal, because that is a real business
outcome.

## Per-check failure table, v4

| check | failed in | of briefs | skipped | most common reason |
|---|---|---|---|---|
| `alpha_matte` | **7** | 12 | 4 | border mean 199.3 (>= 249) — the white-matte situations, on a generated scene |
| `subject_fill` | **2** | 12 | 0 | subject fill 94.3 % vs 8–50 % |
| `background` | **1** | 12 | 4 | corners not the requested level |
| `dimensions` | **0** | 12 | 0 | — (was 12 of 12) |
| `aspect` | **0** | 12 | 0 | — |
| `text_free` | **0** | 12 | 3 | — |
| `reference_subject` | 0 | 12 | **12** | no reference exists, so it does not apply |
| `product_region` | 0 | 12 | **12** | no cutout to preserve, so it does not apply |

The two skipped checks are recorded as skipped with a reason, not as passes.

## Body and label, separated

The model now draws the **body** and the label is composed deterministically and warped on
(`tools/seller_tester/label_warp.py`, six tests):

- `compose_label(brief)` builds the label panel with Pillow — brand, product, weight, lines — from
  the brief, so it is readable by construction;
- `warp_label(...)` maps it onto a quad on the upper front of the body, multiplies by the body's own
  luminance so it sits *on* the material, and writes only inside the quad (the bounding box of a
  trapezoid is not the trapezoid);
- it is deterministic: same brief, same bytes.

The label path is live for a brief with `label_mode: "warp"`. The twelve held-out briefs are being
re-run with it one brief at a time rather than assumed: at v4 they still carry the generated
lettering, and the number above is that run, not a projection.

## What is still wrong

1. **`alpha_matte` 7 of 12.** The white-matte situations ask for a clean near-white border, and a
   generated scene does not have one. That is the same finding the uploaded-reference held-out run
   produced, and the answer is the same: those situations need a composed background, not a render.
2. **Two briefs at 63.6 and 70.0** — fill and background, both fixable with the brief's own numbers
   in the prompt (queued as `sel-09`).
3. **The label path has not been scored yet.** It is built and tested; the rescore is the next run.
