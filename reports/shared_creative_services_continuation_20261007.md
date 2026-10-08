# Shared Creative Services — Continuation Report

Date: 2026-10-07 (second pass)
Worktree: `C:\Users\T2Hol\Desktop\northstar-wt-mogra` (branch `feature/mogra-exact-text-mockup`)
Prior milestone commits preserved: `9bfef9d`, `3ca01e2`.

Status vocabulary: **INSTALLED · IMPLEMENTED · TESTED · VISUALLY APPROVED (owner) ·
INFRASTRUCTURE-ONLY · MISSING · NOT YET INTEGRATED**.

---

## 1. Active consumers and integration status

Every direct ComfyUI consumer found by repository search, classified:

| Consumer | Direct ComfyUI | Classification | Status |
|---|---|---|---|
| `Northstar_backend/creative/comfy_client.py` | yes (HTTP) | Shared-runtime internal implementation | keep |
| `Northstar_backend/creative/workflows.py` | graph builders | Shared-runtime internal | keep |
| `Northstar_backend/creative/stages.py` | via comfy_client | Shared-runtime internal | keep |
| `Northstar_backend/creative/router.py`, `jobs.py`, `pipeline.py`, `provenance.py`, `registry.py`, `workers.py` | no | Shared service definitions | implemented |
| `Northstar_backend/creative/mogra_mockup.py` | scene step | Consumer that must route | **now routes scene generation through `stages.generate`** (Edit-2511 panel prep remains the edit lane) |
| `Northstar_backend/creative/routes.py` `/generate-scene` | was direct | Consumer that must route | **now routes through `stages.generate`** |
| `Northstar_backend/creative/routes.py` `/mockup` | via mogra_mockup | Consumer that must route | routes through the shared scene stage + compositor |
| `tools/generate_images.py` (local backend) | was own client | Consumer that must route | **now routes through the shared pipeline** (in-process `stages.generate`, else HTTP `/api/creative/pipeline`); direct ComfyUI graph retained only as the standalone fallback |
| `Northstar_backend/model_router.py` | no (config/planning) | Intentionally supported diagnostic/config utility | keep |
| `Northstar_backend/creative/video.py` | fal cloud | Specialised video (gated) — not ComfyUI | keep |
| `creative/static/mockup.html`, `MockupStudio.jsx`, `CreativeServicesPanel.jsx`, `AssetRegistry.jsx`, `CloudApprovals.jsx` | via `/api/creative` | UI consumers | shared |
| WT-C `foundation/api/creative.py` (other worktree) | via `local_image_gen` | Consumer that must route | **adapter added** (`creative/foundation_contract.py`, mounted at `/api/v1/foundation/creative/*`); WT-C one-line delegation documented (not auto-applied) |
| WT-C `local_image_gen.py` / `comfyui_client.py` / `local_flux_smoketest.py` etc. | yes | Retired on this branch (absent here); superseded by shared services | retired |

Remaining bypass: none known among active consumers on this branch. The
one cross-worktree consumer (WT-C) is handled by the shared contract adapter plus
a documented delegation.

## 2. Updated routing policy

`creative/router.py`:

| Capability | draft | standard | high |
|---|---|---|---|
| generate | Z-Image-Turbo (8 steps, CFG 1) | **SDXL Base 1.0 (25 steps, CFG 7)** | **SDXL Base 1.0 (32 steps, 1280²)** |
| edit | Qwen-Image-Edit-2511 | same | same |
| inpaint | SDXL + `SetLatentNoiseMask` | same | same |

- **Qwen is no longer a quality label.** It is routed by the *edit* capability and
  is available for generation only as an **explicit opt-in** (`lane="qwen-t2i"`,
  reported under `explicit_lanes`). "High" now means SDXL at a larger size/budget.
- SDXL is the provisional standard-generation candidate; Z-Image-Turbo is a
  separately selectable fast candidate.
