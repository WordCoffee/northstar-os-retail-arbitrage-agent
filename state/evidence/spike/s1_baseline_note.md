# S1 baseline reproduction — record

**Why this file exists.** S1's target check ("that test, 20 consecutive runs under
load") is a *probabilistic* check. Before any candidate ran, the unfixed tree was
measured so the gate's sensitivity would be known rather than assumed.

## What was run

Worktree at `%TEMP%\ns-spike-wt`, checked out from `HEAD = 15f0cc15`, and the
repository's own tree (`feature/chrome-connect-3.0`) before it.

```
python state/evidence/spike/load_run.py --root <tree> --runs 20 --load 20 \
    --test Northstar_backend/foundation/tests/test_jobs_durable_lifecycle.py \
    -k test_cancel_leased_job_cooperative
```

(`--load 20` = 20 busy-loop Python processes running concurrently; 24 logical
cores on this box.)

## What happened (verbatim)

Run 1 — repository tree, 20 runs, 20 spinners, 52.1 s:

```json
{"passed": 20, "failed": 0, "ok": true}
```

Run 2 — HEAD worktree, 20 runs, 20 spinners, 57.3 s:

```json
{
  "passed": 19,
  "failed": 1,
  "ok": false,
  "failures": [
    {
      "run": 2,
      "exit": 1,
      "seconds": 2.42,
      "illegal_transitions": [],
      "tail": [
        "  Northstar_backend.foundation.jobs_durable.JobValidationError: job is cancel_requested not leased",
        "FAILED Northstar_backend\\foundation\\tests\\test_jobs_durable_lifecycle.py::test_cancel_leased_job_cooperative",
        "1 failed, 24 deselected, 1 warning in 1.05s"
      ]
    }
  ]
}
```

Run 3 — HEAD worktree, 60 runs, 20 spinners, 176.9 s
(`state/evidence/spike/s1_baseline_head_60runs.json`):

```json
{"runs": 60, "passed": 60, "failed": 0, "ok": true}
```

Run 4 — HEAD worktree, via `baseline.py` (the gate as the spike uses it), 20
runs: **gate exit 0** (passed).

## What this means

The bug is real — run 2 caught it, with the exact symptom the plan describes
(a cooperative cancel lost to the worker: `job is cancel_requested not leased`
raised instead of the cancellation being acknowledged).

The rate is low: **1 observed failure in 100 baseline runs** (1/20, 0/60, 0/20).
At ~1 % per run, a 20-run gate catches a broken build roughly one time in five.
So S1's target check is **not a discriminating acceptance test**: it passes an
unfixed tree most of the time.

That is why, in the matrix, all three S1 candidates "passed the gate" with an
empty diff, and why S1 is reported as **not measurable** rather than as a lane
failure. A gate that is green on the broken code cannot prove a fix.
