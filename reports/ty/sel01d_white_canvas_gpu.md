# sel-01d — white-canvas main images, a GPU lane that proves its bookkeeping, a measured upscaler, and FLUX 3 unstarved

Branch `ty/sel-01d` (from `staging`). Four jobs, in order. Every number below is from a
command run in this worktree on 2026-11-08/09.

## 1. Main images are pure composites on flat white

`tools/seller_tester/generators.py` now routes `situation: white_background_main` (fidelity
`exact`) to a **flat 255 canvas**, not to ComfyUI:

* canvas 2000 × 2000, background exactly (255, 255, 255);
* the cutout is composited at **85 % of the frame's long side**, centred;
* a contact shadow is allowed only if the finished picture keeps every corner at 255 —
  if it does not, the composite is re-placed without the shadow and
  `shadow_dropped` is recorded;
* no scene model, no prompt, no grade, no lane start (proved: the renderer is never called).

The wide Mogra pair (two pouches side by side) cannot be 85 % *tall* without running past
the frame width, so 85 % is applied to the longest side and both fills are measured and
recorded. A portrait product gets 85 % height from the same rule.

### MG-C01 proof (real upload, real brief)

Command (the CLI's `--renderer comfy` precheck is irrelevant here: no lane is started):

```
python <proof driver>   # run_pass on tools/seller_tester/mogra_briefs.json, MG-C01 only,
                        # CompositeGenerator(method="grabcut", renderer=ComfySceneRenderer())
```

Result: `score 100.0`, `passed true`, `failed_checks []`, artefact
`renders/seller_composite/MG-C01.png`.

| check | ok | detail |
| --- | --- | --- |
| dimensions | **pass** | `2000x2000 vs min 1536x1536, max 8192x8192` |
| aspect | **pass** | `aspect 1.0000 vs 1.0000 +-0.020` |
| background | **pass** | `corners [(255,255,255) ×4] vs target (255,255,255) +-14; max deviation 0, corner spread 0` |
| subject_fill | **pass** | `subject fill 45.9% vs 10.0-85.0% (distance > 20)` |
| alpha_matte (brief: any) | pass (skipped) | `matte free for this brief` |
| alpha_matte (white_matte 255±6, run independently) | **pass** | `border mean 254.2 (>= 249), std 2.80 (<= 6.0)` |

Measured canvas numbers, from the finished pixels:

```
canvas             [2000, 2000]
corners            all [255,255,255]; corners_exactly_255 true
subject_fill_pct   45.86
height_fill_pct    60.55
width_fill_pct     84.70   <- longest side at 85 %
identity SSIM      0.9958
```

The cutout: the white path starts no ComfyUI, so BiRefNet (which lives in the lane) is
refused and **GrabCut** is used, with the substitution recorded on the result
(`cutout_refused.method = "birefnet"`, reason states the lane is deliberately not started).
GrabCut is 14/14 items on the same cutout eval (5.08 px mean edge).

MG-C01 previously failed at score 60 on a generated grey "studio" (corners 81–158,
fill 85.5 %). The failure was the scene, and removing the scene removes the failure.

## 2. The image lane owns the GPU and proves it

`tools/comfy_lane.py` now records, in one row per lane (and one authoritative `render` row
per generated brief), in `state/gpu/comfy_lanes.jsonl` (the directory the digest already
reads):

* `gpu_before` — `nvidia-smi --query-gpu=memory.total,memory.used,memory.free,...`;
* `ollama_ps_before` — `/api/ps`, with the resident names;
* `unloaded` — only the models that were actually resident (keep_alive 0), each with
  `verified` from a second `/api/ps` read;
* `gpu_ready` — the snapshot **after** the unload; **this is the number the budget uses**;
* `budget` — `{free_gb, needed_gb, reserve_gb, headroom_gb, ok, reason}` where
  `ok = (free_gb - needed_gb) >= reserve_gb` and the reserve is read from
  `tools/gpu_budget.RESERVE_GB` (1.0 GB);
* `gpu_before_work`, `gpu_after_work`, `gpu_after`;
* `stopped` — the port-closed proof;
* `reloaded` — the same tags put back after ComfyUI stopped, each `verified` by `/api/ps`;
* `ollama_ps_after`, `gpu_after_reload`, `seconds`.

The reload runs in `finally`, so a render that raises still restores the residents
(pinned by a test). A budget that does not fit refuses **before** `start()` with the real
numbers; a budget with no VRAM reading refuses rather than guessing.

### Full lane row (SDXL 1536, bojo resident then restored)

Taken from `state/gpu/sel01d_scene_probe.json` → `renders[0].lane`; the same row is in
`state/gpu/comfy_lanes.jsonl`.

```
role             scene:sdxl          needed_gb 11.95     reserve_gb 1.0
gpu_before       used 3210 MB  free 12.49 GB
ollama_ps_before [bojo:latest 2.31 GB]
unloaded         bojo:latest  verified true      (after /api/ps: [])
gpu_ready        used 0 MB     free 15.63 GB
budget           fits: 15.63 GB free - 11.95 GB needed = 3.68 GB >= 1.0 GB reserve
start            pid 33372       ready 18.1 s
gpu_before_work  used 172 MB    free 15.46 GB
gpu_after_work   used 274 MB    free 15.36 GB
stopped          ok true, port 8188 closed in 1.5 s
gpu_after        used 0 MB     free 15.63 GB
reloaded         bojo:latest  verified true      (ollama_ps_after: [bojo:latest 2.31 GB])
gpu_after_reload used 3210 MB  free 12.49 GB
seconds          56.7           work_ok true
```

When another session held `qwen2.5vl:7b`, the same code refused instead:

```
budget: refused: 9.44 GB free - 11.95 GB needed = -2.51 GB < 1.0 GB reserve
```

## 3. Upscaling is measured; Lanczos is no longer assumed

`tools/upscale.py` (new) benchmarks four backends through the model-scout machinery:
`ty/model_roles.json` has an `upscalers` role, and the result is merged into
`ty/model_leaderboard.json` by `model_scout.write_leaderboard` (other roles untouched).

Eval: the three Mogra uploads, centre-cropped at the largest native square (known good),
downsampled 2× for the probe. Two fixed conditions, both reported:

* **clean** — the 2× downsample alone;
* **soft** — the downsample plus a 0.8 px blur and σ=2 noise, because a 768 diffusion
  scene is not a Lanczos-downsampled photograph.

Items = PSNR, SSIM and edge sharpness beating the Lanczos control, per image (18 items).

| method | correct / items | clean PSNR / SSIM / edge | soft PSNR / SSIM / edge | mean s | VRAM | licence |
| --- | --- | --- | --- | --- | --- | --- |
| Lanczos (control) | 0 / 18 | 32.667 / 0.94628 / 0.02466 | 27.862 / 0.87096 / 0.01831 | 0.78 | 0 | Pillow MIT; no weights |
| **SwinIR-M ×4 GAN** | **14 / 18** | 30.006 / **0.93096** / **0.02838** | **30.394** / **0.92154** / **0.02346** | 8.31 | 3.94 GB | Apache-2.0 |
| Real-ESRGAN ×4plus | 14 / 18 | 30.005 / 0.92842 / 0.02680 | 29.870 / 0.91538 / 0.02340 | 7.08 | 3.56 GB | BSD-3-Clause |
| ComfyUI latent upscale | 0 / 18 | 18.550 / 0.63783 / 0.02629 | 19.217 / 0.66321 / 0.01746 | 40.46 | SDXL lane | Apache-2.0 nodes + OpenRAIL++-M |

**Winner: SwinIR.** It and Real-ESRGAN both clear the control by 14 items; the fixed
tie-break is mean SSIM, where SwinIR leads 0.92625 vs 0.92190 (and mean PSNR 30.20 vs
29.94). ComfyUI's latent upscale is not an upscaler: it regenerates the picture and
destroys fidelity (PSNR 18.6, SSIM 0.64) at 40 s an image.

Honest reading of the clean column: on a *clean* downsample Lanczos wins PSNR/SSIM outright
because the degradation is its own inverse; the GPU upscalers win the **soft** condition —
the one that resembles the pipeline's actual input — on every item, and win the
lowest-resolution clean case too. The decision is made on the production-like condition,
and both tables are printed.

Measured on the real 768 → 1536 step: `swinir`, 8.49 s, 3.94 GB.

`CompositeGenerator._upscale_to` now calls `upscale.upscale_to_min`: the active method is
recorded with its licence, and if the GPU backend is refused (lane busy, VRAM short) the
Lanczos fallback and the refusal reason are recorded — a resample can never pass as a
reconstruction. Licences and install method: `provenance.csv` (+3 rows).

## 4. FLUX 3 was starved, not broken

Both models now render 1536 on this box, through the lane, with the lane's budget applied:

| model | steps | result | wall time | lane row |
| --- | --- | --- | --- | --- |
| **SDXL** (`sd_xl_base_1.0`) | 24 | **1536×1536 PNG, mean luma 98.2** | **60.8 s** | 56.7 s, budget 3.68 GB headroom |
| **FLUX 3** (`flux3-image-klein-nvfp4`) | 16 | **1536×1536 PNG, mean luma 132.3** | **93.8 s** | headroom 1.48 GB |

Working command (the same call the renderer makes):

```python
render_scene(prompt, width=1536, height=1536, steps=24, seed=20261108, model="sdxl")
# FLUX 3: model="flux3", steps=16
```

Diagnosis: the earlier `cuDNN Frontend: No valid execution plans built` and
`aimdo Fault failed: 2` happened while another lane held ~7 GB of VRAM (free 8.7–9.4 GB).
With the lane owning the GPU (free 15.63 GB) the identical nvfp4 weights and graph render
1536 in 93.8 s. The failure was starvation, and the fix is the budget + unload above, not
a different graph.

Decision: **SDXL at 1536 stays the default** scene model (60.8 s vs 93.8 s, smaller
checkpoint); FLUX 3 is selectable with `model="flux3"` and now has a timed 1536 run.
Neither path can fail silently: the lane refuses with the numbers, and a FLUX 3 runtime
error is raised with the gateway's own message into `GeneratorUnavailable`.

## Tests

```
python -m pytest Northstar_backend/test_seller_tester_composite.py \
                 Northstar_backend/test_scene_lane_gpu.py -q
...........................                                              [100%]
27 passed in 2.28s

python -m pytest Northstar_backend/test_seller_tester.py \
                 Northstar_backend/test_comfy_lane.py \
                 Northstar_backend/test_model_scout.py -q
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 13.31s
```

New cases: the white main builds a flat 255 canvas, never calls the renderer, has exact
corners, 80–90 % height fill and 10–85 % area fill, and passes dimensions/background/fill;
the lane-free cutout substitution is recorded; a short render goes through the measured
upscaler; the Lanczos control records its licence; unload only when resident; reload in
`finally` even when the work raises; a refused budget names the numbers and never starts;
both snapshots are recorded; an unload that does not take is a refusal.

## Files

```
tools/seller_tester/generators.py     white-canvas route, measured upscaler, render journal
tools/seller_tester/scene_render.py   1536 default, model VRAM need, lane watchlist
tools/comfy_lane.py                   snapshots, unload/reload, budget verdict, render row
tools/upscale.py                      new: Lanczos/Real-ESRGAN/SwinIR/latent, benchmark
ty/model_roles.json                   upscalers role
ty/model_leaderboard.json             upscalers merged; other roles untouched
provenance.csv                        +3 rows (spandrel, Real-ESRGAN, SwinIR)
Northstar_backend/test_seller_tester_composite.py   +5 tests
Northstar_backend/test_scene_lane_gpu.py            new, 6 tests
reports/ty/sel01d_white_canvas_gpu.md
```

## Caveats, stated rather than glossed

* **Shared box.** Another session cycled `qwen2.5vl:7b` (≈5.4 GB) during this work; that
  is real evidence (the lane refused with the numbers) and it is also why the benchmark
  was run in a free window. The probe passes an explicit watchlist that includes
  `qwen2.5vl:7b` for those runs; the library default remains the two owner-named residents.
* **Peak VRAM sampling.** `gpu_after_work` is post-render, so it shows the released state,
  not the peak; `needed_gb` is the model's stated need, and the upscaler's `vram_gb` is a
  measured peak-minus-baseline sample. Neither is presented as a peak claim.
* **The latent candidate is measured, not recommended.** It is a regeneration, and the
  numbers say so.
* **Test runs no longer write the evidence journal** (`NS_LANE_JOURNAL` redirects it).
  Rows written before that change include a few `T-1` test rows in the same file.
