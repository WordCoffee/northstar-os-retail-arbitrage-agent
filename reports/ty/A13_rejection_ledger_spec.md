# A13 — rejection ledger: build spec (condensed from the design lane)

Depends on: A11 (evaluator), A12 (freeze/replay), **A12b (launcher seam)**. Queue entry
`M1e-rejections` was amended: `write_paths` now includes `Northstar_backend/test_tys_rejections.py`
and it carries three acceptance commands (repo-root relative — `_gate_target` runs argv with
`cwd=repo` and ignores `contract["cwd"]`).

## Fingerprint (what makes two attempts "the same")

`attempt_fingerprint = sha256({"v":1,"item":item_id,"sig":attempt_signature(contract),"files":patch_identity(diff_bytes)})`

- `sig` = sha256 over **material only**: sorted casefolded `write_paths`, `acceptance_commands`
  (order preserved), `check_sha256`.
- `files` = per file: `path`, first letter of `status`, ordered `added`, ordered `removed`, ordered
  `context`. Line numbers and `@@` offsets are dropped on purpose.
- Normalisation is narrow: drop `\r`, rstrip trailing spaces. **Keep** indentation and blank lines.
- **Not** hashed: `diff_sha256`, `candidate_id`, `frozen_at`, `pre_changed`, `objective`,
  `timeout_s`, `model`, verdict detail, and **the gate** (the gate is a second dimension, stored on
  the row and used for strikes).

## Store

`state/author/rejections.jsonl` (already gitignored via A12, so no `.gitignore` edit and it can never
trip the scope gate). Append-only, one row per line, `flush` + `fsync`, hash-chained via `prev` /
`row_sha256`. `load_rejections` drops a torn tail and any row whose hash fails, and reports
`torn` / `corrupt` / `chain_broken_at`. Never rewrite; never trust a stored `strike`.

Row: `schema, at, item_id, candidate_id, cycle, gate, fingerprint, signature, diff_sha256, artifact,
payload_sha256, strike, detail, prev, row_sha256`.

## Three-strike rule

- A row is written only when: verdict not ok, gate in the five real gates, the artifact was frozen and
  seal-verified, and no row exists yet for `(item_id, candidate_id)`. Never for artifact gates
  (`artifact_missing/invalid/tampered`, `already_scored`) or pre-run skips.
- `rejection_streak(item_id, signature)` = 1 + trailing run of rows with the **newest row's gate**.
  So `target_red, target_red, out_of_scope` = 1 (a different gate resets). Derived on demand, never
  accumulated.
- At `STRIKE_LIMIT = 3` the item leaves ACTIVE: status `needs_author` (the *status*, not just the
  field), plus `needs_author: "rejection_cap:<gate> x<n>"`, `parked_signature`, `parked_cycle`, and
  `defer_until_cycle = None`.
- Written twice: eagerly in `cmd_complete` (before `mark`) and repaired by `reconcile_parks()` at the
  top of `cmd_next` — so a crash between evaluation and completion still parks.
- Revival is a **signature change only** (`write_paths` / `acceptance_commands` / `check_sha256`).
  Rewriting the identical contract or bumping `contract_written_at` must NOT un-park.
- `defer_until_cycle` and strikes never touch each other: strikes read only the ledger; deferral is
  written on every non-shipped cycle; `select_next`'s `pool = ready or unblocked` makes deferral soft,
  which is exactly why the stop has to be a status change.

## Query seam

Inside `evaluate_frozen`, between the `already_scored` block and `verdict = evaluate(...)`:
bind `diff_bytes` once, call `duplicate_rejection(...)`; on a hit write `scored` with gate
`duplicate_rejection` (so a second call returns `already_scored`) and return without running checks.
After `evaluate`, if not ok and the gate is real, `record_rejection(...)` and attach it to the verdict.
The launcher needs **no** edit; it already calls `evaluate_frozen` after A12b.

## New surface

`tools/tys_evaluator.py`: `STRIKE_LIMIT`, `REJECTION_SCHEMA`, `rejections_path`, `row_sha256`,
`load_rejections`, `duplicate_rejection`, `record_rejection`, `rejection_streak`, `attempt_signature`,
`patch_identity`, `attempt_fingerprint`.
`tools/tys_runner.py`: `reconcile_parks(queue=None, *, apply=False, repo=None)` — lazy import, `repo`
defaults to `ROOT` at call time so the test fixture works; called from `cmd_next`, `cmd_complete`, and
`cmd_status` with `apply=False`.

## Tests (`Northstar_backend/test_tys_rejections.py`)

1 identical diff twice → `duplicate_rejection`, runner calls did not grow · 2 CRLF/reflow/base-shift →
same fingerprint · 3 different line → allowed, command runs · 4 three distinct `target_red` → strikes 3,
parked, `select_next` skips · 5 `target_red,target_red,out_of_scope` → 1, not parked · 6 torn tail →
1 record, append still works · 7 parked item never reaches the worker · 8 changed contract revives ·
9 a deferral does not change the count · 10 queue item signature == frozen contract signature ·
11 artifact gates never count · 12 duplicate scored once · 13 differing `check_sha256` → different sig.

## Hard dependencies to check first

- A12b must have landed: the launcher must call `freeze`/`evaluate_frozen`, and `task_contract` must
  pass `check_sha256` through (otherwise the tamper gate is silently disabled).
- `pre_changed_source` must be `"dispatch"`; the `freeze-observed` fallback records other lanes'
  edits as pre-existing and must be visible in the log line, not assumed away.
