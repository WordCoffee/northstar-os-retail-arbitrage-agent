# Git history rewrite — PLAN ONLY (owner review; NOT executed)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Status:** **DEFERRED / PLAN ONLY.** No rewrite, no history mutation, no force-push has been performed. This document is the deliverable for owner review (directive item #3).
- **Security scan state (standing line):** **0 new / 0 known-active (baseline empty) / 231 allowlisted** — scan exit 0.
- **Context:** rotated credential values were recorded owner-confirmed (2026-10-11) and are dead; the old values remain in git history only (historical exposure, not live credentials).

## Preconditions (all required before any execution)

1. **Owner approval for the rewrite** — and a **separate explicit approval before any force-push** (protected-branch rule: no remote op on `main`/`release/*`/`hotfix/*` without fresh approval; this plan grants nothing).
2. **Parallel-session coordination:** the parallel session commits or stashes its local changes first (currently: uncommitted `opencode.jsonc` permission-insert in the main checkout — its owner's call), and both sessions **pause pushes** for the rewrite window. Any local-only commits made after the rewrite would otherwise be lost/conflicting.
3. **Backup first:** fresh `git clone --mirror` snapshot of the repo, stored **offline** under operator custody; restore verified by test-cloning from the mirror before anything else is rewritten.
4. **Replacement list:** exact byte-strings of the dead values, maintained **outside the repository** (never committed, never inside any working tree). Source: the documented rotation/findings inventory (`reports/security_findings_20261011.md`) — not re-typed from memory.

## Procedure (single pass, fresh clone — never in-place in either worktree)

1. **Fresh clone** of the repo into a temporary directory (not the worktrees).
2. **One pass** with `git filter-repo --replace-text <file>` (or equivalent) covering **all refs** (branches + tags). Single pass only — no iterative re-runs on the same clone.
3. **Verify before any push:**
   - HEAD **tree hash identical** to the pre-rewrite HEAD tree (contents unchanged; only history rewritten);
   - full-history scans clean: **gitleaks (full history)** + the repo scanner over `git rev-list --all` blobs for the dead values — expect zero;
   - commit count and tag list unchanged (modulo rewritten hashes).
4. **Push:** **owner-only decision.** Only after explicit approval: single force-push of the rewritten refs, then all clones/worktrees re-clone fresh (worktrees recreated from the rewritten branch).
5. **Post-rewrite:** re-run the standard gates (`secret_scan --tracked`, `pytest tests/security`, `scripts/security_checks.ps1`) on the fresh clones; notify the parallel session.

## Risks / caveats (honest)

- **Forks/clones/caches:** the rewrite purges *this repo's* reachable history. Any fork, external clone, or hosting-side cache retaining old objects is outside the rewrite's reach — verify remotes/forks before claiming full purgation.
- **Local-only work:** any unpushed commit in any clone is not rewritten; coordination (precondition 2) is the mitigation.
- **No stealth:** this is a mechanical history purge of already-dead values; it is not a substitute for the rotation that already happened (owner-confirmed).
- **Stop-and-ask:** the replacement file itself is radioactive — if it is ever staged inside the repo, abort and re-do from the mirror.

## Files affected

To be enumerated at execution time from the findings inventory (the rewrite's replacement file is derived from that inventory; every occurrence across all paths/refs is replaced in the single pass). No guesses are recorded here by design.
