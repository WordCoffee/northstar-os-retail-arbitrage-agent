"""Brand SEO Profile schema (V3 S7) — additive tables for the SEO engine.

Standalone constant so BOTH the data layer's shared DDL (SQLite + Postgres) and
the offline unit tests consume ONE source of truth (same pattern as
chat_schema.py). This module imports nothing.

Design (S7):
  • ONE canonical, versioned profile per brand — not a listings feature.
  • The profile row holds identity + a pointer (`current_version`) at the live
    version; the version rows hold the immutable body. Editing a profile means
    APPENDING a new version, never rewriting an old one.
"""

SEO_TABLES_SQL = """
            -- Brand SEO Profiles (V3 S7). One row per brand (per account).
            CREATE TABLE IF NOT EXISTS brand_seo_profiles (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                brand_key TEXT NOT NULL,         -- slug; unique per account
                name TEXT NOT NULL,
                current_version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_brand_seo_profiles_key
                ON brand_seo_profiles(account_id, brand_key);
            CREATE INDEX IF NOT EXISTS idx_brand_seo_profiles_account
                ON brand_seo_profiles(account_id);

            -- Immutable profile versions. Append-only: a rewrite is a new row.
            CREATE TABLE IF NOT EXISTS brand_seo_profile_versions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                body_json TEXT NOT NULL,         -- the profile body (canonical JSON)
                note TEXT,                       -- why this version exists
                created_by TEXT,                 -- operator id / 'master_brain'
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_brand_seo_versions_unique
                ON brand_seo_profile_versions(profile_id, version);
            CREATE INDEX IF NOT EXISTS idx_brand_seo_versions_profile
                ON brand_seo_profile_versions(profile_id);

            -- Listing revisions (V3 S7 §5.2). Additive: does NOT touch
            -- ds_listing_records. A listing build/update APPENDS a revision; the
            -- newest revision is the only object SEO work targets, and prior
            -- revisions stay read-only (history, diffs, rollback).
            CREATE TABLE IF NOT EXISTS ds_listing_revisions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                listing_key TEXT NOT NULL,       -- asin | legacy_key | slug
                asin TEXT,
                revision INTEGER NOT NULL,       -- 1-based, monotonic per (account, listing_key)
                title TEXT,
                bullets TEXT,                    -- JSON array
                backend_terms TEXT,
                description TEXT,
                source TEXT DEFAULT 'operator',
                note TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_listing_revisions_unique
                ON ds_listing_revisions(account_id, listing_key, revision);
            CREATE INDEX IF NOT EXISTS idx_ds_listing_revisions_key
                ON ds_listing_revisions(account_id, listing_key);
        """
