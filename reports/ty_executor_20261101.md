# Ty executor — protocol hardening and the CPU resource wall (2026-11-01)

Continues `reports/ty_autonomy_gate_20261101.md`. The accepted blocker was
envelope-level model output, not creative ability. That blocker is now handled by
an executor; the remaining blocker is host RAM on the operator's restored CPU-only
Ollama configuration. Nothing in that configuration was changed.

---

## 1. VERIFIED / REPORTED / BLOCKED

| Area | Status | Evidence |
|---|---|---|
| Resident RAM, restored CPU config | **VERIFIED — floor not met at dispatch today** | `state/evidence/model_resident_coder_ctx8192_20261101.json` (4.55 GB free → 2.58 GB min); one earlier pass at 5.31 → 3.13 GB |
| Model JSON/tool execution | **VERIFIED (with refusals)** | `tools/probe_lane_protocol.py`, `state/evidence/lane_protocol_qwen25coder_3b_20261101b.json` |
| Real model-authored implementation | **VERIFIED in a disposable workspace** | `tools/executor_proof.py` → `state/evidence/executor_proof_qwen2.5-coder_3b.json`; `add(2,3)==5` |
| Restricted commit by the supervisor | **NOT ACHIEVED** | repo task `ty-budget-stop` failed; file restored; no commit |
| Rollback / recovery | **VERIFIED, unchanged** | STOP, crash-resume and acceptance restore demonstrated in the prior report; supervisor/agent tests green |
| Campaign readiness | **BLOCKED** | `--ready` → NO-GO when the measured resident headroom is 2.39–2.58 GB against the 3 GB floor |

**Verdict: the system is not ready for a bounded model-authored campaign on this
host as configured.** The next proven capability is a *cleaner failure mode*: the
executor now refuses or normalises every bad turn and the model completes a real
fix in a disposable workspace; what remains is host memory, not model or harness
behaviour.

---

## 2. Actual lanes (resolved through the Ollama API, not disk inference)

| Tag | Digest | Params | Quant | Size |
|---|---|---|---|---|
| `qwen2.5-coder:3b` | `f72c60cabf62…6225` | 3.1B | Q4_K_M | 1.8 GB |
| `bojo:gpu-orig` | `5f1256d250e9…a48` | 1.9B | Q8_0 | 2.5 GB |
| `qwen3.5:2b` | `0689d44085e0…30a` | 1.9B | Q8_0 | 2.5 GB |
| `qwen2.5vl:7b` | `5ced39dfa4ba…1cc` | 8.3B | Q4_K_M | 5.56 GB |

Runtime, unchanged and verified: `OLLAMA_LLM_LIBRARY=cpu` (User scope),
`OLLAMA_NUM_GPU=0`, `inference compute id=cpu`. No environment variable, service,
backend or system setting was modified. 27B is excluded (does not fit).

### Measured residency (CPU, the configuration in force)

| Run | baseline free | min free while resident | resident | verdict |
|---|---:|---:|---:|---|
| `qwen2.5-coder:3b`, ctx 32768 | 5.31 GB | **3.13 GB** | 2.34 GB system | FLOOR-MET |
| `qwen2.5-coder:3b`, ctx 8192 | 4.55 GB | **2.58 GB** | 2.05 GB system | FLOOR-MISSED |
| `qwen2.5-coder:3b`, at dispatch | 4.65 GB | **2.39 GB** | 2.05 GB system | FLOOR-MISSED |
| `bojo:gpu-orig`, ctx default | 5.08 GB | 2.44 GB | 2.25 GB system | FLOOR-MISSED |

The drop is a stable ~2.0–2.3 GB (weights + KV). The verdict flips on the host's
free RAM, not on the model: the CPU lane needs ≈5.0 GB free to clear the floor, and
this 15.4 GB box carries ~10.9 GB of other work. `--ready` now measures **every
model the authorized queue names**, so this is the number the campaign sees.

