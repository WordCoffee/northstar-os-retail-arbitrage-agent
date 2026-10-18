"""Curated corpus schema (V3 S8) — a local, provenance-labelled index.

One additive store for the curated research corpus: pre-aggregated index files the
operator already has on disk (a local `research/**` tree, GitHub/HF sweeps, source
registries). Nothing here scrapes; nothing calls a paid service.

Kept as a standalone constant so BOTH the data layer's shared DDL (SQLite +
Postgres) and the offline unit tests consume ONE source of truth. The only
SQLite-ism is the `datetime('now')` default, which data_layer already translates
for Postgres.

Additive only: no existing table or column is touched. The FTS index is created
separately (guarded) by `CorpusDB`, because FTS5 may not be compiled into every
SQLite build — an index problem must never break schema creation.
"""

CORPUS_TABLES_SQL = """
            -- Curated corpus (V3 S8): pre-aggregated, local, provenance-labelled.
            -- account_id NULL means a shared/global curated record. ADDITIVE ONLY.
            CREATE TABLE IF NOT EXISTS corpus_records (
                id TEXT PRIMARY KEY,
                account_id TEXT,
                source TEXT NOT NULL,             -- github | hf | csv | doc | registry
                source_id TEXT NOT NULL,          -- stable id within the source
                kind TEXT,                        -- repo | dataset | doc | source_row
                title TEXT,
                url TEXT,
                license TEXT,                     -- as reported by the source sweep
                summary TEXT,
                content TEXT,
                tags_json TEXT,
                provenance_json TEXT,
                content_hash TEXT,                -- idempotency key (skip unchanged)
                ingested_at TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_corpus_records_key
                ON corpus_records(source, source_id);
            CREATE INDEX IF NOT EXISTS idx_corpus_records_source ON corpus_records(source);

            -- One row per ingest attempt: resumable runs with honest counts.
            CREATE TABLE IF NOT EXISTS corpus_ingest_runs (
                id TEXT PRIMARY KEY,
                source TEXT,
                source_path TEXT,
                status TEXT DEFAULT 'running',    -- running | done | error
                counts_json TEXT,
                errors_json TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_corpus_runs_source ON corpus_ingest_runs(source);
"""
