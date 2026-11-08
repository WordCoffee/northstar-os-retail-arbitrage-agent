# Local Model Inventory — 2026-10-27 22:31

Read-only survey. No model pulled, deleted, loaded or reconfigured. Evidence: `ollama list` /
`/api/tags` / `/api/ps`, `ollama show --modelfile`, disk listing of `~\models`,
`C:\Users\T2Hol\ComfyUI\models`, `C:\Users\T2Hol\ComfyUI-LTX\models`, HF cache,
`shared/model-suite.json`, `shared/service-model-map.json`, `Northstar_backend/model_router.py`,
`autothink/backend/llm_adapter.py`, `Northstar_backend/studio_generation.py`,
`Northstar_backend/local_vision.py`, `corpus_drift.py`, live `GET /api/v1/provider-suite`.

## 1. Ollama (127.0.0.1:11434 — LIVE, 4 tags, 8.7 GB blobs, nothing resident)

| tag | size | identity | wired use |
|---|---|---|---|
| `bojo:latest` | 2.5 GB | Qwen 3.5 2B (qwen35, 1.9B, Q8_0), vision+tools+thinking, num_ctx 8192, num_predict 2048, temp 0.2, SYSTEM prompt baked | Bojo assistant identity. `autothink/llm_adapter.DEFAULT_LOCAL_MODEL` → chat_adapter/chat_router (Bojo chat), design_studio_agent. CPU (`OLLAMA_NUM_GPU=0`, `OLLAMA_LLM_LIBRARY=cpu`). |
| `qwen3.5:2b` | 2.5 GB | same weights as Bojo (shared blobs) | Base tag for Bojo + `OOM_FALLBACK_MODEL_MAP['bojo']`. Removing it breaks Bojo. |
| `qwen2.5vl:7b` | 5.56 GB | Qwen2.5-VL 8.3B Q4_K_M, vision | V1/V2/V3 understanding tiers (`model_router`, `model-suite.json`); `/api/design-studio/lanes/qc` vision QC (`local_vision.py`, CPU + keep_alive 0); `tools/browser_agent.py` fallback; `audit_sb.py` / `run_vision_sb.py`. |
| `qwen3-embedding:0.6b` | 0.6 GB | 1024-d | `corpus_drift.py` semantic search (sqlite-vec, cosine), chat_tools knowledge/retrieval. |

## 2. llama.cpp GGUF workers (not running; :8080 :8123 closed)

`C:\Users\T2Hol\models\northstaros-qwen3.8\`
- `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` 9.73 GB — served by `scripts/start-northstar-llm.ps1`
  as alias `northstaros-qwen3.8:27b` on :8080, `-ngl 99`, 65536 ctx, q4_0 KV, MTP draft.
  Measured ~69 tok/s decode. Role: large local text worker (coding/general).
- `Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` 11.29 GB — installed 2026-10-27, benched at
  80K ctx (55 tok/s, 15.1 GB VRAM). **Not wired**: no launcher references it.
- `mmproj-Qwen3.8-27B-BF16.gguf` 0.87 GB — 27B vision projector, **not loaded** (needs 32 GB+ VRAM).

## 3. ComfyUI (127.0.0.1:8188 — DOWN right now)

Wired to `studio_generation.py` lanes:
- `Flux-2-Klein-9B-KV-Q8_0.gguf` 9.29 GB — image generate (STUDIO_FLUX2_MODEL default)
- `qwen-image-edit-2511-Q4_K_M.gguf` 12.34 GB — edit/refine (OCR drift gate)
- `birefnet.safetensors` — cutout
- `Wan2.2-TI2V-5B-Q5_K_M.gguf` 3.55 GB — local video
- `flux-2-klein-base-9b-Q6_K.gguf` 7.33 GB — UltraTex 3D texturing base
- text encoders: `qwen_3_8b_fp8mixed` (Flux2/edit), `qwen_2.5_vl_7b_nvfp4` (edit encoder),
  `t5xxl_fp8`, `umt5-xxl-Q5_K_M`, `qwen_3_4b_fp8_mixed` (FLUX3 placeholder)

Installed but not wired to a Northstar lane: `flux1-dev-fp8` (FLUX.1-dev non-commercial, legacy
`generate_images.py` default only), `sd_xl_base_1.0`, `z_image_turbo_nvfp4`, `iclight` unets,
controlnet xinsir/union, `ip-adapter-plus_sdxl`, `CLIP-ViT-H-14`, `seedvr2_3b` + vae
(upscale path deprecated — RealESRGAN ablation, see 00_STATE), `Qwen3-TTS 1.7B` base +
CustomVoice (only inventoried by `comfy_smoke.py`; Piper is the wired voice engine).

`C:\Users\T2Hol\ComfyUI-LTX` (reached via `extra_model_paths.yaml`, zero copy):
`ltx-2.3-22b-dev-nvfp4` 20.21 GB, `ltx-2.3-22b-distilled-lora-384` 7.08 GB,
`gemma_3_12B_it_fp4_mixed` 8.8 GB, text projection + video/audio VAEs. Native LTX2 nodes exist
in the active ComfyUI; **no Northstar code path drives them yet**.

## 4. Audio / vision utilities (all local, no key)
- Piper `en_US-lessac-medium.onnx` 60 MB — preferred narration engine (`local_voice.py`).
- faster-whisper `base` (HF cache) — `local_transcribe.py`, CPU int8.
- RapidOCR (onnxruntime) — text-fidelity gate in `text_fidelity.py`.
- Laya 421M ONNX — optional `decision_layer` backend (6/12 vs rules 12/12; never default).

## 5. Drift found (not fixed — needs an operator call)

1. **Text tiers resolve to a deleted model.** `shared/model-suite.json` T1/T2/T3 `local` is
   still `northstaros-qwen3.8:27b`, which was removed from Ollama today. The config overlay
   beats the hardcoded defaults, so `model_router.resolve('local', t)` returns the missing id
   for all three tiers (`model_router.py` `LOCAL_MODELS` says `bojo`). Live check:
   `T1/T2/T3 -> northstaros-qwen3.8:27b`. Choice: repoint to `bojo` (real quality drop for
   T3 "audit-grade") or teach the router the llama.cpp :8080 worker.
2. `chromeconnect_model_bench.CANDIDATE_MODELS` lists three ids that no longer
   exist (`northstaros-qwen3.8:27b`, `qwen3.8-27b-coder:latest`, `...-ctx64k-orig`), so the
   Phase-4 browser-brain benchmark cannot reproduce its recorded pass_rate.
3. `autothink NUM_CTX=16384` vs Bojo's baked `num_ctx 8192`; `~/.config/opencode/opencode.json`
   still labels Bojo "qwen3.5:4b Q4_K_M" (it is 1.9B Q8_0) and routes `ollama-local` at :8080
   with the deleted 27B id, plus `"model": "llamacpp/local"` (no such model id; the llamacpp
   entry is `coding-worker`). This session runs on opencode-go/deepseek-v4.1-flash, not local.

## 6. Not touched
No pull, no delete, no load, no policy/allowlist change, no `.env` read, no spend.
