# History rewrite plan — extended (commit map, quiet window, re-point, remap)

Owner-gated. **Nothing in this document has been run**, by instruction. It extends
`reports/ty/secret_exposure_report.md` with the four things the first plan did not cover: a
commit map, a quiet-window procedure, how to re-point the local clones, and how to remap every
hash the queue, tags and reports cite. It also evaluates delete-and-recreate-private against a
rewrite, because that alternative removes the hardest step.

Preconditions, unchanged and not negotiable: **rotate first** (`DIR-1a/b/c` plus the three hosts
in `SEC-1`). A rewrite of a public default branch while the keys are live only hides them better.

---

## 1. The commit map: capture it, or the rewrite is unrepeatable

`git filter-repo` writes `.git/filter-repo/commit-map` in the rewritten repository: a header
line then `<old-sha> <new-sha>` for every commit, with a deleted commit mapped to forty zeros.
The September mirror at `state/security/mirror` **does not have it any more** — the directory was
copied without that folder, so the mirror is currently a rewritten tree whose old→new mapping is
lost. That is the one thing this plan must not repeat.

Procedure, in the mirror, before any ref moves:

```bash
cd state/security/mirror
git filter-repo --force --invert-paths --paths-from-file ../paths_to_remove.txt
cp .git/filter-repo/commit-map ../commit-map          # the artefact that makes this repeatable
git filter-repo --force --replace-text ../replacements.txt
cp .git/filter-repo/commit-map ../commit-map          # second pass: merge both maps
```

The second `filter-repo` run rewrites the first run's hashes, so the final map must be composed:
`old → intermediate → final`. `tools/remap_hashes.py` reads a single flat map, so compose it into
one file (awk on the two maps, chaining by the intermediate column) and keep **both** originals.
Name them by date: `state/security/commit-map-2026-11-11.txt`.

Sanity checks, before the map is trusted:

- `wc -l commit-map` minus one == `git rev-list --count --all` in the mirror (1,710 after the
  reference run: one commit was the merge that only added the three captured pages).
- No `<new>` value appears twice.
- Every dropped commit's `<old>` still exists in the *unrewritten* repo, so the citation can be
  explained to a reader instead of vanished.

## 2. Quiet-window procedure

A rewrite while anything is writing is how a half-pushed history happens. The window is one
ordered list; each step has a check that must pass before the next.

| # | step | check before continuing |
|---|---|---|
| 1 | Rotate all keys (`DIR-1a/b/c`, `SEC-1`). | Each provider shows the old key revoked, or the owner states it in writing. |
| 2 | `PAUSE` file at `state/vision/PAUSE`, and stop the launcher task. | `Get-ScheduledTask NorthstarTyDirector` is `Disabled`; `ty_director.py --once` reports `blocked`. |
| 3 | Stop the dev stack with the recorded pids; confirm `dev-start.pids` is empty. | Ports 8000 and 8101 have no listener. |
| 4 | Close every worker session and worktree: `git worktree list` shows only the main tree. | No `opencode run` process carries `--agent builder`. |
| 5 | Announce the window in `reports/ty/handoff.md` **with the start time and the intended end**. | The line is in the file. |
| 6 | `git fetch origin --prune --tags`; record `origin/main` and the SHA of every tag. | The record matches what the mirror was cloned from. |
| 7 | Run the rewrite in the mirror and produce the commit map (section 1). | Map checks pass. |
| 8 | `gitleaks git` on the mirror. | No leaks found (this is the gate that decides go/no-go). |
| 9 | Force-push heads and tags (owner runs this, not Ty). | GitHub shows the new tip. |
| 10 | Re-point local clones (section 3) and remap hashes (section 4). | `tools/remap_hashes.py --check` reports zero unmapped citations. |
| 11 | Remove `PAUSE`, re-enable the launcher. | Heartbeat state is `running`. |

The window needs roughly 30 minutes of nobody pushing. The rewrite itself is minutes; the
verification and remap are the rest.

## 3. Re-pointing the local repos

The local clone's objects do not survive the rewrite — the hashes are different, so it must be
re-pointed rather than patched:

```bash
git fetch origin --prune --tags          # brings the rewritten heads and tags
git branch -u origin/main main           # re-attach tracking at the new tip
git reset --hard origin/main             # ONLY after the worktree is clean and stashed/committed
```

Rules that matter on this machine:

