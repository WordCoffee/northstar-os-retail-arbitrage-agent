# Staging bundle — 2026-11-13 (private path, no push)

A full copy of the `staging` branch, taken to a path outside the repository and outside any sync
folder, with the ACL restricted to the owner. **Nothing was pushed.** The public remote
(`origin` → `github.com/WordCoffee/northstar-os-retail-arbitrage-agent`) is untouched; the bundle is
local.

| item | value |
|---|---|
| path | `C:\Users\T2Hol\Northstar-backups\bundles\staging-20261113.bundle` |
| ACL | inheritance removed; `T2Hol` full control only |
| ref contained | `refs/heads/staging` @ `b238a076bdb54d8e78b58cb7a8ab282de69bb615` |
| size | 693,193,251 bytes (661.1 MiB) |
| **SHA256** | `053218077C5EC57D2CC56768FFB380572FDC158491A4EBF4F16959182A88B438` |
| `git bundle verify` | *"The bundle records a complete history."* / *"is okay"* |
| created | 2026-11-13T05:55Z |

## What it is for

A restore point that does not depend on the public remote and does not need the 2 GB working copy to
be healthy. `git clone <bundle> restored/` produces a repository whose `staging` is exactly
`b238a076`, verifiable against the SHA256 above.

## What it is not

- Not a backup of untracked files, `state/`, `renders/` or `dist/` — those are gitignored by design.
- Not a push, a mirror, or a remote. No ref on `origin` changed.
- Not a substitute for the rotation work: the two chat exports are still in this history, which is
  why it lives in a private, ACL-restricted path.
