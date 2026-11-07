# M0.5-spike — the coding lane's authoring capability, measured

**Date:** 2026-11-06
**Unit:** A10
**Question (from `reports/ty/M0.5_spike_plan.md`):** can the loop author acceptable patches at
all? If it cannot, a "best-of-N auto-repair" would be a pretend evaluator.
**Answer:** **0 of 5 problems solved. The verdict is STOP** — no local best-of-N, and no pretend
evaluator. The measurement also localises the failure: the lane never got as far as reasoning
about the fixes. It failed in the mechanics of its own tool surface.

---

## 1. Method, as run (and the four places it deviates from the plan)

Fixed before any candidate ran; nothing was tuned after seeing results.

* Five real problems (S1–S5), three candidates each, through the local coding lane
  (`agent_kernel.CodingAgent` via `scripts/ty_task_runner.py`) on a local Ollama model.
  **15 candidates** in the scored matrix, **9 more** in a post-hoc diagnostic arm (§6).
* Every candidate started from a clean `git worktree` at `HEAD 15f0cc15`, so no candidate
  inherited another's work and **no product source in the repository was touched**.
* Each problem has an independent acceptance gate, held **outside** the candidate's write scope
  (`<worktree>/.spike_acceptance/`), plus the targeted test file. The gate is run again by the
  harness after the candidate stops — a candidate's own claim is never the verdict.
* `solved` = gate passed **and** targeted test file green **and** a non-empty diff **and** that
  diff touched the module the problem lives in **and** the diff parses as a unified patch
  (`agent_kernel/content.validate_patch`).

**Deviations, stated plainly:**

