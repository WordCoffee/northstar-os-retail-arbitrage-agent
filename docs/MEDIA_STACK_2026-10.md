# NorthstarOS media stack (2026-10-14) — local image / video / audio

Operator-directed install (same method as the master-brain hunt: verify names,
fit to the actual machine — RTX 5080 Laptop 16 GB VRAM / 15.4 GB RAM / C: SSD).

## Hardware gates (measured)

- **Image generation: fully local-ready.** All picks below fit 16 GB VRAM with
  the master brain unloaded.
- **Video generation: VRAM fits, SYSTEM RAM is the gate.** Every credible
  2026 video pipeline (LTX-2.3/2.5, Wan 2.2, Kandinsky 6 Lite, Prism) wants
  32–64 GB system RAM for offload; independent benchmarks on this exact GPU
  (RTX 5080 16 GB, driver 610.88) show 36–46 GB RAM peaks. On 15.4 GB RAM the
  good video models cannot run properly. **RAM upgrade (2×32=64 GB) is the
  unlock**, exactly like the MoE lesson from the Qwen build.
- **Sequential VRAM policy (enforced):** the master brain (Ollama,
  `northstaros-qwen3.8:27b`, ~14 GB) and ComfyUI renders cannot co-reside.
  Unload before media jobs:
  `curl.exe -s http://127.0.0.1:11434/api/generate -d '{\"model\":\"northstaros-qwen3.8:27b\",\"keep_alive\":0}'`
  Ollama auto-reloads on the next LLM request.

## Runtime

- **ComfyUI** `C:\Users\T2Hol\ComfyUI` (git clone, venv Python 3.14, CUDA via
  torch, updated to 0.40.0 on 2026-10-14). Start: `venv\Scripts\python.exe
  main.py --listen 127.0.0.1 --port 8199` (dev/diagnostic port; default UI
  port 8188 free for the Studio integration).
- Custom nodes: ComfyUI-GGUF, controlnet_aux, IPAdapter_plus, ComfyUI-QwenTTS.
- **ffmpeg** — required for clip tooling (`tools/clip_split.py`). Discovered via
  $FFMPEG / PATH / WinGet Links / imageio-ffmpeg fallback.

## Image models (verified installed)

| Slot | Model (file) | Notes |
|---|---|---|
| Photoreal base (fast) | **Z-Image Turbo** `z_image_turbo_nvfp4.safetensors` (4.2 GB) + `qwen_3_4b_fp8_mixed` + `ae.safetensors` | Apache 2.0 · 8 steps, CFG 1, `res_multistep/simple` · first verified render 1024² mug ~catalog grade |
| Commercial-safe FLUX | **FLUX.2 klein 4B** `flux-2-klein-4b-Q8_0.gguf` (4.3 GB, via UnetLoaderGGUF) + `flux2-vae.safetensors` | Apache 2.0 · distilled: `euler` + Flux2Scheduler 4 steps + CFGGuider cfg 1 |
| Photo edit / A+ text | **Qwen-Image-Edit 2511** `qwen-image-edit-2511-Q4_K_M.gguf` (12.3 GB) + `qwen_2.5_vl_7b_nvfp4` + `qwen_image_vae` | pre-installed; edit lane for real product photos and text-in-image |
| Legacy photoreal | `flux1-dev-fp8.safetensors` (11.1 GB) | NON-COMMERCIAL license — personal/eval only, do not ship client work |
| Upscaler (product/video) | **SeedVR2 3B** `seedvr2_3b_fp8_e4m3fn.safetensors` (3.4 GB) + `seedvr2_ema_vae_fp16` | Apache 2.0 · Comfy's own guide names SeedVR2 for product photography; upscales images AND video |

## Video models

| Slot | Model | Status |
|---|---|---|
| Trial / product b-roll | **Wan 2.2 TI2V-5B** (`Wan2.2-TI2V-5B-Q5_K_M.gguf` 3.8 GB + `umt5-xxl-encoder-Q5_K_M.gguf` + `wan2.2_vae.safetensors`) | installed; **RAM-gated** — needs 32 GB+ RAM for practical runs |
| UGC clips + native audio + lip sync | **LTX-2.3 I2AV** (+ distilled LoRA, Gemma-3 encoder, ~25–43 GB) | Phase B — install after RAM upgrade |
| Talking heads on existing footage | InfiniteTalk / MultiTalk (Wan 2.1 I2V base + extras) | later, RAM-gated |
| Interim UGC | app cloud lane (fal: wan-2.5 / kling / veo, behind `MEDIA_GEN_LIVE`) | gated, not local |

