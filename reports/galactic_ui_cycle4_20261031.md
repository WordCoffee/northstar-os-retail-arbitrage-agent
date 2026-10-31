# Cycle 4 — HITL approval panel on the local queue

- date: 2026-10-31
- commit: `31bd8a69`
- scope: operator intervention surface for the Galactic deck, local-only.

## What shipped

### Backend

| route | behaviour |
|---|---|
| `GET /api/v1/hitl/pending` | pending requests from `agent_kernel.hitl`, repo-root scoped |
| `POST /api/v1/hitl/{id}/approve` | final approval with operator + note |
| `POST /api/v1/hitl/{id}/deny` | final denial with operator + note |

The queue root is `Path(__file__).resolve().parent.parent`, never a path from
the request. Unknown or already-decided IDs return `409`. The routes were
inserted with `agent_kernel.ast_edit.add_after`, not a text diff.

### Frontend

`src/galactic/HitlQueue.jsx`:

- reads `/api/v1/hitl/pending` every 10 s;
- renders action, requested_by and created_at (no payload contents);
- Approve/Deny post to the decision routes and refresh;
- publishes `hitl.approve` / `hitl.deny` into the unified event bus;
- shows "Queue unavailable" on an HTTP/network failure and "No pending
  approvals" only when the queue actually answered empty.

Mounted in `CommandDeck` next to the KV heatmap. The grid is now:

```
topology  detail
heat      hitl
events    events
```

and collapses to one column at 1040 px.

## Verification

```
npm run test:ui          # 73 passed / 0 failed
npm run test:contrast    # 11/11 WCAG AA
npm run verify:galactic  # 34/34 static checks
npm run build            # ✓ 0 errors, 1.39 s
python -m pytest Northstar_backend/test_hitl_api.py \
  Northstar_backend/test_galactic_state.py -q   # 4 passed
```

`test_hitl_api` covers pending → approve, pending → deny, and the 409 unknown-ID
path. The queue is exercised against a `tmp_path`, so the test does not write
the repo's state.

## Honest limits

- This is the **local** approval queue, not a Matrix/AgentTeams room. Those
  packages are not installed; `hitl.publish` remains the bridge hook for later.
- The panel polls every 10 s; it does not yet receive a queue event over the SSE
  stream.
- Decisions are final; there is no undo (the queue's original contract).
- No browser screenshot; build, syntax, static contract and API tests are the
  verification.
- No Amazon request, no paid provider call, no credential read.

## Next cycle (selected immediately)

**Cycle 5 — Bojo keep-alive.** Add an explicit `keep_alive` to the local chat
stream so the 1.9B model is not reloaded between turns, with an env override and
a payload test. It is a latency win, not a model change, and stays local.
