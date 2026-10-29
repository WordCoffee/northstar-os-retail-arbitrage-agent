# Task execution — the one contract

There is exactly one way to execute a work order. Everything else that once
appeared in design notes — `?engine=`, `202 Accepted`, SSE/websocket progress,
per-task worktrees, a telemetry daemon choosing the lane — is **not built here**
and is not referenced by any route.

## The route

```
POST /api/admin/tys/tasks/{task_id}/run
     ?max_steps=<1..40>          (optional)
     Authorization: admin session
→ 200 OK
{ "task":   { ...the work order, its status, steps, cursor, checkpoint... },
  "kernel": { ...kernel evidence, when the order ran through the kernel... } }
```

* **Synchronous.** The run happens inside the request and the response arrives
  when the bounded work is finished. There is no job handle to poll *instead of*
  a result; `GET /tasks/{id}` exists for reading the event log afterwards, not
  for waiting on a run.
* **Admin-gated.** `require_tys_admin` rejects anything that is not an operator
  or platform administrator (`403`), before the task is even loaded.
* **No engine parameter.** The assistant chooses the lane from the work order
  itself: a `scope.workspace` selects the bounded coding-tool loop, otherwise the
  read-only step lane runs. The caller does not name a model.
* **Bounded.** `max_steps` is capped at 40; the work order's own
  `limits.max_wall_s` and `limits.max_steps` are honoured underneath it.

## The `kernel` member

When a work order runs through the agent kernel, the kernel's own result is
recorded as a `kernel_result` event and returned on the same response, so a
client can see the plan, per-node evidence and interventions without a second
call:

| member | meaning |
|---|---|
| `status` | `complete`, `needs_human`, `denied`, `exhausted`, `failed`, `blocked` |
| `plan` | nodes, edges, gates, version, state |
| `interventions` | every point where the kernel stopped and asked |
| `budget` | steps, wall clock, attempts consumed |
| `events` | count of journal entries for the session |

`kernel` is `null` when the order used the step lane, and the run itself never
fails because evidence could not be read.

## Related routes (not substitutes)

| Route | Purpose |
|---|---|
| `POST /tasks/{id}/resume` | continue from the stored checkpoint after an interruption |
| `POST /tasks/{id}/cancel` | stop the order |
| `POST /tasks/{id}/controller-result` | hand a Chrome Connect result back for an `awaiting_controller` step; Chrome Connect owns the browser, so the browser lane's result is posted in rather than executed here |
| `GET /tasks/{id}` | the order plus its append-only event log |

## Acceptance outranks the stop reason

A bounded loop can finish the work and still stop without reporting success —
step budget exhausted, or a model that forgot its final call. The kernel treats
the node's acceptance as the authority: if every verifier passes, the node is
`done` and the executor's self-report is superseded. If any verifier fails, the
node is blocked and the run returns `needs_human`. This is defect **p01**, fixed
in `agent_kernel/kernel.py::_verify_node` and `agent_kernel/coding_agent.py`.

## Writes are atomic and bounded

`agent_kernel/coding_tools.py::Workspace.write` writes to a sibling temp file,
flushes and `fsync`s it, then swaps it in with `os.replace`. A stall is reported
as a tool error after `write_timeout_s` (default 15 s) instead of hanging the
run, and a late-finishing worker discards its temp file rather than replacing the
target. Secrets (`.env`, `.env.*`), the operator-owned Chrome Connect policy and
benchmark fixtures are read-only to every lane, in every workspace. This is
defect **p03**.