- FLUX.1 [dev] remains quarantined and is never selected.
- **Quality-based defaults are NOT finalised** — they remain provisional pending
  owner visual review.
- UI (`CreativeServicesPanel.jsx`) now states the model per mode, the device-VRAM
  implication per lane, the quarantined model, and the pending-review caveat.

## 3. Benchmark methodology (exact)

- Harness: `tools/creative/benchmark.py` via the live API (`/api/creative/pipeline`),
  1 variant, no batch; results in `reports/creative_benchmarks/`.
- Recorded per run: task, lane, component, family, **model filename, precision,
  workflow, sampling preset (steps/CFG/sampler/scheduler), dimensions**, cold/warm
  flag, total wall seconds, retries, output decode check, rejected flag, provenance.
- Metric: `peak_device_vram_mb` = `nvidia-smi memory.used` — **device-wide usage**
  (all processes, including ~0.5 GB desktop), sampled ~1.5 s; **not** per-process
  allocated or reserved VRAM. The pre-render baseline is also recorded so the
  per-lane delta can be derived.
- Because the pipeline unloads ComfyUI models between jobs, each sequential run
  includes model load; cold/warm refers to the GPU's prior state, and load time is
  part of the reported full-job latency.

### Generation results (1024×1024, 1 variant)

| Lane | Model | Precision | Sampling | Total s | Peak device VRAM |
|---|---|---|---|---|---|
| sdxl-standard | sd_xl_base_1.0.safetensors | fp16 weights | 25 steps, CFG 7, dpmpp_2m/karras | **12.49** | **7 563 MB** |
| z-image-draft | z_image_turbo_nvfp4.safetensors | nvfp4 | 8 steps, CFG 1, euler/simple | **15.54** | 11 755 MB |
| qwen-t2i (explicit) | qwen-image-2512-Q4_K_M.gguf | gguf-q4_k_m | 20 steps, CFG 4, euler/simple | **110.79** | 14 123 MB |

The Qwen figure is **not comparable** to the earlier 30:41 job (that was a
4032×3024 render with a different model/step budget) nor strictly to the earlier
53.1 s figure (same nominal settings but different thermal/run context). The
spread under repeated heavy runs is thermal/power variance on a laptop; no
throttling conclusion is drawn from temperature alone.

### Full-job results (required helpers + finishing included)

| Task | Stages executed | Total s | Output |
|---|---|---|---|
| product_ad | BiRefNet mask → exact-text compose | 4.02 | 896×1152 |
| packaging_concept | generate → exact-text compose | 16.09 | 1024×1024 |
| ad_layout | BiRefNet mask → product composite → exact-text banner → export | 2.00 | 1080×1080 |
| inpaint | SDXL masked redraw (`SetLatentNoiseMask`) | 12.04 | 896×1152 |

## 4. Verified end-to-end outputs

`reports/creative_validation/validation_report.{json,md}` (all statuses):

| Check | Result |
|---|---|
| routing policy | draft=z-image-draft, standard=sdxl-standard, high=sdxl-high, inpaint=sdxl-inpaint, explicit=[qwen-t2i] |
| product_ad | done — exact label text, PNG 896×1152, provenance `allowed` |
| packaging_concept | done — `concept=true`, `disclaimer=true`, composited 1024×1024, provenance `allowed` |
| ad_layout | done — 1080×1080 finished ad (top banner + product), provenance `allowed` |
| inpaint | done — 896×1152, provenance `allowed` |
| failure recovery | error (bad source) with a clear message, no crash/hang |
| cancellation | **cancelled** (ComfyUI `/interrupt` + cooperative flag) |

Product identity: the faithful product ad preserves the source product via BiRefNet
cutout; the exact label text is deterministic (no AI glyphs). Packaging concepts are
labelled as concepts. Text correctness verified visually and by the brand guard.

## 5. Tests and regressions

- `test_creative_shared_services.py`: **23 passed** (added inpaint routing, inpaint
  workflow, dict-spec compose, ad_layout export+provenance, foundation readiness).
