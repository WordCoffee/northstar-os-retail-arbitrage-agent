# Handoff

## Goal

Close the weekly ops digest for run-2026-10-27-a by assembling a single digest from local evidence only, with no invented numbers and every gap explicitly named.

## Decisions

- Evidence is read exclusively from the local `evidence/` directory, and no live calls are made during assembly.
- Any missing number is reported as missing rather than estimated, so the digest stays faithful to the source data.
- Publishing is handled by the ops owner, and publishing does not require a separate approval step.

## Evidence

- `evidence/ops_week_41.json` is complete and contains all expected fields for the digest.
- `evidence/ops_week_42.json` is present but the `renders_completed` field is missing, so that value is reported as missing.
- The digest draft is written to `digest_week_41_42.md` once assembly is complete.

## Next step

Resume at the digest assembly step and do not re-collect evidence that is already present in the workspace.

## Known unknowns

- The render worker was offline all week, so the real `renders_completed` count is unknown and remains reported as missing.
