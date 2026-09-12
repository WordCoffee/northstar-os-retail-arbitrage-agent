# Local Image Generation — RTX 5080 Mobile 16GB Setup Guide

> Your MSI Vector 16 HX AI (RTX 5080 Mobile, 16GB VRAM) is a **very capable** local image generation machine. Here's what fits and how to set it up.

---

## TL;DR — What Runs on Your GPU

| Model | Size | VRAM | Steps | Quality | Speed | License |
|-------|------|------|-------|---------|-------|---------|
| **FLUX.1 Dev FP8** | ~12GB file | ~12-14GB VRAM | 20-50 | ⭐⭐⭐⭐⭐ | ~15-25s | Non-commercial |
| **FLUX.2 Klein 4B** | ~13GB FP16 | ~13GB VRAM | 4 | ⭐⭐⭐⭐ | ~3-5s | **Apache 2.0 (commercial)** ✅ |
| **FLUX.2 Klein 9B FP8** | ~9GB | ~14-16GB VRAM | 4 | ⭐⭐⭐⭐+ | ~4-6s | Non-commercial |
| **HiDream-I1-Fast NF4** | ~8GB | ~14GB VRAM | 16 | ⭐⭐⭐⭐⭐ | ~10-15s | MIT ✅ |
| **HiDream-I1-Dev NF4** | ~8GB | ~14GB VRAM | 28 | ⭐⭐⭐⭐⭐ | ~20-30s | MIT ✅ |
| **FLUX.1 Schnell** | ~12GB | ~12GB VRAM | 4 | ⭐⭐⭐⭐ | ~3-5s | Apache 2.0 ✅ |
| **SDXL** | ~6.5GB | ~8GB VRAM | 20-30 | ⭐⭐⭐ | ~5-10s | CreativeML OpenRAIL |
| **SD 3.5 Large** | ~16GB | ~16GB VRAM | 20-50 | ⭐⭐⭐⭐ | ~15-30s | Stability AI Community |

**Best picks for your 16GB:**
1. 🥇 **FLUX.1 Dev FP8** — best quality-to-VRAM ratio, the community gold standard
2. 🥈 **HiDream-I1-Fast NF4** — **best for photorealistic people**, MIT licensed
3. 🥉 **FLUX.2 Klein 4B** — fastest, commercially usable (Apache 2.0)

---

## Option A: ComfyUI (Recommended)

ComfyUI is the most popular local image generation interface. Full control, workflow sharing, huge node ecosystem.

### Install ComfyUI

```bash
# 1. Clone ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Install PyTorch with CUDA (check https://pytorch.org for latest)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 4. Install ComfyUI dependencies
pip install -r requirements.txt
```

### Download Models (pick one or more)

#### FLUX.1 Dev FP8 (recommended first model)
```bash
# ~11.9 GB download
# Download the FP8 quantized version (fits in 16GB VRAM)
# Get from: https://huggingface.co/Kijai/flux-fp8
# Files needed:
#   - flux1-dev-fp8.safetensors → ComfyUI/models/unet/
#   - ae.safetensors (VAE) → ComfyUI/models/vae/
#   - clip_l.safetensors → ComfyUI/models/clip/
#   - t5xxl_fp8_e4m3fn.safetensors → ComfyUI/models/clip/
```

Or with `huggingface-cli`:
```bash
pip install huggingface-hub
huggingface-cli download Kijai/flux-fp8 flux1-dev-fp8.safetensors --local-dir models/
huggingface-cli download Kijai/flux-fp8 ae.safetensors --local-dir models/vae/
huggingface-cli download comfyanonymous/flux_text_encoders clip_l.safetensors --local-dir models/clip/
huggingface-cli download comfyanonymous/flux_text_encoders t5xxl_fp8_e4m3fn.safetensors --local-dir models/clip/
```

