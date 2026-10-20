# Speed & thinking deep dive — 2026-10-20

Scope: make the local brain faster and think better *without* changing model.
Machine: RTX 5080 Laptop, 16,303 MiB VRAM. Model `northstaros-qwen3.8:27b`
(UD-Q3_K_XL, 100 % GPU).

## Baseline (measured)

| metric | value |
|---|---|
| generation | 44.3 – 44.6 tok/s |
| prefill (warm) | 1,579 – 1,631 tok/s |
| cold load | 6.9 – 8.2 s |
| VRAM at ctx 16,384 | 11.25 GB |
| VRAM at ctx 64,576 | 14.0 GB |

## Findings, ranked by user-visible damage

### 1. The 4,096-token cap was deleting answers (worst)
`CHAT_NUM_PREDICT` defaulted to 4096. `num_predict` counts **thinking** tokens.
When the budget runs out mid-reasoning Ollama returns `done_reason="length"`
with **zero content characters**, and the router then persisted
`[LOCAL FALLBACK] Ollama is unavailable` — a false diagnosis of an outage.

Reproduced with a 3-crate algebra proof:

| budget | thinking | answer | stop reason | wall |
|---|---|---|---|---|
| 200 (probe) | 354 chars | **0 chars** | `length` | 2 s |
| 4,096 (old cap) | would truncate at ~4k | **0 chars** | `length` | ~95 s |
| 16,384 (new cap) | 6,376 tok | 1,869 chars | `stop` | 318 s |

### 2. Every embedding call evicted the brain
`OLLAMA_MAX_LOADED_MODELS=1`. The embed lane loaded `qwen3-embedding:0.6b` at its
own 32k default — **5.8 GB** — and evicted the 27B, so the next chat turn paid a
6.5 – 8.2 s cold reload. Measured `ollama ps` immediately before/after an
embedding call; it happens even with `num_gpu=0` (the scheduler counts loaded
models regardless of device).

### 3. Context-size thrash reloads the model
App asked 16,384, Modelfile 64,576, AutothinK 64,576, `browser_agent` 32,000.
Switching the requested window forces a full reload: measured **7.59 s**, and the
resident footprint changed 14 GB → 11 GB.

### 4. A restarted Ollama leaves a GPU-hogging orphan
Killing `ollama` / `ollama app` does **not** kill `llama-server.exe`. The orphan
kept ~11 GB and the next load died with
`cudaMalloc failed ... failed to allocate CUDA0 buffer of size 9676124160`.
Killing the orphan returned 15,750 MiB free. This is the real cause of
"model won't load" after a restart.

### 5. Flash attention is not the lever here
On: 44.4 / 44.3 / 44.6 tok/s. Off (baseline): 44.5. No measurable gain on this
card; kept enabled (no regression), not relied on.

### 6. Reasoning effort *is* the lever
`think` accepts a level, not just a bool:

| level | thinking tokens | wall | answer |
|---|---|---|---|
| `true` (template default xhigh) | 6,376 | 318 s | correct, verified |
| `"medium"` | 2,209 | **141 s** | correct, verified |
| `"low"` | 2,026 | 133 s | complete |

Same question, same arithmetic, same conclusion — 2.3× faster at medium.

## Changes shipped

Code:
- `Northstar_backend/chat_adapter.py` — `CHAT_NUM_PREDICT` 4096 → **16384**;
  new `truncation_notice()` that names the real cause.
- `autothink/backend/llm_adapter.py` — `done_reason="length"` now emits
  `{"type":"notice","code":"output_truncated"}`; string think levels pass
  through instead of being coerced with `bool()`.
- `Northstar_backend/chat_router.py` — truncated turn keeps its thinking and
  appends `[BUDGET REACHED]` instead of the offline notice; `_think_level()`
  maps the composer switch: `off` → no thinking, `standard` → `medium`
  (override with `CHAT_THINK_STANDARD=true`), `deep` → model default (xhigh).
- `Northstar_backend/corpus_drift.py` — embed lane sends `options.num_ctx=2048`
  and `keep_alive=2m` (was 32k / forever).

Environment (User scope, survives reboot):
- `OLLAMA_MAX_LOADED_MODELS=2`
- `OLLAMA_FLASH_ATTENTION=1`
- `OLLAMA_CONTEXT_LENGTH=16384`

## Verified result

- Brain + embed co-resident: 11 GB + 2.2 GB = 13.5 GB of 16.3 GB.
- Chat turn after an embedding call: **load 0.00 s** (was 6.5 – 8.2 s).
- Hard question that returned nothing now returns a full verified answer
  (318 s at `deep`, 141 s at `standard`).
- Gates: **125 passed, 0 failed** (`test_chat_core`, `test_chat_tools`,
  `test_turn_contract`, `test_chat_plan`, `test_shell_modes`, `test_corpus_drift`).

## Still on the table (not done)

1. **KV cache `q8_0`** — halves the KV block (64k ctx back to ~12 GB, or more room
   for co-residency). Needs an A/B; quality risk is small but must be measured.
2. **Align the Modelfile** (`num_ctx 64576` / `num_predict 6000`) with the app, so
   manual `ollama run` cannot cause a 7.6 s reload.
3. **History budget** — not a bottleneck today: the largest real transcript is
   553 tokens. Revisit when sessions grow.
4. **Canvas/WebGL contention** while a turn streams — unmeasured. The shader runs
   every frame during generation on the same GPU.
5. **Swift 1.5** — still gated on the licence review, not on speed.
6. **Continuation on truncation** — an automatic bounded retry instead of the
   honest notice, if the operator prefers waiting to rephrasing.

## Operational note

To restart Ollama cleanly:
`Stop-Process -Name 'ollama','ollama app','llama-server' -Force`, wait ~3 s,
then start `ollama app.exe`. Always confirm `nvidia-smi` shows the VRAM released
before loading the 27B.
