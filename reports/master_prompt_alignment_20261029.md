# Master-prompt alignment — engine tiering, task contract, p01/p03, guardrails

**Date:** 2026-10-29
**Verdict:** all four tasks are done and the two benchmark defects are fixed at the
layer that caused them — not just at the reporting layer. The engine is
synchronized to hardware that exists. Live evidence below is from this box: a real
27B worker, real briefs, real pytest.

---

## Task 1 — model-suite drift corrected

`shared/model-suite.json` named `northstaros-qwen3.8:27b` as the **local** model for
T1, T2 and T3. That id is **not an Ollama tag** — it is a client alias for the
llama.cpp worker on `127.0.0.1:8080`. So every local text tier resolved to a model
Ollama did not have, which is the same defect class as the vision drift recorded in
`00_STATE.known_issues` on 2026-10-22.

| Change | Where |
|---|---|
| T1/T2/T3 `local` → `bojo`, plus `local_engine` | `shared/model-suite.json` |
| New `local_engines` block: Ty and Bojo, measured values only | `shared/model-suite.json`, surfaced by `model_router.catalog()` |
| `LOCAL_ALTERNATES` emptied — `qwen3:14b` was never on disk, so it advertised a fallback that could not load | `Northstar_backend/model_router.py` |
| `resolve(..., installed=[...])` → `local_model_not_installed`; `catalog()` gains `text_local_status` | `model_router.py` |
| Reference doc for the measured profile | `docs/LOCAL_ENGINES.md` (new) |
| `proj_bench.start_server()` launched the worker at `-c 8192 -ctk q8_0` — a configuration that does not exist in production — and refused to run when a worker was already up | `tools/proj_bench.py`, now `-c 65536 -ctk q4_0 -ctv q4_0` + MTP, and a healthy running worker counts |

**Live proof of the profile** (worker log, 2026-10-29):

```
n_ctx_slot = 65536, kv_unified = 'false'
creating MTP draft context against the target model
eval time =  169.90 ms / 14 tokens (13.07 ms per token, 76.52 tokens per second)
eval time =  1548.36 ms / 123 tokens (12.69 ms per token, 78.79 tokens per second)
draft acceptance = 0.83 / 0.56 / 0.73 / 0.60   (mean len 2.4–4.3)
```

Decode measured **10.5–17.6 ms/token (57–95 tok/s)** across calls, consistent with
the documented `~69 tok/s / ~14.5 ms/token`. `n_ctx_slot = 65536` is the launch
ceiling, not an aspiration.

## Task 2 — one task-execution contract

No `?engine=`, no `202`, no SSE anywhere in code. `POST /api/admin/tys/tasks/{id}/run`
stays synchronous and admin-gated, and now returns the kernel evidence on the same
`200`:

```
{ "task":   { ...completed work order... },
  "kernel": { status, plan, interventions, budget, events }   // null if the step lane ran }
```

Contract documentation: `docs/TASK_EXECUTION.md` (new).
Tests: `test_run_route_is_synchronous_and_has_no_speculative_parameters`
(query params are exactly `{max_steps}`; no `202`; no declared responses),
plus evidence-present, evidence-absent and evidence-unreadable cases. Evidence
retrieval can never fail a run.

## Task 3 — p01 and p03

### p01 — the real root cause was acceptance weaker than the scoring bar

The prompt's description ("returns `needs_human` even when checks pass") was half
the story. The first live run reproduced the **inverse** signature:

```
p01: ok=false  agent_ok=true  content_valid=true  extra=false
fix.patch = correct diff          calc.py = still `return a - b`
```

The model wrote a valid patch, never applied it, and the loop stopped *satisfied*
because acceptance only asked "does the artifact exist and parse". The outcome
checks (`calc_fixed`, `pytest`) were applied afterwards to compute `ok` — a bar the
loop could not see, so it could not repair against it.

Three layers fixed:

1. **`agent_kernel/kernel.py::_verify_node`** — the executor row is a self-report
   and can no longer veto passing acceptance. A bounded loop that wrote the
   artifacts and passed the verifiers is `done`, with the self-report superseded
   ("acceptance satisfied after the loop stopped without finishing"). No
   acceptance and no self-report is still a block — the fail-closed rule is intact.
