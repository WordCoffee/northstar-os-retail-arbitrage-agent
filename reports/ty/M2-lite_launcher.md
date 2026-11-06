# M2-lite — the launcher (build log)

`tools/tys_launcher.py` (11 tests). This is the answer to "did it stop?" — the loop is now a
process, not a turn.

## What it does

```
next (reserve) → build task contract → run worker → validate evidence → complete → rotate?
```

- **Runnable means checkable.** An item is dispatched only when it declares `write_paths`
  *and* `acceptance_commands`. Anything else is marked `needs_author` and skipped. The
  launcher never invents a pass criterion.
- **Evidence is mandatory.** The runner refuses a shipped cycle without it, so the launcher
  persists `state/evidence/cycle_NNN_<item>.json` (task + worker output + exit + seconds).
- **Stop reasons are recorded**, never inferred: `STOP`, `token_cap`, `queue_empty`,
  `max_cycles`, `max_hours`, `worker_failure_streak` (3), `model_lane_down`.
- **A dead model lane costs zero cycles.** The preflight health-checks
  `127.0.0.1:8080` (`--start-model` can bring the lane up) and stops with
  `model_lane_down` instead of burning an attempt per refused connection.
- **Heartbeat + journal**: `state/tys_runner/heartbeat.json` and `launcher.jsonl` show
  state, cycles, tokens (estimated, chars/4), seconds, exit codes.

## First real dispatch (evidence of the whole chain)

Item `S1-cancel-race` (the load-sensitive cooperative-cancel bug) with acceptance
`pytest foundation/tests/test_jobs_durable_lifecycle.py -k cancel`:

```
ok: false · summary: "model call failed" · steps: 1
error: worker unreachable at http://127.0.0.1:8080/v1/chat/completions (WinError 10061)
```

The launcher did exactly what it should: dispatched, received a precise failure, **reverted**
the item to `pending`, **deferred** it, wrote `worker_failed` to the journal, and recorded
the run in the heartbeat. No silent retry, no half-finished state, no damage.

Then the preflight was added, and the same command now stops before dispatching:

```
{"stopped": true, "reason": "model_lane_down", "base_url": "http://127.0.0.1:8080"}
```

## What is still missing for truly unattended work

1. **The model lane is down.** `scripts/start-northstar-llm.ps1` (27B, ~13 GB VRAM) is the
   default endpoint. It collides with ComfyUI on this 16 GB box, so the lane needs the
   brain/render handoff to start and stop it — that is M4 scheduling work, not a launcher bug.
2. **Most queue items have no `acceptance_commands`.** That is M1's job (the author lane):
   turn a gap into a task that names its own check. Today the launcher honestly skips them.
3. **Boot persistence.** A Windows Scheduled Task running
   `python tools/tys_launcher.py --max-hours 8 --start-model` is the last mile; it is a
   one-line `schtasks` call and should be created only once (1) and (2) are green.
