# Security history purge — 2026-11-15

Owner-authorized final purge of the 18 historical findings. **No secret value was printed, read
into a report or committed.** The file-level findings were removed from all history; the one
synthetic test token was replaced; a 406 MB audio artifact was removed because GitHub refused the
push over its 100 MB limit.

## Backups taken first

| artifact | location | SHA256 |
|---|---|---|
| full bundle, all refs, pre-purge | `C:\Users\T2Hol\Northstar-backups\northstar-pre-purge-20261114-234441.bundle` | `00B2848088DADAB6C94E87327D2141C5224A83D9F477F07F28139E30ACA9BB7F` |
| earlier pre-final bundle | `…\northstar-pre-final-20261114-214330.bundle` | `82FA4660…D337A` |
| 4 dirty worktrees (incl. uncommitted work) | `C:\Users\T2Hol\Northstar-backups\worktrees\*.tar.gz` | archived before removal |

## The 18 findings (paths and rules only)

| rule | count | file | commit |
|---|---|---|---|
| `sourcegraph-access-token` | 12 | `reports/_bd_amazon.html`, `_bd_beeswax.html`, `_bd_unpaper.html` | `e5dccbbd` |
| `generic-api-key` | 4 | `FirstNorthstarautomationchat.md` | `a299d6e9` |
| `github-pat` | 1 | `autothink-ui-chat-export.md` | `21aed4e3` |
| `generic-api-key` | 1 | `Northstar_backend/test_chat_export_guard.py` (synthetic fixture) | `40986a96` |

## What was rewritten

In a fresh mirror (`state/security/mirror-purge`), `git filter-repo`:

1. **removed** `FirstNorthstarautomationchat.md`, `autothink-ui-chat-export.md`,
   `reports/_bd_amazon.html`, `reports/_bd_beeswax.html`, `reports/_bd_unpaper.html` from every
   commit;
2. **replaced** the single 32-character synthetic test literal in the guard test's history with
   `REMOVED_SYNTHETIC_TEST_TOKEN` (replacement file generated, never echoed);
3. **removed** `research/research_wave2_20261019/_audio_tmp/HkoRkNLWQzY.m4a` (406 MB) after GitHub
   rejected the push with `GH001: Large files detected`.

The rewritten mirror scans **0 findings** (gitleaks, 1,824 commits). 1,868 commits were parsed;
all real refs survived (only the mirror's own `origin/HEAD`/`origin/main` tracking refs were
dropped).

## Remote state after the force-push

| ref | new commit |
|---|---|
| `refs/heads/main` (and remote HEAD) | `98875d7f` (full hash in git) |
| `refs/heads/staging` | `d9e778c1` (full hash in git) |

All 47 branches and all tags were pushed. Tag **names** are unchanged; their hashes were rewritten.

## Working-repo reconciliation

- Reset to `origin/staging` (`d9e778c1`); the five purged files are gone from the tree.
- 25 clean stale worktrees removed; the 4 dirty ones archived first, then removed
  (`main-suite`, `stageslice`, `northstar-wt-mogra`, `NS-autonomy-wt`).
- 22 local branches re-pointed to their rewritten origin counterparts; the stash ref dropped;
  reflog expired; `git gc --prune=now`.
- Reachable commits in the working repo: **1,865** (mirror: 1,867) — the old history is no longer
  reachable from any ref.
- Final independent scan of the working repo: **0 findings across 1,824 commits** (gitleaks,
  553 MB scanned). The mirror scan also returned 0. Both are clean.

## Consequences and limits

- **Every commit hash quoted in reports before this purge is stale.** Unit tag names are stable;
  the hashes behind them are not.
- GitHub keeps unreachable objects reachable **by SHA** until its own garbage collection; a
  support request naming the repository is the only way to force that. The public refs are clean
  now.
- The 72 MB `reports/ty/d17_artefacts/rea-local-app.json` remains in history (GitHub warns, does
  not block). It is not a credential.
- The backup bundle and archives contain the pre-purge history. They are the recovery path and
  should be stored encrypted/off-machine by the owner (SEC-2).
