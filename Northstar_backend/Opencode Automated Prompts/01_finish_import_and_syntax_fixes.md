STATUS: PENDING

# BATCH 01 — Finish Import & Syntax Fixes (Account Safety, Blocking Bugs)

Read `00_MASTER_INSTRUCTIONS.md` rules before starting. This batch fixes the bugs that
prevent modules from importing at all — nothing downstream can be trusted until these
are green.

If you already completed some of these steps in a prior session (check git status /
file contents to confirm), skip the already-done step, note it in the summary as
"already complete," and still run its test command to confirm.

## Step 1 — Restore `AmbiguousTransportError`
- Search the repo for every reference to `AmbiguousTransportError` (imports and usages).
- Determine the correct home for this class based on how `validation_run.py`,
  `dataforseo_adapter.py`, and `proof_batch_contracts.py` use `GuardError`,
  `BindingError`, and `RunAbort` today.
- Re-add `AmbiguousTransportError` with the same shape/interface the importing code expects
  (constructor args, base class, attributes read elsewhere).
- Fix every import site: `validation_run.py`, `test_compare.py`,
  `test_dataforseo_adapter.py`, `test_validation_run.py`.
- Do not change the existing behavior of `GuardError`, `BindingError`, or `RunAbort`.
- Run: `python -m unittest test_compare.py test_dataforseo_adapter.py test_validation_run.py -v`
- Record pass/fail counts.

## Step 2 — Fix `enrich_cached_asins.py:283` IndentationError
- Show the exact broken block (a few lines of context) before editing.
- Fix only the syntax. If the indentation error reveals an actual logic bug
  (e.g., a line that was supposed to be inside a conditional but isn't), flag it
  explicitly in the summary as a separate finding — do not silently "fix" the logic
  without calling it out.
- Run: `python -m unittest test_enrich_cached_asins.py test_enrich_manifest_runner.py -v`
- Record pass/fail counts.

## Step 3 — Fix `test_proof_batch_easyparser_adapter` `tearDownModule` error
- Identify the state-leak or cleanup bug causing the `tearDownModule` failure.
- Fix only the test isolation issue — do not touch the adapter's production logic
  unless the leak is caused by a real bug in the adapter itself (if so, flag it).
- Run: `python -m unittest test_proof_batch_easyparser_adapter.py -v`
- Record pass/fail counts.

## Step 4 — Consolidate the network-guard double-stub
- `test_network_guard.py` patches `requests.api.*` + `requests.sessions.Session.request`
  and raises `RuntimeError`. `test_brain_orchestrator.py:35` separately patches
  `requests.get`/`post` and raises `AssertionError`. These conflict.
- Create ONE real module, `network_guard.py`, exposing a single reusable guard
  (context manager or fixture) that raises one typed exception, e.g.
  `NetworkGuardViolation(RuntimeError)`.
- Update both `test_network_guard.py` and `test_brain_orchestrator.py` to import and
  use this single guard instead of maintaining separate ad hoc patches.
- The guard must still block 100% of real outbound HTTP calls during any offline test.
- Run: `python -m unittest test_network_guard.py test_brain_orchestrator.py -v`
- Record pass/fail counts.

## Step 5 — Confirm no regression across the whole suite
- Run the full suite once: `python -m unittest discover -s . -p "test_*.py"`
- Run: `node test_ui_display.cjs`
- Compare totals against the baseline in `00_STATE.json`
  (`python: 1022 ran / 29 failures / 6 errors / 1 skipped`, `node: 981/5/986`).
- You do NOT need all failures fixed yet — this batch only fixes the 6 import/collection
  errors plus the network-guard conflict. Confirm those specific failures are gone and
  no new failures were introduced.

## End of batch
Follow the STATUS update and stop-and-report instructions in `00_MASTER_INSTRUCTIONS.md`.
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`02_provider_safety_and_honesty.md`, append a history entry, and stop for approval.
