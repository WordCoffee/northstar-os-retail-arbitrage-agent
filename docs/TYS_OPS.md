# Tys Assistant — operations layer (`tys_ops`)

The agent (`Northstar_backend/tys_assistant.py`) owns the queue, the lanes and
the evidence trail. This layer owns the infrastructure around it. Every module
is local, dependency-free and testable on its own; nothing here opens a network
socket, spends money, or contacts Amazon.

```
Northstar_backend/tys_ops/
  storage.py     local-master ledger, tiers, quotas, pruning, retention, purge
  bridge.py      signed tokens, offline queue, sync envelopes, gateway descriptor
  validators.py  structural + semantic checks, hunk arithmetic, workspace acceptance
  memory.py      context index, compression, vector retrieval, epistemic facts
  budgets.py     token/VRAM throttling, hyperparameter tuner, feedback router
  selfheal.py    diagnostics, safe pid checks, atomic write + rollback
  ui.py          adaptive component tree (tys.ui.v1)
  routing.py     intent interception: visual -> graphics, code -> coding
  graphics.py    FLUX 3 lane, direct endpoint, engine suspension, no ComfyUI
  stress.py      the multi-profile stress harness
```

## Storage policy

| Tier | Images | Video | Behaviour |
|---|---|---|---|
| `free` | 1 GB | none | video returns `not_stored`, `retention_seconds=0`, a download prompt |
| `paid_10gb` | 10 GB shared | 30 days (configurable) | video stored with `expires_at`; swept on expiry |

* Pruning removes the **oldest unprotected** media only. Downloaded or
  paid-retained media is never evicted to make room.
* If pruning cannot free enough, the write is refused with `over_quota` and the
  exact byte deficit. Nothing is written past the cap.
* An image must fit `min(image_quota, total_quota - retained_video)` — the total
  cap is not bypassed by checking a per-kind cap alone.
* Session end purges media that was never downloaded and returns the prompts
  the client owed the seller.

## Cloud bridge

* Tokens: HMAC-SHA256, scoped, TTL-bounded, revocable, 60 s clock skew.
* Offline queue: one operation per `idempotency_key`, bounded exponential
  backoff (2/4/8/16/32 s), and dead letters after `max_attempts`. A transport
  failure never loses an operation.
* Sync envelopes are per-profile monotonic; a replayed mobile request is
  acknowledged and **not** re-applied.
* `gateway_descriptor()` refuses plaintext HTTP on a non-loopback host. Dynamic
  DNS is described (record + TTL), not registered by this process.

## Validation

`workspace_acceptance` decides a step from the workspace — `artifact_exists`
plus real command exit codes — and records `self_report_outranked` when the
executor claimed success and the workspace disagreed. `check_patch` prefers
`agent_kernel.content.validate_patch` so the CLI, the work order and the
benchmark share one definition of a usable diff.

## Routing: visual work goes to FLUX 3

`tys_ops.routing` intercepts before any lane sees the work order:

| request | lane | executor |
|---|---|---|
| images, graphics, UI styling, rendering | `graphics` | FLUX 3 Image Klein, direct |
| code, tests, refactors, repository edits | `coding` | Qwen3.8-27B llama.cpp worker |
| video, animation, motion | `creative` | existing studio/ComfyUI services |

* The rewrite applies to explicit steps **and** to planner output, so the
  orchestrator cannot route visual work to the coding model.
* `scope.lanes` gains `graphics` when a visual step is intercepted; the step is
  never an escalation outside its own order.
* Every interception is recorded as a `routing_intercepted` event with `from`,
  `to`, matched signals and a sentence of reason.
* Defence in depth: the coding lane refuses a visual step
  (`visual_requires_graphics_lane`) and the creative lane refuses image work,
  so a hand-written order cannot bypass the policy either.
* The graphics lane checks FLUX 3 availability **before** suspending anything.
  When it is ready it suspends the MoE coding worker and unloads Ollama, takes
  the shared GPU lock, renders, and releases. It never starts ComfyUI.
* Coaching a missing engine is explicit, not a fallback: no FLUX 3 endpoint or
  weights means a blocked step (`flux3_unavailable`,
  `flux3_weights_not_installed`), not a silent render on another model.

Classifier precedence is graded: strong visual terms beat code words, strong
code terms beat context words like "render lane", and video wins over both.

## State endpoint under load

`GET /api/admin/tys/state` re-probes every lane, including a Chrome Connect
check that costs ~1.5 s. `TysAssistant.cached_state(ttl=3 s)` serves a snapshot
so a burst of mobile clients cannot each spawn a probe; `?fresh=1` bypasses the
cache for the operator. New routes: `GET /api/admin/tys/ui` (component tree)
and `GET /api/admin/tys/storage` (ledger summary).

## Running

```powershell
cd Northstar_backend
python -m pytest test_tys_ops.py test_tys_assistant.py -q
python -m tys_ops.stress --profiles 100 --tasks-per-profile 2
python -m tys_ops.stress --minutes 20      # bounded sustained run
```

The report lands at `reports/master_execution_stress_test_report.json`.

## What the harness does not do

* It does not start the 27B coding worker or the Bojo planner; orders carry
  explicit steps so no model is called.
* Storage volumes are accounted in bytes in a real ledger; only the purge test
  materialises a file. Nothing gigabyte-sized is written.
* The 100-profile load drives the real queue on a throwaway SQLite file; the
  live gateway burst is a separate, optional loopback probe.
* Adaptive UI is a validated tree spec; the SPA renders it.
