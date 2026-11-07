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

## Live status (2026-11-06T13:00Z)

15 of 17 automation units done. Done: runner, name guard, disk, lanes, launcher, watchdog, git revert, red gate, token meter, worker lane, A9b meter wiring, A11 evaluator, A14 scope deriver, A15 contract writer, plus both T0 incidents.

Running: A12 candidate artifacts, A10 coding-lane spike.

Remaining: A12 -> A13 rejection ledger -> A16 work generator -> M3 intel I0-I3. Product and perf work stay blocked behind M2-work-generator.

