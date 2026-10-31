# Continuous loop execution — Ty bridge + bounded campaign

- date: 2026-10-31
- starting HEAD verified: `21bae7da` on `feature/chrome-connect-3.0`; no staged
  content; the reported `423bd9cb`, `4109d158`, `cycle6-completed` were real.
- bridge commit: `58b79cb3`
- Ty-generated commit: `96be935d`
- campaign manifest: `state/campaign_20261031.json`

## 1. Capability table

| capability | status | evidence |
|---|---|---|
| Supervisor dispatches Ty and Ty edits a real file | **VERIFIED** | `demo-hitl-counts`; Ty wrote `agent_kernel/hitl_counts.py`; commit `96be935d` |
| Ty writes are restricted to task `write_paths` | **VERIFIED** | probe attempt to write `fix.patch` rejected; `Workspace` scope test; 22 coding tests |
| Acceptance failure restores task-owned files and leaves failure evidence | **VERIFIED** | disposable worktree demo; `reports/continuous_loop_failure_demo_20261031.json` |
| Byte-level rollback for create/modify/delete/bad edit | **VERIFIED** | `test_continuous_loop_rollback.py` 2 passed; worktree removal |
| Pre-existing staged work is preserved | **VERIFIED** | `test_commit_task_preserves_pre_existing_staged_work` |
| Single-supervisor lock, heartbeat, interrupted recovery | **VERIFIED** | `test_continuous_loop.py` 18 passed; lock released; heartbeat `finished` |
| Bounded campaign limits | **VERIFIED** | `--max-tasks 3`, `--deadline-minutes 90`, 1 implementation task |
| Local Ollama JSON adapter (installed Bojo) | **VERIFIED** | `test_local_model_ollama.py` 3 passed; real Ty probe and demo |
| Token-level SSE | **BLOCKED** | cycle7 remains blocked; snapshot-level SSE exists |
| Matrix/AgentTeams HITL | **BLOCKED** | not installed; local HITL queue is the current surface |
| 27B lane for this campaign | **NOT USED** | 27B lane consumed RAM below the 3 GB floor; Bojo used, no download |
| Background persistence after session | **UNKNOWN / not attempted** | foreground supervisor run; no service installed |

## 2. Implemented

| path | change |
|---|---|
| `scripts/continuous_loop.py` | task contract validation, Ty dispatch, lifecycle states, lock/heartbeat, STOP/timeout, byte baseline/restore, `git commit --only`, campaign limits, status buckets |
| `scripts/ty_task_runner.py` | Ty child runner; scoped `Workspace`, acceptance, STOP guard, heartbeat, result JSON |
| `Northstar_backend/agent_kernel/coding_tools.py` | `allow_paths`, `read_paths`, `run_allowlist` enforced on write/read/grep/apply_patch/ast_edit |
| `Northstar_backend/agent_kernel/local_model.py` | `OllamaChatModel` native JSON mode (`format=json`, `think=false`) and provider dispatch |
| `config/continuous_loop_tasks.json` | v2 contracts: authorization, risk, execution, scope, acceptance, timeout, repair bound, dependencies |
| `Northstar_backend/agent_kernel/hitl_counts.py` | **Ty-generated** `hitl_counts(root)` helper |
| `Northstar_backend/test_hitl_counts.py` | regression for the generated helper |
| tests | `test_continuous_loop.py` 18, `test_continuous_loop_rollback.py` 2, `test_local_model_ollama.py` 3, `test_hitl_counts.py` 2 |
| docs | `docs/CONTINUOUS_LOOP.md` updated to the bridge/lifecycle/rollback contract |

## 3. Test evidence

```
python -m pytest \
  Northstar_backend/test_continuous_loop.py \
  Northstar_backend/test_continuous_loop_rollback.py \
  Northstar_backend/test_local_model_ollama.py \
  Northstar_backend/test_hitl_counts.py \
  Northstar_backend/test_hitl.py \
  Northstar_backend/test_hitl_api.py \
  Northstar_backend/test_coding_agent.py \
  Northstar_backend/test_coding_guardrails.py \
  Northstar_backend/test_galactic_state.py -q
```

**69 passed.**

UI baseline from the prior cycle remains green: 73 unit tests, 11 contrast
pairs, 34 Galactic static checks, `npm run build` 0 errors. No UI source changed
in this cycle.

## 4. Demonstrations

### A. Controlled failure — disposable worktree

- Sandbox: temporary detached worktree at `58b79cb3` (removed after the test).
- Task: create `Northstar_backend/sandbox_target.py`; acceptance intentionally
  exits 1.
- Ty wrote 9 bytes to the target. The acceptance failed.
- Restoration removed `Northstar_backend/sandbox_target.py`, verified `true`,
  state `failed`, ledger `failed` with the real reason.
- Evidence: `reports/continuous_loop_failure_demo_20261031.json`.

### B. Real repository implementation

- Task `demo-hitl-counts`, provider `ollama`, model `bojo`.
- Ty created `Northstar_backend/agent_kernel/hitl_counts.py`.
- Acceptance command validated pending/approved/denied/total counts.
- The supervisor committed **only** that file: `96be935d`.
- It then advanced to `post-demo-test` (prebuilt regression) and completed it.
- `Northstar_backend/test_hitl_counts.py` covers the generated helper (2 tests).

## 5. Campaign state

**Completed, bounded, not running.**

- Started after the bridge acceptance gates; `--max-cycles 0` bounded by
  `--max-tasks 3` and `--deadline-minutes 90`.
- Implementation tasks dispatched: **1** (`demo-hitl-counts`).
- Prebuilt tasks completed: `post-demo-test`.
- External spend: **$0**. External network operations: **0**.
- No background process remains; the lock is released. Heartbeat's last stage is
  `finished`.
- The campaign stopped because no authorized eligible task remains:
  `cycle7-token-sse` is explicitly blocked.

## 6. Process / heartbeat

- No owned supervisor process is running now.
- Last heartbeat: `state/continuous_loop_heartbeat.json` (`stage: finished`).
- Lock: `state/continuous_loop.lock` absent.
- For a foreground run use the command in §8; this environment does not install a
  Windows service or scheduled task.

## 7. Remaining work

| task | state | reason |
|---|---|---|
| `cycle7-token-sse` | blocked | token-level streaming needs a request-scoped model stream and a UI consumer action; broader than this bridge and not authorized by this prompt |
| Matrix/AgentTeams HITL | blocked | packages not installed |
| 27B campaign | not used | 27B lane left less than the 3 GB free-RAM floor; Bojo used, no download |

## 8. Commands

```powershell
# Status (eligible / blocked / failed / interrupted / running / completed)
python scripts/continuous_loop.py --status

# Safe stop (checked before dispatch and once per second while Ty runs)
New-Item -ItemType File STOP -Force
Remove-Item STOP

# Explicit resume after fixing an interrupted/failed task
python scripts/continuous_loop.py --resume <task-id>

# Bounded foreground campaign (max 3 Ty tasks, 90 min, $0)
python scripts/continuous_loop.py --max-cycles 0 --max-tasks 3 --deadline-minutes 90
```

## 9. Limitations

- Bojo (1.9B) was used because the 27B lane could not coexist with the 3 GB
  free-RAM floor; this is a model-quality trade-off, not a 27B result.
- The generated `hitl_counts` expects a `Path`; callers pass `Path(root)`.
- Token-level SSE is not implemented; the deck's SSE remains snapshot-level.
- No background supervisor survives this session; the campaign was completed in
  the foreground.
- No Amazon, Chrome Connect, paid provider, credential, or production operation
  was performed. Chrome Connect was connected but not used.
