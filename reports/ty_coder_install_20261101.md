# Authorized coder install — decision, integrity, resources, screen (2026-11-01)

Two authorized artifacts were installed and evaluated. **No lane qualified.** The
primary was rejected on the native tool interface; the fallback passed integrity and
the resource gate but failed the disposable engineering screen, so the three real
tasks were not dispatched.

---

## 1. MODEL DECISION

| | Primary | Fallback |
|---|---|---|
| Artifact | `qwen2.5-coder:7b` (official Ollama) | `qwen3:8b` (official Ollama) |
| Digest | `dae161e27b0e…` | `500a1f067a9f…` |
| Size on disk | 4.7 GB | 5.2 GB |
| Install time | 32.5 s | 43.5 s |
| Capabilities | completion, tools, insert | completion, tools, thinking |
| Verdict | **REJECTED — native tool interface** | **REJECTED — engineering screen** |

Installs: **2 of 2 allowed**. Disk after both: **54.9 GB free** (above the 10 GB
floor). No existing model was removed or altered.

### Primary rejection (measured, not assumed)

Three prompts, exact Ollama `tools` schema, `temperature 0`:

```text
prompt 1 -> content "{\n  \"name\": \"calc.py\"],\n  \"arguments\": {}\n}"
prompt 2 -> content "```json\n{\n  {\n   "
prompt 3 -> content "```json\n{\n \"name\": \"read_file\", \n \"arguments\": \n\"path \"path\": ..."
structured tool_calls: 0 of 3
```

The model knows the call (`read_file`, correct path) but emits it as **content**, not
as `<tool_call>` tags, and Ollama 0.40.4 does not parse it into `tool_calls`. The
artifact's template *does* ask for `<tool_call>`; the runtime does not lift it. The
only runtime remedy is a custom Modelfile `PARSER`, which this directive forbids, so
the fallback was authorized on "tool interface fails".

---

## 2. INTEGRITY / INTERFACE

### `qwen3:8b` (fallback) — passed

```text
sentence  "A Python function is a block of organized, reusable code that performs
           a specific task."                              -> coherent
json      {"ok": true, "color": "blue"}                   -> exact, parseable
tools     3 of 3 structured tool_calls, name "read_file", arguments
          {"path": "Northstar_backend/calc.py"}           -> native interface works
```

### Runtime finding that matters for every future lane

Under the operator's restored `OLLAMA_KV_CACHE_TYPE=q4_0`, `qwen2.5-coder:7b`
produced corrupted repetition — `"Rencontre Rencontre…"`, `"A a one one"`,
duplicated tokens inside the tool JSON. With a campaign-scoped serve at
`KV_CACHE_TYPE=f16`, the same artifact produced perfect prose and exact JSON. The
q4_0 KV cache is hostile to these Qwen models; the operator's environment was left
as-is and restored at the end, but **any lane used for Ty needs an f16 profile**.

---

## 3. RESOURCES (`qwen3:8b`, GPU, `num_ctx=8192`, KV f16)

| Measure | Value |
|---|---|
| Host before load | **8.467 GB** (≥ 6.0 required) |
| Host low-water during generation | **7.519 GB** (drop 0.948) |
| Floor 3.0 GB | **FLOOR-MET** |
| Placement | GPU-resident, 5.879 GB VRAM, `/api/ps` reports 0.0 GB system |
| GPU used during generation (nvidia-smi) | **6,262 MiB** |
| Throughput | 30.3 tok/s |

The host cost is not zero (0.95 GB) even though the placement field says 0.0 GB; the
floor is judged on the host figure, which is why it is sampled directly.

---

## 4. SCREEN (`qwen3:8b`, native tools, disposable workspace)

| Attempt | Valid? | Outcome |
|---|---|---|
| 1 | **no** — harness defect | the candidate edited `summarise()` to return `None` and my acceptance raised `AttributeError` instead of scoring it. Fixed with a pure verdict function and 5 tests (`cb8b91a0`). |
| 2 | yes (replacement) | read ✓, `ast_edit` on **the correct symbol** `summarise`, but the first body was invalid Python (`unexpected character after line continuation`), then two applied edits removed the `return` → `summarise()` returns `None` → behavioural check failed. 9 steps, 1 protocol error. |

The lane can read, hold the symbol and issue a real edit — a genuine step forward —
but it cannot author a correct body within the budget. **Screen failed**, so per the
directive the three real tasks were **not** dispatched.

---

## 5. WHAT WAS NOT RUN

* Real qualification (`ty-artifact-jpeg`, `ty-hitl-skip-report`,
  `ty-diff-select-headers`) — gated on the screen.
* 120-minute soak, Northstar repair campaign — gated on qualification.
* No supplied patches, no outer-agent repairs, no task state was reset.

The three probes still fail on HEAD (`t5` 1, `t6` 2, `t7` 2) and are ready.

---

## 6. STATE / CLEANUP

* Operator daemon **restored**: `ollama app`, 8 models, 0 resident,
  `OLLAMA_LLM_LIBRARY=cpu`, `OLLAMA_KV_CACHE_TYPE=q4_0`, GPU 0 MiB.
* Campaign-owned orphans (two `llama-server.exe` holding 5.6 GB host RAM from the
  earlier 8.3B session) were stopped; that is why the pre-load reading went from
  2.83 GB to 8.47 GB.
* No lock, no STOP, no worker. HEAD after this report.
* Regression: **169 passed in 5.11 s** across 12 suites.

---

## 7. VERDICT

**BLOCKED — no installed lane authors an accepted fix.** The adapter, resource gate
and read discipline are in good shape; the missing piece is a model that can turn a
read file into a correct function body through native tool calls.

Concrete next options (none authorized here):

1. re-test `qwen2.5-coder:7b` under an **f16 KV profile** with a `PARSER`-enabled
   runtime — its tool JSON was correct, only the runtime did not structure it;
2. accept a slightly larger lane with a stronger edit record;
3. accept the current limit: the automation refuses bad output precisely and the
   qualification queue remains ready.
