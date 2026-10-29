# Handoff

## Goal

Close the weekly ops digest for run-2026-10-27-a: one digest assembled from local evidence, no invented numbers, every gap named.

## Decisions

- Evidence is read from `evidence/` only; no live calls.
- A missing number is reported as missing, never estimated.
- TODO: decide who publishes, and whether publishing needs an approval.

## Evidence

- `evidence/ops_week_41.json` - complete
- `evidence/ops_week_42.json` - `renders_completed` missing
- TODO: add the digest draft path once written

## Next step

Resume at the digest assembly step. Do not re-collect what is already here.

## Known unknowns

- The render worker was offline all week; the real count is unknown.
