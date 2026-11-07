# Session resume — 2026-11-07 (handoff #3: A13 + A16 landed, the gate is measuring)

A fresh session can continue from this file alone. Nothing here needs the previous chat.

## Where the programme stands

**All 17 automation units A1–A17 are done.** A18–A21 (the M3 intelligence plane) are
still todo and now sit at the front of the ordered queue.

| unit | commit | what it actually does |
|---|---|---|
| A13 `M1e-rejections` | `41fdceaf` | material fingerprint ledger, hash-chained strikes, park on the third |
| A16 `M2-work-generator` | `9d6bb3b4` | T0–T5 ladder, honest starvation, dedupe, supply brakes |
| A16 deltas 1/2/4 | `8230b730` | next refills, complete tops up, watchdog backs off on starvation |
| A16 delta 3 + dry-run | `603f73e7` | dispatchable-first ordering; dry-run obeys depends_on/defer |
| queue integrity | `6158c001` | 34 product items had `depends_on: null` — the no-skipping rule had holes |
| C3 probe fixes | `896b7aaa` `ebaa13d9` `66f7c952` `9cd8a12a` | see below |

Verification (real output):

```
python -m pytest -q Northstar_backend/test_tys_generator.py test_tys_rejections.py \
  test_tys_evaluator.py test_tys_runner.py test_tys_launcher.py test_tys_author.py
-> 161 passed in 30.5s
```

## What each new piece does, in one paragraph

**A13 — rejection ledger.** `state/author/rejections.jsonl`, append-only, hash-chained.
The fingerprint is over *material*: sorted casefolded `write_paths`, ordered
`acceptance_commands`, `check_sha256`, and the diff reduced to
path/status/added/removed/context with every line number and `@@` offset dropped. So a
reflowed, rebased or one-line-shifted patch is the same attempt and cannot buy a retry.
Three rejections in one trailing run of the same gate flip the item to `needs_author`
with a `parked_signature`; only a change to the material contract revives it. Artifact
gates never count. `reconcile_parks` runs in `cmd_next` (apply), `cmd_complete` (eager,
before `mark`) and `cmd_status` (report only).

**A16 — work generator.** `tools/tys_generator.py` + `tools/tys_probes.py`. Strict
T0→T5 ladder, one item per call, fixed priority bands, 12-active / 24-per-day brakes.
"Never empty" is deliberately amended to "never empty without saying exactly why": all
tiers green and non-vacuous returns `starvation` with a per-tier record of numbers and
writes nothing. A scanner that reports zero findings from zero files is itself a
finding. Dedupe keys across every status; `needs_author` promoted in place; `done`
reopened at most twice; a deleted key gets one re-emit then `deleted twice`.

## The five defects the C3 probe found (report: `reports/ty/C3_PROBE.md`)

1. **No contract gate on dispatch.** A shell-string `acceptance_commands` passed
   `runnable()` (two non-empty lists) and killed the launcher with `FileNotFoundError`
   in the pre-run gate. `validate_contract` is now a dispatch gate; `pre_run_red_gate`
   catches `OSError`; the skip is journalled as `skipped_invalid_contract`.
2. **The command policy was loaded from the state root.** `import continuous_loop`
   after a module-level `sys.path` insert bound it to whichever root was current at
   first import. Under a redirected `NORTHSTAR_TY_ROOT` it failed, `_dispatchable`
   swallowed the error and returned False, so every item was silently
   non-dispatchable. Now loaded by path from `CODE_ROOT` (`Path(__file__).parents[1]`).
3. **A reservation could not be completed by another process.** The lease's pid was
   the authorisation, so a worker in its own process looked like a stranger (exit 5)
   and a recycled pid looked authorised. `_take_lease` now returns a token, the brief
   carries it, and `complete --token` honours it. The pid stays the liveness test for
   `next`.
4. **`--per-session` did not exist on the launcher** although the gate's own C2
   command passes it; and `--dry-run` never completed a cycle, so it could never show
   the 3 rotations C2 asks for.
5. **A shipped cycle was never committed.** The loop judged, accepted, marked done,
   and left the bytes in the worktree. `commit_shipped` now stages exactly the
   declared `write_paths`, re-checks them against
   `continuous_loop.validate_commit_paths`, commits and tags `autonomy-cycle-NN`.

