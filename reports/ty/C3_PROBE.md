# C3 integration probe — the fix chain, driven end to end

Date: 2026-11-07. Lane: C3 integration probe (no product source touched).
Fixture: `C:\Users\T2Hol\AppData\Local\Temp\opencode\c3probe_fixadd` (`$PROBE` below).
Every command ran in a subprocess with `NORTHSTAR_TY_ROOT=$PROBE`, so all loop state,
queue, journal, artifacts and ledger lived in the fixture, never in the repo.

## Generation probed (this matters — the tools moved while I probed)

The loop tools were being edited by other lanes throughout the probe. Five commits landed
between 07:33 and 07:39, plus one uncommitted half-write at 07:36 (`_top_up` called before it
was defined, `NameError` at `cmd_complete`).

| generation | commit / state | `tys_runner.py` sha256 | used for |
|---|---|---|---|
| G1 | `603f73e7` (blobs extracted to `$PROBE\tools_head`) | `6f526372…4063d649` | S1–S7 (status, next, complete, in-process chain, green gate, dry-run, dispatchable) |
| G2 | `4b11b860` (== working tree, verified clean + hash-stable before and after) | `6faa8d33…3833eda8` | V1–V3, L1–L2, M1–M3 (re-verification of the lease and contract claims) |

`tys_author.py` (`8607acf5…`) and `tys_evaluator.py` (`9a782da1…`) were byte-identical across
every generation — their results are generation-independent. `tys_launcher.py` changed once
(`447e60ca` → `d19c0b14`), and only in the `queue_empty`→`starvation` label; neither the
pre-run red gate nor the skip watchdog changed.

Fixture: git repo, `pkg/calc.py` = `def add(a, b): return a - b  # bug`, `tests/test_calc.py`
asserts `add(1, 2) == 3` (RED, exit 1), one queue item `probe-fix-add` (priority 900,
`write_paths ["pkg/calc.py"]`, `acceptance_commands [["python","-m","pytest","-q","tests/test_calc.py"]]`).

## Result table

