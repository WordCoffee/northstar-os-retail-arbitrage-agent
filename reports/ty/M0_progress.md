# M0 — Foundations (build log)

Started 2026-11-06. Plan: `C:\Users\T2Hol\.opencode\plan\northstar-autonomy-master-plan.md`.
This is the part that must exist before the loop can run unattended.

## M0.1 — Runner owns the loop — DONE

`tools/tys_runner.py` (11 tests). The loop's state lives outside any model session:

| command | behaviour |
|---|---|
| `next` | reserves the highest-priority non-deferred item, writes the cycle brief, takes the lease |
| `complete --result f.json` | validates evidence, records the cycle, updates the ledger, decides rotation |
| `status` | queue counts, next item, lease, tokens today, cap state |
| `rotate --reason` | ends the session cleanly at a boundary |
| `stop` | writes `STOP`, releases the lease |
| `dry-run --cycles N --per-session K` | simulates rotations, writes nothing |

Behaviour that matters:

- **One lease at a time.** A second `next` is refused (`exit 5`), so two workers cannot
  fight over the same cycle.
- **Lease expiry = crash recovery.** A lease older than the TTL is dropped and the same
  item is re-reserved, so a dead session resumes instead of stalling.
- **Reverted items are deferred two cycles.** Without it, a failed item jumped straight
  back to the front and the loop retried the same wall. (Found by test, fixed.)
- **Token cap** at 90 % of `TY_TOKEN_CAP_PER_DAY` stops `next` with a clear code.
- **Handoff validation**: a shipped cycle without evidence or a tag is refused
  (`handoff_invalid`), not recorded.
- **Rotation at `cycles_per_session`** (default 3) or on `context_heavy`.

Live status after M0.1:

```
stop:false  phase:C  cycle:9
queue: pending 26 · in_progress 3 · done 8 · blocked 1 · partial 2 · needs-owner 1
next: W0-c1 (author/evaluator)
```

## M0.2 — Regression by test name — DONE (wiring verified on a subset)

`tools/check_regression.py` (7 tests) + `tests/BASELINE_TESTS.json` (**6,039 unique ids**
from 6,402 collected; parametrised cases collapse to their base id).

- New tests are **allowed and reported**.
- A removed test is a regression, by name.
- A failing/erroring test blocks, by name.
- A **subset run is refused** (`exit 2`) rather than reported as "6,039 tests removed" —
  a footgun the first real run exposed.

`scripts/run_all_tests.ps1` now emits junit and calls the checker; the old count equality
became a floor (`passed >= baseline`) because identity is checked by name.

## M0.5 - Lane leases - DONE

`tools/lanes.py` (9 tests). One holder per lane, TTL expiry, and a **deferral**
instead of a failure when the box cannot serve it:

- `gpu` needs 4096 MB VRAM free **and** 3000 MB RAM; unknown VRAM is a refusal,
  not a guess
- a busy lane returns `lane_held` with the holder; an expired lease is reclaimable
- an unreadable lease file is treated as free (a stuck file must not block the loop)

Live: `gpu defer: ram_below_floor (2850 < 3000)` - the honest answer on this box
right now.

## M0.3 - Token ledger - PARTIAL

The ledger and the cap enforcement exist in the runner (`ledger.json`, per day, 90 % stop).
What is missing is the **measurement**: the worker reports `tokens` in its result and the
runner sums it, but nothing yet estimates usage from the session transcript. That
estimation is the remaining piece and it belongs to M0.3b.

## M0.4 — Disk reclamation — DONE

`tools/reclaim_disk.py` (7 tests), dry-run by default, explicit allowlist.

**Measured result:** `1,284 targets · 3.86 GB freed · 0 failures`
**Disk: 9.74 GB → 14.21 GB free** — the download/GPU floor is clear again.

Protections proven by test: `data/`, `backups/`, `renders/references/`,
`renders/mogra_lions_mane/`, `.git`, `node_modules`, `shared/`, `config/`, `docs/`.
Retry artifacts (`*_a[2-9].png`) go; attempt 1 stays.

## Incident during M0.2 verification

The first full-suite run hung: pytest CPU flat at 208 s for 20 s, 36 minutes elapsed
against a ~16 minute baseline. Cause not yet isolated; the UI (8101) was down at the
time. The run was killed and the suite is being re-run with `--timeout=120` so a hang
becomes a named failure instead of an infinite block. **This is exactly the class of
failure the runner has to survive, and it is now visible instead of silent.**

## Next

- M0.3b: transcript-based token estimation (±20 % is acceptable if labelled).
- M0.5: lane leases (GPU / CPU / browser) with deferral instead of failure.
- M0.5-spike: 5 real failures × 3 candidates to decide the author/evaluator design.
