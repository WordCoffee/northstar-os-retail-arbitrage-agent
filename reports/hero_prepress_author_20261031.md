# Hero remediation, surface luminance, local 27B author, print-DPI sidecars

- date: 2026-10-31
- base commits: `7e443d8` (measure_surface verified), `b9c64776` (this build),
  `187706b5` (low-contrast guard + author form note)
- directive: clear the three hero rubric defects, shade labels with the vessel's
  own light, author prompts dynamically on the local 27B, and emit print-ready
  DPI/quad sidecars.

## 1. Hero rubric remediation

`Northstar_backend/listing_image.py` now enforces three guardrails instead of
asserting them afterwards:

- **Background compliance.** Every pixel outside the subject and its clipped
  contact shadow is forced to exact RGB 255,255,255. Alpha-blended subject edges
  survive because the subject alpha mask defines what is kept. `audit_white`
  reports both the whole-image share (`pure_white_ratio`) and the ring share
  (`background_purity`), plus the subject bbox and margins.
- **Safe-zone padding.** The subject is scaled to `DEFAULT_FILL = 0.82` and
  centred; if any margin falls below the 5% trigger, it is rescaled to the 10%
  target and re-centred. The live heroes have ~9% side margins and ~7% bottom
  margin (the bottom includes the visible contact shadow).
- **Ground-shadow normalization.** The contact shadow is an ellipse at the
  subject's base, clipped to a band inside the subject's own footprint (plus 2%
  of canvas below it for a visible ramp). It cannot tint the outer ring, extend
  the subject bbox, or carry a floor gradient.

`Northstar_backend/asset_rubric.py` measures **background purity on the outer
6% ring**, not the whole frame. An 85%-fill product cannot leave 90% of the whole
image white, so the old whole-image statistic made `background_not_white_enough`
mathematically unavoidable. The defect names and thresholds are unchanged; the
statistic now matches what the defect name says. `contact_shadow_or_floor` is
raised only when the background ring is not clean.

Live hero result (4/4):

| format | score | defects | background purity | margins (L,T,R,B) |
|---|---|---|---|---|
| pouch | 95.1 | none | 1.0 | 0.211, 0.091, 0.211, 0.070 |
| box | 90.1 | none | 1.0 | 0.091, 0.105, 0.090, 0.084 |
| bottle | 94.1 | none | 1.0 | 0.321, 0.091, 0.321, 0.070 |
| tube | 95.0 | none | 1.0 | 0.288, 0.091, 0.289, 0.070 |

## 2. Cylindrical and tapered curvature shading

`format_compositors._apply_luminance` extracts the plate's grayscale luminance
`L(x,y)`, normalizes it by the median under the label, and multiplies the label
layer by `1 + strength * (L/median - 1)` (clamped). The bottle applies it to the
resampled label crop; the tube applies it to the warped label before masking.
Default strength is 0.35, so a cream field stays cream while the vessel's
specular highlight and ambient falloff cross the print.

Tests pin the transfer (a left-dark/right-bright plate makes the label left side
darker), and the shading-off identity (a flat label stays flat). The live bottle
and tube heroes show the bottle's shoulder highlight and the tube's side falloff
continuing through the label instead of a flat sticker.

## 3. Local 27B prompt author

`Northstar_backend/prompt_author.py` posts an OpenAI-compatible chat completion
to the local lane at `http://127.0.0.1:8080/v1` (model alias
`northstaros-27b-coder`). The brief is built per job and carries:

- format + verbal form note (crimp/cap, tuck flaps, weld/gusset);
- geometry profile (face/panels, diameter, usable height, clearances);
- product category/substrate/material tier/finish;
- brand facts from `brand_memory` and Memory Bank context from
  `memory_bank.retrieve_context`;
- lighting, camera and background constraints, and the unprinted-plate bans.

Fail-closed: an unreachable lane, an empty completion, or `finish_reason=length`
raises `PromptAuthorUnavailable`; the runner records `author_unavailable` and
does **not** render on a template. The runner authors all four prompts first,
stops the lane, waits for VRAM to drop, then renders. A 5 s settle plus one tiny
warm-up completion avoids the `/health`-ready-but-slot-not-ready reset observed
on the first attempts.

Live authored prompts were format-specific and warning-free, e.g.:

- pouch: "Matte kraft stand-up pouch, 200mm tall, flat continuous matte material,
  pristine plain surface, unprinted uniform texture, sealed top weld, bottom gusset..."
- box: "Flat die-cut box layout in matte kraft, pristine plain surface, unprinted
  uniform texture, flat continuous matte material..."
- bottle: "Amber glass bottle, 60mm diameter, 200mm height, pristine plain
  surface, unprinted uniform texture, flat continuous matte material..."
- tube: "Matte kraft paper tube, 40mm diameter, 160mm height, pristine plain
  surface, unprinted uniform texture..."

The installed lane is the local **Qwen3.8-27B** weights under the
`northstaros-27b-coder` alias. The directive names Qwen 2.5-Coder 27B; the
integration targets the configured local lane, and no cloud model is used.

## 4. Print DPI enforcement and dieline sidecar

`Northstar_backend/print_prep.py`:

- `face_pixels(quad)` measures the TL/TR/BR/BL quad (mean of opposite edges).
- `physical_face(profile)` maps the format to millimetres (box front face, pouch
  width/usable height, bottle label width/height, tube diameter/usable height).
- `dpi_report` computes px/mm and DPI, the required pixels at 300 DPI
  (11.811 px/mm), and the deficit.