| # | link | command run | exit | result | evidence |
|---|---|---|---|---|---|
| 1 | **author** (derive write scope + check pin) | `tys_author.py --item probe-fix-add --command "python -m pytest -q tests/test_calc.py" --repo $PROBE` | 1 | **RED** — `reason: scope_unproven`, `write_paths: []`, no `derivation.json` written | `$PROBE\logs\05_author_derive.txt`; `tools/tys_author.py:341-364` drops every `tests/` frame; `$PROBE\logs\11_author_frames.txt` shows pytest yields exactly one frame, `tests\test_calc.py:5: AssertionError` |
| 2 | **reserve** | `tys_runner.py next` | 0 | **GREEN** — brief written, lease taken, item `in_progress` | `$PROBE\logs\s2_next_head.json` |
| 3 | **candidate** (freeze) | `tys_evaluator.freeze(repo=…, item_id=…, candidate_id="1", contract=…)` | 0 | **GREEN** — `cand_1.diff` 182 B, `diff_sha256 617efaa8…` | `$PROBE\logs\03_freeze_judge.json`; `$PROBE\state\author\probe-fix-add\cand_1.*` |
| 4 | **evaluator** (5 gates) | `tys_evaluator.evaluate_frozen(cand_1.json)` | 0 | **GREEN** — `gate: pass`, `5 gates green over 1 changed path(s): pkg/calc.py`, acceptance command exit 0 | same file; `tools/tys_evaluator.py:100,1150` |
| 5 | **drift check** (live tree vs frozen) | `tys_launcher.judge_cycle(…)` | 0 | **GREEN** — `live.gate: pass` | `$PROBE\logs\03_freeze_judge.json`; `tools/tys_launcher.py:484-563` |
| 6 | **acceptance evidence + commit, one process** | `runner.cmd_complete(completion.json)` after `cmd_next` in the same process | 0 | **GREEN** — item `done`, `last_result shipped`, checkpoint written, lease cleared | `$PROBE\logs\s4_inprocess_head.txt` |
| 7 | **commit, separate processes** (`next` … `complete`) | `tys_runner.py complete --result …` in a new process | **5 then 0** | **RED** — non-deterministic: `{"ok": false, "error": "no lease held; nothing to complete"}` when the reserving pid is dead, success when the pid is alive or reused | `$PROBE\logs\s3_complete_head.json` (exit 5), `$PROBE\logs\l1_dead_pid.txt` (exit 5), `$PROBE\logs\l2_live_pid.txt` (exit 0), `$PROBE\logs\v2_complete.txt` (exit 0) |
| 8 | **pre-run red gate** (negative half of C3/C4) | `tys_launcher.py --worker deepseek --max-cycles 1` with the check already green | 0 | **GREEN** — 40 × `check_already_green`, **0** worker/judge events, `reason: no_runnable_items`, item stays `pending` | `$PROBE\logs\s5_launcher_gate_head.txt`; journal `check_already_green=40`, `deepseek_worker|candidate_judged=0`; `tools/tys_launcher.py:711-716` |
| 9 | **rejected candidate on disk with gate + output** | `freeze` + `evaluate_frozen` on a red in-scope candidate (`rej2`) | 0 (verdict `target_red`) | **GREEN** — `cand_rej2.json` holds `scored.gate = target_red` and the pytest tail; `rejections.jsonl` row `{gate: target_red, strike: 1}`, hash-chained (`prev "" → 57964dd9`) | `$PROBE\logs\s8b_rejection_stdout.txt`; `$PROBE\state\author\probe-fix-add\cand_rej2.*`; `$PROBE\state\author\rejections.jsonl`; `tools/tys_evaluator.py:867,1087,1242-1268` |
| 10 | **contract gate before dispatch** | `tys_runner.py next` on an item whose `acceptance_commands` is a shell string | 0 | **RED** — accepted and reserved; then `tys_launcher.py` **crashed** with `FileNotFoundError: [WinError 2]` | `$PROBE\logs\m1_next_malformed.txt`; `$PROBE\logs\m3_launcher_malformed.txt`; `tools/tys_launcher.py:149` (wrap), `:464` (unguarded `subprocess.run`) |
| 11 | **contract validator portability** | `tys_runner._dispatchable(item)` / `validate_contract(item)` under a non-repo root | — | **RED** — `dispatchable: False`; `ModuleNotFoundError: No module named 'continuous_loop'` swallowed by `except Exception` | `$PROBE\logs\v3_dispatchable.txt`; `tools/tys_runner.py:130-133,517` |
| 12 | **dry-run harness** | `tys_launcher.py --dry-run --max-cycles 3` | 0 | **GREEN** — 3 cycles, `reason: max_cycles`, 3 × `dry_run_cycle`, nothing outside `$PROBE` | `$PROBE\logs\s6a_launcher_dryrun_head.txt` |
| 13 | **`--per-session` as specified** | `tys_launcher.py --dry-run --max-cycles 3 --per-session 1` | 2 | **MISSING** — `error: unrecognized arguments: --per-session 1` (it is a `tys_runner dry-run` flag, not a launcher flag) | `$PROBE\logs\s6c_per_session_head.txt`; `tools/tys_launcher.py:828-835` |
| 14 | **defer semantics** | `tys_runner.py next` with `defer_until_cycle: 91`, queue `cycle: 92` | 0 | **RED** — deferred item selected and reserved at cycle 93 | `$PROBE\logs\v1_next.txt`; `tools/tys_runner.py:167-168` (`pool = ready or unblocked`) |
| 15 | **hang check** | all of the above | — | **GREEN** — no hang; slowest command 53.9 s (40 green-gate skips), all others < 5 s | `$PROBE\logs\s5_launcher_gate_head.txt` |