Clip assembly: **`tools/clip_split.py`** — `split` (fixed 5–15 s windows or
scene-detect) and `concat` (stream-copy with re-encode fallback). JSON output is
Design-Studio-consumable. Design Studio consumes clip lists for piecing
together 5–15 s segments; long video → clips is this tool, per operator spec.

## Audio / narration (local)

- **Qwen3-TTS (12 Hz)** via ComfyUI-QwenTTS — `Qwen3-TTS-12Hz-1.7B-Base`
  (3-second voice clone) + `Qwen3-TTS-Tokenizer-12Hz` in
  `ComfyUI/models/TTS/Qwen3-TTS/`. Narration presets via CustomVoice (not yet
  downloaded) or Chatterbox in TTS-Audio-Suite (optional).
- In-video native audio arrives with LTX-2.3 (Phase B). Cloud voiceover lane
  (elevenlabs/deepgram) unchanged in the app suite.

## Wiring status

- Repo `shared/model-suite.json` still references `comfyui:flux2-klein-4b` —
  accurate; extend when the Studio integration (MEDIA_GEN_LIVE runner) is
  built. This doc is the source of truth for runner model IDs.
- ComfyUI's own outputs land in `C:\Users\T2Hol\ComfyUI\output`.

---

## 2026-10-14 install results (smoke-verified)

| Test | Result | Time | Output |
|---|---|---|---|
| Z-Image Turbo · 1024² product render | PASS | **~11 s warm** | `ns-smoke-zimage_00001_.png` (catalog-grade mug) |
| FLUX.2 klein 4B Q8 · 1024² product render | PASS | **24–31 s** | `ns-smoke-klein_00002_.png` (studio kettle) |
| SeedVR2 3B · 2× upscale (1024→2048) | PASS | **27.1 s** | `ns-smoke-seedvr2_00001_.png` |
| Wan 2.2 TI2V-5B · 832×480 · 2 s clip · 20 steps | PASS | **105.8 s** | `ns-smoke-wan_00001_.mp4` |
| Qwen3-TTS narration (CustomVoice) | see `_tts_weights.log` + smoke json | — | pending final run |

Notable: Wan 2.2 produces a real clip on 15.4 GB RAM at 480p/2s in under two
minutes (the RAM wall applies to ≥720p / longer clips). Sequential policy
enforced (brain unloaded) for every test.

## Fixes applied during install (keep this list)

1. **flux2-vae was truncated** by an early guess at its size — re-downloaded
   with the true size/SHA (`d64f3a68…`, 336,213,556 B). All other files were
   SHA-256-verified at staging time.
2. **Chunk merges** use a streaming .NET concat (`_part0..5` → file), not
   `cmd copy /b` (unreliable with this file mix).
3. **ComfyUI-QwenTTS node** (user-installed copies may overwrite these):
   - vendored `qwen_tts` needed `sox` + `onnxruntime` + `transformers==4.57.0`
     (5.18 broke vendored config classes with `pad_token_id` AttributeError);
   - patched `@check_model_inputs()` → `@check_model_inputs` in
     `qwen_tts/core/tokenizer_12hz/modeling_qwen3_tts_tokenizer_v2.py`;
   - TTS model weights pulled to `models/TTS/Qwen3-TTS/<repo>/`.
4. **Pagefile** was ballooning (36 GB+) under video renders and ate disk space
   mid-download. Capped via registry to 4 GB initial / 24 GB max
   (`HKLM\...\Memory Management\PagingFiles = "C:\pagefile.sys 4096 24576"`) —
   **applies at next reboot** and reclaims ~12 GB then.
5. Disk hygiene: pip cache purge (10.2 GB), HF cache cleared (3.6 GB), TEMP
   cleanup (4.1 GB).
