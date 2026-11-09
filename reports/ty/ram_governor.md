# Free-RAM governor — builders start on a measured gate, not a hope

Branch `ty/ramgov`. New `tools/ram_governor.py`; wired into
`scripts/ty_director.py` and `tools/director_queue.py`.

## What it decides

| free physical RAM | max new builders | paused |
|---|---|---|
| >= 2.0 GB | 4 | no |
| < 2.0 GB | 2 | no |
| < 1.0 GB | 0 | yes |

Running sessions are never touched: the gate is only consulted on the start path,
after `find_director()` has already said no session is alive.

Two readings are taken every time: `psutil.virtual_memory().available` and
`Win32_OperatingSystem.FreePhysicalMemory` (via `Get-CimInstance`). When they differ by
more than 20 % the decision uses the **lower** and the reason string names both. A
`state/director/caps.json` with `cloud_workers` lowers the number to the minimum of the
two; a missing file is not a cap (it is not silently assumed to be 4).

Every decision appends one JSON line to `state/director/ram_gate.jsonl`:
`free_gb`, `max_builders`, `paused`, `who`, plus `event`/`running`/`allowed` for gate
calls and both raw readings. No model, no network, no process killing.

## Where the gate is consulted

- `tools/director_queue.py:242` `claim()` — before the write lock, for a `queued` job
  whose unit needs a builder; refuses `{"ok": false, "reason": "ram_paused", ...}` and
  records a `ram_refused` event without changing the job's status
  (`director_queue.py:256-262`). Results are journaled by the governor.
- `scripts/ty_director.py:421` `tick()` start path and `ty_director.py:489` the main
  loop, both after the live-session check, both logging one line naming the free RAM.
- `scripts/ty_director.py:298` the heartbeat records the governor verdict under
  `"ram"`; `ty_director.py:440` `--status` does too.

Builder-lane exemption: `unit_needs_builder()` (`director_queue.py:184`) reads the
units mirror; `"needs_builder": false` or a lane of operator/verifier/measurement is
not builder work, so bookkeeping still claims while paused. The default is True.

Both entry points are injectable (`claim(..., governor=...)`, and the launcher tests
stub `D.ram_status`), so no test depends on this machine's free RAM.

## Real runs (this worktree, 2026-11-09)

```
$ python tools/ram_governor.py --status --who ramgov-evidence
{
  "at": "2026-11-09T07:32:20+00:00",
  "free_gb": 2.21,
  "max_builders": 4,
  "paused": false,
  "reason": "free RAM 2.21 GB >= 2.0 GB: up to 4 builders",
  "readings": {"psutil_gb": 2.21, "win32_gb": 1.92},
  "disagreement": false,
  "disagreement_pct": 13.1,
  "who": "ramgov-evidence",
  "event": "status"
}
EXIT=0
```

```
$ python tools/ram_governor.py --gate 3 --who ramgov-evidence
{ "free_gb": 2.01, "max_builders": 4, "paused": false,
  "readings": {"psutil_gb": 2.01, "win32_gb": 2.23},
  "allowed": true, "running": 3, ... }
GATE3_EXIT=0

$ python tools/ram_governor.py --gate 4 --who ramgov-evidence
{ "free_gb": 2.18, "max_builders": 4, "paused": false,
  "readings": {"psutil_gb": 2.18, "win32_gb": 2.17},
  "allowed": false, "running": 4, ... }
GATE4_EXIT=1
```

`python scripts/ty_director.py --status` now carries:

```
  "ram": { "free_gb": 2.05, "max_builders": 4, "paused": false, ... }
```

Note on the 13 % gap above: this box reports `available` 2.21 GB against Win32
`FreePhysicalMemory` 1.92 GB. That is inside the 20 % tolerance, so the primary
reading is used as specified. A wider gap (the 3.0 vs 1.5 case in the tests) picks
the lower.

## Test tails

```
$ python -m pytest Northstar_backend/test_ram_governor.py -q
17 passed in 0.28s

$ python -m pytest Northstar_backend/test_ty_director_launcher.py -q
20 passed in 2.21s

$ python -m pytest Northstar_backend/test_director_queue.py -q
13 passed in 6.68s
```

`test_ram_governor.py` covers 3.0→4, 2.0→4, 1.9→2, 1.0→2 (boundary), 0.9→0 paused,
0.4→0 paused, the lower-wins disagreement, the measured `cloud_workers` minimum,
`--gate 3` pass/fail, `--gate` at the cap, unreadable probes, and the journal shape.
The launcher tests prove a paused gate starts nothing (`tick` and the loop) and leaves
a running director alone; the queue tests prove `claim()` returns `ram_paused` from an
injected governor, leaves the job queued, and still allows a non-builder unit.

## Hard lines respected

No process was killed to free RAM (nor by the governor at all), no Amazon host was
contacted, and the render lane's own 3 GB floor was not changed.
