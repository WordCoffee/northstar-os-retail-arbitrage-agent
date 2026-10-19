# ROLLBACK — snapshot and restore this build

Every meaningful build gets a **snapshot**: a git tag, a database copy, the served
bundle's identity, and a manifest. Restoring is non-destructive: it creates a
`rollback/<name>` branch at the snapshot commit and restores the databases, so
nothing you have committed is ever deleted.

```powershell
# take a snapshot before a risky change (tags + copies DBs + records the bundle)
.\tools\rollback.ps1 -Action snapshot -Name pre-bojo

# see what snapshots exist
.\tools\rollback.ps1 -Action list

# go back to one (creates rollback/<name>; your current branch is untouched)
.\tools\rollback.ps1 -Action restore -Name pre-bojo
```

## What a snapshot contains

| Item | Where |
|---|---|
| Git tag `snapshot/<name>` at HEAD | the repository |
| Product DB copy | `backups/rollback/<name>/northstar.db` |
| Foundation DB copy | `backups/rollback/<name>/foundation.db` |
| Manifest (commit, date, bundle hash, counts) | `backups/rollback/<name>/manifest.json` |

`backups/` is gitignored: snapshots are local, so they never bloat the repository
and never risk committing data.

## What restore does — and does not do

1. Verifies the tag exists.
2. Copies the CURRENT databases to `backups/rollback/pre-restore-<timestamp>/`
   (so a restore can itself be undone).
3. Creates and checks out `rollback/<name>` at the snapshot commit — **the current
   branch is not moved, reset or deleted**.
4. Restores the snapshot databases over `Northstar_backend/data/*.db`.
5. Rebuilds `northstar-os-ui/dist` so the served bundle matches the restored source.
6. Prints the resulting branch, commit and bundle hash.

It does **not** delete commits, force-push, touch `main`/`release/*`/`hotfix/*`, or
overwrite anything outside `Northstar_backend/data/` and `backups/`.

## If you only want the files back

```powershell
git switch --detach snapshot/pre-bojo      # look around, no branch created
git switch -                                # come back
```

## Rolling forward again

`git switch feature/v4.1-mesh` (or whichever branch you were on) and rebuild:

```powershell
npm --prefix northstar-os-ui run build
```
