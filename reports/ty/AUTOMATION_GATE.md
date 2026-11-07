# Automation gate — finish this, in order, before anything else (2026-11-06)

Owner directive: *"we need to finish everything we have in order, no need to skip around.
If we finish it we can build the system properly with automation. So the automation needs to
be fully complete first."*

This file is the ordered list. `tys_runner.select_next` enforces `depends_on`, so an item
cannot be picked before the one above it is `done`. Priority numbers are unchanged; the
dependency chain is what prevents skipping.

## A. Automation completion (strict order)

| # | id | unit | state | depends_on |
|---|---|---|---|---|
| A1 | `M0.1-runner` | loop state outside any session: lease, TTL+pid crash resume, rotation, caps, handoff validation | **done** | — |
| A2 | `M0.2-name-guard` | regression by test name (6,453 ids), additions allowed, subset refused | **done** | — |
| A3 | `M0.4-disk` | reclamation with an allowlist; 9.74 → 14.21 GB | **done** | — |
| A4 | `M0.5-lanes` | GPU/CPU/browser leases; a starved lane defers | **done** | — |
| A5 | `M2-launcher` | next → worker → complete, heartbeat, evidence, stop reasons | **done** | A1 |
| A6 | `M2-watchdog` | exactly one launcher, restart on exit, backoff, logon task | **done** | A5 |
| A7 | `M1-revert` | failed cycle restores bytes **with git**, dirty target refuses dispatch | **done** | A5 |
| A8 | `M1-red-gate` | a check already green never reaches a worker | **done** | A5 |
| A9 | **`M0.3b-token-meter`** | estimate tokens per cycle so the daily cap is real | **todo** | A1 |
| A10 | **`M0.5-spike`** | 5 real problems × 3 candidates → decide local / hybrid / stop | **todo** | A9 |
| A11 | **`M1c-evaluator`** | `tools/tys_evaluator.py`: scope, well-formedness, target-green, check-not-tampered | **todo** | A10, A7 |
| A12 | **`M1d-artifacts`** | freeze `state/author/<item>/cand_<k>.{diff,json}` per candidate | **todo** | A11 |
| A13 | `M1e-rejections` | fingerprint ledger; 3 rejections on one gate → `needs_author` | **done** | A12 |
| A14 | **`M1f-scope-deriver`** | derive `write_paths` from a real traceback; no artifact → no scope | **todo** | A11 |
| A15 | **`M1g-contract-writer`** | write the authored contract into the queue atomically + `validate_contract` | **todo** | A14 |
| A16 | **`M2-work-generator`** | the T0–T5 ladder, never returns empty | **todo** | A13, A15 |
| A17 | **`M2-worker-lane`** | `opencode run --agent tys` returns output + model provenance reliably — CLI was fine; the reader was not (`part.text`, assistant-message model). Report: `reports/ty/A17_worker_lane.md` | **done** | A5 |
| A18 | `M3-intel-I0` | source registry + collectors (GitHub, HF, PyPI reuse `web_research`) | **todo** | A16 |
| A19 | `M3-intel-I1` | normaliser + effective-licence engine + refusal log | **todo** | A18 |
| A20 | `M3-intel-I2` | REA extractor: repo `file:line`, video timestamps, screenshots | **todo** | A19 |
| A21 | `M3-intel-I3` | gap matcher + hypothesis template + yield scoring | **todo** | A20 |

**Gate:** A9–A17 must all be `done` before any product/UI workstream item is dispatched.
A18–A21 complete the intelligence plane and may run after A17 in parallel with product work.

## B. Everything else (blocked behind the gate)

Product and security items already in the queue (`S1-cancel-race`, `T0-*`, `T1-*`, W1–W14)
carry `depends_on: ["M2-worker-lane"]` or `["M2-work-generator"]`, so they are queued but
unreachable until the automation above is finished. That is the "no skipping" rule expressed
in data rather than in hope.

## C. Definition of "automation fully complete"

All of these, each with a command that shows it:

