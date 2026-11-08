# D7 — GPU diagnosis: why Ollama ran on CPU, and what fixed it

Measured 2026-11-07. Owner decision: diagnose before upgrading anything. The
diagnosis did not require an upgrade, a `llama-server` switch, or a llama.cpp build.

## The five checks the owner asked for

| # | check | measured | verdict |
|---|---|---|---|
| 1 | `nvidia-smi` driver version (need ≥ 570) | `617.42`, CUDA UMD `13.4` | **OK** — far newer than required |
| 2 | `ollama ps` PROCESSOR per role, before | bojo `100% CPU`, coder `100% CPU`, vision `100% CPU`, embeddings `100% CPU` | FAIL |
| 3 | server log GPU discovery line | `inference compute id=cpu library=cpu compute="" driver="" ... "no usable GPU found"` ×4 | FAIL |
| 4 | pinned `OLLAMA_LLM_LIBRARY` | **`cpu`** — set in the **User** scope, inherited by the service | **THE CAUSE** |
| 5 | Windows GPU assignment for Ollama | `HKCU\...\UserGpuPreferences`: `C:\Users\T2Hol\AppData\Local\Programs\Ollama\ollama.exe = GpuPreference=2` (high performance) | OK — Windows was not sending it to the iGPU |

Two more pinned variables were found alongside #4:

```
OLLAMA_LLM_LIBRARY=cpu     (User scope)
OLLAMA_NUM_GPU=0           (User scope)
```

`OLLAMA_NUM_GPU=0` means *zero GPU layers*; `OLLAMA_LLM_LIBRARY=cpu` forces the CPU
library. Together they explain every symptom exactly: a visible GPU, a healthy driver,
a correct Windows preference, and `library=cpu` in the log. The earlier note in
`reports/ty/director_probe.md` — "the 0.40.4 runner cannot see this GPU" — was wrong.
The runner was told not to look.

## What was done, in the owner's order

**(1) Update Ollama and retest — superseded by the diagnosis, and recorded as such.**
An upgrade cannot override an environment pin, so the pins were cleared first and the
runtime retested. `ollama --version` remains `0.40.4`; no upgrade was performed, so no
upgrade risk was introduced. (If the pins had not explained it, the next step was the
upgrade — that step is still available and unspent.)

Changes made, all reversible:

1. `[Environment]::SetEnvironmentVariable('OLLAMA_LLM_LIBRARY', $null, 'User')`
2. `[Environment]::SetEnvironmentVariable('OLLAMA_NUM_GPU', $null, 'User')`
3. Ollama service restarted (`ollama app.exe --hide`), so the server inherited the
   cleared environment.
4. `bojo:latest` was quarantined as **`bojo:cpu-quarantine`** and rebuilt from its own
   Modelfile with the single line `PARAMETER num_gpu 0` removed — that parameter was
   baked into the model, so clearing the environment alone still left Bojo on CPU.
   Nothing was deleted.

New discovery line, after:

```
msg="inference compute" id=0 filter_id=0 library=CUDA compute=12.0 name=CUDA0
description="NVIDIA GeForce RTX 5080 Laptop GPU"
```

## Before / after, per role

| role | model | before | after | model size | VRAM used | RAM free | budget |
|---|---|---|---|---|---|---|---|
| Bojo router | `bojo:latest` | 100% CPU, 0 VRAM | **100% GPU** | 2.25 GB | 3.07 GB | 6.20 GB | 3.0 |
| planner / coder | `qwen3:8b` | 100% CPU, 0 VRAM | **100% GPU** | 6.43 GB | 6.63 GB | 6.20 GB | 6.0 |
| vision | `qwen2.5vl:7b` | 100% CPU, 7.4 GB RAM | **100% GPU** | 6.01 GB | 7.41 GB | 6.41 GB | 7.0 |
| embeddings | `qwen3-embedding:0.6b` | 100% CPU (unmeasured) | **100% GPU** | 1.89 GB | 2.08 GB | 6.55 GB | 2.0 |

Idle after unload: **15.63 GB VRAM free, 7.23 GB RAM free**.

The budgets above are being corrected to the measured numbers plus headroom (bojo 3.5,
coder 7.0, vision 8.0, embeddings 2.5) because every one of them overshoots its old
budget by the KV-cache/context overhead — `OLLAMA_CONTEXT_LENGTH=65536` with
`OLLAMA_KV_CACHE_TYPE=q4_0` is why a 6.01 GB model occupies 7.41 GB of VRAM.

## Consequence for the work order's budget rule

Before: two roles resident at once was impossible (one 7B load left 0.5–0.9 GB of RAM
free). After: Bojo (3.07) + vision (7.41) = 10.48 GB of 15.63 GB free, with 6.2 GB of
RAM free. The 80–90 % VRAM target and the 1 GB reserve are now reachable, and
`OLLAMA_MAX_LOADED_MODELS=1` is the remaining limit on concurrency — a deliberate one,
raised only after a two-model soak proves the UI stays responsive.

## Two measurement bugs this diagnosis exposed (both fixed)

- `gpu_budget.load()` sampled RAM in the same instant as the load and reported a good
  GPU load as a refusal (the host RAM spike). It now measures the steady state.
- `roles_report` warmed an embedding-only model through `/api/generate`, so embeddings
  read as "never loaded". It now uses `/api/embeddings` for that role.

## What D7 still does, and in what order

Structure first, regardless of the GPU: the UI Automation tree and the browser DevTools
protocol are the primary read, because structure is faster and cheaper than pixels. The
VLM is now a working GPU path rather than a fallback, so the D7 benchmark measures
`qwen2.5vl:7b` **on GPU** (element-click accuracy on the 40-screen set, latency, VRAM,
RAM) instead of disqualifying it by latency.
