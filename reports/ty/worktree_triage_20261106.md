# Worktree triage — 2026-11-06

Owner decision: commit the outstanding work ("it might be good stuff"), keep what we do not need out of git.

## What was committed

`e4a56fb9` — **277 files** of source work from parallel sessions:
`Northstar_backend/`, `agents/`, `tools/`, `steward/`, `northstar-os-ui/`, `shared/`, `data/`,
`config/`, `scripts/`, `docs/`, `tests/`, plus the `.gitignore` rules below.
Rollback tag: `pre-worktree-triage`.

## What was deliberately kept out of git (still on disk)

Added to `.gitignore` so a candidate freeze stops carrying megabytes of generated output:

```
exports/             464 MB build zip + 406 MB audio tree + repo dumps
out_lions_mane/  out_sb/
tmp-patterns/  tmp-probe/
screenshots by ty/   review videos (129 MB)
*.mp4  *.m4a  *.zip
state/               runtime: queue, ledger, checkpoints, evidence, candidates
research/            re-derivable sweep dumps (780 files)
Downloads/           loose documents
```

Nothing was deleted. Any of these can be committed by removing its line and staging the path.

## What was BLOCKED, and why it matters

`reports/` (2,130 files) was staged and **refused by the pre-commit secret scanner: 290 findings**.
That is not housekeeping noise to bulldoze — reports from agent sessions frequently contain pasted
tokens, sample keys, JWTs from tests, or connection strings. Committing them would put whatever is
real into history permanently.

Left staged-out and untracked. The correct next step is a review pass:

1. run the scanner per file to get the rule and the match for each finding;
2. classify each as false positive (test key, example, hash) vs real credential;
3. allowlist the false positives in `.gitleaks.toml` with a comment saying why;
4. for anything real: rotate it (owner action) and redact the file before committing;
5. only then commit `reports/`.

Until that pass, `reports/ty/*` (the programme's own log, queue, digests) remains tracked and keeps
working; the historic bulk stays on disk untracked.

## Effect on the loop

- Freeze size: **94 MB → 52 MB**. Still large because 44 tracked files remain modified (renders,
  report updates) — those are next cycle's job, not this one.
- The evaluator's `out_of_scope` refusals caused by other lanes' dirty test files are now much
  rarer: the 403 test/policy paths that blocked every candidate are no longer dirty in the working
  tree.
- `state/` being ignored also removes `state/tys_runner/*` from the untracked set, which A13's design
  named as a reason the ledger must live under `state/author/`.

## Remaining

416 status entries: 44 modified tracked files, ~370 others, 2,270 untracked report files.
Next units in order: the gitleaks review above, the 44 modified tracked files, then `A13` → `A16`.
