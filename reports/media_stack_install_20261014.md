# Local media stack — ComfyUI image / video / audio install (2026-10-14)

**Branch:** `feature/overnight-remediation-20261009` · Operator-directed install
("same logic as the master-brain hunt": verify names → fit to hardware → install
→ prove with real outputs). All local; zero paid calls. Companion doc:
`docs/MEDIA_STACK_2026-10.md` (per-model map + fix list).

## Smoke results — 5/5 PASS (real outputs, real timings)

| # | Lane / test | Result | Time | Output (ComfyUI `output/`) |
|---|---|---|---|---|
| 1 | **Z-Image Turbo** · 1024² photoreal product render | PASS | **~11 s warm** | `ns-smoke-zimage_00001_.png` (catalog-grade mug) |
| 2 | **FLUX.2 klein 4B Q8** · 1024² studio product render | PASS | **24.4 s** | `ns-smoke-klein_00002_.png` (kettle, studio lighting) |
| 3 | **SeedVR2 3B** · 2× upscale (1024→2048) of #1 | PASS | **27.1 s** | `ns-smoke-seedvr2_00001_.png` |
| 4 | **Wan 2.2 TI2V-5B** · 832×480, 2 s, 20 steps, 24 fps | PASS | **105.8 s** | `ns-smoke-wan_00001_.mp4` (H.264, 2.04 s) |
| 5 | **Qwen3-TTS CustomVoice** · narration ("Ryan") | PASS | **27.3 s** | `ns-smoke-tts_00001.flac` (6.54 s, 24 kHz mono) |

Evidence: `reports/comfy_media_smoke_20261014_222559.json` (+ two earlier runs).
Harness: `tools/comfy_smoke.py` (re-runnable; auto-skips missing files).

## Installed inventory (all SHA-256-verified unless noted)

**ComfyUI** `C:\Users\T2Hol\ComfyUI` — updated **0.40.0**; custom nodes
ComfyUI-GGUF, controlnet_aux, IPAdapter_plus, **ComfyUI-QwenTTS**.

| Slot | File(s) |
|---|---|
| Fast photoreal | `z_image_turbo_nvfp4.safetensors` (4.2 GB, pre-existing) + `qwen_3_4b_fp8_mixed` + `ae.safetensors` |
| Commercial-safe FLUX | `flux-2-klein-4b-Q8_0.gguf` (4.30 GB) + `flux2-vae.safetensors` (re-fetched; sha `d64f3a68…`) |
| Photo edit / text-in-image | `qwen-image-edit-2511-Q4_K_M.gguf` (12.3 GB, pre-existing) + `qwen_2.5_vl_7b_nvfp4` |
| Upscaler (image + video) | `seedvr2_3b_fp8_e4m3fn.safetensors` (3.39 GB) + `seedvr2_ema_vae_fp16` |
| Video | `Wan2.2-TI2V-5B-Q5_K_M.gguf` (3.81 GB) + `umt5-xxl-encoder-Q5_K_M.gguf` (4.15 GB) + `wan2.2_vae` |
| Narration / voice clone | Qwen3-TTS `1.7B-Base` (3.68 GB) + `1.7B-CustomVoice` (3.57 GB) + `Tokenizer-12Hz` |
| Legacy (keep/decide) | `flux1-dev-fp8` (non-commercial), SDXL base, t5xxl, controlnets, IPAdapter |

**Tools:** ffmpeg **9.0.2** at `C:\Users\T2Hol\tools\ffmpeg\bin` (on PATH) ·
`tools/clip_split.py` (long video → 5–15 s clips, fixed or scene-detect; plus
`concat`) · `tools/comfy_smoke.py`.

## Hardware notes (measured, not guessed)

- **VRAM**: all lanes fit 16 GB with the master brain unloaded (sequential
  policy enforced via `keep_alive:0`).
- **RAM (15.4 GB)**: Wan 2.2 produced a real clip at 480p/2 s in 106 s — the
  RAM wall applies to ≥720p/longer clips. LTX-2.3 I2AV (native audio + lip
  sync) stays deferred until the 64 GB upgrade.
- **Pagefile** ballooned to 36 GB under renders → capped via registry
  (4/24 GB) — **reboot required** to reclaim ~12 GB of disk.

## Install-saga fixes (details in MEDIA_STACK doc)

1. Truncated `flux2-vae` (bad size guess) → re-downloaded with true size+sha.
2. Part-merge rewritten as streaming .NET concat (`cmd copy` unreliable).
3. QwenTTS chain: `sox` + `onnxruntime` installed; `transformers` pinned
   **4.57.0** (5.18 breaks vendored configs); one vendored patch
   (`@check_model_inputs()` → `@check_model_inputs`).
4. Network collapsed to ~30 KB/s mid-install → resumable 6-connection chunked
   downloads won; all files verified after.
5. Disk hygiene: pip cache (10.2 GB) + HF cache (3.6 GB) + TEMP (4.1 GB) purged.

## Open items

- **Reboot** to apply the pagefile cap (frees ~12 GB).
- Base-model voice cloning verified at the dependency level; formal clone test
  when a reference clip is supplied.
- **Design Studio wiring** (next build): MEDIA_GEN_LIVE runner using the
  verified graphs in `tools/comfy_smoke.py`; clip list → `clip_split.py`
  concat; cloud lanes (fal: wan-2.5/kling/veo) unchanged for the interim.
- LTX-2.3 / InfiniteTalk: install after RAM upgrade.

## Rollback

Delete the files above from `ComfyUI/models/**`; re-download from the pinned
repos in `docs/MEDIA_STACK_2026-10.md`. Code reverts via git.
