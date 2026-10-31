# Continuous loop supervisor

`scripts/continuous_loop.py` is the operator that turns an authorized task into
local work. It selects one task, takes a rollback baseline, dispatches Ty's
bounded coding pipeline (`scripts/ty_task_runner.py`) or runs a prebuilt task,
runs the real acceptance checks, restores task-owned changes on failure, commits
only the task's paths, records evidence, and advances.

It is not a model and it never grants itself permission.

## Run

```powershell
python scripts/continuous_loop.py --status
python scripts/continuous_loop.py --dry-run --task demo-hitl-counts
python scripts/continuous_loop.py --task demo-hitl-counts --max-tasks 1
python scripts/continuous_loop.py --max-cycles 0 --max-tasks 3 --deadline-minutes 90
python scripts/continuous_loop.py --resume <task-id>
```

`--max-cycles 0` still stops at `--max-tasks` (default 3 Ty tasks) and the
90-minute campaign deadline. A cycle is successful only when every check exits 0.
A failure stops the loop, never retries, never commits, and appends scrubbed
evidence to `reports/evaluation_ledger.jsonl`.

## Task contract

`config/continuous_loop_tasks.json`:

```json
{
  "id": "demo-hitl-counts",
  "name": "Add HITL queue counts helper",
  "authorized": true,
  "risk": "low",
  "execution": "ty",
  "objective": "Create ...",
  "dependencies": ["cycle6-continuous-loop"],
  "write_paths": ["Northstar_backend/agent_kernel/hitl_counts.py"],
  "read_paths": [],
  "acceptance_commands": [["python", "-m", "pytest", "...", "-q"]],
  "checks": [{"name": "tests", "cmd": ["python", "-m", "pytest", "...", "-q"], "cwd": "."}],
  "commit_paths": ["Northstar_backend/agent_kernel/hitl_counts.py"],
  "timeout_seconds": 600,
  "max_repairs": 0,
  "max_steps": 6,
  "required_artifact": "Northstar_backend/agent_kernel/hitl_counts.py",
  "provider": "ollama",
  "model": "bojo"
}
```

- `authorized` must be exactly `true`; `risk` must be `low` or `medium`.
- `execution: ty` needs an objective, `write_paths` and at least one acceptance
  command/check. `execution: prebuilt` runs checks only.
- Dependencies must be `completed`; a `blocked` string is shown verbatim and the
  task is not eligible.
- `write_paths` are the only paths Ty may write (the Workspace allowlist). The
  read allowlist is `read_paths` or the write paths.
- `commit_paths` are relative and validated against an allowlist
  (`scripts/`, `config/`, `docs/`, `reports/`, `tools/`, `Northstar_backend/`,
  `northstar-os-ui/src/`, `northstar-os-ui/scripts/`, `state/fragments/`).
  `.env`, databases, `exports/`, `screenshots/`, `node_modules/`, absolute paths
  and `..` are refused.
- Commands are argv lists, never shell strings. Only `python`, `pytest`, `npm`,
  `npx` and `node` are allowed; Amazon, Chrome Connect, paid providers and
  marketplace URLs are refused before execution.
- `timeout_seconds` <= 900; `max_repairs` <= 1; `max_steps` is the Ty loop bound.

## Lifecycle

`state/continuous_loop_state.json` records `running`, `verifying`, `completed`,
`failed`, `blocked`, `interrupted` per task. The registry is never rewritten.
`--status` shows separate eligible / blocked / failed / interrupted / running /
completed buckets. An empty eligible queue with blocked work is reported as
blocked, not complete.

- **Lock:** `state/continuous_loop.lock` is exclusive; a live owner refuses a
  second supervisor. A dead owner's stale lock is reclaimed.
- **Heartbeat:** `state/continuous_loop_heartbeat.json` is updated while Ty runs;
  a running record whose process is dead or heartbeat is stale is marked
  `interrupted` on the next start. It is not replayed.
- **Recovery:** `--resume <id>` restores the recorded baseline (byte backups for
  task-owned paths), verifies it, and returns the task to pending. Decisions are
  explicit; there is no automatic retry.
- **STOP:** checked before dispatch and once per second while Ty runs; the child
  process tree is terminated.
- **Timeout:** the Ty child is killed with its process tree; the task is failed
  and restored.

## Baseline, acceptance and rollback

Before a Ty task:

1. `git status -- <write_paths>` must be clean; dirty targets are refused so
   user work is never overwritten.
2. `snapshot.snapshot` captures a diff-scoped baseline; every existing target is
   also byte-copied to `state/runs/<run-id>/baseline/`.
3. Ty writes inside the Workspace allowlist only.

After Ty:

- the changed-path set is recomputed from the snapshot;
- any change outside `write_paths` is out of scope: it is restored from the
  snapshot if tracked, removed if newly created, and never deleted if it was
  pre-existing untracked (the run fails with that exact reason);
- every `checks[].cmd` runs; a non-zero exit fails the task;
- `commit_paths` must contain every changed path;
- `git add` stages only those paths, `git diff --cached --check` runs, and
  `git commit --only -m ... -- <paths>` commits exactly them. Pre-existing
  staged work stays staged and out of the commit.
- the commit's file list is verified against the approved paths.

On failure, task-owned files are restored from byte backups (or removed if
newly created), the index is reset for those paths, and the working-tree status
is compared with the baseline. A restoration failure is reported and the
campaign stops.

## Ledger

Each line in `reports/evaluation_ledger.jsonl` records the run id, task,
status, checks, commit, changed paths, restoration and a scrubbed error. Output
per check is capped at 1,200 chars.

## Current registry

| task | status |
|---|---|
| `cycle6-continuous-loop` | completed |
| `demo-hitl-counts` | completed (Ty created `agent_kernel/hitl_counts.py`; commit `96be935d`) |
| `post-demo-test` | completed (prebuilt regression task) |
| `cycle7-token-sse` | blocked - token-level streaming needs a request-scoped model stream and a UI consumer action; broader than this bridge |

The loop stops with `pending: []` when only blocked work remains. It does not
invent tasks.

## Limits

- The supervisor executes a task contract; it does not invent a scope or grant a
  task authorization.
- `00_STATE.json` is read-only to the loop (operator-apply only).
- Matrix/AgentTeams is not installed; HITL is the local queue.
- No Amazon request, no paid provider call, no credential read.
