# Postgres for the hosted beta

## What connects

The API and the foundation layer read `DATABASE_URL` (and `DB_URL`,
`FOUNDATION_DB_URL` where the older services expect them). In
`docker-compose.yml` all three point at the `postgres` service; the hosted
overlay changes nothing about the database identity — only the posture.

- Service: `postgres` (image pinned in the compose file), healthcheck
  `pg_isready` against `${POSTGRES_USER}`/`${POSTGRES_DB}`.
- The API container never waits on a DNS race: compose `depends_on` carries the
  healthcheck condition.
- **No port is published** by the postgres service in any composition. Only the
  proxy (Caddy, 80/443) is reachable from outside the VM. The compose guard
  (`tools/check-compose-deploy.cjs`) fails the regression if a port appears.

## Schema layout

- The Design Studio store lives in the dedicated schema **`northstar_data`**
  (`ds_*` tables: projects, assets, jobs, imports, listing records, variants,
  metrics, amazon files / proposals / change files, and the rest).
- The foundation store keeps its own tables; both live in the same database
  under the same role. No cross-schema foreign keys are required by the app.

## Behaviour notes that matter in production

- **Read-commit**: the data layer commits after reads so a request cannot leave
  an idle-in-transaction connection holding locks. A long-running psql session
  will NOT block the API; if it appears to, check for a manual session rather
  than the app.
- **Parameterised SQL only** — the data layer builds statements with
  placeholders; string interpolation of values does not appear in the store
  code (the regression's static scans would flag it).
- **Migrations are explicit**: `Northstar_backend/migrate_ds_identity.py`
  (dry-run by default, `--apply` to run, quarantines ambiguous records), and the
  schema bootstrap is idempotent (`CREATE SCHEMA IF NOT EXISTS` /
  `CREATE TABLE IF NOT EXISTS` on first use).

## Config the operator sets (names only)

In `deploy/hosted.env` (untracked, 0600, root-owned):

```
POSTGRES_USER=…
POSTGRES_PASSWORD=…
POSTGRES_DB=…
DB_URL=postgresql://<user>:<password>@postgres:5432/<db>
```

Values are never committed and never echoed in a command line. The compose
files default to a dev-only password string; the hosted overlay expects the
real values to come from `deploy/hosted.env`.

## Verifying a deploy's database posture

```
# The deploy composition publishes nothing besides the proxy:
node tools/check-compose-deploy.cjs

# In-container sanity (no secret printed):
docker compose -f docker-compose.yml -f docker-compose.hosted.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select schema_name from information_schema.schemata where schema_name='northstar_data';"
```

An empty result means the schema was not created — the API creates it on first
boot, so run the check after the first successful request, not before.
