# V3 S5 — AutothinK premium surface (backend): plan graph · artifact browser · run panel

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BACKEND BUILT, tests green, local commit.

## What this closes

The AutothinK focus had session fork/rewind. It was missing the three planned
pieces: a plan/DAG visualiser, a run (sandbox) panel, and a build-artifact
browser. This unit builds the **backend** for all three, honestly and offline.

## Design rules honoured

- **Reconstructed, not invented.** There is no persisted agent "plan". The plan
  graph is rebuilt from the real evidence — message parts + the `chat_tool_calls`
  ledger — as a **linear** chain (`prompt → step 0 → … → answer`). The tool loop
  is bounded and sequential (`MAX_TOOL_STEPS`), so a chain is the true shape and
  no hidden edges are fabricated. The response says so in `caveats`.
- **A run is not a code sandbox.** The tool gateway deny-list
  (`shell/exec/eval/…`) stays the enforceable boundary. A "run" records something
  that actually ran — a chat turn or a tool execution — with status, timings and
  a live `ref` for cancel.
- **Honest cancel.** Cancelling only stops a genuinely live chat turn; a finished
  or non-turn run reports `cancelled:false`, never a pretended stop.
- **Honest artifacts.** A missing `ds_assets` row is reported `present:false`,
  never hidden or faked.
- **Tenant-scoped** on every read and write; session-scoped joins.

## Pieces

| Piece | Where | What |
|---|---|---|
| Step order | `chat_schema.py` + `data_layer._migrate_chat_columns` | Additive `chat_tool_calls.step_index` (+ idempotent ALTER for existing DBs). Written by the turn loop. |
| Plan builder | `chat_plan.py` `build_plan` | Pure reconstruction of nodes / edges / turns + caveats. |
| Plan endpoint | `GET /api/chat/sessions/{sid}/plan` | The session graph. |
| Artifacts | `ChatAttachmentsDB.list_by_session` + `GET /api/chat/sessions/{sid}/artifacts` | Session artifacts with `ds_assets` metadata. |
| Runs | `chat_runs` + `RunRegistryDB` + `turn_event_stream` wiring | Bounded run ledger; registered at turn start, finalised on every exit path. |
| Run endpoints | `GET /api/chat/runs`, `POST /api/chat/runs/{id}/cancel` | List + honest cancel. |

## Evidence

```
python -m py_compile chat_router.py chat_plan.py chat_schema.py data_layer.py            → PY OK
python -m pytest test_chat_plan.py                                                       → 16 passed
python -m pytest test_chat_plan test_chat_core test_chat_fork test_chat_tools \
                  test_shell_modes test_tool_gateway test_voicestudio_adapter           → 101 passed
chat_router.routes → /api/chat/sessions/{sid}/plan ·
                     /api/chat/sessions/{sid}/artifacts ·
                     /api/chat/runs · /api/chat/runs/{run_id}/cancel                     → all present
```

`test_chat_plan.py` (16) covers: the chain shape, `step_index` ordering (not
insert order), edge connectivity, elapsed/ok, tool-less turns; the plan endpoint
(+404); the artifact browser (metadata, missing-asset honesty, session scoping);
and the run registry (create/finish/list, tenant scoping, status filter, endpoint
list, honest cancel, 404).

## Honest limits / next

- **UI next:** the Simple-shell side panels (plan graph, artifact browser, run
  panel). The **visual treatment of the plan graph is the deep-visual part** —
  a model switch is worth it there (see the build note to the operator).
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