- Creative suite (8 files): **138 passed in 38.26 s**.
- UI production build: **0 errors**.

## 6. License-manifest verification status

`shared/creative-components.json` (20 components; 19 approved, 1 quarantined) with
presence + SHA-256. Licenses verified from primary sources for SDXL, Z-Image,
IP-Adapter, xinsir ControlNet, BiRefNet, Real-ESRGAN, Qwen, fonts, FLUX.1 [dev].
**Not independently re-verified this pass:** the exact SHA-256 of every weight
against the publisher's published digest (file sizes verified; digests computed
locally but not cross-checked against upstream checksums). Hosted-use obligation
review for ComfyUI GPL-3.0 is documented, not legal advice.

## 7. Visual approval — pending items

Representative samples are in `generated_images/creative/` (product_ad, packaging
concept, finished ad, conditioned/control outputs). **Owner visual approval of the
quality-based defaults (draft=Z-Image, standard=SDXL, high=SDXL-1280) and of the
representative samples is pending.** No quality default is final until then.

## 8. Video / audio implementation status

| Capability | Status |
|---|---|
| Cloud video generation (fal Wan/Kling/Veo) | **INFRASTRUCTURE-ONLY + GATED** — catalog, cost estimate, request builder, armed submit (`creative/video.py`, `cloud.py`); requires FAL key + `MEDIA_GEN_LIVE=1`; never run here |
| Local short-clip generation | **MISSING** — no local video model installed |
| Timeline assembly / captions / short-shot stitching | **MISSING** — no backend |
| Narration / TTS | **MISSING** |
| Audio input / transcription (STT) | **WORKING (specialist)** — browser voice components + `server/voice-transcribe.cjs` + `functions/api/transcribe.js` |
| Multi-GPU video workers | n/a — the worker config is generic and does **not** imply video is implemented |

**Next concrete scope for short image-conditioned clips:** add a `video` capability
lane reusing the cloud-gated fal path for the first delivered clips (image→video
models already in `video.py`), with the shared queue/provenance wrappers; then a
local backend (e.g. an image-conditioned SVD/LTX lane) only after owner choice and
a commercial-compatibility check. Backend assembly (ffmpeg timeline + burned
captions + narration mix) is a separate `video_assemble` task that reuses the
existing STT service for captions.

## 9. Inpainting clarification

- **What exists now:** an SDXL **masked redraw** (`SetLatentNoiseMask`, core node,
  commercially compatible) — denoise only inside a supplied mask, preserving the
  rest of the image pixel-for-pixel. Mask value 1 = region to redraw.
- **What does not exist:** a dedicated inpaint *checkpoint* service and
  mask-aware Qwen editing. Qwen-Image-Edit-2511 does **instruction-based** edits
  (not mask-precise), so it is not a substitute for mask-bounded inpainting.
- Protected product/text regions: pass a mask that excludes them; the masked redraw
  leaves unmasked pixels unchanged. There is no semantic lock beyond the mask.
- New tests: `test_router_inpaint_lane`, `test_sdxl_inpaint_workflow`, and the live
  `inpaint` job.

## 10. Genuine remaining gaps

- Cross-worktree WT-C delegation is **documented but not auto-applied** (to avoid
  clobbering unrelated changes in that worktree).
- `mogra_mockup`'s Edit-2511 panel-prep step still calls `comfy_client` directly
  (edit lane, not generation) — acceptable, but not yet abstracted behind `stages`.
- No dedicated inpaint checkpoint; no local video backend; no video assembly.
- Weight SHA-256 cross-check against upstream publisher digests not done.
- `tools/generate_images.py` cloud backends (Cloudflare/HuggingFace/Pollinations)
  are outside the local shared contract; the local backend now routes through it.
- Quality-default visual approval pending.

**"Blocked: none" means no step required an owner gate. It does not mean all
required work is complete** — items in §10 remain.
