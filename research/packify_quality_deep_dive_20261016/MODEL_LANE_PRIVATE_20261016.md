# MODEL LANE — private-use revision (2026-10-16, operator decision)

Operator: *"for now let's not focus on commercial use, since we will be using
this for our own private brands first — we can look at non-commercial if it
fits better."*

**Policy change:** the commercial-safe constraint is relaxed for the private
lane. Non-commercial (NC) models are now allowed where they fit better. The one
line that still matters (not a blocker, just bookkeeping): NC licenses restrict
*commercial use of the outputs*, and selling a product is commercial use — so
every asset sidecar records its model + license class, and NC-tagged artwork
gets re-derived or re-rendered on commercial-safe models before print plates go
to a co-packer. Tagging now makes that cleanup cheap later.

## Revised picks (private lane)

| Role | Pick | License class | Status |
|---|---|---|---|
| Base generation | FLUX.2 **klein 4B** Q8 GGUF | Apache-2.0 | installed (in production use) |
| Base generation (upgrade) | FLUX.2 **klein 9B** Q8 GGUF (`flux-2-klein-9b-Q8_0.gguf`, leejet) | FLUX Non-Commercial | **pulling now** (~9.5 GB) |
| Edit / refine | **Qwen-Image-Edit-2511** Q4_K_M GGUF (`qwen-image-edit-2511-Q4_K_M.gguf`) + `qwen_2.5_vl_7b_nvfp4` encoder | Apache-2.0 | **already on disk** (since 2026-10-06; verify VAE, then smoke) |
| Layout / reference control | **refcontrol klein 4B depth** LoRA (`flux2_klein_4b_refcontrol_depth.safetensors` + official workflow JSON) | Apache-2.0 | **pulling now** |
| Layout / reference control (9B) | **refcontrol 9B pose** LoRA (`refcontrol_v2_poses.safetensors` + workflow JSON) | see card | **pulling now** |
| FLUX.1 ecosystem (IPAdapter / ControlNet / regional prompting / UNO / In-Context-LoRA) | `flux1-dev-fp8.safetensors` | FLUX.1-dev Non-Commercial | on disk since 2026-10-04 — **blocked: `t5xxl` text encoder missing** (next pull ≈ 5 GB: `t5xxl_fp8_e4m3fn.safetensors`) |
| Design/typography generator | `Qwen-Image-2.1` Q4 GGUF (2K, typography, alpha) | Qwen Research License (NC) | next candidate (≈12 GB) — directly on-target: professional type + alpha cutouts |
| Matting | BiRefNet (MIT) stays default; RMBG-2.0 now also permitted | MIT / BRIA NC | BiRefNet installed path planned |
| LoRA training | ai-toolkit on klein **base** 4B/9B | Apache / NC weights | plan phase P4 |
| Existing (unchanged) | SeedVR2 (Apache), Wan 2.2 (Apache), IC-Light (Apache + BRIA matting note no longer blocking) | — | installed |

## What this actually unlocks for quality (why NC fits better here)

1. **klein 9B > 4B** for scene/art quality and its refcontrol LoRAs give us the
   depth/reference conditioning the 4B lacks (the "ControlNet replacement").
2. **Qwen-Image-Edit-2511** was already the headline upgrade — it is Apache,
   and it is already on this machine; the next step is purely a smoke test.
3. **FLUX.1-dev unlocks the whole 2025 control ecosystem** (faithful layout
   control via ControlNet depth/canny, IPAdapter consistency, regional
   prompting) once the missing `t5xxl` encoder lands (~5 GB).
4. **Qwen-Image-2.1** is the strongest open typography generator (2K) — best
   candidate to *preview* label art, with our deterministic text layer still
   owning final type.

## Install commands (reproducible, resumable)

```powershell
# klein 9B Q8 GGUF  -> models\unet\
curl.exe -L -C - --retry 5 -o "C:\Users\T2Hol\ComfyUI\models\unet\flux-2-klein-9b-Q8_0.gguf" `
  "https://huggingface.co/leejet/FLUX.2-klein-9B-GGUF/resolve/main/flux-2-klein-9b-Q8_0.gguf"
# 4B depth refcontrol LoRA -> models\loras\   (+ official workflow -> tools\comfy_workflows\)
curl.exe -L -C - --retry 5 -o "C:\Users\T2Hol\ComfyUI\models\loras\flux2_klein_4b_refcontrol_depth.safetensors" `
  "https://huggingface.co/thedeoxen/refcontrol-FLUX.2-klein-4B-reference-depth-lora/resolve/main/flux2_klein_4b_refcontrol_depth.safetensors"
# 9B pose refcontrol LoRA
curl.exe -L -C - --retry 5 -o "C:\Users\T2Hol\ComfyUI\models\loras\refcontrol_v2_poses.safetensors" `
  "https://huggingface.co/thedeoxen/refcontrol-FLUX.2-klein-9B-reference-pose-lora/resolve/main/refcontrol_v2_poses.safetensors"
# NEXT (not yet pulled): t5xxl encoder (unblocks flux1-dev) and Qwen-Image-2.1 Q4
```

## Provenance rule (effective now)

Every generated asset's sidecar JSON carries `model` + `license_class`
(`apache` | `nc-flux` | `nc-qwen` | `nc-bria` | …). Renders from NC models are
private-lane by default; before any print plate for sale, either re-derive on an
Apache model or replace the NC-derived artwork. The studio render sidecar
already records `model`; extend it with `license_class` when the studio lane is
next touched.

Talk-track (one line, for the record — not a blocker): "NC-licensed models are
fine while this is private R&D; their outputs get re-derived on Apache models
before they go on a product we sell."
