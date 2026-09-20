# Rollback Drill — Phase F/S13

**Date:** 2026-09-20 · **Cost:** $0 · **Network:** none

## Why

A launch-critical guarantee: if the live backend misbehaves, the operator can
return to the last known-good tagged release (`v0.1.0-alpha` = Phase E5
baseline, commit `61a023c`) with a boot-verified path — not a hope.

## The drill (`scripts/rollback_drill.ps1`)

Runs automatically (offline):

1. **Preconditions** — abort if the working tree is dirty or the target is HEAD
   itself.
2. **Worktree**, not checkout — `git worktree add <tmp> <tag>` checks the tagged
   release into a temp directory; the live working tree is never touched
   (safe even while tests are running).
3. **Boot probe** — the tagged backend imports and `GET /health` returns 200
   via TestClient (no server, no network).
4. **Import smoke** — `main`, `data_layer`, `auth` import clean on the tag.
5. **Cleanup + assertion** — the worktree is removed, `HEAD` is confirmed back
   at the pre-drill sha, and the tree is verified clean.

Expected output ends with:

```
PASS: rollback to v0.1.0-alpha verified; returned to <sha>; tree clean.
```

## Operator procedure (real rollback)

1. `git tag` — confirm the known-good tag.
2. Deployer command: `git checkout <tag> && <deploy step>` on the machine that
   runs the backend, OR point the runtime image at the tag's commit sha.
3. Verify: `/health` 200, then `GET /api/monitoring/error-alerts` returns the
   bff/v1 envelope (S4 wiring is present on HEAD; the tag is pre-S4 — for the
   tag, just verify the app boots and core routes respond).
4. If the rollback target predates a schema change, run the applicable
   `migrations/*.sql` (S9) — in order — before serving traffic.
5. Record the incident in a scrubbed manifest; never auto-retry, never skip the
   failed item silently (circuit breaker, §OPERATING_CONSTITUTION).

## Constraints

- **Never** execute this against a live/production data source; the drill only
  exercises the code tree.
- Never `git push` anything from this drill; tags are local.
- The live/paid gate still applies after rollback — rolling back code does not
  unlock live provider calls.