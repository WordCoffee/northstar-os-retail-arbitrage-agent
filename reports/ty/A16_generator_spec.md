# A16 — work generator: build spec (condensed from the design lane)

Purpose: the queue never runs empty **without saying exactly why**. That renegotiation is deliberate —
"never empty" is how a generator starts inventing busywork.

Status: not built. Design received 2026-11-06; this file is the buildable version.

## Priority bands (fixed, so generated work can never outrank the owner's order)

```
T0 incident        1300-1399   preempts everything
T1 red check        900- 999
T2 scan finding     700- 799
T3 backlog ready    500- 599
T4 intel gap        300- 399
T5 maintenance      100- 139   floor
```
Within a band: `base + min(99, days_first_seen)`. `select_next` then breaks ties by `attempts`, `id`.

## One item per call, one tier at a time

Strict T0→T1→T2→T3→T4→T5. First tier that yields a candidate wins. Not round-robin: a scan finding must
never displace a red check.

Brakes: `MAX_GENERATED_ACTIVE = 12`, `MAX_GENERATED_PER_DAY = 24`; over either →
`{"reason": "supply_capped"}`, add nothing. The launcher halts at 40 consecutive skips, so a
discovery bug that floods `needs_author` items **stops the loop** rather than degrading it.

## Where each tier gets work

| Tier | Source (exists?) | Dispatchable when | Otherwise |
|---|---|---|---|
| T0 | probe with `severity: incident` failing; or a `done` item whose check now fails (`check_regression.py --junit`) | `tys_author.derive()` returns a scope from the probe's own traceback | `needs_author: scope not derived (<reason>)` |
| T1 | `state/backlog/proposals.json` (exists, 10 proposals) | derive ok **and** paths inside the commit allowlist **and** `validate_contract == []` | `needs_author` naming the missing datum |
| T2 | `tools/production_readiness_scan.py --json` | **never** — a scan finding has no check and no derivable scope | always `needs_author: name the check that proves <check> at <path>:<line>` |
| T3 | `state/backlog/improvements.json` items with `status: ready` | item already names `write_paths` + `checks` (validated by `improvement_backlog --check`) | quote the check's problem verbatim |
| T4 | `state/intel/gaps.json` (A21 — **absent**) | only when the gap names a falsifiable argv **and** a derivable scope | `{"state":"no_source"}` and **zero** candidates |
| T5 | `tools/tys_probes.py --probe <id>` (to build) + `improvement_backlog --check` + `check_regression` | same rule as T0, at priority 100-139, `fixable_by: worker` | `fixable_by: owner` → `needs-owner` item + `needs_you.md` line, **not** counted as supply |

`tools/tys_probes.py` is a policy path (`tools/tys_*.py`), so no candidate can weaken the probe that
grades it.

## Dedupe

`dedupe_key` on the item, indexed across all statuses:

```
probe:<probe_id>              T0/T5 probe
regression:<done_item_id>     T0 regression
pytest:<nodeid>               T1
scan:<check>:<path>           T2 (line number excluded on purpose)
backlog:<id>:sha256(first argv)[:8]   T3 (a changed check is a new question)
intel:<gap_id>                T4
```

Existing key: pending/in_progress/partial → skip; `needs_author` → **promote in place** (same id,
attempts untouched), never re-emit; `done` → reopen only if the surface still reports it, attempts
preserved, max 2 reopens then `needs_author`. Deleted keys get one re-emit from an append-only
`state/tys_generator/emitted.jsonl`, then `needs_author: deleted twice`.

## Never-empty, honestly

- All tiers green and all surfaces non-vacuous → return `{"ok": false, "reason": "starvation"}` with a
  per-tier record of numbers (`1043 files scanned, 0 findings`) and write **nothing**.
- **Vacuity is a finding**: `scan total:0` with `files_scanned:0` emits one T5 item
  (`discovery-vacuous`) — "zero findings from a scanner that saw nothing" is a defect.
- Also produce nothing with its own reason for: `STOP` present, token cap reached, `gate_closed`
  (product tiers gated), `targets_dirty`.

## Runner deltas (operator lane — `tys_runner.py` is not dispatchable)

1. `cmd_next` (~line 282): if `select_next` is None, call `generate()` once inside try/except, reload,
   re-select; on None print `queue_empty` + `starvation` and return 6.
2. `cmd_complete` (~line 463): low-water top-up when dispatchable active < 3, **before**
   `_clear_lease`, in try/finally so an exception cannot leak a live-pid lease.
3. `select_next` ordering: dispatchable first —
   `key=lambda i: (not _dispatchable(i), -priority, attempts, id)` — else `needs_author` items are
   skipped one at a time and 40 of them end the run at `no_runnable_items`. Keep `pool = ready or
   unblocked` so the stall is journalled, not hidden.
4. `scripts/tys-watchdog.ps1` (~line 66): back off on `reason -eq "starvation"` as well as
   `model_lane_down`, or a starving system probe-loops every 20 s.

## Signatures to build

```python
# tools/tys_generator.py   (POLICY PATH)
generate(*, queue_path=QUEUE, tier=None, max_items=1, dry_run=False,
         probe_runner=subprocess.run, now=None) -> dict
append_item(queue, item, *, queue_path=QUEUE) -> dict      # atomic via tys_runner._write + readback
discover(tier, *, probe_runner, now) -> dict               # {state, candidates, detail}
dedupe_key(item) -> str
needs_forward(queue=None) -> int                           # dispatchable active count

# tools/tys_probes.py      (POLICY PATH)
probe_table() -> list          # {id, tier, argv, why, fixable_by, cadence, timeout_s}
run_probe(spec, *, run=subprocess.run, cwd=ROOT) -> dict
run(*, ids=None, run=subprocess.run) -> dict   # exit 0 green, 1 red, 2 could-not-run
```

## Tests (`Northstar_backend/test_tys_generator.py`)

queue empty → exactly one item and `select_next` returns it · generated item without a check is
`needs_author` · dispatchable passes `validate_contract` · second call adds nothing (`duplicate`) ·
dedupe ignores line drift · `needs_author` promoted in place, attempts unchanged · probe red with
traceback → dispatchable, without → `needs_author` · all green → `starvation`, queue bytes identical ·
vacuous scanner is the finding · absent T4 source → `no_source`, zero candidates · refuses under
`STOP` · live-pid lock → `busy` · reopen capped, attempts never reset · 3 reverts with no ledger →
`needs_author` (fallback until A13) · gate closed → T2/T3/T4 carry `depends_on:["M2-work-generator"]`
and T0/T1/T5 carry none · append atomic and rolls back on tampered readback · budget overrun →
`deferred_budget`, cycle still exits 0 · generated argv passes `continuous_loop.check_command` (so
`amazon` in a generated command is refused).

## Two side findings to fix while here

- `cmd_dry_run` picks by priority only and ignores `depends_on` / `defer_until_cycle`, so the gate's
  own 9-cycle acceptance trace can show cycles the real selector would refuse.
- `validate_contract` returns early when `acceptance_commands` is None; correct only because
  `runnable()` refused it first — rely on `validate_contract` wholesale.
