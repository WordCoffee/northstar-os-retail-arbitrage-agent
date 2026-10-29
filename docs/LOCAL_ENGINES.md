# Local engines — Ty and Bojo, as measured

This is the reference for what runs on this machine. Every value was read off the
running server or its launch line; nothing here is a target. `shared/model-suite.json`
→ `local_engines` carries the same numbers as data.

Box: RTX 5080 Laptop, 16 GB VRAM, 15.4 GB system RAM. **RAM is the binding limit**,
not VRAM.

## Ty — orchestrator and coding worker

| | |
|---|---|
| Weights | Qwen3.8-27B GSQ-RCO **IQ3_XXS** + MTP, 10.4 GB |
| Backend | `llama-server` (llama.cpp, CUDA) |
| Endpoint | `http://127.0.0.1:8080/v1` — OpenAI-compatible |
| Alias | `northstaros-qwen3.8:27b` (a name for clients, **not** an Ollama tag) |
| Launch | `scripts/start-northstar-llm.ps1` |
| GPU layers | `-ngl 99` (full offload) |
| Context | `-c 65536` |
| KV cache | `-ctk q4_0 -ctv q4_0` |
| VRAM | ~13 GB |
| Speed | ~69 tok/s with MTP (~14.5 ms/token); ~47 tok/s without |
| Residency | none — started on demand, never a service |
| Vision | unavailable: the `--mmproj` is withheld for VRAM. Use the V tiers. |

**Why 65536 and q4_0 — measured, not chosen.** The previous Ollama build of this
model crashed on `cudaOccupancyMaxActiveBlocksPerMultiprocessor` at
`num_ctx 64576`. Bisection gave 8192 / 16384 / 32768 working and 64576 failing
(`0xc0000409`). q8_0 KV caps around 32K on this card; q4_0 is what fits 64K in
16 GB. Any document claiming a 128k context or an 8-bit KV cache for this engine
is describing hardware this machine does not have.

## Bojo — the user-facing brain

| | |
|---|---|
| Weights | **qwen3.5 1.9B Q8_0**, 2.7 GB |
| Backend | Ollama |
| Definition | `scripts/bojo-cpu.Modelfile` (`FROM bojo:gpu-orig`) |
| Placement | `PARAMETER num_gpu 0` — CPU only, **0 GB VRAM**, ~2.7 GB RAM |
| Context | 8192 |
| Capabilities | completion, **vision**, **tools**, thinking |
| Residency | kept warm; `unload_brain` drains `/api/ps` before any ComfyUI render |

Bojo serves **every local text tier** (`T1`, `T2`, `T3`). It is not a formatter
shim and not a lint pass — it is the resident interaction layer that answers chat
while the GPU is busy or idle.

## What this rules out

These were never built here, and no config should name them:

- `telemetryd`, a 100 ms hardware sampler, or a routing score. `lane_telemetry.py`
  records measured runs and refuses to recommend a lane below 30 samples; there is
  no live VRAM/thermal input for a score to read.
- KV-cache offload hooks or context compression. The ceiling is enforced by
  refusing to launch above it.
- AgentScope, Matrix rooms, `state_dict`/`load_state_dict`. The kernel's own
  `plan` / `subagents` / `session` / `policy` modules are the topology.
- Per-task `git worktree`. Isolation is `diff.py` snapshots plus session
  checkpoints; `patch_tool.worktree_root()` only resolves the repo root to keep
  patch paths inside the trust boundary.
- `POST /tasks/{id}/run?engine=…`, `202 Accepted`, SSE. The one real route is
  synchronous and admin-gated — see `docs/TASK_EXECUTION.md`.