2. **`agent_kernel/coding_agent.py`** — re-checks acceptance after the step budget,
   and reports it explicitly as `CodingResult.acceptance_recovered`, so every
   caller inherits the rule instead of re-implementing it.
3. **`tools/coding_bench.py::acceptance_for`** — the loop's acceptance is now
   identical to the scored bar: `calc_fixed` **and** `pytest == 0` for p01,
   `py_compile == 0` for p05.

**Live before → after** (`tools/coding_bench.py`, real 27B):

| | before | after |
|---|---|---|
| p01 | `ok=false`, 3 steps, 4.3 s — patch written, never applied | **`ok=true`**, 10 steps, 18.0 s — loop read `FAIL: calc_fixed=False; pytest=1` and repaired |
| p02 | `ok=true` | `ok=true`, 1 step, 2.1 s |
| p05 | `ok=false`, 2 steps | **`ok=true`**, 5 steps, 5.3 s |
| total | 1/3 | **3/3** |

Verified artefact, not just a verdict: `p01/calc.py` → `def add(a, b): return a + b`,
summary line `calc_fixed=True; pytest=0`.

### p03 — the write-stall guard

`Workspace.write` is now atomic and bounded: chunked write to a sibling temp file,
`flush` + `os.fsync` (the stream-flush hook), then `os.replace`. A write that
exceeds `write_timeout_s` (default 15 s) is reported to the model as a tool error
with the target left untouched; a late worker sees the cancel flag before the swap
and discards its temp file. No partial file, no hung run, no exception escaping the
tool.

The pressure loop was also wrong in a second way: it cleared only on the `write`
tool, so an `apply_patch` that produced the artifact left the model stuck in
write-only pressure with its other tools hidden. It now clears when the declared
artifact exists on disk, however it got there.

**Live:** `coding_full_bench.py --ids p03` → `ok 1/1`, `refactor.md` 1,138 B beside a
`report_builder.py` split with its test, `pytest` return code **0**. No stall.

## Task 4 — guardrails verified, not asserted

| Guardrail | Evidence |
|---|---|
| No Amazon linkage | `tools/test_no_amazon_linkage.py` → **2276 passed, 0 failed**; kernel policy denies every Amazon host before any grant |
| Browser via Chrome Connect only | `test_chromeconnect_*` → **38 passed**; `tools/chromeconnect_guard.py` → `PASS: direct playwright import refused`, `PASS: cdp lock holder` |
| Write denylist | 6 new tests: `.env`, `.env.local`, `config/chromecontrol_policy_owner.json`, `config/chromecontrol.json`, `fixtures/*`, `tests/fixtures/*` all refused; `.env.example` still writable |
| No installs, no credential reads, no spend | none performed; no secret was opened or printed |

## Test totals (real counts)

| Suite | Result |
|---|---|
| kernel / coding agent / guardrails / tys / model router / chat / provider / chromeconnect / bojo | **231 passed** |
| new guardrail tests (`test_coding_guardrails.py`) | 13 |
| new route-contract tests (`test_tys_assistant.py`) | 4 |
| `tools/proj_bench.py --limit 20` | harness validation **20/20**, evidence 1.0, resume pass |
| `tools/rea_regress.py --quick` | **PASS** — every measured metric at or better than baseline |

## Not claimed

* No 20-brief full re-run. One brief (p01, p03) each was run live; the full hybrid
  sweep is a separate, longer run.
* No AST patching lane exists. `patch_tool` is `git apply` on a unified diff, by
  design, with path escapes refused.
* `p01`/`p03` are **brief ids**, not kernel defects — that framing came from the
  source document and is corrected here and in
  `reports/spec_reconciliation_engine_tiering_20261029.md`.
* The 27B worker is not left resident: `8080` closed after the runs.

## Files changed

```
shared/model-suite.json                     Northstar_backend/agent_kernel/kernel.py
Northstar_backend/model_router.py           Northstar_backend/agent_kernel/coding_agent.py
Northstar_backend/tys_api.py                Northstar_backend/agent_kernel/coding_executor.py
Northstar_backend/test_model_router.py      Northstar_backend/agent_kernel/coding_tools.py
Northstar_backend/test_tys_assistant.py     Northstar_backend/test_coding_guardrails.py  (new)
tools/proj_bench.py                         tools/coding_bench.py
docs/LOCAL_ENGINES.md  (new)                docs/TASK_EXECUTION.md  (new)
```
