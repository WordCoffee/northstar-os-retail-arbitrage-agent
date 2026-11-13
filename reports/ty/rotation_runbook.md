# Rotation runbook — owner steps, then Ty's steps

Nothing in the queue depends on this. It is a **pre-launch gate only**: the launch checklist carries
one line, *"rotation complete"*, and it is ticked when `state/security/keys_rotated.json` exists.
Until then the program continues; the public remote stays as it is.

Order matters: **new key → put it in `.env` → verify the app still works → revoke the old one →
make the repo private → write the marker.** Revoking before the new key is live takes the services
down; making the repo private before rotation hides the leak without killing the credential.

---

## Part 1 — the owner (about 30 minutes)

### A. The three committed credentials

| # | service | where it was committed | what to create | what to revoke |
|---|---|---|---|---|
| 1 | **Scavio** | `FirstNorthstarautomationchat.md` lines 1143, 1291 | a new API key in the Scavio dashboard | the old key |
| 2 | **Bright Data** | `FirstNorthstarautomationchat.md` lines 1148, 1296 | a new API token in the Bright Data control panel | the old token |
| 3 | **GitHub** | `autothink-ui-chat-export.md` line 7852 (a personal access token) | a **fine-grained** token, one repo, `contents:read` only | the old PAT (Settings → Developer settings → Tokens) |

Two more real hosts carry credential-shaped lines and are worth doing in the same sitting:

| # | host | action |
|---|---|---|
| 4 | `www.packify.ai` | change the account password if an account exists |
| 5 | `api.scrape.do` | rotate the token if the account is live |

### B. Install the new values (never paste a key into chat)

1. Open `.env` at the repo root in a local editor.
2. Replace the value only — keep the key names exactly:
   `SCAVIO_API_KEY=…`, `BRIGHTDATA_API_KEY=…`, `GITHUB_TOKEN=…` (the names already in the file;
   if one is missing, add it beside the others).
3. Save. Do not commit `.env` (it is ignored; if `git status` ever shows it, stop).
4. Restart the backend **through the launcher**, not a bare uvicorn:
   `scripts/launch_alpha.ps1 -Restart`
5. Confirm the app still works: `GET http://127.0.0.1:8000/health` → 200, and one Scavio/Bright
   Data call from the app succeeds.

### C. Revoke the old credentials

Only after step B5 passes, revoke at each provider (the "what to revoke" column above). A key that
is still valid after being replaced is still a leak.

### D. Make the repository private

GitHub → the repo → **Settings → General → Danger Zone → Change visibility → Make private**.
(The repo is `WordCoffee/northstar-os-retail-arbitrage-agent`. Making it private does **not** remove
the blobs from GitHub's object store; that is the history rewrite, which is separate and still
yours.)

### E. Write the marker

Create the file **`state/security/keys_rotated.json`** with exactly this shape:

```json
{
  "rotated_at": "2026-11-XXT00:00:00Z",
  "keys": ["scavio", "brightdata", "github"],
  "revoked_old": true,
  "repo_private": true,
  "notes": "anything you want Ty to read; no key values"
}
```

**No key values in this file.** It is a marker, not a vault.

---

## Part 2 — exactly what Ty runs afterwards (automatic, no questions)

A watcher is already running (`tools/keys_rotated_watch.py`, five-minute checks, no model call).
The moment the marker appears it runs, in this order:

| # | command | what it does | what a pass looks like |
|---|---|---|---|
| 1 | `python tools/retire_chat_exports.py --retire` | removes the two exports from the tree and allowlists their **dead** fingerprints, then re-scans | the two files gone; allowlist entries cite "rotated keys only" |
| 2 | `gitleaks dir . --config .gitleaks.toml --redact` | the same gate the pre-commit hook runs | `no leaks found` |
| 3 | `python tools/promote_closure.py --dry-run` | the promotion test for the green staging candidate, in a throwaway worktree — it does **not** touch `main` | collection and import gates pass |
| 4 | `python tools/history_rewrite_map.py --scan` (or `tools/remap_hashes.py --scan`) | counts the hashes a rewrite would invalidate | a number, recorded |
| 5 | resume the queue | the launch work continues where it stopped | no job waits on the marker |

Results land in `state/security/keys_rotated_result.json` and `reports/ty/keys_rotated_watch.log`.
**Promotion to `main` is never automatic**: it needs a passing verifier run and a rollback tag taken
immediately before the merge, and that is a director decision recorded in `handoff.md`.

## What Ty will not do

- Enter, read, print or store any key value.
- Revoke a credential, change repo visibility, rewrite history, or force-push.
- Ask about any of it again. This file is the whole instruction.
