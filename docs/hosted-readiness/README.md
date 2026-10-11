# Hosted-readiness package (2026-10-11)

Everything needed to run NorthstarOS on a hosted VM for the private beta,
written against what is actually in this repository. No provider is contacted
by anything described here; generation stays UNARMED throughout.

| File | What it covers |
| --- | --- |
| `POSTGRES.md` | The Postgres store: connection, schema, pooling, read-commit behaviour, migrations. |
| `DEPLOY_CHECKLIST.md` | The ordered deploy checklist, with the verification command after each step. |
| `BACKUP_RESTORE.md` | Nightly backup and the restore drill (`deploy/backup.sh`, `deploy/restore.sh`). |
| `INCIDENT_RUNBOOK.md` | Incident response and the kill-switch inventory. |
| `SECRET_HANDLING.md` | Secret handling: where secrets live, what never happens, rotation. |

## The guards that make this package true

These run in the regression and fail closed:

- `tools/check-compose-deploy.cjs` — the LOCAL composition publishes the API on
  loopback only; the DEPLOY composition publishes **nothing** besides the proxy
  (80/443); no harness opt-out (`*BYPASS*`, `*TEST_MODE*`,
  `NORTHSTAR_DISABLE_RATE_LIMIT`, `NORTHSTAR_OWNER_SELF_APPROVAL`) is set to 1
  in either composition; `NORTHSTAR_DISABLE_RATE_LIMIT=0` is pinned in the
  hosted overlay.
- The API refuses to boot in staging/production with a harness opt-out set
  (`test_rate_limit_posture.py`, `test_live_posture_guard.py`).
- `tools/check-no-third-party.cjs` — the served UI makes zero third-party
  requests (fonts are self-hosted at `/ui/fonts/`).
- `tools/test_no_amazon_linkage.py` — no Amazon sign-in, API, OAuth or
  credential path exists anywhere in the product.

## Posture facts

- Environment marker: `ENVIRONMENT=staging` in the hosted overlay
  (`docker-compose.hosted.yml`), which also pins `NORTHSTAR_OWNER_TEST_MODE=0`
  and `NORTHSTAR_OWNER_SELF_APPROVAL=0`.
- The dev sign-in shim does not authenticate through the containerized API in
  any environment; the hosted overlay disables it outright.
- Generation arming flags (`CLOUD_MODEL_LIVE`, media arming) are **not** set in
  the hosted overlay. The studio reports UNARMED from `/api/design-studio/generation-status`.
