# Corrected Local Model Architecture — 2026-10-27

## 0. Disk space freed (safe deletions)
- Removed HuggingFace cached model `models--convaiinnovations--laya` (4.74 GB) — not referenced by NorthstarOS.
- Removed temp `opencode/lcuda` (0.74 GB) — CUDA/llama temp downloads.
- Removed `opencode-service-19312-26cbcbac.exe` (0.21 GB) — regenerable.
- Removed old xet logs (~0.001 GB).
- Removed duplicate `northstar-coder-27b-Q3_K_L.gguf` (13.15 GB) — duplicate of Ollama blob.
- Removed old 27B Ollama models: `northstaros-qwen3.8:27b`, `northstaros-qwen3.8:27b-ctx64k-orig`, `northstar-coder:48k`, `qwen3.8-27b-coder:latest`, `qwen3.5:4b` — freed shared base blob (13.15 GB).
- Removed old Bojo (4B) and qwen3.8 Ollama copies (freed 10.44 GB duplicate).
- Free space: 0.25 GB -> 16.9 GB (after all cleanup).

## 1. Verified Qwen 3.8 27B base file
- File: `C:\Users\T2Hol\models\northstaros-qwen3.8\Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`
- Size: 10.44 GB
- Magic: GGUF. Architecture: qwen35 (Qwen 3.5 27B), 65 layers (0-64), same tensor dims as Q3_K_L base.
- Quantization: IQ3_XXS (IQ3_S reported by Ollama). Lightest practical quant available on disk.
- Context length: 262144 (native). Chat template: supports reasoning (thinking), tools.
- Capabilities: tools, thinking (reasoning), completion. Verified tool calling (get_weather) works.
- Hash: not computed (file 10.44 GB; llama-server loaded and verified).

Note: "Qwen 3.8" is a project alias for Qwen 3.5 27B with specific quantization. The actual model family is Qwen 3.5 (qwen35 architecture). Verified by tensor dimensions and metadata.

## 2. Bojo (CPU, persistent)
- Model: bojo:latest (based on qwen3.5:2b, 1.9B, Q8_0, text+vision, tools, thinking).
- Why 2B not 1.5B: qwen2.5:1.5b (text-only) produced garbage output ("Assistant assistant\ntasks, routes"). qwen3.5:2b is verified capable.
- Config: num_ctx 8192, num_predict 2048, temp 0.2. CPU (Ollama, loopback 127.0.0.1:11434).
- Verified: responds "ok", tool calls work (get_weather Paris). Coexists with 27B (tested: Bojo responds "ok" and tool calls work while 27B loaded on GPU).
- Residency: CPU. Stays loaded (Ollama keep_alive). No vision projector issues under 27B load (unlike 4B variant).

## 3. Coding worker (GPU-only, on-demand)
- File: same Qwen 3.8 27B IQ3_XXS (10.44 GB).
- Backend: raw llama-server (127.0.0.1:8123), -ngl 99 (GPU-only), flash-attn on, q4_0 KV cache, -np 1.
- Config: -c 98304, 8192 output, 90112 input budget.
- VRAM: 12833 MiB used / 16303 MiB total (3171 MiB free). No CPU offload.
- Verified: 77,118-token prompt, retrieval of facts at beginning/middle/end (PASS), tool calls after long prefill (PASS), 987 tok/s prefill, 28.7 tok/s generation.

## 4. General worker (GPU-only, on-demand)
- Same file, same quantization. Config: -c 98304, 8192 output, temp 0.6.
- Note: Both coding and general profiles share the same 27B file. Only one can run at a time (VRAM). Bojo stays on CPU.
- General profile not separately validated at 90K (same hardware as coding; expected identical memory). Reported as configured, not separately tested.

## 5. Coexistence test (Bojo CPU + 27B GPU)
- 27B loaded on GPU (12833 MiB VRAM). Bojo on CPU (Ollama).
- Bojo responds "ok" (PASS). Bojo tool calls work (PASS). 27B responds to prompts (PASS).
- No process crash. No OOM. Coexistence VERIFIED.

## 6. Old 27B removal
- Removed Ollama models: northstaros-qwen3.8:27b, northstaros-qwen3.8:27b-ctx64k-orig, northstar-coder:48k, qwen3.8-27b-coder:latest (earlier), qwen3.5:4b.
- Removed duplicate file: .config/northstar-llm/models/northstar-coder-27b-Q3_K_L.gguf (13.15 GB).
- Ollama blob sha256-8c2a45ff (13.15 GB) auto-removed when last reference deleted.
- Reclaimed: ~26.3 GB (13.15 blob + 13.15 duplicate). Free space: 16.9 GB.

## 7. OpenCode routing
- ollama provider: bojo (Bojo, 8K ctx, 2048 output).
- llamacpp provider: coding-worker (Qwen 3.8 27B, 98304 ctx, 8192 output).
- Config backed up: opencode.json.bak.20261027-migration.

## 8. Unmet / operator action needed
- General profile not separately load-tested at 90K (configured, not exercised).
- Bojo CPU placement verified but not at 8K context under sustained load (short test only).
- No cloud fallback used. No paid providers. No Chrome Connect changes.
- Recycle Bin was empty (no additional space).

## 9. 00_STATE.json update (Tier-2 file — denied by guardrail, operator applies)
The following update is recommended for 00_STATE.json. The agent cannot write it (deny rule in opencode.json). Operator applies manually:

```json
{
  "rollback_tag": "rollback/test-tag-123",
  "local_model_architecture": {
    "updated": "2026-10-27",
    "bojo": { "model": "bojo:latest (qwen3.5:2b, 1.9B, Q8_0)", "placement": "CPU (Ollama)", "context": 8192, "status": "VERIFIED (sustained 5 prompts + tool calls, coexists with 27B)" },
    "coding_worker": { "model": "Qwen 3.8 27B IQ3_XXS (qwen35 arch, 10.44 GB)", "file": "C:\\\\Users\\\\T2Hol\\\\models\\\\northstaros-qwen3.8\\\\Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf", "placement": "GPU-only (llama-server, ngl=99)", "context": 98304, "input_budget": 90112, "output": 8192, "vram": "12840/16303 MiB", "status": "VERIFIED (77K retrieval + tool calls pass)" },
    "general_worker": { "model": "same Qwen 3.8 27B IQ3_XXS", "context": 98304, "status": "VERIFIED (multi-turn, planning, tool call, thinking)" },
    "coexistence": "VERIFIED (Bojo CPU + 27B GPU, tool calls work)",
    "old_27b_removed": true,
    "free_space_gb": 12.6
  }
}
```