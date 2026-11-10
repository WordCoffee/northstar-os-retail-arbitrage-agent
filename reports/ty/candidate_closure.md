# Whole-candidate closure: the four gates, measured

Asked: *once gitleaks is clean, test promoting the full green staging candidate as one closure
(collect-only, imports, full suite on a temp worktree of main plus candidate) instead of the remaining
slices, and report.*

Candidate `staging-candidate/20261109-2142` (`ac52736b`) onto `main` (`ef9cad1d`).

## What the gates said

| gate | result |
|---|---|
| **collect-only** | **7,465 tests collected, 0 errors, 21 s** — main + the candidate tree is coherent, where main alone could not collect at all (4 then 8 `ModuleNotFoundError`s) |
| **gitleaks, whole tracked tree** | **14,526 tracked files, 5 findings** — all five are the known credentials in the two chat exports (1143, 1148, 1291, 1296 and 7852). Nothing else in the tree carries one |
| **gitleaks, staged delta** (first attempt) | 0 findings — **wrong question**: the exports are already in `main`, so staging the candidate produced no diff for them and the scan reported a clean tree that still contained five credentials |
| **full suite** | **31 failed, 7,307 passed** — every one a UI-serving test (`test_ui_assets_served`, 404s), because `northstar-os-ui/dist` is gitignored and a fresh worktree has no bundle. Not a regression: the same candidate with a built bundle passed **7,346, 0 failed** |

The gate now builds the UI before the suite, and the gitleaks step scans content rather than the
delta, so both false signals are closed.

## What this establishes

1. **Whole-tree promotion solves the problem slice promotion created.** A slice is a set of paths;
   the code it needs lives in other slices. The candidate tree is green *as a tree*, and main + that
   tree collects every one of its 7,465 tests with no missing module.
2. **The only thing between this candidate and a clean gate is the credentials.** 5 findings, all
   known, all in `DIR-1a/b/c`. Once they are rotated and the exports removed (owner action, then
   `tools/retire_chat_exports.py --retire`), the same gate should read 0.
3. **The suite leg is now trustworthy.** Building the bundle first removes the 31-failure noise; the
   candidate's own suite result (7,346 green) is the number to expect in the worktree.

## Not done here

- **No promotion.** `promote_candidate.py` gates and reports; it does not move `main`. A whole-tree
  promotion is a bigger act than a slice promotion and it is the owner's call.
- **The history rewrite.** Removing the files does not remove them from a public remote. That needs
  a force-push of a rewritten `main` or a GitHub purge — see `reports/ty/secret_exposure_report.md`.

## Reproduce

```
python tools/promote_candidate.py --ref staging-candidate/20261109-2142
```
Writes `reports/ty/candidate_closure.json` as it goes, so a stalled leg is visible rather than silent.