- `validate_print` raises `PrintDPIError` when the measured face is below target.
- `emit_sidecar` writes `02_labelled.dieline.json` with the quad, face pixels,
  physical mm, scale factors, DPI metrics, RGB working / CMYK target metadata,
  method, residual, source plate hash and `print_ready`.

`creative_flow.step_compose` now emits the sidecar for every format and, when
`require_print_dpi` is set, gates on the **actual rendered face** rather than the
nominal profile. The nominal shortfall is still recorded as a bind warning. A
low-resolution print job blocks with `resolution_below_300dpi` and keeps the
sidecar with `print_ready: false`.

Live 1024x1024 mockups (honest result: not print-ready at these physical sizes):

| format | measured face px | physical mm | worst DPI | print_ready |
|---|---|---|---|---|
| pouch | ~330 x 1030 | 100 x 170 | 86.8 | false |
| box | ~410 x 690 | 80 x 180 | 92.1 | false |
| bottle | ~255 x 390 | 45 x 80 | 37.0 | false |
| tube | ~290 x 460 | 40 x 132 | 98.9 | false |

To pass, render a larger plate (e.g. 4096²) or reduce the physical face; the
sidecar already reports the exact pixel deficit. The CMYK field is metadata only:
no ICC transform is applied, and the sidecar says so.

## Verification

```
python -m pytest Northstar_backend/test_listing_image.py \
  Northstar_backend/test_asset_rubric.py \
  Northstar_backend/test_format_compositors.py \
  Northstar_backend/test_surface_measure.py \
  Northstar_backend/test_prompt_author.py \
  Northstar_backend/test_print_prep.py \
  Northstar_backend/test_format_integration.py \
  Northstar_backend/test_creative_flow.py \
  Northstar_backend/test_geometry_profiles.py -q
```

**87 passed, 1 skipped.**

| suite | result |
|---|---|
| `test_listing_image.py` | 8 passed |
| `test_asset_rubric.py` | 7 passed |
| `test_format_compositors.py` | 17 passed |
| `test_surface_measure.py` | 11 passed |
| `test_prompt_author.py` | 5 passed |
| `test_print_prep.py` | 8 passed |
| `test_format_integration.py` | 11 passed |
| `test_creative_flow.py` | 6 passed, 1 skipped |
| `test_geometry_profiles.py` | 14 passed |

All edits are UTF-8 without BOM.

## Live run

```
python tools/run_flow_formats.py --out exports/flow_formats_live_final_20261031
```

Local ComfyUI `:8188` FLUX 3 Klein, local 27B lane `:8080`, gateway `:8190`,
RTX 5080 laptop. All four authored, all four rendered, all four `ok`; total
render/flow time 159.6 s (42.5 + 39.6 + 38.8 + 38.7 s).

| format | surface | residual | hero score | defects | OCR |
|---|---|---|---|---|---|
| pouch | `pouch-measure_face` | 0.281 px | 95.1 | none | matches expected |
| box | `box-quad` | 0.215 px | 90.1 | none | matches expected |
| bottle | `bottle-band` | 0.311 px | 94.1 | none | matches expected |
| tube | `tube-band` | 0.121 px | 95.0 | none | matches expected |

Artefacts: `exports/flow_formats_live_final_20261031/run_report.json`, each
format's `01_plate.png`, `02_labelled.png`, `02_labelled.dieline.json`,
`03_hero.png`, `flow_report.json`. JSON evidence is committed; PNGs stay local.

## What the live run exposed

- **Low-contrast cylinder guard.** A light-grey tube on a light-grey background
  produced a fragmented colour mask; the band detector fitted a narrow strip
  (29% of the silhouette's widest row) and the label landed on one side. That
  case is now refused with `silhouette_touches_frame` / "mask likely missed the
  body" rather than printed. The guard is tested; the good tube still measures
  0.121 px.
- **Tube form.** The 27B wrote "matte kraft paper tube" and FLUX returned an open
  cylinder. The author brief now carries a verbal form note ("flat heat-sealed
  crimp at one end and a cap at the other"), so the next prompt asks for a closed
  cosmetic tube rather than relying on millimetres alone.
- **Author startup race.** `/health` is ready before the first slot; the runner
  now waits 5 s and sends one tiny warm-up completion before authoring.

## Honest caveats

- The 1024² plates are **not 300 DPI** for these physical faces; the sidecars
  say `print_ready: false` and report the deficit. This is a render-resolution
  task, not a hidden pass.
- The CMYK target is metadata only; no ICC soft-proof is performed.
- The measured quad is a mockup fit from the render, not a converter die drawing.
- The 27B lane is the local Qwen3.8-27B alias, not literally Qwen 2.5-Coder.
- No Amazon request, no paid provider call, no credential read. All local
  ComfyUI/llama.cpp, PIL/numpy and pytest.

## Commits

```
7e443d8  measure_surface report + verified four-format evidence
b9c64776  hero remediation, surface luminance, 27B author, print-DPI sidecar
187706b5  low-contrast cylinder guard + author form note
```

## Next

1. Render at a resolution that clears 300 DPI for the real face sizes (the
   sidecar names the deficit); keep the sidecar as the acceptance record.
2. Tune curvature shading strength per material (glass vs kraft) and add a
   specular-preserving mode for foil/spot-UV labels.
3. Feed the tube form note through a live render and re-check the crimp/cap
   boundaries.
4. Add a contrast constraint to the author brief so a light product on a light
   background is less likely; the guard already refuses it.
