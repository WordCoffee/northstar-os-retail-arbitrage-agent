# NorthstarOS autonomy readiness — handoff (2026-10-31)

## 1. Capability table

| Capability | Status | Evidence |
|---|---|---|
| Full GO/NO-GO readiness gate | **VERIFIED** | `python scripts/continuous_loop.py --ready` → GO; 17 checks |
| Rollback checkpoint: git ref, DBs, configs, model manifest, uncommitted patch | **VERIFIED** | `state/checkpoints/20261101T021052Z-ready/`; 7 files, patch 34.3 MB |
| Disposable byte-for-byte restore demo | **VERIFIED** | sandbox `bytes_match=true`, `created_removed=true` |
| Policy fingerprint vs committed envelope | **VERIFIED** | 5/5 policy files match HEAD; mismatch is NO-GO |
| Working-tree/staged-work preservation | **VERIFIED** | recorded status/staged paths; `test_commit_task_preserves_pre_existing_staged_work` |
| Disk/RAM/state/ledger/STOP/lock preflight | **VERIFIED** | all 17 gate checks pass; stale-lock and STOP tests |
| Actual installed model lane selection | **VERIFIED** | selected `bojo:gpu-orig`; 7 B/27 B not fit; no download |
| Authorized diverse work queue | **VERIFIED** | 8 runnable v2 tasks + 1 blocked auth proposal |
| Precheck (fails before) → apply → checks (pass after) | **VERIFIED** | 8/8; `hitl-pathlike` precheck failed with `AttributeError: 'str' object has no attribute 'exists'` |
| `--max-tasks` and `--deadline-minutes` both enforced | **VERIFIED** | campaign stop `max_tasks` at 8; deadline test |
| `--max-consecutive-failures` halt | **VERIFIED** | test stops after 2 failures; halt reason persisted |
| Campaign heartbeat + scrubbed live log + final manifest | **VERIFIED** | `state/continuous_loop_campaign.json`, `reports/autonomy_log_20261101.log`, `state/campaigns/campaign-20261101T015753Z.json` |
| One-screen `--status`, safe `--stop`, explicit `--resume` | **VERIFIED** | live status; STOP test; resume test |
| Multi-file rollback and user-work preservation | **VERIFIED** | `test_multi_file_task_failure_restores_all_task_owned_bytes_and_user_work` |
| Mid-task STOP kills worker, no partial commit | **VERIFIED** | `test_stop_mid_task_terminates_worker_and_writes_failure_result` |
| Supervisor crash → interrupted → resume, no duplicate | **VERIFIED** | `test_kill_supervisor_mid_task_then_recover_and_resume` |
| 8-task foreground campaign | **VERIFIED** | 8 completed / 0 failed / 1 blocked·not-authorized; commits `b42171c5…74c7d49c` |
| UI baseline | **VERIFIED** | 73 unit, 11 contrast, 34 static; build 0 errors |
| Hours-long soak | **NOT USED** | campaign finished in 45 s; 180-minute bound not exercised |
| Typhoon/Ty model editing in this campaign | **NOT USED** | campaign tasks were deterministic prebuilt; prior Ty demo `96be935d` |
| Auth-sensitive test repair | **BLOCKED** | `test_text_fidelity.py::test_text_check_endpoint_auth_and_404`; needs separate auth authorization |
| External/Amazon/browser/paid calls | **BLOCKED by policy** | command allowlist and no calls made |
| 27B lane | **NOT USED** | does not fit RAM floor; only `bojo:gpu-orig` selected |

## 2. Final readiness gate

`verdict: GO` at `2026-11-01T02:10:52Z`.

- 17/17 checks pass.
- Checkpoint: `state/checkpoints/20261101T021052Z-ready`
- Lane: `ollama/bojo:gpu-orig`; free RAM 4.34 GB at dispatch; estimated post-load headroom **2.09 GB**.
- Policy fingerprint: 5/5 committed files match HEAD.
- No lock; STOP absent; sandbox restore byte-for-byte.
- `state/autonomy_readiness.json` contains the full check list and remediations.

## 3. Campaign queue and outcomes

Run `campaign-20261101T015753Z`, 8/8 completed, 0 failed, stop `max_tasks` after 8 (45 s).

| Task | Result | Commit | Duration | Precheck | Apply |
|---|---|---|---:|---|---|
| `hitl-pathlike` | completed | `b42171c5c332` | 4.512 s | failed as required | pass |
| `format-quad-guard` | completed | `ca29ceea6f44` | 5.599 s | failed as required | pass |
| `geometry-bottom-guard` | completed | `03da4b07a6a0` | 5.463 s | failed as required | pass |
| `print-quad-guard` | completed | `190c8e456fb8` | 5.588 s | failed as required | pass |
| `surface-wrap-guard` | completed | `ff4985247a12` | 6.289 s | failed as required | pass |
| `panels-format-guard` | completed | `48daca5b0fc4` | 6.342 s | failed as required | pass |
| `dead-code-cleanup` | completed | `558eceb947ab` | 5.525 s | failed as required | pass |
| `docs-autonomy` | completed | `74c7d49c7f64` | 5.458 s | failed as required | pass |
| `blocked-auth-text-check` | blocked-not-authorized | — | — | — | — |

