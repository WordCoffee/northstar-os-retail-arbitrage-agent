# Item 5 — promotion record: REFUSED

Run 2026-11-09, worktree `state/worktrees/item5`, branch `ty/item5`.
`python tools/promote_staging.py --check` against the real repo. Nothing was merged, no tag
was created, `main` stayed at `ecef24a7`.

| gate | result | evidence |
|---|---|---|
| 1 suite | **FAIL** `suite_stale` | `_fullsuite_final_20261108.txt` is green (7067 passed, 117 skipped, 2 xfailed, 0 failed) and its ids reconcile 7186 = 7186, `_idlist_full_20261108.txt` vs `_idlist_20261107.txt` -> 450 added, 0 removed. But the run was written 2026-11-09T00:52:29 and the newest `staging` commit is 2026-11-09T01:00:14, so the run predates the two commits that landed after it. |
| 2 verifier | **FAIL** `verifier_failed_unit_in_bundle` | `reports/ty/d15_verification.md`: 17 agree, 2 FAILED, 1 BLOCKED. `verifier_findings.json` lists open FAILED units **D17** and **V9**; both are in the bundle (D17: 20ccd103, 93682edc, 1b53c526, 41b000bc, b70fab7a; V9: 0d0241c7, 22fd9069, 0abf3944). BLOCKED V3 is also in the bundle (52 commits) and is reported, not refused, because it is blocked rather than failed. |
| 3 bundle | **FAIL** `bundle_visual` | `main..staging` is 1151 commits / 9735 changed paths, of which **262** are visual or creative under `northstar-os-ui/src/` (e.g. `App.jsx`, the galactic asset set). 570 images changed. |

Verdict: `REFUSED -- gate 'suite', gate 'verifier', gate 'bundle'`.

A pending full-suite run is the only thing in the way of gate 1, and a fresh run on the current
`staging` head is what clears it. Gate 2 cannot be cleared by a document: D17 and V9 must be
fixed or moved out of the bundle. Gate 3 is a human look: the pack is
`reports/ty/staging_review_20261109.md`.

When all three are green:

```
python tools/promote_staging.py --promote --verifier "<session that reproduced the deltas>" \
    --approve-visual "<what was looked at and accepted>"
```

That tags `rollback/<date>-<main-sha>`, merges `--no-ff`, tags `promote/<date>-<staging-sha>`,
and prints the new `main` sha. To undo a promotion: `python tools/promote_staging.py --revert promote/<date>-<sha>`.

## Tests

```
python -m pytest Northstar_backend/test_promote_staging.py -q
16 passed in 10.08s
```

Each gate is tested refusing on its own (stale run, red run, FAILED unit in the bundle, visual
path in the bundle), the eligible case produces a `promote/` tag and a two-parent merge commit,
and `--revert` is a no-op when the tag is absent. All fixtures are scratch repos under `tmp_path`.
