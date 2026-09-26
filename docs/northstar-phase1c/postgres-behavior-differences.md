# PostgreSQL Behavior Differences (1C-02 preflight)

Documented **before** any PostgreSQL application. Since PostgreSQL is unavailable here,
these are STATICALLY_CONFIRMED (from the type mapping) — **not** runtime-confirmed.

| Concern | SQLite (current) | PostgreSQL (target) | Handling |
|---|---|---|---|
| JSON columns | `TEXT` (JSON string) | `JSONB` | Repository layer uses explicit `json.dumps`/`json.loads`; identical behavior. No SQLite JSON functions used. |
| Booleans | `INTEGER` 0/1 | `BOOLEAN` | Serialized explicitly (0/1 on SQLite, native bool on PG); no truthiness coercion relied upon. |
| Timestamps | `TEXT` ISO-8601 | `TIMESTAMPTZ` | Freshness/staleness computed in Python, not SQL; no string date comparisons in queries. |
| Money/rates | `REAL` (float) | `DOUBLE PRECISION` | P0 foundation stores **no** money columns; canonical money (`NUMERIC`/Decimal) is introduced in 1C-03, not here. |
| `id`/`text` | `TEXT` | `TEXT` | identical |
| int columns | `INTEGER` | `BIGINT` | wider; no behavior change |
| PRIMARY KEY | inline | `PRIMARY KEY (...)` | generated from one SCHEMA |
| UNIQUE | inline | `UNIQUE (...)` | `idempotency_key`, `marketplaces.code`, `providers.provider_key` |
| Foreign keys | none in P0 | none in P0 | additive schema; FK ordering is not a concern yet |
| Extensions | n/a | none required | — |
| Identifier case | case-insensitive-ish | case-sensitive; quoted | all PG identifiers are quoted |
| Reserved words | tolerated | `key` column | quoted `"key"`; safe |
| Identifier length | none | 63-byte limit | max column name 22; safe |
| Advisory lock / single migrator | n/a | required for apply | to be implemented in the apply step (not yet) |

## Known SQLite-only behaviors that MUST NOT be relied upon

- `datetime('now')` defaults (used in the legacy `auth.py` schema) — the foundation schema
  uses no SQL defaults; timestamps are set in Python.
- `PRAGMA` usage (foreign_keys) — foundation uses `PRAGMA foreign_keys=ON` on SQLite only;
  irrelevant to PG.
- Type affinity coercion — avoided by explicit serialization.

## Residual risk

Runtime confirmation (round-trip JSONB/BOOLEAN/TIMESTAMPTZ, concurrent membership inserts,
transaction rollback) is **pending** and requires the ephemeral PostgreSQL exercise that
is currently blocked.