The `hitl-pathlike` precheck is a real behavior failure: the old function
called `root.exists()` on a string and raised `AttributeError`; after the patch
it accepts path-like roots and the regression test passes.

A separate pre-fix replay proved the non-helper behavior change in
`format-quad-guard`: against parent `e111977e`, a 3-point bottle quad produced
**no `ValueError`** (exit 1, silent bad transform); against the current commit it
returns `ValueError` (exit 0). Command output:

```text
PRE-FIX exit 1 FAIL no ValueError
POST-FIX exit 0 PASS ValueError
```

## 4. Recovery results

`11 passed` for the autonomy/recovery suite, plus `142 passed` for the bridge,
coding and kernel regression batch.

- Multi-file failure: both task files restored byte-for-byte; unrelated user work untouched; created file removed.
- Mid-task STOP: worker process tree terminated; result recorded as failure; no commit.
- Supervisor crash: child killed mid-task; relaunch marked the task `interrupted`; explicit resume restored the baseline and left only the original commit.
- Three consecutive failures: campaign halted at two failures with `stop_reason=max_consecutive_failures`; no infinite loop; lock released.
- Apply-worker PID tracking added so a crashed prebuilt task's child can be terminated on recovery.

## 5. Test totals and commands

```text
142 passed  bridge + coding + autonomy batch
 11 passed  autonomy readiness/recovery/crash subset
173 passed  package/creative/specialist/chat batch
 73 passed  UI unit
 11 pairs   UI contrast
 34 checks  Galactic static verifier
  0 errors  UI production build
```

Commands used:

```powershell
python -m pytest Northstar_backend/test_continuous_loop.py Northstar_backend/test_continuous_loop_rollback.py Northstar_backend/test_autonomy_readiness.py Northstar_backend/test_autonomy_recovery.py Northstar_backend/test_autonomy_supervisor_crash.py Northstar_backend/test_loop_breaker.py Northstar_backend/test_coding_agent.py Northstar_backend/test_coding_guardrails.py Northstar_backend/test_agent_kernel.py Northstar_backend/test_snapshot.py -q
cd northstar-os-ui; npm run test:ui; npm run test:contrast; npm run verify:galactic; npm run build
```

## 6. Operator commands

```powershell
# readiness gate
python scripts/continuous_loop.py --ready

# launch a bounded foreground campaign
python scripts/continuous_loop.py --max-tasks 8 --deadline-minutes 180 --max-consecutive-failures 2

# live status / live log
python scripts/continuous_loop.py --status
Get-Content reports\autonomy_log_YYYYMMDD.log -Tail 40 -Wait

# safe stop (then remove STOP when ready to run again)
python scripts/continuous_loop.py --stop
Remove-Item STOP

# explicit recovery
python scripts/continuous_loop.py --resume <task-id>

# post-run
python scripts/continuous_loop.py --status --json
Get-Content state\campaigns\campaign-<run-id>.json
```

## 7. Remaining limits before hours-long unattended operation is routine

1. **Foreground only.** No Windows service or scheduler is installed. A closed
   terminal stops the supervisor. Upgrade evidence: install a service wrapper,
   run a 6-hour soak, kill/restart the host, and verify the same checkpoint,
   lock and resume path.
2. **Post-load RAM headroom is 2.09 GB.** `bojo:gpu-orig` fits at dispatch and
   is the smallest installed chat lane, but after load it is below the 3 GB
   advisory floor. The 7 B and 27 B lanes do not fit. Free at least ~5.25 GB or
   install a smaller lane before a long Ty campaign.
3. **The 8-task campaign was deterministic prebuilt work.** Ty model editing was
   not exercised in this campaign; the prior approved Ty demo is commit
   `96be935d`. Upgrade evidence: run a Ty task with a verified acceptance test
   under the same lane/heartbeat/recovery path.
4. **The 180-minute bound was not soaked.** The campaign completed in 45 seconds.
   Upgrade evidence: a 6-hour campaign with scheduled task spacing, a forced
   crash, and a successful resume.
5. **Some queue prechecks prove failure by a missing regression file.** Only
   `hitl-pathlike` uses an inline behavioral failure. Future queue entries
   should each carry an inline failing probe before the apply step.
6. **No service, no scheduler, no Amazon, no browser, no credentials, no
   external network, no paid provider, and no model/package downloads were used.**