Plus, found by the first real dispatch: the scope gate checked `forbidden_reason`
**before** `attributable()`, so 40 pre-existing dirty test files (other lanes' work)
were reported as the candidate's edit and every cycle was refused `out_of_scope`
after a 23-minute worker run. Split into `policy_reason` (never excused) and
`test_reason` (excused by the dispatch snapshot); order is policy → pre_changed →
test → scope (`9cd8a12a`).

## Two things that are by design, not defects

- `defer_until_cycle` is soft (`pool = ready or unblocked`). That is why every hard
  stop is a status change: a deferral alone would be re-admitted on the next cycle.
- The author lane cannot derive a scope from a test-only traceback. That is the A10
  verdict: authoring stays human/DeepSeek; the loop is detect → scope → check →
  park → refill.

## Gate acceptance (C1–C7): final state

| # | claim | state |
|---|---|---|
| C1 | status coherent; killed holder recovered by pid | **green** — `status` reports lease/caps/next/parks; `test_crash_recovery_keeps_the_reserved_item`; a dead-pid lease is reclaimed and a live token completes |
| C2 | 9 cycles / 3 rotations / no stray writes | **green** — measured on a redirected root: exit 0, `cycles 9`, 3 `session_ended` rows, real repo clean |
| C3 | author → candidate → evaluator → acceptance → commit | **green** — cycle 45 shipped `T1-scan-files-scanned` unattended: red check → 38 s worker → five gates → live drift → commit `1f6e0e89`, tag `autonomy-cycle-45`, 25,789 tokens. Rejected candidates before it are on disk with their gate and detail (`state/author/W10-scanner-csv/cand_0044.json`, `rejections.jsonl`) |
| C4 | already-green → `check_already_green`, never a ship | **green** — and it parks the item, because soft deferral re-admitted it (measured: 40 acceptance runs in 54 s) |
| C5 | watchdog restarts a killed launcher | **green** — `started launcher pid=9452`, killed, `started launcher pid=3668` five seconds later |
| C6 | 8-hour unattended, ≥3 shipped | **soak running; diagnosis written** — one bundle shipped, and the *C6 supply diagnosis* in `AUTOMATION_GATE.md` names every remaining item and the check it lacks |
| C7 | every refusal logged with its reason | **green** — `launcher.jsonl`: `skipped_not_runnable`, `skipped_invalid_contract`, `check_already_green`, `targets_dirty`, `commit_refused`, `reverted_bytes`; `sessions.jsonl`: `starvation` with the generator's per-tier numbers |

Verification: `164 passed in 31.5s` across the seven gate-surface test files.

## The one honest caveat

The loop is finished. The *work* is not. Every remaining queue item has an
acceptance command that either points at a path that does not exist or at a suite
that is already green, and a green check cannot prove a patch. Making the soak
produce bundles needs authored checks — a perf assertion, a bug reproduction, a
bundle-size assertion — not more loop engineering.

## Numbers worth knowing before the soak

- One real worker cycle: **23.5 minutes, 127,914 tokens** (measured, `session_v2`).
  The daily cap is 3,000,000 tokens, so ~22 cycles/day. The 90 % cap check means ~20.
- Disk free at 08:30: **11.02 GB** (GPU/download work pauses below 10 GB).
- `tys_runner.py status` → `next` is product work; the automation dependency gate has
  opened, so nothing is blocked by A9–A17 any more.

## Next moves, in order

1. Finish C3: let the re-dispatch run to a shipped commit; confirm the rejection
   ledger has the earlier `out_of_scope` row on disk with its gate and detail.
2. C5: start `scripts/tys-watchdog.ps1`, kill the launcher, confirm a restart line in
   `logs/tys_watchdog.log`.
3. C6: run the watchdog for 8 hours with `--max-hours 8`; count shipped bundles from
   `state/tys_runner/launcher.jsonl` (`candidate_judged` with `ok: true` and a
   `commit`), and record any starvation with its reason.
4. Then A18–A21 (M3 intel) and product/perf work, which is now dispatchable:
   W10 scanner p95 6.6 s, lanes/status 418 ms, 1,088 kB entry bundle, X-Env default.

## Security item still open (operator action, not a code task)

`reports/ty/GITLEAKS_TRIAGE.md`: three real credentials are already committed in two
tracked root-level chat exports (`SCAVIO_API_KEY`, `BRIGHTDATA_API_KEY`, a GitHub
PAT) — under commits `a299d6e9` and `21aed4e3`. Rotation is the operator's; deletion
alone is insufficient because the values are in history. `.gitleaks.toml` now
allowlists only the two Walmart page-JS sources (326 → 156 findings, zero real
findings masked) and `reports/` is no longer blocked.
