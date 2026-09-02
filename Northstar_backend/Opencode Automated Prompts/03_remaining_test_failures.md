STATUS: PENDING

# BATCH 03 — Remaining Test Failures & Protected-Artifact Integrity Check

Prerequisite: Batches 01–02 complete and approved.

## Step 1 — Investigate `proof_batch` protected-artifact byte-identity failures (careful — read fully before acting)
- There are 3 failing assertions comparing protected artifacts byte-for-byte, plus the
  tearDown issue (should already be fixed in Batch 01, confirm here).
- For each failing assertion: compute a hash/diff between the current file on disk and
  the value the test expects. Show this evidence BEFORE deciding anything.
- Two possible outcomes:
  a) A protected file actually changed unexpectedly. If so: STOP immediately, do not
     "fix" it by reverting or editing anything, and report this as a critical finding
     under "Blockers / decisions needed from operator." This could indicate an
     unauthorized or accidental modification and needs a human decision.
  b) The test's stored baseline/fixture is stale (e.g., benchmark data was legitimately
     updated in an earlier approved session and the fixture wasn't refreshed). If so,
     update ONLY the test fixture/baseline, never production code or protected data.
- Run: `python -m unittest test_proof_batch_run.py test_proof_batch_easyparser_adapter.py test_proof_batch.py -v`

## Step 2 — Resolve `test_provider_switch` failures (4)
Failing: `test_offers_honest_gaps`, `test_rapidapi_mode_maps`,
`test_missing_key_returns_gap_not_raises`, `test_parse_bsr_variants`.

- For each failure, determine: is the TEST describing correct honest behavior that the
  CODE violates, or is the TEST asserting outdated/incorrect behavior?
- Do not simply edit assertions to force a pass. If the code is wrong, fix the code.
  If the test is outdated, fix the test — but explain why in your response.
- Pay special attention to `test_missing_key_returns_gap_not_raises`: a missing API key
  must produce an honest "gap" result, never a raised exception that could crash a
  caller, and never a silently fabricated value.
- Run: `python -m unittest test_provider_switch.py -v`

## Step 3 — Resolve remaining `test_offer_enrichment` failures
- After Batch 02's fixes, re-run: `python -m unittest test_offer_enrichment.py -v`
- For each still-failing case, apply the same "test vs. contract" judgment as Step 2.
- List every failure you could NOT confidently resolve without an operator decision —
  do not guess on data-honesty-relevant contract questions.

## Step 4 — Costco skip confirmation (no action needed, just confirm)
- Confirm the 1 skipped test (`COSTCO_CSV_PATH` unset) is still correctly skipping for
  the documented reason and is not masking a real failure.

## Step 5 — Full suite check
- `python -m unittest discover -s . -p "test_*.py"`
- `node test_ui_display.cjs`
- Report final counts. At this point Python failures/errors should be at or very near
  zero (excluding the intentionally-excluded `test_scavio.py`). If anything remains
  unresolved, list it explicitly with your recommended interpretation — do not hide it.

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`04_bsr_and_comparison_engine.md`, append history, stop for approval.
