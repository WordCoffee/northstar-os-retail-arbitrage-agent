# Tys Assistant — admin automation agent: build + smoke verification

**Date:** 2026-10-28
**Branch:** `feature/chrome-connect-3.0`
**Commit:** `16f7fa77`
**Verdict:** **VERIFIED COMPLETE** — Tasks A, B and C passed through the actual
`/api/admin/tys` API, with the browser action performed by Chrome Connect and its
controller run id recorded as the agent's evidence.

---

## 1. Identity and routing

| | |
|---|---|
| Name | **Tys Assistant** |
| Id | `tys-assistant` |
| Kind | `admin_automation` |
| Surface | `admin` |
| User-facing | **false** |
| API namespace | `/api/admin/tys` (10 routes) |
| Chat protocol role | **unchanged**: the wire format still speaks `assistant` |

The persona split is explicit and tested:

* **Tys Assistant** — admin/operator automation agent. API + CLI only, no page in
  the customer shell. Deliberately not mounted in the SPA.
* **Customer chat** — untouched. `/api/chat` is a different router; Tys never
  writes to it and a test asserts the namespace is not `/api/chat`.
* **Coding worker** — internal model role (the 27B llama.cpp worker).
* **Creative worker** — internal generation role (existing ComfyUI services).

`CHAT_PROTOCOL_ROLE_UNCHANGED = "assistant"` is a constant in the module and a
test asserts `identity()["chat_protocol_role"] == "assistant"`, so a future edit
cannot "helpfully" rename the protocol role to `tys` and break every client.

### Authorization

`require_tys_admin`:

* no session → **401** `tys_auth_required`
* platform admin → allowed in any environment
* `ENVIRONMENT=production` + any tenant role → **403** `tys_platform_admin_only`
  (this agent drives the operator's own machine services; a subscriber must never
  reach it)
* development + operator-and-above → allowed (the operator runs locally through
  the dev identity shim)

### CLI

`python -m tys_assistant {state|submit|run|resume|list|show|drain}` — the
operator's own handle on the queue, sharing the same store as the API.

---

## 2. Model placement and resource behaviour

| Component | Placement | Evidence |
|---|---|---|
| Orchestrator (**Bojo**) | **CPU only** | `ollama ps` → `bojo:latest 2.4 GB PROCESSOR=100% CPU CONTEXT=8192` |
| Coding worker (27B IQ3_XXS) | **GPU only, on demand** | `-ngl 99` launcher; `:8080` closed between tasks |
| GPU | **592 MiB / 16303** — the no-model baseline | `nvidia-smi` |
| ComfyUI | undisturbed | `:8188` reachable, `vram_free 14.64 GB` |
| Chrome Connect controllers | **exactly one** | only `mcp_profile_Profile 6.lock` has a live pid (22868); 1 chromecontrol node process |

Bojo responded to a live turn during the run: `READY` in **4.0 s**, on CPU. The
two `llama-server.exe` processes visible on the box both resolve to
`…\Programs\Ollama\lib\ollama\llama-server.exe` — Ollama's own runners, not the
27B worker (which lives in `…\.config\northstar-llm\bin`).

Serialization: the coding and creative lanes take the **same cross-process GPU
lock** the render lanes already use (`studio_generation.gpu_lock()`), so a coding
run, a render and a creative job can never overlap on the single 16 GB card. The
adapter refuses with `gpu_busy` (blocked, retriable) rather than queueing.

After the coding step the worker is stopped by the adapter itself and Ollama is
drained — `:8080` closed, GPU back to 592 MiB, verified after Task B.

---

## 3. Orchestrator: model, settings, measured behaviour

`OllamaOrchestrator` → `bojo:latest`, `think: false`, `format: "json"`,
`temperature: 0`, `num_predict: 500`.

**The measurement that forced `think=false`** (direct probe, 2026-10-28):

```
think=true   19.8 s   content_len=0     thinking_len=2154   done_reason=length
think=false   1.5 s   content_len=92    thinking_len=0      done_reason=stop
```

With thinking on, a 1.9B model spent the entire budget reasoning and returned
**empty content** under `format=json` — every plan was unusable. The planner
therefore disables thinking **for orchestration only**, and the module never
claims thinking was used: evidence records `think: false` verbatim.

Planning is bounded and fail-closed:

1. attempt 1 — the plain contract prompt;
2. attempt 2 — **one corrective retry** that echoes the rejected reply and
   restates the lane/objective requirements;
3. if still invalid → task `blocked`, `stop_reason=orchestrator_plan_invalid`,
   with **both attempts, their metadata and the raw reply** preserved in the
   `plan_requested` event.