1. **No full-suite run.** The plan's condition 2 is a full backend suite green *by test name*
   (`tools/check_regression.py`). This unit was explicitly instructed not to run the full suite,
   so the substitute is the targeted test file for each problem, plus the semantic diff validator
   (the plan's condition 3). The full-suite check remains unmeasured.
2. **The lane's entry point.** `TysAssistant.run_kernel(coding_agent=True)` is not runnable here:
   its coding path builds the model against `CodingWorkerAdapter.BASE` = `http://127.0.0.1:8080`
   and requires a task store. Probe (`state/evidence/spike/lane_probe.json`):
   `{"available": false, "detail": "worker not started (on demand)"}`, `llama_cpp_health: false`.
   `scripts/ty_task_runner.py` is the supervised entry point for the *same* `CodingAgent` loop
   (`scripts/continuous_loop.py` calls it) and takes any local model, so that is what ran.
3. **S1's target check is void.** Measured, not assumed: 1 failure in 100 baseline runs (§4).
4. **The candidate needs a failing check to iterate against.** The first dry run
   (`s5_plate_cleanliness/cand0_harness_dryrun`) exposed that a task whose acceptance command is
   already green makes the lane answer `finish` immediately and report success with zero edits.
   The acceptance command for each case is therefore a visible copy of the gate, placed at
   `<worktree>/spike_check/`. The judging copy stays hidden. This is recorded because it is a
   design fact about the loop, not plumbing.

## 2. Environment (real numbers)

| Item | Value |
|---|---|
| Model | `qwen3:8b` (Ollama, Q4_K_M, 8.2 B) |
| Residency | **CPU only** — `/api/ps` reports `size_vram: 0` while the RTX 5080 shows 0 MiB used; the daemon runs with `OLLAMA_NUM_GPU=0`, `OLLAMA_LLM_LIBRARY=cpu` |
| Throughput | ~25 s per turn; 12 steps per candidate; 600 s hard cap per candidate |
| Ollama health | up, 13 models; **no `northstaros-*` model present** |
| Wall clock | matrix 46 min (19:48→20:34), arm B 50 min (20:37→21:27) |

**Why `qwen3:8b` and not a coder model.** The obvious choice is not usable. Both installed
qwen2.5-coder builds break the agent's one-JSON-action protocol, reproducibly
(`state/evidence/spike/model_smoke.json`):

```
qwen2.5-coder:7b              -> {"":"ast_edit","object":{"path":" "}}      parsed_tool: null
qwen2.5-coder:7b-parser-f16   -> {"":"ast_edit","object":{"path":" "}}      parsed_tool: null
qwen3:8b                      -> {"tool":"read","args":{...}}               parsed_tool: read
bojo                          -> {"tool":"read","args":{...}}               parsed_tool: read
qwen3.5:4b                    -> {"tool":"ast_edit","args":{...}}           parsed_tool: ast_edit
```

`qwen3:8b` was picked as the strongest protocol-valid model installed. `bojo` (4.8 s) is faster
but smaller. The 27 B llama.cpp lane (13.9 GB GGUF, launcher present) was **not** started: this
box had 6.75 GB free RAM, the daemon is pinned to CPU, and the task specified the local Ollama
lane. That is a real limitation of the measurement and is repeated in §8.

## 3. The five checks, and proof that each one can fail

`state/evidence/spike/baseline.json` — every gate run against the **unmodified** tree:

| # | Problem | Gate | Baseline result | Discriminates? |
|---|---|---|---|---|
| S1 | cancel race (`test_cancel_leased_job_cooperative`) | 20 runs under 20-way CPU load | **green** (and green in 60/60 runs) | **no** |
| S2 | `product_fidelity` cannot score a composite | explicit `product_box` must score ≥ 85 on `lifestyle_linen_composite.png` | red: score **0.0** (`ssim 0.0059`, `phash 32`) | yes |
| S3 | Documents page fails AA | 11 real Documents-page colour pairs from `tokens.css`+`app.css` | red: `.pill-ochre` **2.48:1**, `.pill-warn` **2.86:1**, `.pill-unknown` **3.1:1** | yes |
| S4 | Shiitake plate under a Lion's Mane headline | plate OCR contradicts copy ⇒ refused | red: function absent | yes |
| S5 | cleaned plate still smeared | 0 OCR boxes + residual marks ⇒ reported | red: `measure=` not accepted | yes |

The targeted test file was green at baseline for all five, so a green test file alone can never
be evidence of a fix — which is why the gate is the primary condition.

**S1 is not measurable with this check.** The bug reproduces (`JobValidationError: job is
cancel_requested not leased`) but at roughly 1 % per run — 1 failure in 100 baseline runs
(`state/evidence/spike/s1_baseline_note.md`). A 20-run gate therefore passes a broken build about
four times in five. All three S1 candidates "passed the gate" while changing nothing. S1 is
reported as **no signal**, not as a lane failure, and it is excluded from the capability score
(§5 gives both denominators).

**The S2 bar is reachable.** Calibrated before any candidate ran
(`state/evidence/spike/s2_calibrate_masked.py`): a correct implementation — mask the composite's
product box by the cutout's alpha, flatten both onto white — measures `ssim 0.9954`,
`phash 0`, score **100.0**. The generic subject-crop path measures `ssim 0.1118`. So ≥ 85 tests
the fix, not an arithmetic ceiling.

## 4. The matrix (arm A — the plan's method, 15 candidates)

`model qwen3:8b` · 12 steps · 600 s cap · worktree at `15f0cc15` · full evidence per candidate in
`state/evidence/spike/<slug>/cand<N>/` (`task.json`, `agent_result.json`, `candidate.diff`,
`gate.txt`, `targeted_test.txt`, `verdict.json`).

| # | Problem | cand 1 | cand 2 | cand 3 | solved |
|---|---|---|---|---|---|
| S1 | cancel race | gate green, **0-byte diff**, claimed ok | gate green, **0-byte diff**, claimed ok | gate green, **0-byte diff**, claimed ok | 0/3 (gate void) |
| S2 | `product_fidelity` + `product_box` | no diff (list loop) | no diff (list loop) | no diff (list loop) | 0/3 |
| S3 | Documents AA contrast | no diff (list loop) | no diff (list loop) | no diff (list loop) | 0/3 |
| S4 | plate/copy guard | no diff (`model call failed: timed out`, 1 step) | **timeout at 600 s** | no diff (12 steps) | 0/3 |
| S5 | plate cleanliness | no diff (`add_constant` loop) | no diff | no diff | 0/3 |

Every failing candidate has the same shape. Verbatim from
`s5_plate_cleanliness/cand1/agent_result.json`:

```
protocol_errors 0 | scope_rejections 5 | diff 0 bytes | summary "step budget exhausted"
PROTOCOL bounded_edit_required: Northstar_backend/render_text_guard.py is an existing source
  file; a whole-file write is refused Hint: use ast_edit (Python) or apply_patch with a small hunk
unknown AST op 'add_constant'; known: replace_function_body, replace_function, add_method,
  add_before, add_after, delete, add_import, replace_imports, replace_global
unknown AST op 'add_constant'; ...            (x7, until the step budget ran out)
```

S2 and S3 are worse: the model never opened the target file. It called `list .` — the repo root —
for most of its 12 steps, and twice tried to read `autothink/backend/llm_adapter.py`, outside its
scope. S3's arm-A transcripts are `list` × 11.

**Score: 0 / 5. Candidates that produced any patch: 0 / 15.**

## 5. Verdict

**STOP.** The plan's rule is explicit: `0/5` → stop, report, and the loop becomes
detect-and-prepare; no pretend evaluator. Applying it with either denominator:

* strict plan, all five cases: **0/5**
* cases whose gate discriminates (S2–S5): **0/4**

There is no basis for local best-of-N, and no basis for the DeepSeek hybrid either (that is the
`1–2/5` branch, and it would buy a paid lane to do work this measurement says the *harness*, not
the model, is blocking).

## 6. Post-hoc diagnosis (arm B — not part of the score)

The 0/15 zero-diff result answers "can the lane author patches *as configured*", not "can an 8 B
model code". So one supported knob was changed and the same cases re-run: `allowed_tools`. That
option (a) removes actions the task cannot use and (b) switches `CodingAgent` to its task-scoped
prompt, which drops the 60-entry repo-root tree that kept re-anchoring the model. Same model, same
gates, same worktree: `run_case_scoped.py`, 9 candidates.

| Case | arm B patches | arm B solved | what changed |
|---|---|---|---|
| S2 | 2 / 3 | 0 | reads `picture_scorecard.py` immediately, then **rewrites `score_case`**: a 197-line hunk replaced by 29 lines, deleting marketplace/text/fidelity logic → targeted test **red** |
| S3 | 0 / 3 | 0 | replaces the `list` loop with 12 attempts to open `/ui/documents/documents.js` — a URL treated as a path |
| S4 | 0 / 3 | 0 | `ast_edit target 'check_plate_agrees_with_copy' not found` × 5, then a 600 s timeout |
| S5 | 0 / 1 | 0 | reads the file correctly, then `add_global` × 9 (`unknown AST op`) |

Three findings, all mechanical:

1. **The default surface is the first blocker.** With `list` available the lane lists the repo root
   and stops working; without it, it goes straight to the target file. The loop's own default
   configuration defeats it.
2. **The edit vocabulary cannot express the task.** `ast_edit` has no "add a module constant /
   add a function"; three of the five problems need exactly that. The model never falls back to
   `apply_patch`, and when it does patch (S2 arm B) it rewrites destructively — the very failure
   `bounded_edit_required` exists to prevent, reached through a different door.
3. **Two 600 s timeouts** (`S4 cand2`, `S4 cand2b`) confirm the wall-clock cap is being hit on
   CPU-resident inference, not on hard reasoning.

None of this makes a case "solved": arm B is 0/9 on the gates. It changes *what should be fixed
next*, not the verdict.

## 7. What this means for the loop (the useful part)

The plan's decision is about building an author/evaluator. This spike says the honest build order
is inverted: **there is nothing yet for an evaluator to grade.** Concretely, in this order:

1. **Give the loop a scoped surface by default.** `allowed_tools` per task, and a workspace root
   or prompt tree that is the task's scope, not the repo root. This alone is the difference
   between 0/15 and 2/15 attempted patches.
2. **Add the missing edit primitives**: "add module-level constant", "add function" — or make
   `apply_patch` the advertised path for adding symbols, with the same whole-file guard applied to
   a patch that deletes more than it adds.
3. **Fix the acceptance contract**: a task's acceptance command must fail before the work and pass
   after (measured here: S1's never fails; S5's dry run "succeeded" with zero edits).
4. **Then re-run M0.5 unchanged** — same five cases, same gates, same model. The gates in
   `state/evidence/spike/harness/` are ready and self-contained; `baseline.py`, `run_case.py` and
   `build_matrix.py` reproduce this run end to end.
5. **Only then** decide best-of-N vs hybrid. A 3/5 result on a fixed lane would justify local
   best-of-N; today's 0/5 justifies none of it.

Also worth fixing regardless of the verdict: the local lane is **CPU-resident** while a 16 GB GPU
is idle. Every number here was paid for at ~25 s/turn.

## 8. Honest limitations

* **One model, one layer.** `qwen3:8b`, CPU, 12 steps. A 27 B lane or a GPU-backed 8 B would have
  had ~5–10× more turns in the same wall clock. This is a measurement of the lane as it runs on
  this box today, not a ceiling for local models.
* **S1 was not measured**, only shown to be unmeasurable with its target check; a deterministic
  interleaving test would be needed and was not written (writing it would have been a sixth
  case, not one of the five).
* **Full-suite regression was not run** (explicitly out of scope for this unit). The targeted test
  file is green in every candidate that patched, but that is not the suite.
* **S3's gate reads the stylesheets, not the rendered page.** It resolves the cascade for the
  classes `Documents.jsx` renders and composites translucent backgrounds; it does not run a
  browser. The plan's `ux_scorecard` readability gate on `/ui/documents` would need a live
  server and a browser and was not run.
* **Two timeouts** are recorded as failed candidates, exactly as instructed; neither was retried.

## 9. Evidence index and reproduction

```
state/evidence/spike/
  baseline.json                 every gate against the unmodified tree
  matrix.json / matrix.md       the scored matrix (arm A) + arm B counts
  run_log.txt / armb_log.txt    the run transcripts, timestamped
  lane_probe.json               run_kernel coding path + Ollama inventory + env
  model_smoke.json              protocol validity per candidate model
  s1_baseline_note.md           S1's measured flake rate (1 in 100 runs)
  s1_baseline_head_60runs.json  60-run baseline
  s2_calibrate*.py              S2 bar reachability (100.0 reachable, 0.0 at baseline)
  harness/                      the five gates + case contracts (cases.py)
  <slug>/cand<N>/               per-candidate: task, agent result, diff, gate, test, verdict
  <slug>/cand<N>b/              arm B, same shape
  run_case.py run_all.py build_matrix.py baseline.py run_case_scoped.py
```

Reproduce: `python state/evidence/spike/baseline.py`, then
`python state/evidence/spike/run_case.py --case S5 --candidate 1`, then
`python state/evidence/spike/build_matrix.py`. The worktree is
`%TEMP%\ns-spike-wt` (`git worktree add --detach ... HEAD`); remove it with
`git worktree remove --force`.
