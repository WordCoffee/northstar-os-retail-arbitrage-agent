# Image Services — Closure Pass Report

Date: 2026-10-08
Worktree: `C:\Users\T2Hol\Desktop\northstar-wt-mogra` (branch `feature/mogra-exact-text-mockup`)
Prior commits preserved: `9bfef9d`, `3ca01e2`, `116fbd9`.
WT-C worktree (`feature/creative-cluster-launch`): commit `75ecb85`.

Vocabulary: **COMPLETED · TESTED · PENDING OWNER REVIEW · PROPOSED · NOT IMPLEMENTED**.

---

## 1. WT-C consumer delegation — COMPLETED + TESTED

- Added a guarded delegation in the WT-C worktree's
  `Northstar_backend/foundation/api/creative.py` only (no unrelated files touched):
  `_shared_contract()` imports `creative.foundation_contract` when present;
  `GET /readiness` and `POST /generate` delegate to it, else fall back to the
  legacy `local_image_gen` path.
- **Tested the active endpoints** with the shared package on `PYTHONPATH`
  (WT-C's app + the mogra `creative` package):
  - `GET /api/v1/foundation/creative/readiness` → **200**, returns shared routing
    (`draft=z-image-draft, standard=sdxl-standard, high=sdxl-high`) and
    `quarantined=['flux1-dev-fp8']`.
  - `POST /api/v1/foundation/creative/generate` → **200**, rendered on
    `z-image-draft` (512×512, 236 934 bytes).
- Committed in WT-C as `75ecb85`. Post-merge the package lives in the same tree,
  so no `PYTHONPATH` shim is needed.

## 2. Panel prep behind the shared edit service — COMPLETED + TESTED

- New `creative/stages.edit(...)` routes through `router.route("edit", mode)`
  (Qwen-Image-Edit-2511), applies the approved-component policy, and writes
  provenance.
- `creative/mogra_mockup.build_mockup` panel prep now calls `stages.edit`
  (prompt unchanged) instead of `comfy_client.blank_panel`; the prep provenance
  is recorded in the mockup result.
- New queued `edit` task in `creative/pipeline.py` (queue, cancellation,
  provenance).
- Test updated to mock `stages.edit`; `test_creative_productization` passes.
- **Consumer re-audit:** no remaining active inference consumer bypasses the
  shared controls on this branch. `comfy_client`/`workflows` are the shared
  runtime; `model_router.py` is diagnostic; `video.py` is gated cloud;
  `tools/generate_images.py` and `/generate-scene` route through the shared
  pipeline.

## 3. Benchmark execution paths — COMPLETED (recorded)

`tools/creative/benchmark.py` now records, per run: `input_source`
(reused vs freshly-generated), `comfy_prompt_id`, `comfy_execution_s`,
`comfy_cached_nodes`/`cache_hits`, `model_load_included`, `stage_times`,
`interval_s`, exact `model_file`/`precision`/`workflow`/`sampling`, dimensions,
`max_observed_device_vram_mb`, retries, and output decode/rejected status.

| Lane | Task | Model / precision | Sampling | input | exec s | interval s | total s | cache hits | max observed device VRAM |
|---|---|---|---|---|---|---|---|---|---|
| sdxl-standard | generate | sd_xl_base_1.0.safetensors / fp16 | 25 st, CFG 7, dpmpp_2m/karras, 1024² | freshly-generated | 12.264 | 12.34 | 12.56 | 0 | 7 499 MB |
| z-image-draft | generate | z_image_turbo_nvfp4.safetensors / nvfp4 | 8 st, CFG 1, euler/simple, 1024² | freshly-generated | 16.625 | 16.94 | 17.19 | 0 | 13 131 MB |
| qwen-t2i (explicit) | generate | qwen-image-2512-Q4_K_M.gguf / gguf-q4_k_m | 20 st, CFG 4, euler/simple, 1024² | freshly-generated | 122.7 | 123.02 | 123.18 | 0 | 13 995 MB |
| product_ad | full | birefnet + exact_text | mask → compose, 896×1152 | reused | — | 1.88 | 3.22 | 0 | 971 MB |

- **Memory wording:** `max_observed_device_vram_mb` is the **maximum** `nvidia-smi
  memory.used` seen across samples at a ~1.5 s interval — **device-wide** (all
  processes), **not continuous peak**, **not** per-process allocated/reserved.
- **Model loading is included** in every `execution_s`/`interval_s` (the pipeline
  unloads ComfyUI models between jobs; `cache_hits=0` reflects that).
- The Qwen figure is **not comparable** to the earlier 30:41 job (4032×3024) or the
  earlier 53.1 s figure (different run/thermal context). No throttling conclusion
  is drawn from temperature alone.

## 4. High-resolution preset — validated, no quality claim

Owner-review samples `5a_sdxl_standard_1024.png` and `5b_sdxl_high_1280.png`
(same seed/prompt):
- 1024/standard rendered a plausible jar but with **garbled AI label text**
  ("TUARIC PPODER") — expected, and exactly why final text uses the compositor.
- 1280/high produced a **different composition** (resolution changes latent
  layout), not a strictly better version of 5a.
- **No claim** that 1280² means higher quality. Provisional defaults preserved.

## 5. Integrity records — COMPLETED

`tools/creative/verify_integrity.py` → `reports/creative_integrity_20261008.{json,md}`.
Local SHA-256 for every installed weight; upstream SHA-256 from the publisher's
Hugging Face LFS OID where exposed.

| Component | Local SHA-256 | Upstream | Status |
|---|---|---|---|
| sdxl-base-1.0 | `31e35c80…` | `31e35c80…` | **match** |
| z-image-turbo | `a553c889…` | `a553c889…` | **match** |
| z-image-text-encoder | `72450b19…` | `72450b19…` | **match** |
| z-image-vae | `afc8e282…` | `afc8e282…` | **match** |
| ip-adapter-sdxl | `3f5062b8…` | `3f5062b8…` | **match** |
| clip-vit-h | `6ca9667d…` | `6ca9667d…` | **match** |
| controlnet-canny-sdxl | `bf47cd75…` | `bf47cd75…` | **match** |
| birefnet | `9ab37426…` | `9ab37426…` | **match** |
| qwen-image-2512 | `b2a5f624…` | `b2a5f624…` | **match** |
| qwen-image-edit-2511 | `8677bac9…` | `8677bac9…` | **match** |
| real-esrgan | `4fa0d389…` | unavailable | **upstream_unavailable** |

**10/11 match the publisher digest exactly.** Real-ESRGAN is a GitHub release
asset with no published SHA-256 → recorded as `upstream_unavailable` (not
invented); source/revision evidence is preserved in the report.

## 6. Owner-review set — PRODUCED, review PENDING

`generated_images/creative/review_set/` + review sheet
`reports/creative_owner_review/review_sheet.md`:

1. `1_faithful_product_ad.png`
2. `2_packaging_concept_exact_text.png`
3. `3_finished_branded_ad.png`
4. `4a_masked_edit_before.png` / `4b_masked_edit_after.png`
5. `5a_sdxl_standard_1024.png` / `5b_sdxl_high_1280.png`

The sheet states exactly what to inspect (product identity, mask edges,
text correctness, dimensions, and whether 1280 is actually better) and the
provisional-default decisions requested.

## 7. Tests / regression

- `test_creative_shared_services.py`: 23 passed.
- Full creative suite (8 files): **138 passed in 38.39 s**.
- UI production build: **0 errors** (previous pass).

## 8. Status summary

- **Image milestone accepted** (per instruction).
- **Image closure completed:** items 1–5 above (WT-C delegation, panel-prep
  routing, benchmark paths, high-res validation, integrity records) and the
  owner-review set (item 6) produced.
- **Owner visual review pending:** quality defaults + representative samples.
- **Video implementation proposed** (`docs/creative/VIDEO_AUDIO_PLAN.md`);
  **not implemented or tested.**
- **Remaining gaps:** Real-ESRGAN upstream digest unavailable; ffmpeg not
  installed (video prerequisite); weight SHA-256 for any future video/audio
  models not yet recorded; owner review outstanding.