Validation rejects: lanes outside `scope.lanes`, missing objectives, plans longer
than the cap, and any objective touching an owner gate (Amazon / spend).

**Task A result** (orchestrator planning, no explicit steps):

```
attempts: 1 attempt, ok=True, corrective=False
think=false  format=json  eval_count=112  done_reason=stop  latency=4832 ms
plan: [inspect] locate the routing configuration
      [inspect] review the current lane assignments
      [coding]  identify missing/incorrect lanes
status: done   3/3 steps   wall 25.2 s
```

---

## 4. Lane inventory

`GET /api/admin/tys/state`:

| lane | executor | availability at start |
|---|---|---|
| `inspect` | this process, bounded scope-confined reads | available |
| `coding` | 27B llama.cpp worker | "worker not started (on demand)" |
| `browser` | Chrome Connect controller | "controller CLI reachable; policy enforced by the controller" |
| `creative` | studio/ComfyUI services | `media_live=True comfyui=True` |
| orchestrator | Bojo (CPU) | available |

---

## 5. Task B — full delegation (real, through the API)

Work order: objective, scope `{lanes: [inspect, coding, browser], paths:
[Northstar_backend/tys_assistant.py]}`, evidence requirements, limits
`{max_steps 8, max_iterations 3, max_wall_s 900}`, three explicit steps.

**Step 1 — inspect** (2 ms): `inspected 1/1 file(s)`.

**Step 2 — coding worker** (31.0 s): the adapter started the worker, answered,
then stopped it.

```
disable_thinking = True        finish_reason_initial = stop
finish_reason_retry = None     recovered_from = None
prompt_chars = 76131           answer_chars = 152
usage.completion_tokens = 55
answer: "Lanes: inspect, coding, browser, creative (line 67).
         Orchestrator model: bojo:latest (line 439).
         Source: Northstar_backend/tys_assistant.py."
```

**Step 3 — browser**: the lane detected that a live controller already owns
Profile 6 and produced an **explicit assignment** rather than spawning a second
controller:

```json
{"controller":"chromeconnect","profile":"Profile 6","owner_pid":22868,
 "url":"http://127.0.0.1:8101/ui/design-studio","max_steps":8,
 "task":"Open the authoritative NorthstarOS Design Studio and send one harmless
         prompt through its composer.\n\nSTEPS:\nprobe textarea[…]\nclick …\ntype …
         | Reply with exactly this and nothing else: TYS ASSISTANT OK\npress Enter\n
         screenshot tys-assignment-01-sent.png",
 "post_result_to":"POST /api/admin/tys/tasks/{task_id}/controller-result"}
```

Task status → **`awaiting_controller`**, cursor held at 2/3.

**The assignment was executed by the owning controller** (Chrome Connect, not a
standalone browser):

```
run_id       open_the_authoritative_northstaros_desig_mvrp2ox0
status       COMPLETE
stop_reason  probe_on_requested_route
steps        6
refusals     []
blockers     []
mode         {headed: true, readOnly: true}
journal      2026-10-28T05-49-25-945Z_open_the_authoritative_northstaros_desig_mvrp2ox0.jsonl
```

**Result posted back** → `task done, cursor 3/3`, and the browser step's evidence
now carries `delegation: "assigned"`, the controller run id, the journal path and
the mode. Event trail:

```
task_created · run_started · step_started · step_result · checkpoint
step_started · step_result · checkpoint
step_started · controller_assignment · checkpoint · run_finished
step_result · checkpoint · controller_result_accepted · run_started · completed · run_finished
```

Evidence file `Northstar_backend/data/tys/evidence/tys_645dbaaafded.jsonl` — 3
lines, one per step. Screenshot: `screenshots/tys_assistant_smoke_20261028/`.

---

## 6. Task C — checkpoint / resume

Three inspect steps, limits `max_steps 3`.

| call | result |
|---|---|
| `run?max_steps=1` | `paused`, `stop_reason=step_limit`, `cursor 1/3`, `next_action=resume`, checkpoint `next_step="read step two"`, `completed_lanes=[inspect]` |
| `resume?max_steps=1` | `paused`, cursor **2/3** |
| `resume` | **`done`**, cursor 3/3 |

No replay: `step_started` fired exactly **3** times, with indices 0, 1, 2 in
order. `run_started` × 3, `checkpoint` × 3, `resumed` × 2, `completed` × 1.

---

## 7. Defects found and fixed during the build

1. **Orchestrator returned empty plans.** Bojo is a thinking model; under
   `format=json` it produced only thinking and `done_reason=length`. Fixed with
   `think=false` for the planner (measured, documented), a corrective retry, and
   a precise `orchestrator_returned_thinking_only` error instead of a generic
   empty reply.
