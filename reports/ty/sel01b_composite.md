# sel-01b — product pictures by compositing the real product

Branch `ty/sel-01b` (from `staging`). Owner redesign 2026-11-08: the product pixels come from
the upload, only the scene is generated. This report is the evidence for the code, the measured
editor choice, and the three-brief proof run.

## What was built

| File | Job |
| --- | --- |
| `Northstar_backend/product_cutout.py` | Four cutout candidates (background distance, LAB/Otsu, GrabCut, BiRefNet) plus the measurements: coverage, edge gradient width, boundary roughness, frame-border contact, bbox. `rembg` is named and **refused** when asked for — it is not installed and nothing was pulled. |
| `tools/seller_tester/scene_render.py` | Scene generation through `tools/comfy_lane.py`: a fresh ComfyUI per job, stop verified (port 8188 closed), `tools/gpu_budget.py` lock held, RAM floor checked. SDXL / SD1.5 / FLUX 3 graphs; the cutout can run inside the same lane. `synthetic_scene` exists only as an explicitly-labelled fallback. |
| `tools/seller_tester/generators.py` | `CompositeGenerator`: same interface as `stored`/`comfy` (`pair`, `generate`), plus per-brief `records` (route, method, scene source, product box, identity SSIM, upscale). Fails with `GeneratorUnavailable` and produces no file when the lane refuses. |
| `tools/seller_tester/briefs.py` | `fidelity` (`exact`/`tolerant`), `brief_fidelity()`, `route_for_brief()`; validation of the new field; `validate_catalog(require_coverage=False)` for the focused proof catalog. |
| `tools/seller_tester/harness.py` | Each result now carries `fidelity`, `route`, the generation record and the full reference-check verdict; `scene_source` is passed to the scorer. |
| `tools/seller_tester/scorers.py` | A picture whose scene is `synthetic` is `cannot_verify` and cannot pass. |
| `tools/seller_tester/reference_check.py` | Text verdict now records both OCR strings; a blank description is `cannot_verify`, not a 1.0 match. |
| `tools/seller_tester/editor_bench.py` | Measures the cutout editors on the three Mogra uploads and writes the `editors` leaderboard row through `tools/model_scout.py`. |
| `tools/seller_tester/mogra_briefs.json` | The three real-upload briefs (`MG-C01`, `MG-C02`, `MG-C03`), all `fidelity: exact`. |
| `tools/seller_tester/cli.py` | `composite` subcommand; `editor_bench` module CLI. |
| `ty/model_roles.json` | New `editors` role (`eval: cutout`). |
| `tools/model_scout/evals/cutout.json` | The eval set: three cases, one per Mogra asset. |
| `Northstar_backend/test_seller_tester_composite.py` | 17 tests (below). |
| `provenance.csv` | Six appended rows (licences + install method). |

## Editor leaderboard (measured, not preferred)

Eval: `tools/model_scout/evals/cutout.json` (3 Mogra assets). Items per asset: coverage consistent
with the reference's own corner mask (not applicable when the reference is full-bleed), alpha does
not own the frame border, printed-text recall ≥ 0.60 on the white composite, alpha edge band ≤ 8 px,
≤ 60 s. Ranking: correct items, then mean edge width, then latency.

| method | correct / items | mean edge | latency (mean/asset) | licence | status |
| --- | --- | --- | --- | --- | --- |
| **BiRefNet** (`birefnet.safetensors`) | **14 / 14** | **1.83 px** | **3.34 s** (in-lane, incl. upload+download) | MIT | measured, winner |
| GrabCut (OpenCV) | 14 / 14 | 5.08 px | 5.11 s | Apache-2.0 | measured, fallback |
| background distance + morphology | 13 / 14 | 4.96 px | 0.027 s | Apache-2.0 + BSD-3 | measured, fallback (fails the full-bleed asset) |
| LAB + Otsu | 10 / 14 | 4.85 px | 0.096 s | Apache-2.0 + BSD-3 | measured |
| rembg | — | — | — | MIT / U-2-Net Apache-2.0 | **not installed**, nothing pulled |

Per-asset detail (coverage / border contact / edge px / OCR recall):

| method | pair_main | pair_lifestyle | forest_dusk |
| --- | --- | --- | --- |
| BiRefNet | 0.495 / 0.00 / 2.64 / 1.00 | 0.454 / 0.00 / 1.56 / 1.00 | 0.503 / 0.00 / 1.29 / 1.00 |
| GrabCut | 0.411 / 0.00 / 7.55 / 0.86 | 0.422 / 0.00 / 4.68 / 1.00 | 0.475 / 0.00 / 3.00 / 1.00 |
| background distance | 0.448 / 0.00 / 7.41 / 0.86 | 0.411 / 0.00 / 4.55 / 0.80 | **0.859 / 0.75** / 2.92 / 1.00 |
| LAB + Otsu | 0.413 / 0.00 / 7.24 / 0.57 | 0.378 / 0.00 / 4.42 / 0.00 | 0.376 / 0.22 / 2.88 / 0.00 |

The full-bleed forest mockup is where the naive method breaks: background distance keeps **75 % of
the frame border** as "product", i.e. it would paste the old forest scene into the new one. BiRefNet
and GrabCut cut the packs out (`border 0.00`). That asset's coverage item is reported as not
applicable because its corner mask (0.85) describes foliage, not a silhouette — using it as ground
truth would have penalised the correct cutouts.

