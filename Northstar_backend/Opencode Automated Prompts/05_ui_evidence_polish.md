STATUS: PENDING

# BATCH 05 — Scout UI Evidence & Safety Polish

Prerequisite: Batches 01–04 complete and approved.

## Step 1 — Verify the Authorization Gate is still fully intact
- Confirm the Gate column and its four states (Authorized, Invoice Pending,
  Needs Review, Blocked) and precedence order (Blocked > Authorized > Invoice
  Pending > Needs Review > default Needs Review) still pass all tests.
- Confirm the earlier correction holds: an explicit `costco_cost_basis: "unavailable"`
  is Invoice Pending, but a completely absent/undefined record falls through to the
  conservative Needs Review default (never silently promoted to Invoice Pending).

## Step 2 — Resolve the Scout table column contract drift noted in Phase 0
- The Node test suite expects 12 columns (including Competition and Est. Monthly
  Sales) — confirm current code matches. If it doesn't, determine whether the test or
  the table markup is out of date and fix the mismatched side, preserving all existing
  working functionality (filters, sort, resizable columns, column-visibility toggles).

## Step 3 — BSR display honesty (uses Batch 04's data model)
- Wherever BSR is shown (table cell, detail dossier, or future comparison view),
  clearly distinguish benchmark-reference BSR from any future live-verified BSR.
- If BSR is `provider_not_supported` or `missing_live`, show that state honestly —
  never blank-as-zero, never silently omitted without explanation on hover/tooltip.

## Step 4 — Confirm no UI path can trigger a live call
- Audit any button, filter, or control added since the last UI audit to confirm none
  of them bypass the existing guarded live-provider flow (Proof Batch panel, live
  gates, approval tokens). Normal page loads and GET routes must remain zero-network.

## Step 5 — Tests and report
- Update/add assertions in `test_ui_display.cjs` for anything changed in Steps 2–4.
- Run: `node test_ui_display.cjs`
- Run the full Python suite once more to confirm nothing regressed:
  `python -m unittest discover -s . -p "test_*.py"`

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`06_master_brain_gateway_groundwork.md`, append history, stop for approval.
