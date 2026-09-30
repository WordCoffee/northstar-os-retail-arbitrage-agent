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

# 4. Upload to the approved off-VM destination (provider CLI must be preinstalled
#    and authenticated by the owner; not configured here).
echo "backup ready: $(basename "${enc}") ($(stat -c%s "${enc}") bytes) -> ${BACKUP_DEST}"
# Example (fill at DEPLOY-F5 when the destination is approved):
#   <provider> upload "${enc}" "${enc}.sha256" "${BACKUP_DEST}/"

# 5. Prune local staging + enforce retention at the destination (implemented at
#    DEPLOY-F5 once the destination CLI is chosen).
echo "retention: ${RETENTION_DAYS} days (destination-side pruning implemented at DEPLOY-F5)"
