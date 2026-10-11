# Secret handling

## Where secrets live

| Secret | Where | Notes |
| --- | --- | --- |
| `POSTGRES_PASSWORD`, `DB_URL` | `deploy/hosted.env` (untracked, 0600, root-owned) | Never committed; compose defaults are dev-only strings. |
| `NORTHSTAR_JWT_SECRET` | same | ≥32 random bytes, generated on the VM, never reused from dev. |
| Provider API keys (vision/search, if ever added) | container env only | Absent in the beta. With no key, the provider is unarmed regardless of flags. |
| `BACKUP_ENC_KEY_FILE` | root-owned 0600 file on the VM | Used by `deploy/backup.sh`; never logged, never in argv. |
| `PGPASSFILE` | root-owned 0600 file | Postgres identity for scripts; no password in command lines. |

## Rules the product already enforces

- The agent and tooling **never read, print, echo, write or commit** `.env`
  values or any credential. The app reads its own config at runtime.
- `deploy/hosted.env.example` carries **names only**; the real file is
  untracked. If a secret ever appears in `git status`, treat it as compromised
  and rotate before continuing.
- Backup scripts take secrets via files/env names, never argv, and the hash
  record contains no secret material.
- No secret is ever put in a URL, a log line, a report, or a chat message.

## Rotation

| Event | Action |
| --- | --- |
| Suspected leak of `NORTHSTAR_JWT_SECRET` | Generate a new value, set it, restart the API. All sessions are signed out — expected and acceptable. |
| Suspected leak of the Postgres password | New password in `deploy/hosted.env`, `ALTER ROLE` on the database, restart the API and any script envs. |
| Lost `BACKUP_ENC_KEY_FILE` | The existing backups are unreadable by design; take a fresh backup with a new key and record the loss. Do not attempt to "repair" old artifacts. |
| Operator leaves the project | Rotate everything in this table; the VM's `deploy/hosted.env` is re-created from the example by the new operator. |

## Verification (no values shown)

```
# The hosted env is untracked (should print nothing):
git status --porcelain | grep -i "hosted.env" || true

# No secret-shaped value is staged:
git grep -I -n -E "(SECRET|PASSWORD|API_KEY)\s*=\s*[A-Za-z0-9/+_-]{16,}" -- ':!deploy/*.example' || true
```

Both commands are read-only. An empty result is the expected state.
