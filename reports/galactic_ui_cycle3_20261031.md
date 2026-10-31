# Cycle 3 — Unified event bus SSE stream

- date: 2026-10-31
- commit: `4dd9f1d0`
- scope: finish the Galactic deck's event transport with a local SSE stream and
  keep the poll as a fallback.

## What shipped

### Backend

`GET /api/v1/galactic/events` is a Server-Sent Events stream. It reuses the
read-only `galactic_state` telemetry and emits:

```
id: sse_1
event: snapshot
data: {"telemetry":"live","nodes":[...],"kv":[...],...}
```

one frame every 8 s. It stops when the client disconnects
(`request.is_disconnected()`), reports a failed telemetry read as an `offline`
payload instead of killing the stream, and sets `Cache-Control: no-cache` and
`X-Accel-Buffering: no`. Inserted into `main.py` with
`agent_kernel.ast_edit.add_after`; no text-diff rewrite.

### Frontend

`CommandDeck` now opens `new EventSource('/api/v1/galactic/events')`:

- `snapshot` frames replace the snapshot and publish `telemetry.snapshot`
  (`transport: "sse"`) into the unified bus;
- `onopen` marks the stream `sse`; `onerror` marks it `poll`;
- the existing 8 s `fetch` poll runs **only** when the stream is not open
  (`stream !== 'open'`), and stops when SSE opens; EventSource's own reconnect
  brings the stream back;
- a bad frame publishes `telemetry.stream.bad_frame` rather than throwing.

The telemetry badge shows `live · sse` or `live · poll` so the operator can see
which transport is active.

## Verification

```
npm run test:ui          # 73 passed / 0 failed
npm run test:contrast    # 11/11 WCAG AA
npm run verify:galactic  # 31/31 static checks (SSE endpoint, EventSource, fallback)
npm run build            # ✓ 0 errors
python -m pytest Northstar_backend/test_galactic_state.py -q  # 2 passed
```

The pytest suite now covers the first SSE frame: `event: snapshot`, JSON body
with `nodes` and `kv`, and a live/offline telemetry marker.

## Honest limits

- The stream carries **snapshot-level** telemetry every 8 s, not token-level
  agent reasoning events. The bus shape is ready for token events later.
- The SSE endpoint probes `/health` and `/slots` on each snapshot; it is
  read-only and local, but it is not a zero-cost stream.
- No browser screenshot; component syntax, build, pure logic and static
  contracts are verified.
- No Amazon request, no paid provider call, no credential read.

## Next cycle (selected immediately)

**Cycle 4 — HITL approval panel on the local queue.** The local `hitl.py` queue
already has request/approve/deny/pending; expose read-only pending plus
approve/deny API routes (repo-root scoped, no path input) and mount a
`HitlQueue` panel in the deck. Matrix/AgentTeams remains blocked.
