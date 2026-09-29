# DATA CONTRACT — Foundation app <-> identity/data pipeline

Status: DRAFT (P0-T2). Owner decision pending (default B applied until answered).
Created: 2026-09-28. Authority: `docs/OPERATING_CONSTITUTION.md` > this file.

## 1. The two repositories

| Repo | Path | Role |
|---|---|---|
| Foundation app (canonical, hosted) | `Northstar OS Retail Arbitrage Agent` | React/Vite SPA + FastAPI Foundation; hosted product; owns users, orgs, rooms, jobs, approvals, audit. |
| Identity/data pipeline | `C:\Users\T2Hol\Desktop\fba-product-screener` | Source-to-ASIN identity layer, Costco/PalletFly/SellerSprite/Prime National data, economics + evidence builds. |

## 2. Owner decision (P0-T2) — PENDING

`ASK OWNER`: (A) Foundation canonical, pipeline imported as a package/module;
(B) keep two repos, exchange via documented ingest contract; (C) other.

**Applied default: B** (two repos + documented ingest contract), per plan 1.3 and
P0-T2 until the owner answers. Logged as an assumption.

## 3. The `northstar.db` name collision (real, verified)

Two files with the SAME name, DIFFERENT schemas. Verified table counts on
2026-09-28:

| File | Size | Tables | Ownership |
|---|---|---|---|
| `Northstar_backend/data/northstar.db` (Foundation app) | 7.8 MB | 32 | Foundation-adjacent legacy store: `audit_log`, `campaigns`, `costco_*`, `invites`, `keywords`, `listings`, `memory_entries`, `products`, `sessions`, `social_content`, `suppliers`, `transactions`, `users`. |
| `fba-product-screener/data/northstar.db` (pipeline) | 87.4 MB | 36 | Identity/evidence store: `amazon_catalog_records`, `amazon_identifier_crosswalk`, `identity_run_log`, `resale_score_inputs`, `sourcing_opportunities`, `nh_*` evidence tables, `product_identifiers`, `costco_discovery_candidates`, `source_files`, `raw_source_rows`. |

Overlapping table NAME that is NOT the same data: `product_identifiers` exists in
both, with different columns/meaning. Treat as distinct.

Third DB in the pipeline repo: `fba-product-screener/data/products.db` (545 MB)
— do not conflate with either `northstar.db`.

The Foundation runtime does NOT use either legacy file as its canonical store:
`foundation/db.py` generates one schema spec for SQLite (dev default) and
Postgres; hosted mode uses `FOUNDATION_DB_URL` (`foundation/db_postgres.py`).
The legacy `Northstar_backend/data/northstar.db` is a production-like artifact,
not the Foundation default.

## 4. Naming disambiguation (P0-T2 action)

Config-only reference rename in the pipeline repo, no file move:
- Edited `fba-product-screener/northstar_identity_config.py` to declare
  `PIPELINE_DB_NAME = "pipeline_northstar.db"` and
  `PIPELINE_DB_PATH = "data/pipeline_northstar.db"`.
- The physical pipeline DB is still `data/northstar.db` and existing modules
  still resolve that path; the rename is a documented target, not a live move.
- Open question OQ-1: when the owner approves the file move, repoint all
  pipeline callers from `data/northstar.db` -> `data/pipeline_northstar.db`.

## 5. Ingest contract (target; materialized in P4-T2)

Direction: pipeline -> Foundation. Foundation never writes into the pipeline DB.

- Transport: pipeline exports to a documented, versioned artifact (JSON/CSV) or
  the Foundation pulls via the registered durable job type
  `pipeline.ingest_identity`.
- Idempotency: each run carries a `run_id`; re-ingesting the same `run_id` is a
  no-op (row counts equal pipeline outputs; no duplicates).
- New Foundation tables (additive migrations, P4-T2): `identity_pairs`,
  `resale_score_inputs`, `ingest_runs`.
- Provenance: every ingested row carries `source_id`, `observed_at`, and a
  truth basis label (OBSERVED / CACHED / ASSUMED / UNKNOWN / SAMPLE / INTERNAL).
- Data rights: pipeline sources may be `INTERNAL_ONLY` (P4-T3); such rows are
  excluded from customer-tenant views.
- Fail closed: an unregistered/unversioned ingest payload fails the job.

## 6. Table ownership boundary

| Data | Owner | Notes |
|---|---|---|
| orgs, users, memberships, roles | Foundation | canonical identity/RBAC |
| durable jobs, approvals, audit, browser_jobs | Foundation | |
| catalog/identity/evidence, scores, supplier economics | Pipeline | surfaced to Foundation via ingest contract |
| truth labels / freshness / data rights | Foundation (enforcement) | applied on ingest |

## 7. Open questions

- OQ-1: owner decision A/B/C (currently B).
- OQ-2: timing/approval for the physical pipeline DB file rename to
  `pipeline_northstar.db`.
- OQ-3: whether `products.db` is ingested or stays pipeline-internal.