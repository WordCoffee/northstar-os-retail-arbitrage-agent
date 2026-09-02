STATUS: PENDING

# BATCH 07 — Documentation & Operator Runbook

Prerequisite: Batches 01–06 complete and approved.

## Step 1 — Create/update `OPERATIONS_RUNBOOK.md`
Place at the `Northstar_backend/` root. Cover, concisely (reference `AGENTS.md` for
anything already documented there instead of repeating it):
- How to run the app locally.
- How to run the full offline test suite (Python + Node commands).
- How live gates work and which env var NAMES they require (never values).
- How the Authorization Gate states are defined and what each means for an operator.
- How the BSR/comparison evidence model works (from Batch 04).
- The exact procedure for any future live provider run:
  preflight → freeze manifest → authorize → execute (bounded, zero retries) →
  retrieve → report, matching the pattern already used for the DataForSEO and Costco
  discovery runs.
- An explicit "Never do this" list: no live calls in tests, no secret exposure, no
  purchase-authorization inference, no silent retries, no defaulting missing evidence
  to a specific value.

## Step 2 — Provider Readiness Matrix doc
- Produce a short reference table (can live inside the runbook or as a separate file):
  provider | required env var names | live gate flag | known failure modes |
  test coverage present (Y/N).
- Include Costco/Unwrangle, Easyparser, DataForSEO, Bright Data, Chocodata, Scavio,
  Canopy.

## Step 3 — Cleanup pass (low risk, do last)
- Remove or archive the flagged dead dev files from Phase 0
  (`debug2.py`, `debug3.py`, `debug_budget.py`, `debug_compare.py`, `fix2.py`,
  `fix_budget.py`, `outfile.txt`, `output.txt`, `test_out.txt`, `server.log`,
  `server2.log`) — confirm none are imported or referenced anywhere first.
- Consolidate `bright_data_client.py` vs `brightdata_client.py` into a single
  implementation; update all import sites; confirm tests still pass.

## Step 4 — Full suite re-run
- `python -m unittest discover -s . -p "test_*.py"`
- `node test_ui_display.cjs`
- Confirm the cleanup pass introduced zero regressions.

## Step 5 — Final consolidated report for the whole repo-hardening arc (Batches 01–07)
- Compare final test totals against the very original baseline in `00_STATE.json`.
- List every file changed across all 7 batches, grouped by batch number.
- Confirm no protected file was modified anywhere in this arc except where explicitly
  approved (Batch 03, Step 1 scenario, if it occurred).
- State clearly: "Repository hardening arc complete. Ready to proceed to Costco
  live-readiness batches (08–11) pending operator approval."

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`08_costco_client_honesty_audit.md`, append history, stop for approval.
