# Shared Creative Services — Setup & Run

Reproducible local setup for the shared creative pipeline.

## 1. Model weights (ComfyUI runtime)

Install the approved components into the local ComfyUI at `C:\Users\T2Hol\ComfyUI`:

```powershell
C:\Python314\python.exe tools\creative\fetch_models.py          # all approved components
C:\Python314\python.exe tools\creative\fetch_models.py sdxl-base-1.0 birefnet  # subset
```

The fetcher is resumable, verifies byte sizes, and writes SHA-256 digests +
presence back into `shared/creative-components.json`.

| Component | Destination |
|---|---|
| SDXL Base 1.0 | `models/checkpoints/sd_xl_base_1.0.safetensors` |
| Z-Image-Turbo (nvfp4) | `models/diffusion_models/z_image_turbo_nvfp4.safetensors` |
| Z-Image text encoder | `models/text_encoders/qwen_3_4b_fp8_mixed.safetensors` |
| Z-Image / FLUX VAE | `models/vae/ae.safetensors` |
| IP-Adapter Plus SDXL | `models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors` |
| CLIP-ViT-H | `models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` |
| ControlNet Canny SDXL (xinsir) | `models/controlnet/xinsir-canny-sdxl.safetensors` |
| BiRefNet | `models/background_removal/birefnet.safetensors` |
| Real-ESRGAN x4plus | `models/upscale_models/RealESRGAN_x4plus.pth` |

## 2. Custom node

```powershell
git clone --depth 1 https://github.com/cubiq/ComfyUI_IPAdapter_plus `
  C:\Users\T2Hol\ComfyUI\custom_nodes\ComfyUI_IPAdapter_plus
```

## 3. Start ComfyUI (restart required after adding weights)

```powershell
C:\Users\T2Hol\ComfyUI\venv\Scripts\python.exe C:\Users\T2Hol\ComfyUI\main.py --lowvram
```

ComfyUI 0.38.0 has built-in SDXL, Z-Image, Canny, ControlNet, upscaling, and
BiRefNet background-removal nodes — no extra custom nodes are needed except
IP-Adapter Plus.

## 4. Start the backend

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:NORTHSTAR_RATE_LIMIT_EXEMPT_CREATIVE='1'   # optional: local operator lanes
cd Northstar_backend
..\venv-phase1c02\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## 5. Verify

```powershell
# API
Invoke-WebRequest http://127.0.0.1:8000/api/creative/components/status
Invoke-WebRequest http://127.0.0.1:8000/api/creative/lanes
Invoke-WebRequest http://127.0.0.1:8000/api/creative/workers

# One routed generation
$body = @{ task='generate'; payload=@{ prompt='studio product photo of a glass jar'; mode='draft' } } | ConvertTo-Json -Depth 5
(Invoke-RestMethod http://127.0.0.1:8000/api/creative/pipeline -Method Post -ContentType 'application/json' -Body $body).job_id
```

## 6. UI

```powershell
cd northstar-os-ui ; npm run build      # or: npm run dev  (port 8101)
```

The **Studio → Creative Studio → Exact-Text Mockups** surface renders the
`CreativeServicesPanel` (component status, lane routing, mask/upscale/generate jobs).

## 7. Tests

```powershell
cd Northstar_backend
C:\Python314\python.exe -m pytest test_creative_*.py -q
```

## 8. Benchmarks

```powershell
C:\Python314\python.exe tools\creative/benchmark.py --task generate --mode draft `
  --lane z-image-draft --label zimage_draft --prompt "..."
```

Results are written to `reports/creative_benchmarks/`.

## Resource policy

- Heavy-job concurrency: **1** (`shared/creative-deployment.json`).
- ComfyUI models are unloaded between independent heavy stages (`POST /free`).
- Do not run local planning/vision LLMs concurrently with diffusion without
  measured headroom.
- Multi-GPU: add one worker entry per GPU in `shared/creative-deployment.json`;
  do not assume VRAM pooling or single-job multi-GPU acceleration.