---

## 3. The executor (commit `3669f651`)

`Northstar_backend/agent_kernel/tool_protocol.py` (new) sits between the model and
the tools and decides what may run.

**Refusals (no execution):**

* more than one JSON object in a turn (`multiple_actions`);
* unknown action, unknown/extra argument, wrong type, oversize argument;
* a path outside the task scope — checked before *any* tool runs, and a batch is
  atomic (one bad file rejects the whole `write_many`);
* a command that is not an argv list, or contains a control character;
* **a whole-file `write` of an existing source file** — `ast_edit` or
  `apply_patch` is required. This is the rule that stops a small lane truncating a
  module it cannot reproduce (observed: an 8-line module replaced by 54 bytes).

**Normalisation (deterministic, recorded as `notes`):** one fence; case and the
alias table; commentary appended to the tool name (`ast_edit not recognized`); a
double-encoded `"args"` string; arguments lifted to the top level; an empty-string
argument key; a single unknown key for a one-argument action; truncated, basename
or doubled-extension paths when exactly one in-scope path matches; mangled AST op
names. The executor never generates implementation content.

**Bounded repair:** a refused turn becomes one `PROTOCOL <code>: … Hint: …`
observation. After `max_protocol_errors` the run ends with
`error="protocol_failed: <code>"` instead of burning the step budget. Model
failures and executor rejections are counted separately
(`protocol_errors` / `scope_rejections`) and both are in the task evidence.

**Task-scoped protocol:** a task declares `allowed_tools`; the prompt lists only
those actions plus the only commands that will execute. Pressure mode no longer
hides `ast_edit` (it used to narrow the schema to `write`/`finish`, steering the
model into the one action the executor refuses).

**Adapter:** an HTTP 5xx on the JSON-constrained path retries the same prompt
without the constraint (no content generation). `num_ctx` is carried per task as a
request option.

**Tests:** `Northstar_backend/test_tool_protocol.py` — 28 cases covering valid
action, malformed JSON, multiple objects, unknown action, out-of-scope path before
execution, whole-file rewrite refused (including a 38-byte module), atomic batch,
string command, control characters, semicolon inside a legitimate `python -c`,
allowlist still enforced by the workspace, bounded retry count, separate
rejection counters, and a timed-out command.

```
$ python -m pytest test_tool_protocol.py test_coding_agent.py test_agent_kernel.py \
      test_continuous_loop.py test_autonomy_readiness.py test_autonomy_recovery.py \
      test_autonomy_supervisor_crash.py -q
132 passed in 5.30s
```

---

## 4. Live protocol diagnostics (real lane, real executor)

`tools/probe_lane_protocol.py --model qwen2.5-coder:3b` →
`state/evidence/lane_protocol_qwen25coder_3b_20261101b.json`

| Scenario | Result |
|---|---|
| one-step action | **rejected** — `{"path":"North}}..{"}` (truncated/duplicated envelope) |
| two-step sequence | read rejected (truncated path) → **`ast_edit` accepted and executed**, `return a + b` written |
| invalid-output repair | prose → `invalid_json`; the repair turn returned a mangled key → `unknown_argument` |
| bounded timeout | not exercised (request returned before the budget); daemon healthy after |

The two-step result is the important one: when the envelope is usable, the model's
edit is correct.

---

## 5. The one real model-authored fix

`tools/executor_proof.py --model qwen2.5-coder:3b` (disposable workspace, no repo
files touched):

```
ok: true
acceptance_after_run: {"ok": true, "detail": "add(2, 3) == 5"}
steps: 6   protocol_errors: 5   scope_rejections: 0   elapsed_s: 15.9
module_after: def add(a, b): ... return a + b
```

The model authored `return a + b`; acceptance imports the module and calls
`add(2, 3)`. Five envelope failures were refused and repaired inside the budget;
no part of the implementation came from the harness.

**This is a controlled proof, not the repository task.** The repo task is below.

