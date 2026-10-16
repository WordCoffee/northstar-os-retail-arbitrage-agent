#!/usr/bin/env bash
# Nightly PostgreSQL backup -> client-side encrypted -> off-VM destination.
# DEPLOY-F5 tool. Do not run before a destination is approved and free-eligible.
# Secrets come from files/env names only; never print secret values.
#
# Required environment (names):
#   PGUSER, PGDATABASE           (database identity; password via PGPASSFILE, not argv)
#   BACKUP_ENC_KEY_FILE          (path to a root-owned 0600 key; never logged)
#   BACKUP_DEST                  (approved off-VM destination, e.g. oci://bucket/prefix)
#   RETENTION_DAYS               (default 14)
set -euo pipefail

PGUSER="${PGUSER:?PGUSER required}"
PGDATABASE="${PGDATABASE:?PGDATABASE required}"
BACKUP_ENC_KEY_FILE="${BACKUP_ENC_KEY_FILE:?BACKUP_ENC_KEY_FILE required}"
BACKUP_DEST="${BACKUP_DEST:?BACKUP_DEST required}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
work="$(mktemp -d)"
dump="${work}/northstar-${ts}.sql"
enc="${dump}.enc"
trap 'rm -rf "${work}"' EXIT

# 1. Dump (no secrets in argv).
docker compose -f docker-compose.yml -f docker-compose.hosted.yml \
  exec -T postgres pg_dump -U "${PGUSER}" -d "${PGDATABASE}" > "${dump}"

# 2. Verify non-empty, then encrypt client-side before it leaves the VM.
test -s "${dump}"
openssl enc -aes-256-cbc -pbkdf2 -salt \
  -pass "file:${BACKUP_ENC_KEY_FILE}" -in "${dump}" -out "${enc}"

# 3. Integrity record (hash only; no secrets).
sha256sum "${enc}" > "${enc}.sha256"

# 4. Upload to the approved off-VM destination. 2026-10-16: rclone is the
#    chosen transport when RCLONE_REMOTE is set (e.g. "b2:northstar-backups" or
#    "drive:northstar-backups"). Without it the script says so plainly — a
#    backup that never left the machine is NOT reported as done.
if [ -n "${RCLONE_REMOTE:-}" ]; then
  command -v rclone >/dev/null 2>&1 || { echo "REFUSED: RCLONE_REMOTE is set but rclone is not installed"; exit 3; }
  rclone copyto "${enc}" "${RCLONE_REMOTE}/${BACKUP_DEST:-northstar}/$(basename "${enc}")" --no-traverse
  rclone copyto "${enc}.sha256" "${RCLONE_REMOTE}/${BACKUP_DEST:-northstar}/$(basename "${enc}.sha256")" --no-traverse
  echo "UPLOADED: $(basename "${enc}") -> ${RCLONE_REMOTE}/${BACKUP_DEST:-northstar}/"
else
  echo "LOCAL ONLY: RCLONE_REMOTE is not set, so the encrypted backup has NOT left this machine."
  echo "            Set RCLONE_REMOTE=<remote>:<bucket/prefix> (rclone) to complete the off-machine leg."
fi

# 5. Destination-side retention: keep RETENTION_DAYS of encrypted dumps.
if [ -n "${RCLONE_REMOTE:-}" ]; then
  rclone delete "${RCLONE_REMOTE}/${BACKUP_DEST:-northstar}" --min-age "${RETENTION_DAYS}d" --include "northstar-*.sql.enc*" || true
  echo "retention: pruned encrypted dumps older than ${RETENTION_DAYS} days at the destination"
else
  echo "retention: ${RETENTION_DAYS} days (applies once RCLONE_REMOTE is set)"
fi