Summary: **8 GREEN, 5 RED, 1 MISSING, 1 structural red shared by 7/10/11/14.** The judge
(3–5, 9) is sound and its artifacts are honest. The chain that feeds it is where it breaks.

## The exact missing delta, per red link

**1 — author cannot derive a scope from an assertion failure.**
`derive` runs the check once, parses frames with three regexes (`tys_author.py:304-329`), and
drops every frame under `tests/` (`:341-364`). For `assert add(1,2) == 3` pytest prints one
frame — `tests\test_calc.py:5: AssertionError` — plus a `+ where -1 = add(1, 2)` call
expression. Nothing parses the `where` line, so the production file (`pkg/calc.py`) is never a
frame, `write_paths` is empty, and the answer is `scope_unproven`. The check sha is computed,
so the tamper pin is available; only the scope is not.
Delta: resolve the failing call expression in pytest's `Where`/short-tb section (callee name →
module → repo file via `_locate`) and keep the callee frame; or accept an explicit
`write_paths` hint from the item and verify those paths are the callee's.

**7 — a cycle cannot be completed by a process other than the one that reserved it.**
The lease is `{cycle, item, taken_ts, pid}` and `_lease()` (`tys_runner.py:287-306`) treats the
holder's pid as the liveness test; a dead pid clears the lease, so `cmd_complete` answers
`no lease held; nothing to complete` (exit 5, `:582-590`). Conversely any *live* pid — including
an unrelated process whose pid was recycled — is honoured. Demonstrated deterministically:
dead pid `999999999` → exit 5; live pid of the PowerShell host (32416) → exit 0
(`l1_dead_pid.txt`, `l2_live_pid.txt`). The module docstring advertises `next` / `complete` as
separate invocations, and a worker session is by definition a different process.
Delta: give the reservation an identity that survives the reserving process — a lease token
written into `cycle_handoff.json` and required by `complete --lease <token>` — and keep the pid
rule only as a crash *reaper*, never as the authorisation check. Without that, "the loop
survives a session dying" is false for every worker that is not a child of the launcher.

**10 — no contract gate on the dispatch path.**
`validate_contract` exists (`:508`) and `_dispatchable` (`:130`) uses it only to *rank* the
selection pool; nothing refuses dispatch on it. The launcher's own gate, `runnable()`
(`tys_launcher.py:172-177`), asks only whether the two lists are non-empty. A string
`acceptance_commands` therefore reserved cleanly, and then `task_contract` wrapped it into
`[["python -m pytest -q tests/test_calc.py"]]` (`:149`), `pre_run_red_gate` called
`subprocess.run(["python -m pytest -q tests/test_calc.py"])` (`:464`) and the launcher died with
`FileNotFoundError` — no journal row, heartbeat stuck at `state: starting`, lease left behind
with a live-looking pid.
Delta: (a) call `validate_contract(item)` in `_run_cycle` before the pre-run gate and treat a
non-empty result as `needs_author` with the problems attached (the machinery is already there at
`tys_runner.py:508`); (b) catch `OSError` in `pre_run_red_gate` and return `passed: False,
detail: could not start: …` instead of propagating; (c) write a journal row and a `stopped`
heartbeat in a `finally` around `_run_cycle`.

**11 — the validator (and therefore dispatchable-first ranking) only works inside this repo.**
`validate_contract` does `import continuous_loop` from `<ROOT>/scripts` (`:517`), a module that
exists only in the product repo. `_dispatchable` swallows the `ModuleNotFoundError` and returns
`False`, so under any other `NORTHSTAR_TY_ROOT` — the very redirection the tools document — every
item is silently non-dispatchable. `tys_runner dry-run` shows it directly:
`"dispatchable": false` for a fully specified item (`s6b_runner_dryrun_head.json`).
Delta: import the command policy by path from the tool's own directory (as `tys_evaluator` does
for `check_regression.py`, `:249-260`), or inject a policy object; and let `_dispatchable`
distinguish "refused" from "could not ask" instead of collapsing both to `False`.