---

## 6. The repository task, and why it did not commit

Task `ty-budget-stop`: one file (`Northstar_backend/agent_kernel/budget.py`), one
defect (a hard budget stops one step late), one independent probe
(`state/probes/t4_budget_stop.py`, confirmed failing on HEAD), read-only to the
model.

| Attempt | Lane | Result |
|---|---|---|
| 1 | `qwen2.5-coder:3b` | failed, `steps=6`, `protocol_errors=2`, `scope_rejections=1`, then **HTTP 500** from Ollama; file restored, no commit |
| 2 | `qwen2.5-coder:3b` | refused before dispatch: `readiness_no_go` (measured 2.39 GB < 3.0) |

Attempt 1 transcript (summarised): `run` with a string command → refused;
`run` with pytest → not allowlisted (only the probe may run); `run` with a `path`
argument → unknown argument; then no tool name; then a verify-stall refusal.
The model never issued a read or an edit. Attempt 2 never started.

Rollback is intact: `git status -- Northstar_backend/agent_kernel/budget.py` empty,
no commit, `restoration: "ok"` in `state/continuous_loop_state.json`.

---

## 7. Why it is not ready for one bounded campaign

1. **Host RAM.** On the restored CPU configuration the measured resident headroom
   is 2.39–2.58 GB against the 3 GB floor. It passed once at 3.13 GB when the host
   was quieter; the gate is re-measured at dispatch and refuses when it is not.
   This is the floor doing its job, not a model verdict.
2. **Envelope reliability.** The 3B lane produces a usable action on roughly half
   its turns under a task prompt (5 refusals in the passing proof). The executor
   absorbs that within a bounded budget, but one run is still a coin toss on
   whether it converges inside 8 steps.
3. **HTTP 500s.** Two 500s were observed from `/api/chat` after ~9 s on identical
   prompts, with and without the JSON constraint. Not diagnosed further: the
   daemon is the operator's, unchanged.

**What would move it:** ~1 GB more free host RAM (or a lane whose resident cost is
under ~1.5 GB) makes the gate pass reliably; a second bounded attempt then has a
real chance. That is an operator resource decision, not a code change.

---

## 8. Commits, files, commands

| Commit | Content |
|---|---|
| `dbf85b8e` | measured resident-RAM gate + dispatch refusal |
| `8ad91edd` | harness fixes (resume, acceptance verdict, scope rule) |
| `bf5893d2` | residency-dispatch test pin |
| `3669f651` | **strict action executor, bounded repair, task-scoped protocol, per-request ctx** |
| worktree `worktree/ty-autonomy` | `a5197db3`, `0b4ff7e0`, `a864498b` (isolated runs) |

Changed paths in `3669f651`: `Northstar_backend/agent_kernel/tool_protocol.py`
(new), `coding_agent.py`, `coding_tools.py`, `local_model.py`,
`Northstar_backend/test_tool_protocol.py` (new), `scripts/ty_task_runner.py`,
`scripts/continuous_loop.py`, `tools/executor_proof.py` (new),
`tools/probe_lane_protocol.py` (new), `tools/set_task_ctx.py` (new),
`config/continuous_loop_tasks.json`.

```powershell
python scripts/continuous_loop.py --ready                     # GO at 5.39 GB free, NO-GO at 4.65 GB
python tools/probe_lane_protocol.py --model qwen2.5-coder:3b
python tools/executor_proof.py --model qwen2.5-coder:3b
python scripts/continuous_loop.py --task ty-budget-stop --max-tasks 1 --deadline-minutes 20
python -m pytest Northstar_backend/test_tool_protocol.py -q
```

Boundaries: no Amazon, no spend, no credentials, no external network, no browser,
no production data, no downloads, no persistence. `AGENTS.md`, policies, task
authorization, guards and acceptance checks untouched. The 3 GB floor is unchanged.
No parallel supervisor/executor framework was added.
