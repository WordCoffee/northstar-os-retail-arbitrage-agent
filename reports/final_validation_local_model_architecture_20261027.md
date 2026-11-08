# Final Validation — Local Model Architecture — 2026-10-27

## Classification of each item

### VERIFIED COMPLETE
- Bojo sustained CPU load: 5 sequential prompts (ok, 4, Red, tool call get_weather/Paris, done) — all correct, no crash, no CPU_REPACK failure. Latency 0.38-2.31s per prompt. RAM 96.9% load but no OOM. Tool calls valid.
- Bojo coexistence with 27B: responds "ok" + tool calls work while 27B loaded (12833 MiB VRAM used, 3171 MiB free).
- Coding worker GPU-only: 12840/16303 MiB VRAM, ngl=99, no CPU offload. Verified via nvidia-smi.
- Coding worker 90K context: 77,118 tokens, retrieval of facts at beginning/middle/end PASS. Tool calls after long prefill PASS. 987 tok/s prefill, 28.7 tok/s gen.
- General worker: multi-turn conversation PASS, planning PASS, tool call (get_weather/Tokyo) PASS, thinking/reasoning PASS. Loaded on GPU (12840 MiB). Unloaded cleanly.
- Coding worker handoff: stopped general, started coding on port 8123, tool call PASS, 12840 MiB VRAM.
- Old 27B removal: inventory confirms only one 27B file (Qwen 3.8 IQ3_XXS). No obsolete aliases. ComfyUI untouched.
- Disk: 12.6 GB free (was 0.25 GB). ~26 GB reclaimed.
- OpenCode routing: ollama→bojo, llamacpp→coding-worker. Config backed up.

### IMPLEMENTED BUT UNVERIFIED
- General profile at 90K: configured with 98304 ctx but not separately load-tested at 90K (only 8K tested). Largest actually validated context for general: 8K (short prompts). Do not claim 90K for general.
- Bojo at 8K context under sustained load: only short prompts tested (5 prompts, <2K tokens total). Not tested at 8K context capacity.
- NorthstarOS orchestration smoke via Chrome Connect: BLOCKED (sign-in wall on :8101, operator credentials needed). OpenCode routing verified via config inspection only.

### BLOCKED
- NorthstarOS orchestration smoke through Chrome Connect: session expired after backend restart; operator sign-in required on http://127.0.0.1:8101/ui/ or http://127.0.0.1:8000/ui/. Agent cannot enter credentials (credential hygiene rule). Backend code fixed: DEFAULT_LOCAL_MODEL changed from "northstaros-qwen3.8:27b" (removed) to "bojo" (autothink/backend/llm_adapter.py). Backend restarted (PID 29132). Awaiting operator sign-in for live verification.
- 00_STATE.json update: blocked by deny rule in opencode.json (Tier-2 file). Operator applies manually (content provided in corrected report §9).

### DEFERRED
- General profile 90K validation: deferred (would require stopping coding worker and running long test; not done in this pass).
- Bojo sustained 8K context test: deferred (modest prompts only).
- Removing qwen3.5:2b base model: deferred (kept as base for Bojo; removing would break Bojo).

## Exact model identities
- Bojo: qwen3.5:2b (1.9B, Q8_0, qwen35 arch, tools+thinking+vision). Ollama alias bojo:latest. CPU, 8K ctx.
- Coding worker: Qwen 3.8 27B IQ3_XXS (qwen35 arch, 27.3B, 10.44 GB). File: C:\Users\T2Hol\models\northstaros-qwen3.8\Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf. GPU-only (llama-server, ngl=99), 98304 ctx, 90112 input, 8192 output, q4_0 KV, flash-attn.
- General worker: same file, temp 0.6, 98304 ctx.
- Project label: Qwen 3.8 27B. Verified family: Qwen 3.5 / qwen35. Exact file recorded above.

## Memory
- 27B on GPU: 12840/16303 MiB VRAM (3164 free). Host RAM: ~5 GB used by mmap (RAM avail dropped to ~489 MB under 27B load).
- Bojo on CPU: ~2.7 GB RAM. Coexists (verified).
- System RAM total: 15791 MB. Under 27B load: ~489 MB avail (96.9% load). No OOM, no CPU_REPACK failure.

## Speed
- 27B prefill: 987 tok/s (77K tokens). Generation: 28.7 tok/s.
- Bojo: 0.38-2.31s per short prompt.

## Tool calls
- Bojo: get_weather/Paris PASS (under 27B load).
- Coding worker: get_weather/Paris PASS (short + after 77K prefill).
- General worker: get_weather/Tokyo PASS.

## OpenCode routing
- ollama provider: bojo (8K ctx, 2048 output).
- llamacpp provider: coding-worker (98304 ctx, 8192 output).
- Config backed up: opencode.json.bak.20261027-migration.

## Remaining operator action
1. Apply 00_STATE.json update (content in corrected report §9) — Tier-2 file, agent denied.
2. Sign in on http://127.0.0.1:8101/ui/ to enable NorthstarOS orchestration smoke.
3. (Optional) Run general profile at 90K and Bojo at 8K context for full validation.
4. Windows ACL commands (from earlier cycle) still pending.