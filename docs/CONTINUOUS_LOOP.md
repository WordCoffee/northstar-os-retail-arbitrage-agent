# Continuous loop supervisor

`scripts/continuous_loop.py` is the supervisor that turns the improvement cycle
from a manual turn into a command. It is deliberately **not** a model: it reads a
task registry, runs the task's verification commands, commits only the paths the
task names, appends evidence to a ledger, and moves to the next task.

## Run

```powershell
# Show task state + the last eight cycles
python scripts/continuous_loop.py --status

# See the exact commands without writing or committing
python scripts/continuous_loop.py --dry-run --task cycle6-continuous-loop

# Run every pending task, stopping at the first failure
python scripts/continuous_loop.py --max-cycles 0

# One cycle only
python scripts/continuous_loop.py --once

# Verify without committing
python scripts/continuous_loop.py --no-commit --once
```

A cycle is successful only when every check returns 0. A failure stops the loop
immediately; it does not retry or commit. The failure record (commands, exit
codes, scrubbed output) is appended to `reports/evaluation_ledger.jsonl`, so the
next operator or task can see exactly what broke.

## Task registry

`config/continuous_loop_tasks.json`:

```json
{
  "tasks": [
    {
      "id": "cycle6-continuous-loop",
      "name": "Continuous loop supervisor + evaluation ledger",
      "commit_message": "chore(loop): activate continuous loop supervisor",
      "commit_paths": ["config/continuous_loop_tasks.json", "docs/CONTINUOUS_LOOP.md"],
      "checks": [
        {"name": "UI unit", "cmd": ["npm", "run", "test:ui"], "cwd": "northstar-os-ui"}
      ]
    }
  ]
}
```

- Tasks run in array order. Completed ids are stored in
  `state/continuous_loop_state.json`, so the registry is not rewritten.
- `blocked: true` skips a task until an operator removes the flag.
- `commit_paths` are relative and validated against an allowlist
  (`scripts/`, `config/`, `docs/`, `reports/`, `tools/`, `Northstar_backend/`,
  `northstar-os-ui/src/`, `northstar-os-ui/scripts/`, `state/fragments/`).
  `.env`, databases, `exports/`, `screenshots/`, `node_modules/`, absolute paths
  and `..` are refused.
- `checks[].cmd` is an argv list, never a shell string. Amazon, Chrome Connect,
  OpenRouter, DataForSEO, Unwrangle, Bright Data and marketplace URLs are
  refused before execution.
- `checks[].cwd` is relative to the repo root.

## Safety gates

| gate | behaviour |
|---|---|
| `STOP` file | loop refuses to start |
| branch `main`/`release/*`/`hotfix/*` | loop refuses; use a feature branch |
| free disk < 10 GB | loop refuses |
| free RAM < 3 GB (when psutil is available) | loop refuses |
| failed check | no commit; ledger records the failure |
| failed `git diff --cached --check` | no commit |
| no changes in `commit_paths` | cycle is still recorded; no empty commit |
| secret-shaped text in output | redacted before it reaches the ledger |

`git add .` is never used. A task can only stage the paths it names, so the
operator's dirty files (and large generated artefacts) are untouched.

## Ledger

Each line in `reports/evaluation_ledger.jsonl`:

```json
{"cycle":"cycle6-...-20261031T...","task":"cycle6-continuous-loop",
 "started_at":"...","finished_at":"...","status":"ok",
 "checks":[{"name":"UI unit","ok":true,"exit":0,"duration_s":1.2,"argv":["..."]}],
 "commit":{"ok":true,"committed":true,"sha":"..."}}
```

The ledger is append-only and local. It is not committed automatically; a task
may include it in `commit_paths` when a snapshot is wanted.

## Relationship to `00_STATE.json`

The loop **reads** `00_STATE.json` context but never writes it; that file stays
operator-apply only. Cycle evidence lives in the ledger and in
`state/fragments/`. The task registry and state file are the loop's own state.

## Current registry

| task | status |
|---|---|
| `cycle6-continuous-loop` | pending (this harness) |
| `cycle7-token-sse` | blocked — token-level SSE not implemented yet |

Cycle 7 is deliberately blocked: it is a real next task, not a fake green one.
An operator removes `blocked` after the implementation exists; the loop then
picks it up automatically.

## Limits

- The supervisor does not write code. A task's implementation is either already
  in the tree (this cycle) or a separate coding step; the loop's job is to run
  the declared checks and commit the declared paths.
- There is no automatic repair loop. A failed check stops the loop; self-heal
  is a separate, explicitly invoked path (`agent_kernel.self_heal`) and requires
  an isolation runtime for `apply=True`.
- Matrix/AgentTeams HITL remains uninstalled; the local `hitl.py` queue is the
  current approval surface.
