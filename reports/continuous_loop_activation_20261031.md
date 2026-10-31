# Continuous loop activation — 2026-10-31

- harness commit: `423bd9cb`
- first supervisor commit: `4109d158` (the loop committed its own docs)
- state: `state/continuous_loop_state.json`
- ledger: `reports/evaluation_ledger.jsonl`

## What was built

`scripts/continuous_loop.py` is a supervisor, not a model:

1. reads `config/continuous_loop_tasks.json` and
   `state/continuous_loop_state.json`;
2. selects the first unblocked pending task;
3. runs the task's argv-only checks (`cwd` relative to the repo);
4. commits **only** the task's validated `commit_paths`;
5. appends a JSONL evidence record;
6. marks the task complete and moves to the next one.

`--max-cycles 0` runs until no unblocked tasks remain. `--once`,
`--task <id>`, `--dry-run`, `--no-commit` and `--status` are available.

## Safety gates

| gate | behaviour |
|---|---|
| `STOP` | refuses to start |
| branch `main`/`release/*`/`hotfix/*` | refuses |
| free disk < 10 GB | refuses |
| free RAM < 3 GB (psutil) | refuses |
| forbidden command token (Amazon, Chrome Connect, OpenRouter, DataForSEO, Unwrangle, Bright Data, marketplace URLs, curl/wget) | refuses the check |
| commit path outside the allowlist | refuses the commit |
| `.env`, DB, `exports/`, `screenshots/`, `node_modules/` | refuses |
| failed check | stops; no commit, no retry |
| failed `git diff --cached --check` | no commit |
| secret-shaped text in output | redacted before the ledger |

It never runs `git add .`; the operator's dirty files and generated artefacts are
untouched. `00_STATE.json` is never written (operator-apply only).

## First supervised run

```
python scripts/continuous_loop.py --task cycle6-continuous-loop
```

Result:

```
[*] cycle cycle6-continuous-loop: Continuous loop supervisor + evaluation ledger
    ok (6 checks)
    committed 4109d15805eb
{
  "ok": true,
  "completed": 1,
  "pending": []
}
```

Checks: Python syntax; 7 continuous-loop self-tests; UI unit 73; UI contrast 11;
Galactic static 34; UI build 0 errors. The loop committed only
`docs/CONTINUOUS_LOOP.md` (the one path that had changed); the harness and
registry were already committed manually.

State after the run:

```json
{"completed": {"cycle6-continuous-loop": {
  "completed_at": "2026-10-31T20:36:38+00:00",
  "commit": "4109d15805eb"}}}
```

Ledger: one `ok` record with every command, exit code, duration and scrubbed
output (truncated to 1,200 chars per check).

## Current registry

| task | state |
|---|---|
| `cycle6-continuous-loop` | completed |
| `cycle7-token-sse` | **blocked** — token-level SSE is not implemented |

The loop stops cleanly with `pending: []` because the only remaining task is
explicitly blocked. It does not invent work. To continue, implement token-level
SSE, remove `"blocked": true` from `cycle7-token-sse`, and run
`python scripts/continuous_loop.py --max-cycles 0`. The loop will pick it up
automatically.

## Honest limits

- The supervisor does **not write code**; it executes declared checks and commits
  declared paths. Task implementation is a separate coding step.
- No automatic repair: a failed check stops the loop. The self-heal path is
  explicit and requires an isolation runtime for `apply=True`.
- No Matrix/AgentTeams; HITL is the local queue.
- No Amazon request, no paid provider call, no credential read.

## Commits

```
423bd9cb  continuous-loop supervisor + task registry + 7 tests
4109d158  docs committed by the supervisor itself
(this commit) activation report, state, ledger, output truncation
```
