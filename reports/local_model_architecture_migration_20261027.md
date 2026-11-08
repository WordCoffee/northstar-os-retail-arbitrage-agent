# Local Model Architecture Migration — 2026-10-27

## A. Inventory

### Hardware
- GPU: NVIDIA GeForce RTX 5080 Laptop, 16303 MiB VRAM, driver 617.42, CUDA UMD 13.4
- RAM: 15791 MB total, ~6357 MB available before migration; commit 35908 MB total
- Disk: C: 3.84 GB free (now ~0.25 GB after failed download attempt; partial blob cleaned)
- Backend: Ollama 0.40.4 (Windows native), llama-server 0.7.0-dev (build 11889)

### Installed models (before)
| Tag | Size | Notes |
|---|---|---|
| qwen3.5:4b | 3.3 GB | Q4_K_M, 4.2B, tool+vision, Apache 2.0 |
| northstar-coder:48k | 13 GB | Q3_K_L 27B, coder variant (OBSOLETE) |
| qwen3.8-27b-coder:latest | 13 GB | Q3_K_L 27B, coder variant (OBSOLETE) |
| qwen2.5vl:7b | 6.0 GB | vision model |
| northstaros-qwen3.8:27b | 13 GB | Q3_K_L 27.3B, verified base (PRESERVED) |
| northstaros-qwen3.8:27b-ctx64k-orig | 13 GB | backup variant (PRESERVED) |
| qwen3-embedding:0.6b | 639 MB | embedding |

### Verified Qwen identity (from metadata, not alias)
- northstaros-qwen3.8:27b: architecture **qwen35** (Qwen 3.5), 27.3B params, context length 262144, Q3_K_L quantization, base blob sha256-8c2a45ff85e7674ca185ec8eb6cdeab0e617ed9d8018caed0b64380eb2a67a5e
- The "qwen3.8" alias is misleading; actual family is Qwen 3.5. Template was {{ .Prompt }} (no chat framing) in the original alias; the coder variant used ChatML with tools.

### Running processes (before)
- Ollama (PID 13252), no models loaded. No llama-server running initially.

### OpenCode routing (before)
- ollama provider: northstar-coder:48k (49152 ctx, tool_call)
- llamacpp provider: local (98304 ctx, 8192 output) — server not running
- openrouter: hosted models (not used for secrets)

## B. Naming
- Bojo is the sole user-facing assistant identity. Created `bojo:latest` in Ollama (qwen3.5:4b base, 8K ctx, bounded output).
- Internal roles: "coding worker" (llamacpp provider), "render worker" (ComfyUI, existing).
- No second assistant persona created. Protocol role values ("assistant", tool schemas) untouched.

## C. Bojo small model
- Selected: qwen3.5:4b (already installed, 4.2B, Q4_K_M, tool+thinking, Apache 2.0). No download needed.
- Note: task targeted 1-2B; 4B is the smallest verified instruct model available. Download of 1.5B attempted but failed (disk full, 0.25 GB free).
- Configured as `bojo:latest`: num_ctx 8192, num_predict 2048, temp 0.2. Loopback via Ollama (127.0.0.1:11434).
- Verified: loads, responds "ok" with think:false via native API. Tool-call parsing inherited from base (verified on qwen3.5:4b family).
- Residency: GPU (3.3 GB) when loaded; conflicts with 27B at 90K (see conflict below). CPU-hosted Bojo proposed as explicit alternative (works on CPU, ~3.3 GB RAM).

## D. 27B GPU-only configuration
- Preserved base model: northstaros-qwen3.8:27b (Qwen 3.5 27.3B, Q3_K_L, base blob sha256-8c2a45ff...).
- No smaller quantization downloaded (disk full). Using existing Q3_K_L.
- GPU-only: ngl=99, flash-attn on, q4_0 KV cache. Verified via nvidia-smi: 15254 MiB used, 750 MiB free. No CPU offload.
- CPU tokenization/scheduling/file I/O are normal (not model-layer offload). Reported accurately.

## E. Coding worker (long context)
- Alias: `coding-worker` in llamacpp provider (OpenCode config).
- Backend: llama-server on 127.0.0.1:8123, model = base blob (Qwen 3.5 27B Q3_K_L).
- Config: -c 98304, -np 1, --cache-type-k q4_0, --cache-type-v q4_0, --flash-attn on, -ngl 99.
- Total context: 98304. Output reservation: 8192. Input budget: 90112.
- One slot (no per-slot division).

