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

---

# Round 2 — overthinking, and do we need a lighter model?

Question: copy what Swift 1.5 does (think less, same answer) without retraining,
and use a smaller model for non-thinking tasks.

## The Swift effect is mostly level + prompt discipline

Same 3-crate proof every run, every answer verified correct:

| run | thinking tokens | wall |
|---|---|---|
| xhigh, no discipline (old default) | 6,376 | 318 s |
| medium, no discipline | 2,209 | 141 s |
| medium + reasoning discipline | 1,157 | 76.6 s |
| **medium + discipline, real Bojo prompt, end-to-end** | 1,165 | **74.1 s** |
| xhigh + discipline | 5,864 | 280 s |
| low + discipline | 1,428 | 89.6 s |

- The discipline **holds at medium/low but is ignored at xhigh** (5,864 tokens):
  the level sets the ceiling, the prompt only trims the waste below it.
- Net: **4.3× faster than the old default**, same marked answer, all three
  verification steps still present (`A = 1.17 B`, `(A+B)/2 − C = 9`, total 1,271).
- `low` + discipline was *slower* than `medium` + discipline, so medium is the
  efficient level — not the lowest one.

## The "light model" already exists inside the 27B

`think=false` on ordinary requests, measured:

| request | time |
|---|---|
| one-line summary of 3 numbers | 2.1 s |
| filename to kebab-case | 0.6 s |
| three bullet points | 1.0 s |

A separate 4B would not beat that, and it would not fit:

- 27B @16k = 11.25 GB + embed lane 2.2 GB + 4B-Q4 ≈ 2.6 GB = **16.05 GB**
  against 16.3 GB total (≈15.9 GB usable), so loading it would evict the brain
  and cost 7–8 s — far more than the ~1 s it could save.
- Worth it only for **non-interactive bulk work** where the brain is allowed to
  stay unloaded (batch classification, tagging, bulk copy variants).

## Shipped in round 2

- `chat_adapter.py` — `REASONING_DISCIPLINE` composed into `CHAT_SYSTEM_PROMPT`
  so the "no focus → system constant" contract still holds;
  `CHAT_REASONING_DISCIPLINE=0` disables it without a code change.
- `chat_router.py` — level whitelist: the template accepts only
  **xhigh / medium / low** and raises a Jinja exception on `"high"`; unknown
  values now normalize instead of crashing the turn.
- `autothink/backend/llm_adapter.py` — same normalization on the wire, plus
  `"high"` mapped to the model default.
- Gates: **125 passed / 0 failed**.

## What each UI switch now costs

| composer switch | level | simple request | hard proof |
|---|---|---|---|
| off | no thinking | 0.6 – 2.1 s | — |
| standard (default) | medium + discipline | ~1 – 3 s | 74 s |
| deep | xhigh | — | 280 – 318 s |

---

# Round 3 — the standing profile (set 2026-10-20)

Instruction: stop tuning per question; set whatever is best for spend, accuracy,
thinking, coding and extreme reasoning. This is the profile now in force.

## Decisions

| dimension | setting | why |
|---|---|---|
| everyday answer | `standard` = medium + discipline | 74 s on a hard proof vs 318 s, same verified answer |
| coding / proofs / long briefs | auto-escalate to xhigh | code fences, `def/class/import`, tracebacks, SQL, regex, "prove", "derive", "audit", "architecture", "root cause", "step by step", "design a", "opt-in trade-off", "optimise", unit tests, >1,200 chars, or any attachment |
| operator "deep" | xhigh | unchanged, always wins |
| operator "off" | no thinking | 0.6 – 2.1 s on ordinary requests |
| context window | **16,384 on every lane** (chat, AutothinK, browser agent, model fallback) | one number kills the 7 – 8 s reload class; real transcripts are <1 k tokens |
| KV cache | `q8_0` | 12.98 GB vs 13.48 GB at the same window, same speed |
| flash attention | on | measured flat; kept (no regression) |
| loaded models | 2 | brain + embed lane stay resident; chat turn after an embed: **0.00 s** load |
| parallel slots | 1 | one operator, one turn — no wasted KV |
| output cap | 16,384 | thinking counts toward it; below ~6 k an xhigh turn returns nothing |
| reasoning discipline | on | `CHAT_REASONING_DISCIPLINE=0` disables |
| light tier | thinking off, **not** a second model | a 4B cannot co-reside (11.25 + 2.2 + 2.6 > 16.3 GB) and would pay a 7 – 8 s eviction to save ~1 s |

Escalation only ever *adds* thinking: the operator's `off`/`deep` choice always
wins, so no request can be made shallower than the standard tier.

## Honest note on the model manifest

Rebuilding `Modelfile.northstaros-qwen3.8` at `num_ctx 16384` made the **same**
16384-token request load 13.0 – 13.5 GB at ~39 tok/s, against 10 – 11 GB at
~44 tok/s from the original manifest (all lanes pass `num_ctx` explicitly, so
the manifest value is only a manual-`ollama run` fallback). The original values
(64576 / 6000) were restored and the file now carries a warning comment.

The footprint did **not** fully return to 10 – 11 GB after the restore (it sits
at ~13 GB / 39 – 44 tok/s), so part of that drift is environmental — thermals or
driver state on a laptop GPU that has been loaded for hours — not the manifest.
Treat 39 – 44 tok/s as the honest current range rather than a fixed number.

## Operational note

To restart Ollama cleanly:
`Stop-Process -Name 'ollama','ollama app','llama-server' -Force`, wait ~3 s,
then start `ollama app.exe`. Always confirm `nvidia-smi` shows the VRAM released
before loading the 27B.
