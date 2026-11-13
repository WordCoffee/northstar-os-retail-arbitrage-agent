# Decision: the director is canonical; Tys Assistant is the operator's tool; Vision is the director's eyes

Date: 2026-11-12. Owner: Tyrone. Scope: one page, binding until the owner changes it. This does
not add a feature to either loop — it says which one owns the queue, and where Vision plugs in.

## 1. The canonical loop is the Director

The Director is the only program that **owns the product queue and merges code**. That is not a
preference, it is what the artifacts already say:

| the director owns | evidence |
|---|---|
| the mandate and the launch deadline | `ty/MANDATE.md`, `reports/ty/master_standing_order.md` |
| the queue (single writer) | `reports/ty/director_queue.json`, `state/director/queue.sqlite` |
| gap ranking and re-plan | `tools/director_gaps.py` (`gap = impact × (bar − score)`) |
| scope manifests, worktrees, overlap refusal | `reports/ty/director_queue.json` `write_paths` |
| merge gates, rollback tags, verifier | `docs/OPERATING_CONSTITUTION.md`, `reports/ty/handoff.md` |
| staying alive without a human | `scripts/ty_director.py`, `NorthstarTyDirector` task |
| the only merges on this branch | `git log --oneline` — every `ty-dir-*` tag is the director's |

**Rule.** One writer for `director_queue.json`. One merger into `staging`. One launcher. Any second
process that claims the queue is a defect, not a helper — that is exactly what D-011 recorded, when
a launcher-spawned session and an owner session both held the queue for a block and only git
protected the work.

## 2. Tys Assistant is the operator's tool, not a second loop

Tys Assistant (`tys_assistant.py` + `tys_ops/`, 189 tests, `/api/admin/tys`) is the **admin-facing
automation agent**: an operator points it at a bounded task and it plans, delegates, checkpoints,
resumes and records evidence. Its gate is real — an unauthenticated call returns 403, and in
production it is platform-admin only.

It may not:

- write the director's queue, or merge anything;
- run a campaign that edits `staging` outside a director job;
- hold the queue lease.

It may:

- run **bounded campaigns on work orders** (`POST /work-orders` → `tasks` → `run`/`resume`/`cancel`);
- own storage/quota/memory/bridge plumbing (`tys_ops.storage`, `memory`, `bridge`, `budgets`);
- route visual work to FLUX 3 (`tys_ops.routing`), which the director then reviews like any builder.

**The seam:** the director creates a work order; Tys runs it; its result lands as **evidence**, and
the director decides whether it becomes a merge. Tys is the hands an operator can schedule; the
director is the head that knows what the product needs.

## 3. How Vision connects: eyes and hands for the canonical loop

Ty's Vision (`tools/vision/`, 24 modules, V1/V2/V4–V8 verified) is not a loop. It has no queue and
must never grow one. It is the director's **senses**:

- **Route truth.** `director_vision.probe()` drives the real routes and writes
  `state/director/vision.json` (`rendered/total`, which routes still open the generic shell). The
  director's gap ranking reads it, so "renders 3 of 29" becomes a queue job instead of a note.
- **Refusal by name.** With `state/vision/PAUSE` present or the desktop locked, the probe returns a
  named refusal and does nothing. The eyes are not allowed to act on their own judgement.
- **Evidence for seller dogfood** (V9): Vision drives the same task a seller would, and the
  director treats the result as evidence, never as a score.

**Wiring, concretely:** `tools/ty_director.py` reports the eyes' state in every heartbeat
(model-free), runs the probe at most hourly when unblocked, and `tools/director_gaps.replan()`
turns the probe's shell-route list into a bundle. That is the whole integration: one probe, one
state file, one consumer.

```
owner → director (mandate, queue, merges, verifier)
           ├── builders (scoped worktrees)         ← code
           ├── Vision  (eyes: route truth, dogfood) ← evidence
           └── work order → Tys Assistant (bounded campaign) ← operator-scheduled hands
```

## 4. What this decision forbids

- A second queue, a second launcher, or a second merger — regardless of which agent starts it.
- Vision deciding work, merging, or acting while `PAUSE` exists.
- Tys Assistant merging, or writing `reports/ty/director_queue.json`.
- Any new automation surface. The 24-hour soak at the end of this order is a *measurement* of this
  arrangement, not a new feature.