**Winner: BiRefNet.** Tied on items with GrabCut at 14/14 and wins on the measured edge (1.83 px vs
5.08 px) with perfect OCR recall. It runs inside the scene lane, so it adds no second GPU job.
GrabCut stays the lane-free fallback (14/14).

Stored in two places, both from the scout's own machinery
(`model_scout.build_leaderboard` → `write_leaderboard`):

* `ty/model_leaderboard.json` → `roles.editors` (measurements + recommendation; `keep-incumbent`,
  `birefnet` — nothing cleared the +2 swap margin);
* mirror `state/intel/models.json`;
* full per-asset evidence `state/seller/editor_bench.json`.

## Fidelity routing

| brief | route | why |
| --- | --- | --- |
| `fidelity: exact` (default for any reference brief) | `composite` | the seller's pixels must survive |
| `fidelity: tolerant` | `full_generation` | nothing has to be preserved |
| `source_mode: prompt_only` | `full_generation` always | there is no product to cut out |

Every result row records `fidelity` and `route`; the generator's record adds the method, the scene
source, the lane stop evidence, the product box, the identity SSIM and any upscale.

## Proof run — three Mogra uploads end to end

Command: `python -m tools.seller_tester composite --limit 3` (SDXL scene, 768 px, BiRefNet in-lane,
upscaled to the brief's 1536 px). Artefacts: `renders/seller_composite/MG-C0{1,2,3}.png`.
Summary: `state/seller/composite_proof.json`. Room cost: 3 lanes, each `stopped: true` after ~1.5 s.

| brief | route | scene | identity SSIM | OCR recall | key words found | text-embedding sim. | colour gate | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MG-C01 (white main) | composite | generated | 0.9996 | **0.778** (7/9) | mogra, organics, organic, organislionsmane, shiitake, mushroompowder, mograorganics | 0.8665 | false | **failed** — score 60: background corners 81-158 vs 255±14, subject fill 85.5 % > 85 % |
| MG-C02 (greenhouse lifestyle) | composite | generated | 0.9993 | **0.750** (9/12) | organics, organic, organie, organcs, organis, lionsmane, shitake, mushroom, powder | 0.8732 | false | **passed** — 75 |
| MG-C03 (forest mockup) | composite | generated | 0.9994 | **1.000** (10/10) | mogra, organics, healthyorganic, healthy, organic, organiclionsmane, shiitake, mushroom, powder, mushroompowder | 0.9744 | false | **passed** — 100 |

Every brief: `decided_by: printed_text`, `colour_gate: false` (colour is a diagnostic and decided
nothing), subject placed inside the frame with a measured contact shadow, and the product pixels are
the upload's own (identity SSIM ≥ 0.999; visually confirmed on the artefacts).

The one failure is honest and useful: a *generated* "white studio" scene is a grey room with a
horizon (`corners (158,157,158) (94,95,95) (81,83,82) (119,120,122)`), so the white-background-main
brief fails its background constraint even though the product fidelity check passed. That is a scene
problem, not a cutout problem, and it is exactly what the constraint is for.

The media lane was also exercised and refused twice while another lane held `qwen2.5vl:7b` (≈7 GB
VRAM, and free RAM fell to 2.8 GB):

```
generator unavailable: render refused: 2.9 GB free RAM is below the 3 GB floor
generator unavailable: scene render failed: RuntimeError: flux3 render failed: ... 'Fault failed: 2'
```

Those attempts produced no file and no scored result — a refused lane is a failure, not a pass.
The final run went through when the headroom returned; the same three briefs with
`--renderer synthetic` produce `cannot_verify` (proved separately, and pinned by a test).

## Tests

```
python -m pytest Northstar_backend/test_seller_tester_composite.py Northstar_backend/test_seller_tester.py -q
61 passed in 10.91s
```

New cases: exact/tolerant/prompt-only routing, reference default = exact, refused lane raises and
writes no artefact and stops the pass, cutout on a synthetic image produces sane alpha (coverage
within 0.08 of the known subject, border 0, edge ≤ 8 px, bbox), an uninstalled method is refused
rather than substituted, full-bleed references do not judge coverage, the composite keeps the
subject inside the frame and its pixels, a tolerant brief generates instead of compositing, the
reference check decides on OCR text with `colour_gate: false`, colour cannot rescue missing text,
OCR is actually called on both pictures, blank descriptions are `cannot_verify`, a synthetic-scene
picture cannot pass, and the harness records route + fidelity.

## What I could not do, and what it costs

* **1536 px scenes.** FLUX 3 failed at 1536 (`cuDNN Frontend: No valid execution plans built`) and
  later at every size (`Fault failed: 2`, comfy-aimdo vbar) while another lane held ≈7 GB VRAM; SDXL
  rendered at 768 only. The proof therefore renders 768 and Lanczos-upscales to the brief's 1536,
  recorded as `upscaled_from/upscaled_to` — it adds no detail.
* **Vision-description embedding.** The check's `meaning` score is `null` because no local vision
  description was produced (the judge is off, and the VLM was the other lane's resource). The
  reported embedding numbers are text embeddings of the OCR text vs the reference's own text — a
  real measurement, but not the vision-description comparison.
* **rembg** is not installed and was not pulled; it stays a leaderboard row marked `not_installed`.
* **MG-C01** still fails on background. Fixing it needs either a flat-colour scene pass (not a
  generated photo) or a compositor that keys the product onto a true white sweep.
* **`prompt_only` full generation** is wired and routed, but not exercised in this proof: every
  Mogra brief is `exact`, and running a full generation would spend the same contested lane without
  adding fidelity evidence.
