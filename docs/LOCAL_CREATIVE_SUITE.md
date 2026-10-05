# Local Creative Media Suite — Model-Chaining Architecture (2026-10-04)

> Localhost-only, **unarmed** design for producing images, voice, UGC talking-head
> video, short video, and music on a **16 GB RTX 5080 Mobile** by chaining small
> specialists and running **one model at a time**. Nothing here downloads,
> installs, loads, or generates.

## Why chaining

16 GB cannot hold one giant model. The winning pattern: run a **specialist per
stage**, free VRAM between stages, and assemble with ffmpeg. Each stage is small
enough to fit; quality comes from the composition, not one model.

## Stage → specialist map

| Stage | Preferred (commercial-safe) | License | ~VRAM | Alt (non-commercial) |
|---|---|---|---|---|
| **image** | FLUX.2 Klein 4B | Apache-2.0 | 13 GB | FLUX.1 [dev] fp8 *(installed, non-commercial)* |
| **voice** | Chatterbox Turbo | MIT | 6 GB | — |
| **lipsync** | LatentSync 1.6 | Apache-2.0 | 18 GB* | SadTalker (Apache, 6 GB) |
| **video** | Wan 2.2 TI2V-5B | Apache-2.0 | 8 GB | LTX-2.3 nvfp4 (Open Weights, native synced audio) |
| **music** | ACE-Step | Apache-2.0 | 8 GB | Stable Audio Open (Stability Community) |
| **upscale** | ffmpeg scale | LGPL/GPL | 0 | — |
| **mux** | ffmpeg | LGPL/GPL | 0 | — |

\* LatentSync 1.6 officially needs 18 GB but runs on 16 GB with UNet CPU-offload
(the documented 16 GB talking-head pipeline). Requires **32–64 GB system RAM**.

## Pipeline goals

| Goal | Stages |
|---|---|
| `product_image` | image → upscale |
| `ugc_talking_head` | image → voice → lipsync → mux |
| `cinematic_short` | image → video → music → mux |
| `ad_short` | image → video → voice → music → mux |

## Orchestration rules

1. **One model at a time** — sequential stages; explicit unload/offload between.
2. **Manifest-driven** — a job is an ordered list of stages with input/output paths.
3. **Dry-run by default** — planning prints the plan; execution requires `--yes`.
4. **Localhost only**, image/video/audio only; no cloud, no publishing.
5. **License-aware** — the planner prefers `commercial_ok` models; non-commercial
   models are allowed only for internal testing.

## Readiness / truth

- `pipeline_status()` reports per-stage and **per-model install state**
  (`installed` | `missing` | `unknown`) via filesystem/exe probes only.
- `plan_pipeline(goal)` returns the chosen models + the **owner-gated steps** still
  required. It never executes.
- `GET /api/v1/foundation/creative/readiness` now includes a `pipeline` block.
- CLI: `python tools/creative_suite_status.py [--plan <goal>] [--json]`.

**Readiness ≠ activation.** The suite being planned or partially installed does
not enable generation; `MEDIA_GEN_LIVE` remains the single arming gate, and video
generation is separately owner-gated.

## Owner-gated steps to reach each goal

Each model install is a **download** (owner-gated), and enabling video is
**owner-gated**. Current state: **image** stage has FLUX.1 [dev] installed
(test-only); all other stages are `missing`.

| Step | Gate |
|---|---|
| Download FLUX.2 Klein 4B (commercial image) | owner |
| Download + install Chatterbox (voice) | owner |
| Download + install LatentSync 1.6 / SadTalker (lipsync) | owner |
| Download Wan 2.2 TI2V-5B **and enable video** | owner |
| Download ACE-Step (music) | owner |
| Install ffmpeg | local, no download |

## Honest limits

- **16 GB**: quantized (nvfp4/GGUF) + offloading; short clips (~5 s); minutes per clip.
- **Blackwell/Windows**: torch cu128 works; ComfyUI prefers cu130; Triton/SageAttention
  optimized nodes generally unavailable on Windows.
- **Python**: ComfyUI venv is 3.14; several custom nodes want 3.12 → may need a second env.
- **Quality** trails cloud (ElevenLabs/Kling/HeyGen/Veo) but is free, private, unlimited.
