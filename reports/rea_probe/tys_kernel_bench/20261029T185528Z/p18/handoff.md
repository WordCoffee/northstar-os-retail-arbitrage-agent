# Handoff

## Goal

Close the weekly ops digest for run-2026-10-27-a by assembling one digest from local evidence only, with no invented numbers and every gap explicitly named. The handoff must let a fresh session resume without re-collecting data that is already present in the workspace.

## Decisions

- Evidence is read from `evidence/` only; no live calls are made during assembly.
- A missing number is reported as missing, never estimated or back-filled from memory.
- Publishing is handled by the ops lead, and publishing requires a single approval before release.
- The digest draft is written to `digest_week_42.md` once assembly completes.

## Evidence

- `evidence/ops_week_41.json` is complete and contains all required fields.
- `evidence/ops_week_42.json` is present but `renders_completed` is missing, so that field is reported as missing in the digest.
- The render worker was offline all week, which explains why the real render count is unknown.
- No other evidence files are required for this run.

## Next step

Resume at the digest assembly step by reading the two evidence files and writing `digest_week_42.md`. Do not re-collect what is already here, and verify the digest before marking the run complete.
