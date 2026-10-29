# Tys Assistant — routing change: visual work to FLUX 3

**Date:** 2026-10-29
**Scope:** orchestration only — who gets a request, not a new model
**Tests:** 177 passed (`test_tys_routing.py`, `test_tys_assistant.py`,
`test_tys_ops.py`, `test_chat_core.py`, `test_rate_limit_posture.py`,
`test_chromeconnect_api.py`, `test_tys_kernel_integration.py`)

---

## 1. The rule now enforced

| request | lane | executor |
|---|---|---|
| visual graphics, UI styling, image generation, rendering | `graphics` | **FLUX 3 Image Klein, direct** |
| code, tests, refactors, repository edits | `coding` | Qwen3.8-27B llama.cpp worker |
| video, animation, motion | `creative` | existing studio/ComfyUI services |

* Visual work is intercepted **twice**: when a work order is submitted, and
  again when the planner returns steps. The Bojo planner cannot route visual
  work to the coding model.
* A visual step's lane is rewritten to `graphics` and `graphics` is added to
  the order's own `scope.lanes` — the rewrite is never an escalation outside
  scope.
* Every rewrite writes a `routing_intercepted` event carrying `from`, `to`,
  matched signals and a one-line reason.
* Defence in depth: the coding lane refuses a visual step
  (`visual_requires_graphics_lane`) and the creative lane refuses image work,
  so a hand-written order cannot bypass the policy either.
* Video stays on `creative`: FLUX 3 Image Klein is an image model, and sending
  motion work to it would be a quiet wrong answer, not a fix.

### Precedence

1. video beats everything (`"12s clip"` → creative);
2. strong visual beats code (`"build the logo and wire the endpoint"` → graphics);
3. strong code beats weak visual context (`"add a regression test for the render
   lane"` → coding — "render lane" is an engineering noun);
4. anything with no signal is left exactly where the caller put it.

## 2. FLUX 3 lane

* Talks to a **standalone FLUX 3 endpoint** (`FLUX3_SERVER_URL`, default
  `http://127.0.0.1:8190`), never to ComfyUI.
* Availability is checked **before** anything is stopped. If FLUX 3 is not
  ready the step is blocked with `flux3_unavailable` /
  `flux3_weights_not_installed` — there is no fallback to Comfy or to the
  coding model.
* When FLUX 3 *is* ready: suspend the competing engines (MoE coding worker on
  `:8080`, resident Ollama models on `:11434`), take the shared cross-process
  GPU lock, render, release. ComfyUI, Chrome and the backend are never touched.
* `status` reports weights and endpoint separately, so the operator can tell
  "not installed" from "not running".

## 3. Live verification (through the running API)

Work order submitted with `scope.lanes=["coding"]`, a coding step, and the
objective *"generate the pouch hero image for the listing"*:

```
task                tys_d1f05d8e3bc5
step lane           coding -> graphics
scope lanes         coding, graphics
routing             [scope: added graphics for "hero image",
                     step coding->graphics: signals ["hero image","render a"]]
events              task_created, routing_intercepted, run_started, step_started,
                    step_result, checkpoint, blocked, run_finished
status              blocked   stop_reason=step_blocked
blocker             graphics: flux3_weights_not_installed: set STUDIO_FLUX3_MODEL,
                    STUDIO_FLUX3_TEXT_ENCODER and STUDIO_FLUX3_VAE
```

Control case: *"refactor the importer module and add a regression test"* →
`lane=coding`, no routing record, no rewrite.

Before and after the visual run, `:8188` (ComfyUI, pid 23736) and `:8080`
(coding worker, pid 15744) were **unchanged** — a blocked render suspends
nothing, which is the point of checking availability first.

## 4. Blocker (one, honest)

**FLUX 3 weights are not installed on this machine.** `STUDIO_FLUX3_MODEL`,
`STUDIO_FLUX3_TEXT_ENCODER` and `STUDIO_FLUX3_VAE` are unset, and nothing
answers at `FLUX3_SERVER_URL`. Until the weights are installed or a standalone
FLUX 3 server is pointed at, visual steps block instead of rendering.

To enable, either:

1. set the three `STUDIO_FLUX3_*` variables to the official FLUX 3 Image Klein
   files **and** run a FLUX 3 server exposing `POST /generate` +
   `GET /health` on `:8190`; or
2. set `FLUX3_SERVER_URL` to whatever process already serves that contract.

No model download was started: installing weights is a large download and the
capsule's disk rule (free space below 10 GB pauses download work) plus the
model-licence record apply. Current free space: 39.6 GB.

## 5. What changed on disk

* `Northstar_backend/tys_ops/routing.py` — classifier, work-order rewrite,
  planner rewrite, policy summary.
* `Northstar_backend/tys_ops/graphics.py` — FLUX 3 client, availability,
  engine suspension, GPU lock, no ComfyUI.
* `tys_assistant.py` — `graphics` lane + `GraphicsAdapter`, interception in
  `submit()` and `run()`, guards in the coding/creative adapters,
  `routing_policy` in `state()`, graphics grant for the kernel path.
* `agent_kernel/{model,kernel,tys_adapter}.py` — `graphics` lane registered.
* `test_tys_routing.py` — 29 tests; `docs/TYS_OPS.md` routing section;
  `state/fragments/20261029_tys_routing.json` (validates, awaits operator
  `--apply`).

## 6. Limits

1. FLUX 3 produces images; UI styling is routed to it as a **visual artefact**
   request. Editing the actual CSS/component code is still a coding task and
   stays on the coding model — the classifier sends "style this component" to
   graphics, and a request that names code files/verbs stays on coding.
2. The interactive Claude/OpenCode UI is not intercepted: this policy governs
   Tys Assistant work orders and the agent kernel, which is where the
   assistant's orchestration lives.
3. The planner is told the allowed lanes from the order's scope; it now sees
   `graphics`, but Bojo was not re-benchmarked against the new lane.
4. No paid spend, no Amazon request, no ComfyUI launch.
