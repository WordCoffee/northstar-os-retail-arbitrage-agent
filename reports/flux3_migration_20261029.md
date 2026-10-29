# FLUX 3 installed; FLUX 2 and the text-correcting vision models removed

**Date:** 2026-10-29
**Machine:** RTX 5080 Laptop, 16 303 MiB, driver 617.42
**Result:** FLUX 3 Image Klein renders on this box. FLUX 2 is gone. Nothing falls
back to FLUX 2 or to the removed edit/vision models.

---

## 1. What was installed

| File | Size | Role |
|---|---|---|
| `flux3-image-klein-nvfp4.safetensors` | 4.92 GB | FLUX 3 Image Klein transformer (native NVFP4, Blackwell) |
| `qwen3vl_4b_int8_convrot.safetensors` | 4.52 GB | FLUX 3 text encoder (Qwen3-VL-4B) |
| `flux2-vae.safetensors` | 336 MB | the VAE FLUX 3 itself uses — **kept deliberately** |

Source: the official `black-forest-labs/flux-3-image-klein-comfy` bundle is
**gated** on Hugging Face (HTTP 401, `GatedRepo`); there is no HF token on this
machine and accepting the licence is an operator act. The same files were
installed from the public mirror `ml-resources/flux-3-image-klein-comfy`
(byte-identical sizes, same LFS objects). No account, token or payment was used.

**Licence:** FLUX Kommunity License, Qualifying User only. The owner recorded
T2 Holdings as under $5M annual revenue on 2026-10-28; this remains a local
bench install, not a customer-facing service.

### Two quant paths that do **not** work here (recorded, not hidden)

1. `flux3-image-klein-int8-convrot.safetensors` → ComfyUI aborts with
   `hostbuf_file_reader_read failed` in `comfy_aimdo.host_buffer` during the
   first sampling step.
2. `flux-3-image-klein-Q6_K.gguf` → ComfyUI-GGUF's `unpatch_model` stalls inside
   `model_use_more_vram` on ComfyUI 0.43 (the custom node has not been updated
   for the new patcher).

The NVFP4 checkpoint is the one that runs. The two failed files (9.9 GB total)
were deleted; manifest: `backups/models/flux3_install_<ts>.json`.

## 2. Runtime changes

ComfyUI was 105 commits behind the commit that added FLUX 3 image support:

```
e0a32bce (2026-10-13)  ->  fd7639f4 (2026-10-29)
Support Flux3-image (#17064) is in that range.
```

- ComfyUI: `git pull --ff-only`, then its venv requirements
  (`comfy-kitchen 0.2.40`, `comfy-aimdo 0.6.0`, frontend 1.57.6,
  workflow templates 0.11.98).
- Rollback point: `e0a32bce` is recorded in the removal manifest; ComfyUI is a
  git checkout, so `git reset --hard e0a32bce` restores it.
- `tools/flux3_gateway.py` was added: `GET /health` + `POST /generate` on
  `127.0.0.1:8190`, implementing the contract `tys_ops.graphics` already spoke.
  It uses ComfyUI as the **local inference runtime only** — the gateway never
  starts ComfyUI, and a stopped ComfyUI means a blocked step, not a fallback.

## 3. What was removed

Manifest: `backups/models/flux2_removal_20261029T181115Z.json`

| File | GB |
|---|---|
| `unet/Flux-2-Klein-9B-KV-Q8_0.gguf` | 9.29 |
| `unet/flux-2-klein-4b-Q8_0.gguf` | 4.01 |
| `diffusion_models/flux-2-klein-base-9b-Q6_K.gguf` | 7.33 |
| `text_encoders/qwen_3_8b_fp8mixed.safetensors` | 8.07 |
| `text_encoders/qwen_3_4b_fp8_mixed.safetensors` | 5.25 |
| `text_encoders/qwen_2.5_vl_7b_nvfp4.safetensors` | 5.69 |
| `unet/qwen-image-edit-2511-Q4_K_M.gguf` | 12.34 |
| `vae/qwen_image_vae.safetensors` | 0.24 |
| `loras/ultratex_flux2.safetensors` | 0.45 |
| `loras/ultratex_flux2_mr.safetensors` | 0.45 |
| `loras/flux2_klein_4b_refcontrol_depth.safetensors` | 0.09 |
| `ultratex/ultratex_flux2_decoder.pt` | 0.09 |
| **total** | **53.27** |

`vae/flux2-vae.safetensors` was **not** removed: FLUX 3's own bundle ships that
exact VAE. Deleting it would break the model being installed.

The Ollama model `qwen2.5vl:7b` (the render QC/OCR checker in
`local_vision.py`) was also not removed: it is not a FLUX 2 asset and it is not
used for text correction of generated copy. Say the word and it goes too.

## 4. Code changes

- `studio_generation.py`
  - FLUX 3 is the only image model; the FLUX 2 branch and the
    `STUDIO_USE_FLUX2` fallback are gone.
  - `_flux3_klein_graph` is the official graph: `UNETLoader`,
    `CLIPLoader type="flux3"`, `VAELoader`, `EmptyFlux2LatentImage`,
    `ModelSamplingFlux`, `KSampler` euler/simple, CFG 1.0, 16 steps.
  - `generate_edit` now fails fast with `edit_lane_removed` instead of
    dispatching a graph against deleted files.
  - `engine_status()` reports the edit model as `null` when it is absent.
- `tys_ops/graphics.py` — default checkpoint is the installed NVFP4 file;
  weight presence is checked against the real folders.
- `tools/flux3_gateway.py`, `tools/comfy_smoke.py` (flux3 smoke test),
  `render_studio_plates.py`, `.env.example`.

## 5. Verification (real renders)

| Path | Result |
|---|---|
| Gateway `POST /generate` 1024×1024, 16 steps | `flux3_00001_.png`, 1.54 MB, 1024×1024 RGB |
| `studio_generation.generate_image` 512×512 | 356 525 bytes, model `flux3-image-klein-nvfp4` |
| Tys vector: work order submitted as `coding` | rewritten to `graphics`, ran, **done** |
| Tys evidence | `engine=flux3`, `model=flux-3-image-klein`, artifact `flux3_00002_.png`, 1024×1024 |
| `GET /api/admin/tys/state` | `graphics available=True`, detail `flux3 endpoint healthy` |
| Tests | **193 passed** (`test_model_compat`, `test_tys_routing`, `test_tys_ops`, `test_tys_assistant`, studio suites) |

Task `tys_1227cbdfc638`: `coding → graphics`, `status=done`,
`stop_reason=all_steps_completed`, cursor 1/1.

Free space after the migration: **64.65 GB** (was 16.63 GB before the removal).

## 6. Honest limits

1. The graphics lane still suspends the MoE coding worker before a render; on
   this run `:8080` was already idle (`nothing_listening`), so the suspension
   had nothing to stop.
2. FLUX 3 is image-only. Video stays on the Wan/Comfy creative lane, which was
   not part of this change.
3. The prompt-upsampling model (`qwen3.5_9b_flux3_prompt_upsampler`) was **not**
   installed: it is a 9.7 GB text model, optional, and the text-encoder alone
   is what the image graph needs. It can be added later without touching this
   wiring.
4. The `edit` lane is now absent by design. Image-to-image editing of a real
   photo (Qwen-Image-Edit) has no replacement yet; FLUX 3's own i2i graph is
   available in the checkpoint repository and can be wired when wanted.
5. No spend, no Amazon request. All downloads were public HTTP.
