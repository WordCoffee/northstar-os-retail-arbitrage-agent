# NORTHSTAR MASTER BRAIN — MASTER TASK RUNNER

You are OpenCode operating inside the Northstar OS Retail Arbitrage Agent repository
for T2 Holdings LLC. This folder (`opencode-tasks/`) is your persistent work queue.

## READ THIS FILE FIRST, EVERY SESSION, BEFORE DOING ANYTHING ELSE.

## How this system works

1. This folder contains numbered batch files: `01_....md`, `02_....md`, `03_....md`, etc.
2. `00_STATE.json` (in this same folder) tracks which batch is next and which are done.
3. On load:
   - Read `00_STATE.json`.
   - Find the batch file matching `"next_batch"`.
   - Read that ENTIRE batch file before doing anything.
   - Execute ONLY the steps in that one batch file, in order.
   - Do not open, read, or execute any other batch file in the same session.
4. After finishing every step in the current batch file:
   - Update `00_STATE.json`:
     - Move the just-completed batch's ID from `"next_batch"` into `"completed_batches"`.
     - Set `"next_batch"` to the following batch's filename.
     - Set `"last_updated"` to the current timestamp.
     - Append a short entry to `"history"` summarizing what happened (files changed, test results, blockers).
   - Mark the batch file itself as done by adding a line at the very top:
     `STATUS: COMPLETE — <timestamp>`
   - Print a stop-and-report summary in this exact shape:

     ```
     ===== BATCH COMPLETE: <batch filename> =====
     Steps completed: <N>/<N>
     Files changed: <list>
     Tests run: <commands>
     Test results: <pass/fail/error counts, before vs after>
     Blockers / decisions needed from operator: <list or "none">
     Protected files touched: <list or "none">
     Live network calls made: <yes/no — must always be "no" unless the batch file explicitly says LIVE AUTHORIZED>
     ===== STOPPING. Waiting for operator to type APPROVE to continue. =====
     ```

5. STOP COMPLETELY after printing that summary. Do not start the next batch file.
   Do not read ahead. Wait for the operator to type exactly: `APPROVE`
   (or give corrective instructions instead — in that case, follow the correction,
   re-run the current batch's affected steps, and re-print the stop summary).

6. When the operator types `APPROVE`, re-read `00_STATE.json` to get the new
   `"next_batch"` value, open that file, and repeat from step 3.

## Non-negotiable global rules (apply to every batch, no exceptions)

- Evidence discipline: classify data as User-Provided, Benchmark/Reference,
  Cached/Historical, Live-Verified, Invoice-Confirmed, Derived, Hypothetical, or Unknown.
  Never invent prices, BSR, UPC, sellers, fees, sales, pack sizes, or invoice status.
  Missing data stays null/Unknown — never zero, never a guessed default.
- Live providers are OFF by default. Do not make any live network/API call unless
  the current batch file contains the literal phrase `LIVE AUTHORIZED` for that
  specific step, AND the operator has typed `APPROVE` for that specific batch.
- You can write to env file when given a command to do so. 
- Protected files — do not modify without the current batch file explicitly naming
  the exact file and explaining why: `finance.py`, `pricing.py`, `product_analysis.py`,
  `fee_engine.py`, any CSV/benchmark/cache/catalog/manifest data file, anything under
  `data/costco-discovery-runs/`, `data/benchmarks/`, `data/validation-runs/`.
- Always inspect before editing. Always propose a smallest-safe-diff plan before
  writing code, inside your own response (not required to pause for approval mid-batch
  unless the step says so — batch-level stopping is the checkpoint).
- Every behavior change must ship with an offline test. Run only offline test commands.
  Never run `test_scavio.py` or any other documented live-only test entrypoint.
- If a step is ambiguous, contradictory, or requires a judgment call that could affect
  data honesty, account safety, or spend — do NOT guess. Stop early, note it under
  "Blockers / decisions needed from operator" in that batch's summary, and skip only
  that sub-step (complete the rest of the batch if independent).

## Batch index (for reference only — do not read ahead)

- 01_finish_import_and_syntax_fixes.md
- 02_provider_safety_and_honesty.md
- 03_remaining_test_failures.md
- 04_bsr_and_comparison_engine.md
- 05_ui_evidence_polish.md
- 06_master_brain_gateway_groundwork.md
- 07_docs_and_runbook.md
- 08_costco_client_honesty_audit.md
- 09_costco_credential_diagnostic.md
- 10_costco_single_item_retry_LIVE.md
- 11_costco_full_run_and_mapping_audit_LIVE.md

End of master instructions. Proceed to read `00_STATE.json` now.
