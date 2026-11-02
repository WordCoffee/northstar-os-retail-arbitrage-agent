# Bounded requalification — 20-step budget did not close the two remaining fixes (2026-11-01)

The authorized step budget (8 → 20) was applied to exactly the two remaining tasks,
and both were re-dispatched on the screened `qwen3.5:4b` lane. **Neither passed.**
Qualification stays at **1 of 3**. No soak, no broad repair.

---

## 1. DECISION

**Qualification: 1/3.** The extra budget did **not** materially work: both tasks spent
it on repeated rewrites, and both ended with the probe raising (their edits broke the
module) rather than with a near-miss. The one accepted fix (`883a7fed`) is untouched.

Contract change, versioned: `ty-artifact-jpeg` and `ty-diff-select-headers` are now
**contract v2** with `max_steps=20` and an explicit `supersedes` line naming the v1
contract (8 steps, two failed dispatches). Nothing else changed — same objective,
probe, acceptance, scope, tools, commit paths, limits.

---

## 2. TASK TABLE

| Task | Steps | Accepted edits | Runs | Result | Probe after | Commit |
|---|---:|---:|---:|---|---|---|
| `ty-diff-select-headers` | 20 | 13 | 3 | `max_steps` | `t6` still FAIL (2) | none — restored |
| `ty-artifact-jpeg` | 14 | 4 | 1 | acceptance failed | `t7` still FAIL (2) | none — restored |

Both ended with the independent probe raising a **Traceback**, i.e. the edits broke
the module (`select_hunks` / `artifact_kind` no longer raise what the probe calls).
Byte-for-byte restoration verified: `git status` clean for both files, probes fail
exactly as before, `t5` still passes.

The campaign halted at `max_consecutive_failures=2` after 2 dispatches (4 allowed).

---

## 3. RESOURCE (fresh measurement, same profile)

| Measure | Value |
|---|---|
| Model | `qwen3.5:4b` (`d8b0f5e9…38c04`), official stock manifest |
| Profile | campaign-scoped GPU serve, f16 KV, `num_ctx=8192`, native tools |
| Host before load | **8.389 GB** (≥ 6.0 required) |
| Host low-water | **7.250 GB** (drop 1.139) → **FLOOR-MET** (3.0) |
| Resident | **3.134 GB VRAM**, 42.3 tok/s |

Evidence: `state/evidence/model_resident_qwen35_4b_requal_20261102.json`.

---

## 4. REGRESSION

```text
python -m pytest test_tool_protocol test_coding_agent test_agent_kernel
      test_continuous_loop test_autonomy_readiness test_autonomy_recovery
      test_autonomy_supervisor_crash test_foreground_launcher test_budget_limits
      test_task_prompt test_local_model_native test_screen_lane test_ast_edit_body
      test_qualification_budget -q
182 passed in 6.91s
```

New coverage this round (`test_qualification_budget.py`, 7 cases): only the two tasks
carry 20 steps; every other task keeps its own limit; the superseding records link to
v1; the completed fix and its state are untouched; a 20-step task still stops on the
campaign deadline and on the consecutive-failure budget; the per-path read budget
stays 4 regardless of step budget.

---

## 5. STATE

* HEAD `bae478a3` (plus this report). Task commit from this round: none.
* Preserved: `883a7fed` (the accepted hitl fix) and every failed-run record
  (`state/runs/*`, `reports/evaluation_ledger.jsonl`).
* Operator daemon restored: `ollama app`, 10 models, **0 resident**, `cpu`/`q4_0`,
  GPU 0 MiB. No lock, STOP, worker or campaign process.
* Read budget, floors, deadlines and failure budgets unchanged.

---

## 6. VERDICT

**PARTIALLY READY** — 1 of 3 accepted, unassisted, task-owned model-authored fixes.
Not ready for the next autonomy gate (soak / broad repair), and not claimed.

---

## 7. NEXT ACTION (one decision)

Accept 1/3 as the demonstrated capability of this lane, or authorise a different
engineering approach. The evidence says more steps are not the constraint: at 20
steps the lane rewrites the same function repeatedly and damages module behaviour it
had already read. A fourth attempt on this lane is not recommended.
