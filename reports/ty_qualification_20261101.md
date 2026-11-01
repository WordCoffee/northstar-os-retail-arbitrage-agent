# Ty qualification run — resource gate cleared, model lane failed (2026-11-01)

Readiness passed on measured evidence. The qualification itself did not: **six of six
authorised attempts were spent and no model-authored fix was accepted.** This is a
model-capability limit, not a memory or executor limit.

---

## 1. VERDICT

**PARTIALLY READY — BLOCKED on gate 2.** Resource/profile readiness is proven for
the restored CPU configuration; the installed model lane cannot complete a two-action
(read → edit) task under the JSON protocol. No Ty commit exists.

---

## 2. GATES

| Gate | Status | Evidence |
|---|---|---|
| 1. Resource / profile readiness | **PASS** | GO at `2026-11-01T19:25:41Z`, pre-load 6.99 GB, measured min **5.056 GB** while resident (2.052 GB system), ctx 8192, FLOOR-MET |
| 2. First accepted model-authored fix | **FAIL** | 6 dispatches, 0 accepted, 0 commits |
| 3. Three-fix qualification | **FAIL** | 0/3, attempt budget exhausted (6 of 6) |
| 4. 120-minute soak | **NOT RUN** | gated on 3 |
| 5. Regression batch | **PASS** | 152 passed in 4.93 s |
| 6. Initial repair campaign | **NOT RUN** | gated on 2–3 |

---

## 3. MEMORY (measured, operator configuration untouched)

| Point | Value |
|---|---|
| Launcher check 19:03:22Z | 6.587 GB free → **GO** |
| Campaign A dispatch | ≥ 6.0 GB free |
| Final readiness 19:25:41Z | pre-load **6.99 GB**, resident min **5.056 GB**, resident 2.052 GB system, **FLOOR-MET** |
| Pre-load requirement | 6.0 GB (unchanged) |
| Resident floor | 3.0 GB (unchanged) |
| Sampling | `psutil` available, 200 ms during generation, 1 s during dispatch |

One genuine memory event: at 19:06 the launcher refused at **5.00 GB** — correctly —
because the previous campaign left a model resident (1.92 GB). Releasing *that
campaign-owned residency* (not an unrelated process) restored 7.0 GB and the gate
passed. No other process was stopped; no Ollama setting changed.

---

## 4. TY WORK — six dispatches, zero accepted

| Run | Task | Steps | Protocol refusals | Scope refusals | Result | s |
|---|---|---|---:|---:|---:|---|---:|
| A | `ty-hitl-skip-report` | 8 | 2 | 2 | max_steps | — |
| A | `ty-diff-select-headers` | 8 | 5 | 1 | max_steps | 53 total |
| B | `ty-hitl-skip-report` | 8 | 3 | 2 | max_steps | — |
| B | `ty-diff-select-headers` | 7 | 7 | 0 | protocol_failed | 219 total |
| C | `ty-artifact-jpeg` | 8 | 1 | 4 | max_steps | 213 |
| D | `ty-hitl-skip-report` | 8 | 4 | 4 | max_steps | 32 |

Every run ended with `restoration: "ok"`, the task file byte-identical, and **no
commit**. Campaign A and B halted at `max_consecutive_failures=2` exactly as
contracted; C and D were the two remaining attempts.

**What the model actually did** (verbatim from the transcripts, trimmed):

```text
run   REFUSED  command not allowlisted; allowed: python state/probes/t5_hitl_corrupt.py
ast_edit  target 'count_corrupt_records' not found   <- guessed symbol, never read the file
write REFUSED  out of scope: src.py  <- path copied from the prompt's own example
ast_edit  missing argument 'op'
ast_edit  unknown argument 'args_content' / 'ource' / '_hitl_counts.py'
```

Across the six runs the lane issued **zero successful `read` of its target file** and
never reached an executing `ast_edit` on it.

**Capability limit, named:** the installed 3B lane does not sustain a two-action
sequence under a multi-turn JSON protocol. It copies example paths from the schema,
guesses symbol names, and its envelope degrades roughly one turn in two. The executor
is not the limiter — it refused 22 bad turns across these runs with precise codes and
no out-of-scope write ever executed.

---

## 5. HARNESS CHANGES MADE BECAUSE OF THE FAILURES

These are executor/prompt defects, not model help, and none of them authors code:

| Commit | Change | Why |
|---|---|---|
| `24427069` | the `run` example in a task-scoped prompt is the task's real allowlisted command | every task lost its first step copying `python -m pytest`, which the workspace refuses |
| `c7ed8936` | `ast_edit` requires a prior `read` of that file (`read_required`); protocol budget 8 | the lane "edited" symbols it had never seen (`count_corrupt_records`) |
| `654839ac` | a scope refusal names the exact writable path; objectives say run the probe instead of "repair from its output" | it repeatedly wrote the acceptance probe or `src.py`, treating the probe as the thing to repair |

---

## 6. WHAT WAS NOT DONE

* No soak, no repair campaign, no Northstar product claim.
* The worker's own `budget.py` control was **not** a model task (blocked as
  self-modification); it was repaired separately as bootstrap maintenance and does
  not count as a Ty fix.
* No forced model choice, no download, no environment change, no floor or
  precondition change.

---

## 7. CURRENT STATE

* Nothing running: no supervisor, no worker, no lock, no STOP, no resident model
  (released), 0 worker processes.
* Queue: all three qualification tasks `failed`; attempt budget 6/6 spent.
* No eligible work remains without an operator decision.

---

## 8. OPERATOR ACTION

There is no remaining attempt under this directive. The next step is a decision, not
a command:

* a more capable installed lane would need an authorised download (not permitted
  here), **or**
* accept the demonstrated limit — the automation can *detect and refuse* bad model
  output reliably, but the installed 3B lane cannot yet author an accepted fix.

Status, if wanted, is read-only:

```powershell
python scripts/continuous_loop.py --status
python scripts/continuous_loop.py --ready
```