- **Worktrees.** `git worktree list` must be empty of feature trees before the reset, otherwise
  each worktree keeps the old base and will re-introduce the old commits on the next merge.
- **Local branch names.** `staging` and every `dev/*` branch that was pushed are now rewritten on
  the remote; the local ones must be deleted after the base reset, not merged.
- **The scheduled task's working directory** is the repo root; nothing to change, but the task's
  next run must be allowed to read the new refs (step 11).
- **Gitleaks allowlist.** `.gitleaks.toml`'s entries are fingerprints of the *old* blobs. They
  become dead entries after the rewrite; `tools/retire_chat_exports.py --retire` rewrites them in
  one commit whose message says "rotated keys only".
- **The pre-commit hook** (`tools/git-hooks/pre-commit`) is content-based, not hash-based, and
  keeps working unchanged.

## 4. Remapping every hash in the queue, tags and reports

Measured now, read-only (`python tools/remap_hashes.py --scan`): **90 files cite a hash — 39 full
40-char hashes and 2,160 short candidates** across `reports/ty/*.md`, `reports/ty/*.json`,
`ty/*.json`, `state/director/*.json`, `docs/*.md`, `tests/BASELINE.json` and `00_STATE.json`.
The short-candidate number is a superset on purpose: a 7–12 character hex token can also be a
colour or a fingerprint fragment, and the scanner labels it a *candidate*, never a rewrite.

`tools/remap_hashes.py` is the remap step:

| command | what it does | what it will not do |
|---|---|---|
| `--scan` | counts citations per file | change anything |
| `--map <commit-map> --check` | reports coverage and the files that would change | change anything |
| `--map <commit-map> --apply` | rewrites full hashes and unique short prefixes that are in the map | touch a token not in the map; rewrite an ambiguous prefix; rewrite a dropped commit's short form |

`--apply` writes a `.remap-backup` beside each file first, so a mistake is reversible without git.
Tests: `Northstar_backend/test_remap_hashes.py` (7) pin the two failure modes — a number that was
never a commit must not change, and an unmapped full hash must be *reported*, not silently kept.

Tags are not text files. After the rewrite they are re-pointed by the force-push in step 9; the
report's job is to state the new tag targets, which the composed commit map gives directly.

## 5. Delete-and-recreate-private, evaluated

The alternative: make a fresh **private** repository, push the current tree to it as one initial
commit, and delete or archive the public one.

| dimension | rewrite in place | delete-and-recreate-private |
|---|---|---|
| exposure removed | yes, once GitHub gc's the unreachable objects | **yes, immediately and completely** — the old repo is gone |
| history kept | 1,710 commits | **none** (one squashed initial commit) |
| commit map / remap needed | yes, 90 files, 39 full hashes | **no map**: there is no old→new relation to explain |
| risk of a bad force-push | real: one wrong ref and the public tip is unrecoverable | none: the public repo is deleted, the new one has one commit |
| what else is lost | the five captured third-party pages, one commit | those pages, every intermediate state, every release tag's history |
| AWS/GitHub object purge | still needed for the old blobs | not needed |
| follow-up work | remap 90 files, re-point clones, re-tag | update remotes and docs, re-tag `v*` at the single commit |
| reversibility | a mistake is a rewrite of a rewrite | a mistake is "restore from the tarball you took first" |

**Recommendation: delete-and-recreate-private, with a full archive first.** The reason is not
speed, it is that the rewrite's two hardest steps — a 1,710-entry commit map and remapping 90
files — exist only to preserve history that contains nothing a seller needs and five pages we
want gone. Take `git bundle create northstar-full-<date>.bundle --all` and a filesystem copy
before anything, keep the bundle offline and unshared, then create the private repo from the
current tree. The rewrite stays the fallback if the owner wants the history preserved.

Either path is owner-only: it changes repo visibility and rewrites a public default branch. Ty
does neither.

## 6. What is deliberately not decided here

- Whether GitHub support should purge unreachable objects (rewrite path only). That is a support
  request in the owner's name.
- Whether the old public repo is deleted or archived (recreate path). Archiving keeps the leak
  readable; deleting does not. The recommendation above assumes delete.
- Anything about the other nine public WordCoffee repos. Their measured state is in
  `reports/ty/wordcoffee_repos_scan.md`; each has its own recommendation, and none of them is
  this rewrite.
