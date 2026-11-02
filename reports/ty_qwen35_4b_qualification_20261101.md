# Qwen3.5 4B engineering lane — installed, screened, one real fix accepted (2026-11-01)

The authorized artifact was installed and evaluated. It is the first lane that uses
native tool calls cleanly and **authors a real, committed Northstar fix**. It is not
yet qualified: 1 of 3 accepted fixes.

---

## 1. MODEL DECISION

| | |
|---|---|
| Artifact | **`qwen3.5:4b`** (official Ollama tag) |
| Digest | `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` |
| Size / class | 3.1 GB, 4.2B, Q4_K_M, family `qwen35` |
| Capabilities | completion, vision, **tools**, thinking |
| Manifest | ships its own `RENDERER qwen3.5` + `PARSER qwen3.5` — no alias, no parser to bolt on |
| Install | `ollama pull qwen3.5:4b`, 29.7 s, 2026-11-01 |
| Bojo fallback | not installed — `qwen3.5:2b` was already present and unchanged |
| `qwen3.5:9b` | **not** downloaded; the 4B passed native-tool and screen gates |

---

## 2. RESOURCE (campaign profile: GPU, `num_ctx=8192`, KV f16)

| Measure | Value |
|---|---|
| Host before load | **8.188 GB** (≥ 6.0 required) |
| Host low-water during generation | **7.084 GB** (drop 1.104) |
| Floor 3.0 GB | **FLOOR-MET** |
| Placement | GPU-resident, **3.134 GB VRAM**, `/api/ps` reports 0.0 GB system |
| Throughput | **42.3 tok/s** |

Measured with the same probe used throughout: `psutil.available` every 200 ms plus
`/api/ps` once a second, during a real generation, then unloaded.

---

## 3. INTERFACE

| Check | Result |
|---|---|
| Structured `message.tool_calls` | **3 of 3** prompts, name `read_file`, correct `{"path":…}` |
| Renderer / parser | present in the stock manifest (`RENDERER qwen3.5`, `PARSER qwen3.5`) |
| Argument schema | validates through the existing executor (0 protocol errors in the screen and in the successful task) |
| Planning agent | uses the native interface end-to-end; a custom alias was not needed |

For the record: the same family on the operator's stock `q4_0` KV produced corrupted
repetition in earlier rounds; this campaign used a campaign-scoped **f16** serve.
The operator's environment was restored afterwards (`cpu` / `q4_0`).

---

## 4. SCREEN (disposable, native tools)

| Attempt | Valid? | Result |
|---|---|---|
| 1 | no — harness | the verify-stall guard did not treat `ast_edit` as a change, so the post-edit check was refused (`83d2474d`, `6bda9739`) |
| 2 | no — harness | a `def …` line passed as the replacement body was nested instead of stripped, guaranteeing `return None` (`61c5adb6`) |
| 3 | no — contract | correct body, `total` counted skipped rows; my screen wording was ambiguous (`02ed2abe`) |
| 4 | **yes** | **screen passed in 3 steps, 0 protocol refusals, 0 scope refusals**, result `{"approved": 2, "denied": 1, "skipped": 3, "total": 3}` |

Each invalidation was a demonstrated harness/spec defect, fixed with regression
coverage before the replacement attempt.

---

## 5. QUALIFICATION (5 of 6 dispatches; halted at 2 consecutive failures)

| Task | Dispatches | Result | Evidence |
|---|---|---|---|
| `ty-hitl-skip-report` | 1 | **COMPLETED — commit `883a7fed`** | 5 steps, 0 refusals; probe `t5` now **PASS** |
| `ty-artifact-jpeg` | 2 | failed (`max_steps`; its edits broke the module — probe traceback) | restored, no commit |
| `ty-diff-select-headers` | 2 | failed (`max_steps` after 5–7 real edits) | restored, no commit |

The accepted fix is minimal and exactly the contract:

```diff
-    pending = approved = denied = 0
+    pending = approved = denied = skipped = 0
     ...
         except (json.JSONDecodeError, IOError):
-            continue
+            skipped += 1
-    return {'pending': pending, 'approved': approved, 'denied': denied, 'total': total}
+    return {'pending': pending, 'approved': approved, 'denied': denied,
+            'skipped': skipped, 'total': total}
```

Task-only commit (`Northstar_backend/agent_kernel/hitl_counts.py`, +7/−7). Probes
`t6`/`t7` still fail, so the two remaining defects are intact and ready.

Harness fixes made during the campaign (each with tests): read pressure now counts
refused reads (`63c90e73`); the two retries got 14 steps.

---

## 6. CLEANUP

* Operator daemon **restored**: `ollama app`, 10 models, **0 resident**,
  `OLLAMA_LLM_LIBRARY=cpu`, `OLLAMA_KV_CACHE_TYPE=q4_0`, GPU **0 MiB**.
* No lock, no STOP, no worker, no campaign process left.
* Regression batch: **175 passed in 6.82 s** (13 suites).

---

## 7. VERDICT

**PARTIALLY READY.** Scope proven: a 4.2B official lane, native tool calls, f16/GPU
resource profile inside the 3.0 GB host floor, and **one real, unassisted,
task-owned, model-authored fix accepted by an independent probe and committed by the
supervisor**.

Not proven: three fixes. The lane edits correctly and reads correctly, but on the
two remaining defects it finishes the step budget without converging.

---

## 8. NEXT ACTION (one operator decision)

Authorise **one further bounded run of the two remaining tasks** (`ty-artifact-jpeg`,
`ty-diff-select-headers`) on this lane, or accept 1/3.

Basis for a retry: both failures were `max_steps` after real, in-scope edits — not
refusals — so a slightly larger step budget (18–20) with the same task contracts is
the specific, limited change to test. Nothing else should move.