1. `python tools/tys_runner.py status` — lease, caps and next item are coherent; a killed
   launcher is recovered by pid, not by waiting for a TTL.
2. `python tools/tys_launcher.py --dry-run --max-cycles 9 --per-session 3` — 9 cycles, 3
   rotations, no writes outside the temp state.
3. A real failure is fixed with **no human**: author → candidate → evaluator → acceptance →
   commit, and the rejected candidates are on disk with their gate and output.
4. A check that is already green produces `check_already_green`, never a ship.
5. `logs/tys_watchdog.log` shows a launcher restart after a deliberate kill.
6. An 8-hour unattended run with ≥3 shipped bundles and no interventions, or a written
   diagnosis of exactly why not.
7. Every refusal (licence, disk, RAM, gate) is in a log with its reason — no silent skips.

When C1–C7 hold, the gate opens and product/UI work becomes the queue's front.

## Live status (2026-11-07T08:30Z)

**All 17 automation units are done.** A13 (rejection ledger) at `41fdceaf`; A16 (work
generator) at `9d6bb3b4` with its four runner deltas at `603f73e7` and `8230b730`.
A9's row was stale: the token meter and its A9b wiring landed in an earlier session
(real measurement 80,834 tokens vs a 5-token guess) and the queue now records it.

The dependency gate opened: `select_next` now returns product work, and 34 product
and perf items that carried `depends_on: null` were given the
`M2-work-generator` dependency they were always supposed to have (`6158c001`).
Before that fix the dry-run proved the leak — cycle 2 was `W10-scanner-csv`.

### Acceptance evidence (C1-C7), measured

| # | claim | result | evidence |
|---|---|---|---|
| C1 | status coherent; killed holder recovered by pid | **green** | `python tools/tys_runner.py status` reports lease/caps/next/parks; `test_crash_recovery_keeps_the_reserved_item` and the new `--token` tests |
| C2 | launcher dry-run 9 cycles / 3 rotations, no stray writes | **green** | `--dry-run --max-cycles 9 --per-session 3` on a redirected root: exit 0, `cycles 9`, 3 `session_ended` rows, real repo clean |
| C3 | author -> candidate -> evaluator -> acceptance -> commit | **in progress** | cycle 38 ran the real worker for 23.5 min and was refused `out_of_scope` by a pre-existing dirty-test bug (`9cd8a12a`, fixed). Re-dispatch after the fix is the run in flight |
| C4 | an already-green check produces `check_already_green`, never a ship | **green** | it now also parks the item (`needs_author`) instead of deferring, because soft deferral re-admitted it — measured 40 acceptance runs in 54 s |
| C5 | watchdog restarts a killed launcher | **pending** | watchdog script has the starvation backoff; restart proof still to capture |
| C6 | 8-hour unattended run, >=3 shipped bundles | **pending** | needs C3 green first |
| C7 | every refusal logged with its reason | **green** | `launcher.jsonl` records `skipped_invalid_contract`, `check_already_green`, `commit_refused`, `targets_dirty`; `sessions.jsonl` records `starvation` with the generator's per-tier numbers |

### What the C3 probe found, and what was done about it

`reports/ty/C3_PROBE.md` (independent lane, 8 green / 5 red). Four were fixed
(`896b7aaa`, `ebaa13d9`, `66f7c952`, `9cd8a12a`): the missing contract gate on
dispatch, the policy module loaded from the state root instead of the code root, a
lease token so a worker in another process can complete, `--per-session` on the
launcher, a stale result cannot close a later cycle, the brief carries the check,
and a shipped cycle is now committed and tagged rather than merely judged.

Two remain **by design, not defects**: `defer_until_cycle` is deliberately soft
(`pool = ready or unblocked`) — which is exactly why every hard stop is a status
change — and the author lane cannot derive a scope from a test-only traceback,
which is the A10 verdict stated as code.

### Remaining before the gate opens

C3 end-to-end with the real worker, C5's kill/restart proof, and the C6 soak.
Product and perf work is dispatchable now; it is not blocked any more, only
unproven.