**14 — `defer_until_cycle` does not defer.**
`select_next` computes `ready` and then `pool = ready or unblocked` (`:167-168`), so when the
deferred item is the only active row the fallback re-admits it. Observed: `defer_until_cycle 91`
with `cycle 92` → item reserved as cycle 93. This is also why the green-gate skip loop burns 40
attempts instead of waiting.
Delta: if `ready` is empty and `unblocked` is non-empty, return `None` with a reason
(`{"deferred_only": [...]}`) rather than the unblocked pool; let the caller decide to wait.

**13 — `--per-session` is not a launcher flag.**
`tys_runner dry-run --per-session` exists; the launcher's parser does not define it
(`tys_launcher.py:828-835`) and exits 2. Delta: either add `--per-session` to the launcher (and
thread it into the rotation decision at `tys_runner.py:CYCLES_PER_SESSION`) or correct the
criterion's command to `tys_runner.py dry-run --cycles 3 --per-session 1`.

## Loop economics observed (not a C3 gate, but the loop is what C3 grades)

- One launcher invocation against a permanently-green item: **40 acceptance runs in 53.9 s**,
  `cycles: 0`, `skips: 40`, reason `no_runnable_items`, and the queue `cycle` counter advanced
  49 → 89 (`s5_launcher_gate_head.txt`). `--max-cycles 1` does not bound this, because a skip
  decrements the cycle counter (`tys_launcher.py:895-899`).
- The item is never parked for being green, only deferred by 2 cycles, which link 14 makes inert.
- The handoff brief carries `"acceptance": ""` for an item whose `acceptance_commands` is fully
  specified (`s2_next_head.json`) — a worker session reading the brief is not told the check.
- `validate_result` does not compare `result["cycle"]` with the lease's cycle: a result file for
  cycle 1 completed a cycle reserved at 94 (`$PROBE\logs\v2_result.json` reused, exit 0).

## Fixture evidence index (`$PROBE\logs`)

`00_baseline_red.txt` (red check, exit 1) · `01_runner_status.txt` · `02_runner_next.txt` ·
`03_freeze_judge.json` (freeze + `evaluate_frozen` + `judge_cycle`) · `04_runner_complete.txt`
(exit 5) · `05_author_derive.txt` · `06_launcher_dry_per_session.txt` (exit 2) ·
`07_launcher_dryrun.txt` · `08_inprocess_chain*` · `09_launcher_green_gate.txt` ·
`10_validate_contract.txt` · `11_author_frames.txt` · `s1…s8*` (generation G1 sweep) ·
`v1…v3`, `l1`, `l2`, `m1…m3` (generation G2 re-verification).
Note: PowerShell `Tee-Object` writes UTF-16LE; read the `.txt` logs with `encoding='utf-16'`.

## Real-repo changes

**none.** `git status --short` at the start (422 entries) and after every probe (425 entries)
differs only by other lanes' work: `.gitleaks.toml`, `reports/ty/gitleaks_triage.json`,
`Northstar_backend/test_tys_generator.py`, `tools/tys_generator.py`, `tools/tys_probes.py`, and
the two tool files that stopped being `M` because commits `41fdceaf` / `603f73e7` landed.
(`state/continuous_loop_heartbeat.json`, `state/continuous_loop_state.json` and
`state/go_usage_ledger.jsonl` show as `M`, but they were already `M` in the baseline snapshot —
they are the running loop's own files, unchanged by this probe.) The only file this lane added is
`reports/ty/C3_PROBE.md`. No
entry mentions `c3probe`, `reports/ty/C3_PROBE.md` beyond this file, `state/tys_runner/` or
`reports/ty/autonomy_queue.json`. Every command ran with `NORTHSTAR_TY_ROOT` pointed at the
fixture, and `tys_runner.py status` reported `"ledger"` and `"queue"` paths inside it.