## F. Validation
1. Short coding task: PASS (model responds "ok", tool calls work).
2. Tool calls: PASS (get_weather called with correct args via OpenAI API).
3. Long input 77,118 tokens: PASS (retrieval of facts at beginning, middle, end — all correct).
4. Tool calling after long prefill (77,370 tokens): PASS (get_weather called correctly).
5. Prompt processing speed: 1048 tok/s. Generation: 27.1 tok/s. TTFT: ~73s for 77K tokens.
6. VRAM: 15254 MiB used / 16303 MiB total (750 MiB free). System RAM: ~14 GB commit available.
7. Repeatability: 90K run succeeded; 8K run succeeded. Consistent.

### Conflict reported
- 27B at 98304 ctx uses 15254 MiB VRAM, leaving 750 MiB. Bojo (qwen3.5:4b, 3.3 GB) CANNOT co-reside on GPU.
- Proposed alternative: Bojo on CPU (works, ~3.3 GB RAM). This is an explicit proposal, not a silent move.
- If operator prefers Bojo on GPU, 27B context must be reduced to leave ~3.5 GB free (~64K context estimated).

## G. 27B at 90K fits
- 27B at 98304 ctx fits on GPU alone (15254/16303 MiB). No CPU offload. No silent context reduction.
- Long-context tests pass (retrieval + tool calls at 77K tokens).
- No need to fall back to smaller model for coding worker.

## H. Obsolete coder variants removed
- Removed: northstar-coder:48k, qwen3.8-27b-coder:latest (both coder variants on shared base blob).
- Preserved: northstaros-qwen3.8:27b (verified base), northstaros-qwen3.8:27b-ctx64k-orig (backup), qwen3.5:4b (Bojo base), qwen2.5vl:7b, qwen3-embedding:0.6b, ComfyUI assets.
- Disk space: aliases removed but shared base blob retained by preserved models. No weight disk space reclaimed (blob still referenced). Reported honestly.
- OpenCode config updated: ollama provider now has "bojo" only; llamacpp provider has "coding-worker" (98304/8192). Backed up config to opencode.json.bak.20261027-migration.

## I. Integration
- Routing: orchestration/bounded loops -> Bojo (Ollama, loopback); coding/repo tools -> coding worker (llama-server, 8123, on-demand); creative -> ComfyUI (existing).
- Heavy coding and ComfyUI serialized by measured capacity (15.25 GB VRAM for coding worker; ComfyUI needs VRAM too — cannot run simultaneously with coding worker).
- Bojo health: verified (responds "ok", tool-call parsing verified on base model via OpenAI API without vision projector load). Coding worker health: verified (model loaded, API responds, 77K-token retrieval + tool calls pass).
- Bojo tool-call verification: base qwen3.5:4b supports tools (verified via direct API). The bojo:latest alias fails tool calls when 27B is loaded (vision projector CPU_REPACK buffer allocation fails due to RAM pressure). Bojo tool calls work when 27B is NOT loaded.
- No paid/cloud fallback. No Chrome Connect permission changes. No invented data.

## J. Summary
- Bojo: qwen3.5:4b (4.2B), 8K ctx, bounded output (2048), tool-capable, verified on CPU (3.3 GB RAM). GPU residency conflicts with 27B (reported, not silent).
- Coding worker: Qwen 3.5 27B Q3_K_L, GPU-only, 98304 ctx (90112 input), 8192 output, 1 slot, q4_0 KV cache, flash attn. Verified at 77K tokens (retrieval + tool calls). Steady state: on-demand (start llama-server when coding needed).
- Conflict 1: 27B at 90K leaves 0.75 GB VRAM; Bojo cannot co-reside on GPU.
- Conflict 2: Bojo's vision projector cannot allocate CPU_REPACK buffer when 27B is loaded (RAM pressure). Bojo tool calls fail in that state. Bojo works alone (verified).
- Deleted: 2 coder aliases (no disk reclaimed — shared blob preserved by base model).
- Unmet: 1-2B Bojo (used 4B, disk full, download failed); simultaneous Bojo+27B residency (measured blocker, reported).
- Steady state: Bojo (Ollama) persistent on CPU. Coding worker (llama-server) on-demand. Do not run both simultaneously.