#### FLUX.2 Klein 4B (fastest, Apache 2.0)
```bash
# ~13GB download (FP16)
huggingface-cli download black-forest-labs/FLUX.2-klein-4B --local-dir models/FLUX.2-klein-4B/
# Place transformer files in ComfyUI/models/diffusion_models/
```

#### HiDream-I1-Fast NF4 (best for people, MIT)
```bash
# ~8GB download (NF4 quantized)
# Get from: https://huggingface.co/azaneko/HiDream-I1-Fast-nf4
# Place in ComfyUI/models/unet/ or ComfyUI/models/diffusion_models/
```

### Launch ComfyUI
```bash
python main.py --lowvram    # Start with VRAM optimization
# Open http://127.0.0.1:8188 in your browser
```

### Connect to Image Generator
```bash
# Set the ComfyUI URL (default is already correct)
set COMFYUI_URL=http://127.0.0.1:8188

# Generate using local backend
python tools/generate_images.py --backend local --concept analysts-desk
```

---

## Option B: Diffusers (Python API, no GUI)

If you prefer pure Python without ComfyUI:

```bash
# Install
pip install diffusers transformers accelerate optimum quanto

# Quick generation script
```

```python
import torch
from diffusers import FluxPipeline
from optimum.quanto import freeze, qfloat8, quantize

# Load FLUX.1 Dev with FP8 quantization
pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-dev",
    torch_dtype=torch.bfloat16,
)
quantize(pipe.transformer, weights=qfloat8)
freeze(pipe.transformer)
pipe = pipe.to("cuda")

# Generate
image = pipe(
    prompt="A photorealistic portrait of a professional woman in a modern office",
    height=1024,
    width=1024,
    num_inference_steps=20,
    guidance_scale=3.5,
    max_sequence_length=512,
).images[0]

image.save("output.png")
```

---

## Model Recommendations by Use Case

### For UI Mockups / Logos (Northstar designs)
→ **FLUX.1 Dev FP8** — excellent at geometric shapes, clean lines, UI layouts

### For Photorealistic People
→ **HiDream-I1-Fast NF4** or **HiDream-I1-Dev NF4** — specifically excels at people, skin, faces

### For Speed (iterating quickly)
→ **FLUX.2 Klein 4B** — 4 steps, ~3-5 seconds, commercially usable

### For Maximum Quality (time doesn't matter)
→ **FLUX.1 Dev FP8** at 50 steps — push it to the limit

---

## Disk Space Budget

| Component | Size |
|-----------|------|
| ComfyUI install | ~2GB |
| FLUX.1 Dev FP8 + VAE + CLIP | ~18GB |
| HiDream-I1-Fast NF4 | ~8GB |
| FLUX.2 Klein 4B | ~13GB |
| **Total for 3 models** | **~41GB** |

Budget **50-60GB** free if you want room for LoRAs and experiments.

---

## VRAM Tips for 16GB

1. **Use FP8 quantized models** — the single biggest VRAM saver, nearly identical quality
2. **Use FP8 T5 encoder** — saves ~5GB over FP16 T5
3. **Keep batch size at 1** — never batch on 16GB
4. **Close GPU-hungry apps** — browsers with many tabs, Discord, games
5. **Use `--lowvram`** flag in ComfyUI if you get OOM errors
6. **Don't run FLUX.2 Dev 32B** — needs ~32GB even at FP8, won't fit
7. **Don't run HiDream Full FP16** — needs ~60GB, use NF4 quantized instead

---

## Quick Start (Fastest Path)

If you just want to get generating NOW:

```bash
# 1. Install ComfyUI (5 min)
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI && python -m venv venv && venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt

# 2. Download FLUX.1 Schnell (fastest to download and run, ~12GB)
#    It's built into ComfyUI as a downloadable model — just open the UI

# 3. Start
python main.py

# 4. Open http://127.0.0.1:8188, load a FLUX workflow, and generate!
```

Then upgrade to FLUX.1 Dev or HiDream when you want better quality.
