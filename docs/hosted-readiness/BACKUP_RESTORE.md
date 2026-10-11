# Backup and restore

Two committed tools, both fail-closed:

- `deploy/backup.sh` — dump → client-side encrypt → hash → upload to the
  approved destination. Secrets come from **files/env names only**; the script
  never takes a password in argv and never prints one.
- `deploy/restore.sh` — restore into a **disposable** database and verify.
  It refuses to run unless `DISPOSABLE_DB` contains `drill` or `restore`, so it
  cannot be pointed at the live database.

## Backup

Required environment (names):

| Name | Meaning |
| --- | --- |
| `PGUSER`, `PGDATABASE` | database identity (password via `PGPASSFILE`) |
| `BACKUP_ENC_KEY_FILE` | root-owned 0600 key used for AES-256 client-side encryption |
| `BACKUP_DEST` | approved off-VM destination (e.g. an object-store prefix) |
| `RETENTION_DAYS` | default 14 |

Run:

```
deploy/backup.sh
```

What it guarantees:

1. `pg_dump` runs inside the compose stack (no host Postgres client needed).
2. The dump is verified non-empty **before** encryption.
3. Encryption happens on the VM; only the `.enc` file and its `.sha256` leave.
4. The upload step is a placeholder until the destination is approved — a
   backup that never left the VM is reported as "ready", not "done".

## Restore drill (required before real testers)

```
RESTORE_FILE=/path/to/northstar-<ts>.sql.enc \
BACKUP_ENC_KEY_FILE=/root/backup.key \
DISPOSABLE_DB=northstar_restore_drill \
PGUSER=northstar \
deploy/restore.sh
```

The drill: decrypt → create `northstar_restore_drill` → restore → verify
integrity → report. A passing drill means the backup is *restorable*, not just
present.

## Cadence and retention

- Nightly (cron on the VM), retention 14 days unless the operator changes it.
- Keep the last backup of any day on which a schema migration ran, beyond the
  retention window, until the next successful drill.
- Backup artifacts are encrypted at rest off-VM; the key never leaves the VM.

## What is NOT backed up

- `deploy/hosted.env` and key files: these are secrets, not data. Losing them
  is a rotation event, not a restore event (`SECRET_HANDLING.md`).
- Container images: pinned by `deploy/images.lock`; re-pull from the registry.
