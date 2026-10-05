# Local Creative Media Suite — Model-Chaining Architecture (rev. 2026-10-05)

> Localhost-only, **unarmed**. Produce images, voice, UGC talking-head, short
> video, and music on a **16 GB RTX 5080 Mobile** by chaining small specialists
> and running **one model at a time**. Nothing here downloads, installs, loads,
> or generates.

## 1. Engine: ComfyUI (headless) + this planner
ComfyUI is the engine; the planner submits **workflow templates** to ComfyUI's
HTTP API (`/prompt`, `/history`, `/queue`, `/interrupt`, `/free`) via
`Northstar_backend/comfyui_client.py`. New models land in ComfyUI first, and its
offloading/model-swapping is already solved. The planner does **not** invent
graphs — templates come from ComfyUI's template library or `creative_workflows/`.
NVFP4/FP8 native support on RTX 50-series (NVIDIA × ComfyUI, GDC 2026) is the
biggest free speedup for this card.

## 2. Model stack by job
| Stage | Pick | License | ~VRAM | Notes |
|---|---|---|---|---|
| Keyframes / product shots | **FLUX.2** (NVFP4/FP8) or **Qwen-Image-Edit** | Apache-2.0 | ~13 GB | Test both on real product photos |
| Fast video + sound (draft) | **LTX-Video 2.3** (22B, NVFP4/FP8) | LTX Open Weights | ~16 GB | Native synchronized audio, ~720p |
| Hero shots (final) | **Wan 2.2 14B** (GGUF Q5/Q6 or FP8) + block swapping | Apache-2.0 | ~16 GB | GGUF Q5 ~11–16 GB; RAM-hungry |
| Talking-head UGC | **Wan 2.2 S2V** or **InfiniteTalk** (LatentSync as fix-up) | Apache-2.0 | ~16 GB | One pass from image + audio |
| Voice | **Chatterbox** (run a shootout on your own scripts) | MIT | ~6 GB | Don't trust vendor blind tests |
| Music / SFX | **ACE-Step** | Apache-2.0 | ~8 GB | — |
| Upscale | **SeedVR2** | Apache-2.0 | ~12 GB | Render small, finish large |
| Interpolate | **RIFE** | MIT | ~4 GB | Raise fps / smooth motion |
| Assembly | **ffmpeg (NVENC)** | LGPL/GPL | 0 | GPU encode; mux/captions/concat |

**Product accuracy:** never let a model invent your packaging. Generate the scene
around the product, then **composite / reference-lock** the real product photo
(Qwen-Image-Edit / FLUX.2 edit). Garbled box text reads as fake and can cause
listing/ad problems.

## 3. Workflow (maximize output)
1. **Draft pass** — low res, few steps, **LTX-2.3**; many variations; pick winners.
2. **Final pass** — re-render **only approved seeds** at full quality (**Wan 14B** hero).
3. **Finish** — upscale (SeedVR2), interpolate (RIFE), mux audio, encode (NVENC).
4. **Chain clips** — last-frame → first-frame for 15–30 s videos.
5. **Overnight queue** — batch finals in ComfyUI's queue (laptops throttle live).

## 4. Speed / stability stack
- torch for **CUDA ≥ 12.8** (Blackwell) + current ComfyUI with NVFP4.
- SageAttention + `torch.compile` where the workflow supports it.
- **64 GB system RAM** for block swapping (32 GB is tight with 14B).
- Fast NVMe, **1 TB+ free** (full set > 100 GB).
- Plugged in, performance mode, cooling stand; keep the active model resident
  between jobs; swap models between stages, not between every clip.

## 5. Hybrid rule
Local for **volume** (UGC, product b-roll, social, variations). Cloud
(Kling/Veo-class) for **long, physics-heavy cinematic** shots (e.g. the soccer
commercial). That split gives the best cost per finished video.

## Readiness / truth
- `pipeline_status()` / `plan_pipeline(goal)` / `render_plan(goal, mode)` are
  read-only and never execute; `GET /api/v1/foundation/creative/readiness`
  includes a `pipeline` block; CLI: `python tools/creative_suite_status.py`.
- **Readiness ≠ activation.** `MEDIA_GEN_LIVE` remains the arming gate, and video
  generation is separately owner-gated.

## Environment reality check (this machine vs the plan)
| Plan assumes | This machine | Verdict |
|---|---|---|
| 64 GB system RAM | **~15.4 GB** | ❌ 14B block-swap will thrash → 5B/FP8 realistic |
| 1 TB+ free NVMe | **~115 GB free** | ⚠️ fits some, not the full set |
| RTX 50-series 16/24 GB | RTX 5080 **Laptop 16 GB** | ✅ thermally constrained |
| torch CUDA ≥ 12.8 | torch **2.11.0+cu128** | ✅ (ComfyUI prefers cu130) |
| ffmpeg | **missing** | install (local, small) |

## Owner-gated steps
Every model download is owner-gated; enabling video is owner-gated. Current state:
**image** = FLUX.1 [dev] installed (test-only, non-commercial); all other stages
`missing`.