2. **The planner names objectives, not paths**, so its `inspect` steps failed
   with `params.files required`. `InspectAdapter._resolve_files` now resolves a
   step against the work order's `scope.paths` deterministically (basename match
   in the objective, else the declared file paths).
3. **Scope allowlist was too coarse.** `_roots` treated each declared path as a
   *root*, so declaring one file granted nothing useful and declaring a path
   could widen reach. It now derives the allowlist from the declared paths'
   **containing directories**, and `_read` verifies containment after resolving.
4. **Coding worker answered with empty content.** A large file in the prompt plus
   thinking consumed the whole budget (`finish_reason=length`). Fixed: thinking
   **off by default**, `max_tokens` 1200, and a bounded recovery that retries
   once with thinking disabled and a doubled budget capped at 4000 — triggered by
   `finish_reason == "length"` **or** a non-empty reasoning block, never when
   thinking was already off, never on transport failure. `recovered_from` is set
   only when content is actually recovered.
5. **A second controller was being spawned for the browser lane** and failed with
   an opaque error. The lane now reads the live `mcp_profile_*.lock`, and when
   another live controller owns the profile it records an explicit assignment
   instead. Stale locks (dead pid) are ignored.
6. **A hand-off was logged as a failed step.** The assignment attempt no longer
   writes a `step_result`; the single result for that step is written when the
   owning controller posts back, so the evidence file carries no phantom failure.

---

## 8. Tests

```
python -m pytest test_tys_assistant.py -q                          -> 55 passed
python -m pytest test_tys_assistant.py test_chat_core.py \
    test_rate_limit_dev_shim.py test_rate_limit_posture.py \
    test_bojo_cpu_placement.py test_chromeconnect_api.py \
    test_studio_render_guard.py -q                                 -> 104 passed
```

Coverage of the areas the requirements call out: default payload
(`enable_thinking False`, `max_tokens 1200`), native thinking preserved when
`disable_thinking=False`, recovery on `length`, recovery on reasoning-only,
no retry when thinking was already off, `recovered_from` absent on a failed
retry, no retry on transport failure, and the full evidence field set.

---

## 9. Exact remaining limitations

1. **No UI.** Tys Assistant is API + CLI only. That is deliberate (admin-only,
   never subscriber-facing) but it means an operator drives it with HTTP or the
   CLI, not a page.
2. **"Persistent" means durable, not always-on.** The queue, checkpoints and
   evidence survive restarts, and `POST /drain` advances it, but nothing
   self-schedules. No cron job or daemon was added — an unbounded loop is exactly
   what the operation rules forbid.
3. **The coding lane is advisory.** It reads the files the scope allows and
   answers; it cannot write code, run commands or edit the repo. A planner
   objective phrased "update the configuration" is answered as advice, never
   performed.
4. **The browser assignment needs the owning controller to post back.** If no
   controller session ever posts to `/controller-result`, the task waits at
   `awaiting_controller` indefinitely — by design, but it is a dependency on a
   second actor.
5. **The creative lane was wired and availability-checked, not exercised.** The
   smoke sequence did not request a render (ComfyUI was verified reachable at
   14.64 GB free VRAM and left undisturbed).
6. **Two Ollama runner processes** were observed on the box (both Ollama's own,
   GPU untouched at 592 MiB). Not investigated — no operational impact seen.
7. **`00_STATE.json` was not updated.** This repo's `opencode.json` denies `edit`
   on it, so the state file change needs a path that is allowed to write it.

## 10. Reproduce

```
powershell -File scripts/launch_alpha.ps1 -Restart -NoTunnel -NoAutothink -NoComfy

# identity + lanes
GET  http://127.0.0.1:8000/api/admin/tys/state

# Task A (orchestrator plans; no explicit steps)
POST /api/admin/tys/work-orders      {objective, scope:{lanes,paths}, limits}
POST /api/admin/tys/tasks/{id}/run

# Task B (explicit steps: inspect -> coding -> browser)
#   browser returns awaiting_controller with the recorded assignment
#   execute that exact task through Chrome Connect, then:
POST /api/admin/tys/tasks/{id}/controller-result   {status, run_id, journal, stats, data}

# Task C (checkpoint/resume)
POST /api/admin/tys/tasks/{id}/run?max_steps=1
POST /api/admin/tys/tasks/{id}/resume?max_steps=1
POST /api/admin/tys/tasks/{id}/resume
```

All requests carry the dev identity shim headers
(`X-User-Id: demo-t2`, `X-Org-Id: org-t2`, `X-Role: operator`) because the
operator's local session is the development shim; in production the same routes
require a platform admin.
