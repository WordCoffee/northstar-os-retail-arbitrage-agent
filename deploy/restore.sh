#!/usr/bin/env bash
# Restore a backup into a DISPOSABLE database and verify integrity.
# DEPLOY-F5 tool. A passing restore drill is required before real testers.
# Never restore over the live database with this script.
#
# Required environment (names):
#   RESTORE_FILE            (path to a *.sql.enc backup)
#   BACKUP_ENC_KEY_FILE     (path to the decryption key; never logged)
#   DISPOSABLE_DB           (throwaway database name, e.g. northstar_restore_drill)
#   PGUSER                  (database identity)
set -euo pipefail

RESTORE_FILE="${RESTORE_FILE:?RESTORE_FILE required}"
BACKUP_ENC_KEY_FILE="${BACKUP_ENC_KEY_FILE:?BACKUP_ENC_KEY_FILE required}"
DISPOSABLE_DB="${DISPOSABLE_DB:?DISPOSABLE_DB required}"
PGUSER="${PGUSER:?PGUSER required}"

[[ "${DISPOSABLE_DB}" == *drill* || "${DISPOSABLE_DB}" == *restore* ]] \
  || { echo "refusing: DISPOSABLE_DB must be a clearly disposable name"; exit 2; }

work="$(mktemp -d)"; trap 'rm -rf "${work}"' EXIT
sql="${work}/restore.sql"

openssl enc -d -aes-256-cbc -pbkdf2 \
  -pass "file:${BACKUP_ENC_KEY_FILE}" -in "${RESTORE_FILE}" -out "${sql}"

# Create disposable DB, restore, verify.
docker compose -f docker-compose.yml -f docker-compose.hosted.yml \
  exec -T postgres psql -U "${PGUSER}" -d postgres -c "DROP DATABASE IF EXISTS ${DISPOSABLE_DB};"
docker compose -f docker-compose.yml -f docker-compose.hosted.yml \
  exec -T postgres psql -U "${PGUSER}" -d postgres -c "CREATE DATABASE ${DISPOSABLE_DB};"
docker compose -f docker-compose.yml -f docker-compose.hosted.yml \
  exec -T postgres psql -U "${PGUSER}" -d "${DISPOSABLE_DB}" < "${sql}"

echo "restore drill complete into ${DISPOSABLE_DB}; verify counts, then drop it."
docker compose -f docker-compose.yml -f docker-compose.hosted.yml \
  exec -T postgres psql -U "${PGUSER}" -d postgres -c "DROP DATABASE ${DISPOSABLE_DB};"
