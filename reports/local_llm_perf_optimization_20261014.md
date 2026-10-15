# Local LLM performance optimization — Qwen3.8-27B on RTX 5080 Laptop (2026-10-14)

**Mode:** operator-directed ("complete this and install everything needed" — the FlashAttention / KV-cache /
MTP / full-offload / power+driver checklist). Local only, zero paid/live calls.
Branch `feature/overnight-remediation-20261009` — local commit, not pushed.

---

## 1. Verdict on each checklist item (all measured on this box, not taken on faith)

| # | Checklist item | Action taken | Measured result |
|---|---|---|---|
| 1 | `OLLAMA_FLASH_ATTENTION=1` | Tested → **reverted** | **REJECTED — ~6x generation regression on this model.** FA forced on: 3.28–3.40 tok/s; engine-default `auto`: 38.95–39.41 tok/s warm (same box/hour, same prompt). The Ollama engine's `auto` already enables the optimized attention path for this Lightning-Indexer/DeltaNet architecture; forcing `on` selects a much slower path. Persisted var removed (absent = auto). |
| 2 | `OLLAMA_KV_CACHE_TYPE=q8_0` | Tested → **reverted to f16** | **REJECTED on the Ollama lane.** q8_0 requires FA forced on (unusable per #1). No memory need: f16 KV = 4048 MiB at 64k ctx and the model runs fully on the GPU. q8_0 KV remains valid on the standalone llama.cpp CUDA lane (used there, measured fast). |
| 3 | MTP speculative decoding | Re-verified + tuned | **REAL — the biggest win.** llama.cpp b11632 CUDA 13.4, `--spec-type draft-mtp --spec-draft-n-max 6 --spec-draft-p-min 0.65`: **70.1 tok/s** gen at **92.7%** draft acceptance vs **41.8 tok/s** with spec off = **+68%**. n-max 4 = 54.6 tok/s; n-max 8 unstable (1.26 tok/s — avoid). |
| 4 | `num_gpu` max / zero spill | Verified | 66/66 layers on GPU; `ollama ps` = **100% GPU**; model+KV ≈ 13.5 GiB resident of 16 GB; no spill. (Ollama auto-offloads fully; no Modelfile change needed.) |
| 5 | Windows power plan | **Set: High performance** active | `powercfg -duplicatescheme` + `/setactive` → GUID `4465a621-3aa7-4e76-9427-05e4cb6878b1` (was Balanced). AC-connected confirmed. |
| 5 | NVIDIA driver | Checked only | Installed **610.88** (CUDA UMD 13.3 — Blackwell-capable). Latest branch **617.42 (Oct 6, 2026)**. NOT auto-installed — driver installs reset the display/need a reboot, so left as an operator step via NVIDIA App. |

## 2. Final state (what is now configured)

- **Ollama lane (app lane, `:11434`)** — persisted user env: `OLLAMA_CONTEXT_LENGTH=64000`,
  `OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`,
  `OLLAMA_KV_CACHE_TYPE=f16`; `OLLAMA_FLASH_ATTENTION` **unset (auto)**.
  Model `northstaros-qwen3.8:27b` (id `77879776424f`), ctx 64576, 100% GPU, warm.
- **llama.cpp lane (`:8080`, OpenAI-compatible + vision)** — `scripts/start-northstar-llm.ps1` updated:
  - binary → `%USERPROFILE%\tools\llama-b11632\cuda\llama-server.exe` (official b11632 CUDA 13.4 release;
    winget b11580 Vulkan build kept only as fallback — measured ~2–3x slower);
  - `--spec-draft-n-max` 4 → **6** (measured +28% over 4);
  - the script now **auto-unloads the Ollama model** before starting (they share the 16 GB card).

## 3. Measurements (2026-10-14)

Ollama lane protocol: 1075-token prompt, 200 generated tokens, temp 0, warm model.
llama.cpp lane protocol: 238-token prompt, 200 tokens, `cache_prompt`, `ignore_eos`, identical request per variant.

| Lane / config | Prompt tok/s | Gen tok/s | MTP acceptance |
|---|---|---|---|
| Ollama 0.32.14 (CUDA), FA **auto**, KV f16, no MTP | **6596** (warm; first-run 1451) | **39.4** | — |
| Ollama, FA **forced on** (checklist #1) | 15–1677 | **3.3** | — |
| llama.cpp b11580 Vulkan, MTP n4 | 344 | 20.7 | 66.7% |
| llama.cpp b11580 Vulkan, MTP n6 | 355 | 1.58 (unstable) | 64.0% |
| llama.cpp b11632 CUDA, **no spec** (reference) | 382 | 41.8 | — |
| llama.cpp b11632 CUDA, MTP n4 p0.65 | 332 | 54.6 | 82.7% |
| **llama.cpp b11632 CUDA, MTP n6 p0.65 (final)** | 265 | **70.1** | **92.7%** |
| llama.cpp b11632 CUDA, MTP n8 | unstable | 1.26 | 94.0% |

End-to-end operator-path validation: script started lane (health ok, Ollama auto-unloaded), sample generation,
`/v1/chat/completions` returned `LANE OK`, clean stop, Ollama reloaded warm (7.5 s, 14 GB, 100% GPU).

## 4. Machine/environment findings (they move the numbers more than the flags)

- **Leftover ComfyUI server** (`C:\Users\T2Hol\ComfyUI`, pid 7148, started 22:13 today) held **~9 GB commit**
  (2 MB resident) and measurably **halved** LLM speed (19.4 vs 39.4 tok/s once stopped). Stopped; restart is
  `C:\Users\T2Hol\ComfyUI\venv\Scripts\python.exe main.py --port 8199 --listen 127.0.0.1`.
- **Pagefile volatility is the disk mystery**: committed memory peaked at **50.9 GB of a 54.5 GB limit**;
  `pagefile.sys` swung between ~24 GB and ~40 GB, so C: free space fluctuated between 0 and 69 GB during the
  session. The 4–24 GB pagefile cap recorded by the 2026-10-13 session applies only **after a reboot**.
- The Ollama engine loads models with `--load-mode none` (no mmap) and its runner holds **~16 GB private
  commit** for this model. On a 16 GB-RAM machine that makes throughput very sensitive to other committers —
  keep media servers / heavy apps closed during long LLM runs.
- **Vulkan vs CUDA** on this architecture: Vulkan build ≈ 2–3x slower (fused Gated-DeltaNet /
  Lightning-Indexer kernels are CUDA-side).
- Ollama **0.40.4** update is already downloaded by the updater; not applied (operator discretion — re-run
  `tools/brain_gate.py` after any Ollama update).

## 5. Incident & repair (transparency)

During disk housekeeping I deletion-audited `.ollama` blobs against the manifest's `layers` array only and
removed two files: `sha256-63f29a21…` (9.73 GB raw staging copy — genuinely unreferenced) and
`sha256-7730b255…` (a **153-byte manifest config blob referenced outside `layers`** — my audit gap). The
model then reported `not found`. Repair used the documented rollback path:
`ollama rm` → `ollama create northstaros-qwen3.8:27b -f Modelfile.northstaros-qwen3.8`.
**All digests reproduced bit-identically** (config `7730b255…`, model `c9250e14…`, system `d5f3f0de…`,
params `e19ebc08…`; model id `77879776424f`), verified by load + generation. The staging-copy blob was later
deleted **after full-manifest verification** (its content also exists at
`%USERPROFILE%\models\northstaros-qwen3.8`, SHA-256-verified on 2026-10-13).

## 6. Disk ledger

Start 1.0 GB free → orphan blob removal +9.73 GB → staging blob removal +9.73 GB → model recreate −9.73 GB →
Windows\Temp + user Temp cleanup → CUDA kit download (~0.55 GB, extracted to `%USERPROFILE%\tools\llama-b11632`) →
pagefile shrink → **69.0 GB free at close**. No protected data touched.

## 7. Files changed (this commit)

- `scripts/start-northstar-llm.ps1` — CUDA b11632 path (+ Vulkan fallback), draft-max 6, auto-unload Ollama,
  measured-config notes.
- `reports/local_llm_perf_optimization_20261014.md` (this file).
- `00_STATE.json` — history entry.

## 8. Operator follow-ups

1. NVIDIA driver 610.88 → **617.42** via NVIDIA App (optional; recommended by the checklist).
2. **Reboot** when convenient → applies the registry pagefile cap (4–24 GB), reducing commit pressure.
3. Keep ComfyUI/media servers stopped during LLM-heavy sessions (measured 2x impact).
4. Optional: apply Ollama 0.40.4 (already downloaded), then re-run `tools/brain_gate.py`.
5. Pending from 2026-10-13: WSL ollama systemd disable — `wsl -d Ubuntu -e sudo systemctl disable --now ollama`.
6. Optional: re-run a vision smoke test on the lane (mmproj loads; verified by the 2026-10-13 session).

## 9. Evidence

- Engine flags: `--flash-attn auto` (baseline/final) vs `on`; `--cache-type-k f16`; `--load-mode none` — from
  `%LOCALAPPDATA%\Ollama\server*.log` engine-start lines (history in log files `server-1..5`).
- Load block (final): `offloaded 66/66 layers`, `K (f16): 2024.00 MiB, V (f16): 2024.00 MiB`, ctx 64768.
- llama.cpp timings JSON per run (persisted in session transcript); draft acceptance lines
  (`draft acceptance = 0.927 … 153/165`) in `%TEMP%\opencode\llama-c2-cuda-nmax6.err.log`.
- VRAM footprint: unload 2349 MiB → load 15846 MiB (model = 13.5 GiB); `ollama ps` = `100% GPU  64576  Forever`.
- Raw commands / full outputs: session transcript of 2026-10-14 (this task).
