# Tys Assistant: why the review gate was missed, and the two mechanisms that now catch it

**Date:** 2026-11-04 · **Asked:** "I thought Tys Assistant was smart. It should've caught all of this and fixed it already. Why hasn't it?"
**Answer in one line:** it was never given a contract that could tell it. Its tasks accept a
unit probe, its kernel accepts a self-report, and its plan was prose the loop cannot read. Two of
those three are now closed.

---

## 1. Why it did not catch it (evidence, not opinion)

| # | Mechanism | Where it is visible |
|---|---|---|
| 1 | **The task's whole acceptance was the unit probe.** `ty-mockup-legibility` is "done" when `state/probes/t11_mockup_legibility.py` exits 0. That probe imports `mockup_quality` and tests it alone; it never calls `product_picture` or the graphics lane, so "the module works" and "the product uses it" are indistinguishable to the loop. | `config/continuous_loop_tasks.json` L1181‑1186 (`acceptance_commands: [["python","state/probes/t11_mockup_legibility.py"]]`) |
| 2 | **The ship gate was prose, not a task.** It appears only as Phase 0 item 3 in the plan. The loop dispatches exclusively from `config/continuous_loop_tasks.json` (`TASKS_PATH`), and the backlog generator only converts **pytest failures** into proposals — a plan paragraph is invisible to both. | `reports/ty/creative_pipeline_plan_20261103.md` §3.3; `scripts/continuous_loop.py` L47, L928 |
| 3 | **The kernel accepts a self-report when the work order names no commands.** `_derive_acceptance` builds `artifact_exists` + `command` verifiers only from `params.acceptance`; with none it falls back to `Acceptance("the lane executor reports success", "executor_ok")`. A step can therefore "complete" by writing a document. | `Northstar_backend/agent_kernel/tys_adapter.py` L62‑112 |
| 4 | **There is no evaluator.** The loop verifies that the named command passed; it has no measure of whether the deliverable obeys the work order. That is the missing author/evaluator unit the autonomy report already names. | `reports/ty/autonomy_20261103.md` §"Why the backlog is not auto-dispatched" |

A fifth fact made it worse: the graphics lane — the surface Tys uses to present an image — had no
gate at all. `GraphicsAdapter.run_step` returned the FLUX 3 render as an artifact immediately.

## 2. What changed today (mechanism, not prose)

### 2a. An image cannot be presented until it has been reviewed

`Northstar_backend/ship_gate.py` — one review call, four truthful outcomes:

* **identity** — pHash distance + global SSIM against the reference product photo (blocking when a
  reference is supplied);
* **legibility** — the existing OCR/sharpness contract (`mockup_quality.assert_legible`), reused
  rather than duplicated (blocking when a wordmark, net weight or `require_text` is present);
* **preference / adherence** — injected scorers (HPSv2 / PickScore), recorded with their floor, and
  **never faked**: an unconfigured required scorer is `needs_review`, not `passed`;
* **unscored** — nothing blocking could be measured, so the render is a *candidate*, not a
  deliverable. `ok` is true only for `passed`.

The Tys graphics lane now calls it before returning: `tys_assistant.GraphicsAdapter._gated_result`.
A refused render fails the step; an unscored or review-held render is labelled a candidate.

### 2b. A new module nobody calls can no longer be "completed"

`scripts/continuous_loop.py` now requires, for a `ty` task whose write path is a module that does
not exist at HEAD:

* `wiring.imported_by` — the **existing** consumer that will call it (naming another new module is
  refused);
* and at acceptance time `verify_wiring()` reads that consumer and fails the task unless the module
  name actually appears there.

The exact historical task is now refused:

```
$ python -c "... validate_task(<ty-mockup-legibility as authored>)"
errors: ['new module Northstar_backend/mockup_quality.py needs wiring.imported_by: name the
          existing consumer that calls it (a unit probe cannot prove use)']
with wiring: []
verify: {'ok': True, ... 'detail': 'product_picture.py references mockup_quality'}
```

## 3. Verification (real runs)

| Run | Result |
|---|---|
| `pytest test_ship_gate.py` | **12 passed** (four statuses, identity refuse/pass, injected scorer floor, lane refusal, candidate labelling) |
| `pytest test_continuous_loop.py test_ship_gate.py test_tys_routing.py` | **64 passed** |
| `pytest test_tys_assistant.py test_mockup_product_picture.py test_product_picture.py test_module_hygiene.py` | **91 passed** |
| `python state/probes/t11_mockup_legibility.py` / `t10` / `t12` | **OK** |
| `python state/probes/t21_image_ship_gate.py` (new) | **OK** |
| task-contract sweep over all 22 loop tasks | 22 checked, **0 newly blocked** (the 2 blocked are the pre-existing auth and self-modification refusals) |
| `python scripts/continuous_loop.py --status` | RUNNING: no · completed=20 failed=0 blocked=2 · RAM 8.9 GB, disk 54.9 GB |

## 4. What is still not fixed (named, not hidden)

1. **Scorers are downloadable but not callable.** PickScore + HPSv2 are staged
   (`ComfyUI/models/_incoming`, provenance rows 2026-11-03) but the service interpreter has no
   `torch` (`ModuleNotFoundError`). Until the runtime is installed, `require_preference` correctly
   yields `needs_review`; the gate does not pretend.
2. **The design-studio API still returns an unscored asset** unless `deliver: true`
   (`design_studio_api.py` L1917, L2045). The next unit runs the same gate before the asset is
   returned and labels it there too.
3. **No plan→task coverage check.** The new rule catches "module with no consumer"; it does not
   catch "plan item with no task". That needs a small compiler/audit that maps work-order items to
   task ids and fails readiness when an open item has no owner.
4. **No best-of-N.** The gate can refuse one render; it cannot yet render three, score them and
   keep the winner.

## 5. Rollback

* `Northstar_backend/ship_gate.py`, `Northstar_backend/test_ship_gate.py`,
  `state/probes/t21_image_ship_gate.py` are new files — delete to revert.
* `tys_assistant.py` — revert `_ship_gate`, `_gated_result` and the two call sites.
* `scripts/continuous_loop.py` — revert `_SPEC_FIELDS`, `new_modules`, `wiring_errors`,
  `verify_wiring`, the `validate_task` call and the acceptance-time check.

Gates held: no Amazon request, no spend, no credential read, no policy or allowlist change, no
model download. All tests and probes are local.
