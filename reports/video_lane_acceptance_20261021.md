# Video lane — acceptance test (Wan 2.2 TI2V-5B, local)

First real measurement of the 5-second ad-clip path on this machine. Nothing
was tuned to flatter the number: stock ComfyUI 0.40 graph, stock GGUF weights
already on disk, one still, one prompt.

## Setup

| item | value |
|---|---|
| ComfyUI | 0.40.0 (torch 2.11.0+cu128, cudaMallocAsync) |
| model | `Wan2.2-TI2V-5B-Q5_K_M.gguf` (3.55 GB) |
| text encoder | `umt5-xxl-encoder-Q5_K_M.gguf` (3.86 GB) |
| VAE | `wan2.2_vae.safetensors` (1.31 GB) |
| graph | native `UnetLoaderGGUF` → `ModelSamplingSD3` (shift 8) → `Wan22ImageToVideoLatent` → `KSampler` (uni_pc/simple) → `VAEDecode` → `SaveWEBM` |
| clip | 121 frames @ 24 fps = **5.04 s**, 960×960, 30 steps, cfg 5.0, seed 42 |
| still | `mogra_forest_dusk_composed.png` (1216×1216, existing studio render) |

## Measured

| metric | result |
|---|---|
| **wall time** | **≈ 690 s (11.5 min)** for one 5-second clip |
| **peak VRAM** | **12,835 MB** — 12.5 GB of the 15.9 GB card |
| output | 0.814 MB WebM (VP9, crf 20) → 0.69 MB MP4 (H.264) |
| quality | label text legible and **unchanged** at 0.2 s / 2.5 s / 4.8 s; product static; background parallax only |
| cost | $0 in API spend (local GPU) |

Evidence: `reports/video_scan/clip_01_test.mp4`, contact sheet
`reports/video_scan/clip_01_frames.png`.

The text-stability result was not luck: the prompt explicitly says *"the pouches
stay perfectly still and the label text stays sharp and unchanged"*, and the
negative blocks *"warping, distorted label text, morphing letters"*. That pair is
the reusable pattern for every product clip.

## What it means

1. **The lane is real.** A product still becomes a usable 5-second clip with no
   cloud call, no download, and no label corruption.
2. **The 13 GB brain and the render cannot co-exist** — confirmed at 12.8 GB
   peak. Renders must take a VRAM lease (unload the brain, reload after).
3. **11.5 min/clip is an async number, not an interactive one.**
   - 5 clips ≈ **58 min**
   - 10 clips ≈ **1 h 55 min**
   That fits "your ad set is ready in two hours", not a chat-time expectation.
4. **This is the honest local baseline.** Any faster figure needs measurement,
   not optimism.

## Where the time can come from (to be measured, not assumed)

| lever | expected effect | risk |
|---|---|---|
| steps 30 → 20-24 | ~20-30 % faster | small quality loss |
| 960² → 704² | ~25-45 % faster (pixel-bound) | lower resolution; still fine for social |
| distilled "lightning" LoRA | large (4-8× in the literature) | needs a verified LoRA for **this** 5B model |
| same graph, several seeds | amortises the ~60 s model load | linear in clips |
| cloud | seconds-to-minutes per clip | per-clip cost, already priced |

The sane split, given the cloud models are already selected for customers:
**local = draft/preview and internal iterations; cloud = paid finals.** That
keeps spend near zero during creative exploration and only pays when a clip is
approved.

## Pricing gap (unchanged from the scan)

`creative_pricing.py` prices `video_short` (15 s) and `video_long` (60 s). A
5-clip pack is 25 s and a 10-clip pack is 50 s — neither maps cleanly. A
`clip_pack` job is still needed so the credit quote matches the deliverable.

## Batch status

Five clips (same still, five motion prompts, seeds 42/137/2024/777/5150) run
sequentially in `tools/render_batch.ps1`, writing
`reports/video_scan/batch/summary.jsonl`. Results are appended to this report
when the run completes.
