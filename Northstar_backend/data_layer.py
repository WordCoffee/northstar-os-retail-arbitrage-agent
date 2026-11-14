"""Northstar OS — Shared Data Layer

Provides a unified interface to the PostgreSQL database (via Supabase) that
all services (SourceScout, ListingForge, AdPilot, SocialPulse, AutothinK)
read from and write to.

For MVP, this module provides:
1. SQLite fallback when PostgreSQL is not configured (local dev mode)
2. Schema definitions (Postgres DDL)
3. Data access objects for each core table
4. Import helpers for CSV/JSON data sources

Usage:
    from data_layer import get_db, ProductsDB, KeywordsDB
    
    db = get_db()
    products = ProductsDB(db)
    products.upsert({"asin": "B01GRGIC9G", "title": "Kirkland Minoxidil", ...})
"""

import os
import json
import re
import hashlib
import sqlite3
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from env_flags import env_flag
from chat_schema import CHAT_TABLES_SQL
from seo_schema import SEO_TABLES_SQL
from corpus_schema import CORPUS_TABLES_SQL
from seo_profile import normalize_body as normalize_seo_body

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).resolve().parent
_SQLITE_PATH = _BASE_DIR / "data" / "northstar.db"


def _get_postgres_url() -> Optional[str]:
    # TODO(Phase F/S2): production data layer. A Postgres/Supabase connection
    # is operator-supplied via DATABASE_URL or SUPABASE_DB_URL in the runtime
    # environment. Tests + locals stay on the SQLite fallback (_SQLITE_PATH).
    # Apply schema changes through /migrations (Phase F Section 9), never by
    # editing SQLite DDL in production.
    return os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")


def _redact_url(url: Optional[str]) -> str:
    """A URL with any credential removed. Safe to log; never a secret."""
    if not url:
        return "<none>"
    from urllib.parse import urlsplit, urlunsplit
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return urlunsplit((parts.scheme, f"{host}{port}", parts.path, "", ""))
    except ValueError:
        return "<unparseable-url>"


class _PgChangesResult:
    """Minimal stand-in for SQLite's `SELECT changes()` result on Postgres."""

    def __init__(self, n: int):
        self._n = int(n)

    def fetchone(self):
        return (self._n,)

    def fetchall(self):
        return [(self._n,)]


def _is_pg_integrity_error(exc: Exception) -> bool:
    """True for any psycopg integrity-family error (v3 or v2)."""
    name = exc.__class__.__name__
    if name in ("IntegrityError", "UniqueViolation", "ForeignKeyViolation",
                "NotNullViolation", "CheckViolation", "ExclusionViolation",
                "RestrictViolation"):
        return True
    return exc.__class__.__module__.split(".")[0] in ("psycopg", "psycopg2") and "Integrity" in name


class DataLayer:
    """Database abstraction — Postgres when available, SQLite fallback.

    P1-04 (2026-10-09): the Postgres branch used to be dead code that lied.
    ``__init__`` set ``_mode = "postgres"`` when a URL was configured and then
    ran ``_init_sqlite()`` anyway, so a misconfigured deployment silently served
    SQLite while claiming Postgres. It now fails loudly at initialization: a
    configured-but-unreachable Postgres raises instead of degrading, and only an
    explicitly absent URL falls back to SQLite.
    """

    def __init__(self, allow_sqlite_fallback: Optional[bool] = None):
        self._pg_url = _get_postgres_url()
        self._conn = None
        self._lock = threading.RLock()
        self._mode = "postgres" if self._pg_url else "sqlite"
        if self._mode == "sqlite":
            self._init_sqlite()
        else:
            self._init_postgres(allow_sqlite_fallback)

    def _init_postgres(self, allow_sqlite_fallback: Optional[bool] = None) -> None:
        """Connect to Postgres, create/refresh the schema, or refuse.

        Never silently degrades: if a URL is configured but the connection
        fails, the caller is told loudly. An operator who genuinely wants the
        SQLite fallback sets ``NORTHSTAR_ALLOW_SQLITE_FALLBACK=1`` explicitly.

        Driver: psycopg v3 (the driver the foundation store already uses); a
        psycopg2 install is accepted as a fallback.
        """
        if allow_sqlite_fallback is None:
            allow_sqlite_fallback = env_flag("NORTHSTAR_ALLOW_SQLITE_FALLBACK")
        try:
            import psycopg  # noqa: F401  (driver presence check)
            from psycopg.rows import dict_row  # noqa: F401
            self._pg_driver = "psycopg3"
        except ImportError:
            try:
                import psycopg2  # noqa: F401
                self._pg_driver = "psycopg2"
            except ImportError:
                raise RuntimeError(
                    "POSTGRES CONFIGURED BUT DRIVER MISSING: "
                    f"{_redact_url(self._pg_url)} was configured but neither "
                    "psycopg (v3) nor psycopg2 is installed. Set "
                    "NORTHSTAR_ALLOW_SQLITE_FALLBACK=1 to run on SQLite instead, "
                    "or install the Postgres driver."
                )
        try:
            if self._pg_driver == "psycopg3":
                import psycopg
                from psycopg.rows import dict_row
                conn = psycopg.connect(self._pg_url, connect_timeout=5, row_factory=dict_row)
            else:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(self._pg_url, connect_timeout=5, cursor_factory=psycopg2.extras.RealDictCursor)
        except Exception as exc:
            raise RuntimeError(
                "POSTGRES CONFIGURED BUT UNREACHABLE: "
                f"{_redact_url(self._pg_url)} did not accept a connection "
                f"({exc.__class__.__name__}). Set "
                "NORTHSTAR_ALLOW_SQLITE_FALLBACK=1 to run on SQLite instead."
            ) from exc
        self._pg_conn = conn
        self._pg_last_rowcount = 0
        # The data_layer owns a dedicated schema. The shared `public` schema
        # already holds foundation tables (keywords, listings, audit_events...)
        # with different shapes; without this, CREATE TABLE IF NOT EXISTS would
        # silently collide with them and later indexes would fail.
        with self._lock:
            cur = conn.cursor()
            cur.execute("CREATE SCHEMA IF NOT EXISTS northstar_data")
            cur.execute("SET search_path TO northstar_data")
            conn.commit()
        # Idempotent schema creation/refresh, same DDL source as SQLite.
        self._create_postgres_tables()

    @property
    def mode(self) -> str:
        return self._mode

    def _init_sqlite(self):
        """Create SQLite database and tables if they don't exist."""
        _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the FastAPI app runs sync handlers in a
        # threadpool, so one process-wide connection must be usable across
        # threads. All access is serialized by self._lock.
        #
        # timeout/busy_timeout: serialisation above only covers THIS connection.
        # The chat turn writes tool calls and assets while a render runs for
        # minutes, and other connections in the process (and short-lived tooling
        # processes) then hit the same SQLite write lock. With the stdlib default
        # (5 s) that surfaced as `sqlite3.OperationalError: database is locked`
        # and an HTTP 500 on POST /api/chat/sessions — i.e. starting a new chat
        # failed whenever another turn was in flight. A writer must wait for the
        # lock, not fail on it.
        self._conn = sqlite3.connect(str(_SQLITE_PATH), check_same_thread=False,
                                     timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_sqlite_tables()

    def _schema_ddl(self) -> str:
        """The full schema DDL, shared by BOTH backends.

        The Postgres creator translates the handful of SQLite-isms (the
        `datetime('now')` defaults) before running it; everything else is
        portable DDL (CREATE TABLE/INDEX IF NOT EXISTS, partial unique indexes).
        """
        return ("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                asin TEXT UNIQUE NOT NULL,
                title TEXT,
                brand TEXT,
                category TEXT,
                marketplace TEXT DEFAULT 'US',
                amazon_price REAL,
                buy_box_price REAL,
                costco_cost REAL,
                cost_basis_source TEXT,
                weight_lbs REAL,
                fba_fee_estimate REAL,
                referral_fee_pct REAL,
                bsr_rank INTEGER,
                bsr_category TEXT,
                monthly_sales_estimate INTEGER,
                review_count INTEGER,
                rating REAL,
                seller_count INTEGER,
                net_profit REAL,
                roi_pct REAL,
                risk_score INTEGER,
                authorization_status TEXT,
                last_enriched_at TEXT,
                data_sources TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS keywords (
                id TEXT PRIMARY KEY,
                keyword TEXT NOT NULL,
                search_volume INTEGER,
                relevance_score REAL,
                trend_direction TEXT,
                competition_level TEXT,
                associated_asins TEXT,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                asin TEXT,
                version INTEGER DEFAULT 1,
                title TEXT,
                bullet_points TEXT,
                description TEXT,
                backend_terms TEXT,
                search_terms TEXT,
                seo_score REAL,
                conversion_score REAL,
                compliance_score REAL,
                visual_score REAL,
                rufus_score REAL,
                overall_score REAL,
                status TEXT DEFAULT 'draft',
                published_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                asin TEXT,
                campaign_type TEXT,
                campaign_name TEXT,
                status TEXT DEFAULT 'paused',
                daily_budget REAL,
                targeting_type TEXT,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                spend REAL DEFAULT 0,
                orders INTEGER DEFAULT 0,
                revenue REAL DEFAULT 0,
                acos REAL,
                roas REAL,
                bid_strategy TEXT,
                negative_keywords TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS keyword_performance (
                id TEXT PRIMARY KEY,
                keyword_id TEXT,
                asin TEXT,
                campaign_id TEXT,
                search_volume INTEGER,
                organic_rank INTEGER,
                sponsored_rank INTEGER,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                spend REAL DEFAULT 0,
                orders INTEGER DEFAULT 0,
                revenue REAL DEFAULT 0,
                acos REAL,
                tier TEXT DEFAULT 'bench',
                movement TEXT,
                days_in_tier INTEGER DEFAULT 0,
                recorded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS social_content (
                id TEXT PRIMARY KEY,
                asin TEXT,
                brand TEXT,
                channel TEXT,
                content_type TEXT,
                body TEXT,
                hashtags TEXT,
                media_urls TEXT,
                scheduled_at TEXT,
                published_at TEXT,
                status TEXT DEFAULT 'draft',
                engagement_metrics TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                asin TEXT,
                transaction_type TEXT,
                amount REAL,
                quantity INTEGER,
                source TEXT,
                report_date TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS search_query_performance (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                asin TEXT,
                date_start TEXT,
                date_end TEXT,
                impressions INTEGER,
                clicks INTEGER,
                cart_adds INTEGER,
                purchases INTEGER,
                impression_share REAL,
                click_share REAL,
                cart_share REAL,
                purchase_share REAL,
                search_frequency_rank INTEGER,
                recorded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                entry_type TEXT,
                content TEXT NOT NULL,
                source TEXT,
                confidence REAL DEFAULT 0.8,
                tags TEXT,
                provenance TEXT,
                retired_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                action TEXT,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            -- Supplier intelligence (Phase 1: universal catalog + supplier discovery)
            CREATE TABLE IF NOT EXISTS suppliers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                public_catalog_url TEXT,
                api_endpoint TEXT,
                api_auth_type TEXT,  -- 'none', 'api_key', 'oauth', 'basic'
                api_credentials_ref TEXT,  -- Ref to encrypted credential store
                account_friction_level TEXT CHECK (account_friction_level IN ('low', 'medium', 'high')),
                requires_liftgate BOOLEAN DEFAULT 1,
                liftgate_notes TEXT,
                invoice_verified_status TEXT CHECK (invoice_verified_status IN ('unverified', 'pending', 'verified', 'failed')),
                last_scraped_at TEXT,
                scrape_success_rate REAL DEFAULT 0,
                categories_supplied TEXT,  -- JSON array of category slugs
                logistics_notes TEXT,
                decision_flag TEXT CHECK (decision_flag IN ('viable', 'marginal', 'reject', 'needs_manual_review')),
                friction_notes TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS supplier_products (
                id TEXT PRIMARY KEY,
                supplier_id TEXT NOT NULL REFERENCES suppliers(id),
                supplier_sku TEXT,
                product_name TEXT,
                brand TEXT,
                category_slug TEXT,
                pack_size TEXT,
                unit_count INTEGER,
                wholesale_price REAL,
                wholesale_currency TEXT DEFAULT 'USD',
                moq INTEGER,
                availability TEXT,  -- 'in_stock', 'limited', 'pre_order', 'discontinued'
                weight_lbs REAL,
                scraped_at TEXT,
                scrape_confidence REAL,
                source_file TEXT,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS supplier_cost_analysis (
                id TEXT PRIMARY KEY,
                supplier_product_id TEXT NOT NULL REFERENCES supplier_products(id),
                amazon_asin TEXT,
                amazon_price REAL,
                estimated_net_profit REAL,
                estimated_roi_pct REAL,
                landed_cost REAL,
                fba_fee_estimate REAL,
                referral_fee_estimate REAL,
                inbound_cost_estimate REAL,
                prep_cost_estimate REAL,
                unit_cogs REAL,
                min_roi_threshold REAL,
                meets_threshold BOOLEAN,
                analysis_date TEXT DEFAULT (datetime('now')),
                decision_flag TEXT CHECK (decision_flag IN ('viable', 'marginal', 'reject', 'needs_manual_review')),
                notes TEXT,
                FOREIGN KEY (supplier_product_id) REFERENCES supplier_products(id)
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin);
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
            CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword);
            CREATE INDEX IF NOT EXISTS idx_listings_asin ON listings(asin);
            CREATE INDEX IF NOT EXISTS idx_campaigns_asin ON campaigns(asin);
            CREATE INDEX IF NOT EXISTS idx_keyword_perf_asin ON keyword_performance(asin);
            CREATE INDEX IF NOT EXISTS idx_keyword_perf_tier ON keyword_performance(tier);
            CREATE INDEX IF NOT EXISTS idx_transactions_asin ON transactions(asin);
            CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
            CREATE INDEX IF NOT EXISTS idx_sqp_asin ON search_query_performance(asin);
            CREATE INDEX IF NOT EXISTS idx_memory_account ON memory_entries(account_id);
            CREATE INDEX IF NOT EXISTS idx_audit_account ON audit_log(account_id);
            CREATE INDEX IF NOT EXISTS idx_supplier_products_supplier ON supplier_products(supplier_id);
            CREATE INDEX IF NOT EXISTS idx_supplier_products_sku ON supplier_products(supplier_sku);
            CREATE INDEX IF NOT EXISTS idx_cost_analysis_product ON supplier_cost_analysis(supplier_product_id);

            CREATE TABLE IF NOT EXISTS live_pulls (
                id TEXT PRIMARY KEY,
                query TEXT,
                task_type TEXT,
                provider_id TEXT,
                credits_used REAL DEFAULT 0,
                rows_returned INTEGER DEFAULT 0,
                account_id TEXT DEFAULT 'default',
                started_at TEXT,
                finished_at TEXT,
                ok INTEGER DEFAULT 1,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_live_pulls_query ON live_pulls(query);
            CREATE INDEX IF NOT EXISTS idx_live_pulls_provider ON live_pulls(provider_id);

            -- Design Studio (Phase 0): shared project, asset and job store.
            -- This replaces the split localStorage state across Creative Studio
            -- and Product Designer with one backend-backed store.
            CREATE TABLE IF NOT EXISTS ds_projects (
                id TEXT PRIMARY KEY,
                account_id TEXT DEFAULT 'default',
                name TEXT NOT NULL,
                section TEXT NOT NULL,  -- listing-images, aplus, storefront, ads, video-ugc, social, packaging, 3d-scene
                asin TEXT,
                brand TEXT,
                brief TEXT,
                state TEXT DEFAULT 'draft',
                metadata TEXT,          -- JSON: tags, target formats, keywords used, search terms
                source_record_id TEXT,  -- e.g. product id, listing id, search-term cluster id
                source_record_type TEXT,
                pulled_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_projects_account ON ds_projects(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_projects_section ON ds_projects(section);
            CREATE INDEX IF NOT EXISTS idx_ds_projects_asin ON ds_projects(asin);

            CREATE TABLE IF NOT EXISTS ds_assets (
                id TEXT PRIMARY KEY,
                account_id TEXT DEFAULT 'default',
                project_id TEXT,
                name TEXT,
                asset_type TEXT NOT NULL,  -- image, video, model, font, color, layer_doc, render
                mime_type TEXT,
                storage_key TEXT,          -- blob store / local path reference
                data_url TEXT,             -- small assets only (< 1 MB); prefer storage_key
                width INTEGER,
                height INTEGER,
                duration_seconds REAL,
                size_bytes INTEGER,
                metadata TEXT,             -- JSON: source, provenance, generation params
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_assets_project ON ds_assets(project_id);
            CREATE INDEX IF NOT EXISTS idx_ds_assets_account ON ds_assets(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_assets_type ON ds_assets(asset_type);

            CREATE TABLE IF NOT EXISTS ds_jobs (
                id TEXT PRIMARY KEY,
                account_id TEXT DEFAULT 'default',
                project_id TEXT,
                asset_id TEXT,
                job_type TEXT NOT NULL,    -- generate, upscale, resize, render, export, compliance_check
                provider TEXT DEFAULT 'local',  -- local/comfyui/replicate/runway/etc.
                status TEXT DEFAULT 'queued',   -- queued, running, complete, error, cancelled
                cost_preview TEXT,         -- JSON: currency, estimated credits, note
                credits_used REAL DEFAULT 0,
                params TEXT,               -- JSON: full generation params / workflow
                metadata TEXT,             -- JSON: provenance, legacy import keys, slot
                logs TEXT,                 -- newline-separated log lines
                result_ids TEXT,           -- JSON array of output asset ids
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_jobs_project ON ds_jobs(project_id);
            CREATE INDEX IF NOT EXISTS idx_ds_jobs_account ON ds_jobs(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_jobs_status ON ds_jobs(status);

            -- Re-check log (Phase 5 item 2): the operator's dated record of
            -- verifying that a LIVE asset still carries the disclosure marker.
            -- Tenant-scoped like every other ds_* store.
            CREATE TABLE IF NOT EXISTS ds_rechecks (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                asset_id TEXT,
                checked_at TEXT NOT NULL,
                checked_by TEXT,
                verdict TEXT NOT NULL,     -- marker-present | marker-missing | not-required | exported
                passed INTEGER DEFAULT 0,  -- 0/1: a failed check is recorded as a failure
                detail TEXT,
                surface TEXT,              -- upload-check | library-recheck | export
                tag_required INTEGER,
                legacy_key TEXT,           -- idempotency key for the localStorage import
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_rechecks_account ON ds_rechecks(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_rechecks_asset ON ds_rechecks(asset_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_rechecks_legacy
                ON ds_rechecks(account_id, legacy_key) WHERE legacy_key IS NOT NULL;

            -- Imported marketplace reports (Phase 6 item 4): each import is
            -- archived per account with its source label and observed date, and
            -- is NEVER live data. Fingerprint idempotency: re-importing the
            -- same file is a no-op, not a duplicate.
            CREATE TABLE IF NOT EXISTS ds_imports (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                kind TEXT NOT NULL,            -- sp_search_terms | brand_analytics_sqp
                source_label TEXT NOT NULL,    -- operator-supplied, e.g. "SP console export"
                filename TEXT,
                format TEXT,                   -- csv | json
                observed_from TEXT,            -- first day the file covers (nullable)
                observed_to TEXT,              -- last day the file covers (nullable)
                observed_source TEXT,          -- operator | row-dates | none
                row_count INTEGER DEFAULT 0,
                skipped_rows INTEGER DEFAULT 0,
                columns_found TEXT,            -- JSON array of canonical columns present
                missing_columns TEXT,          -- JSON array: their values are NULL, never 0
                notes TEXT,                    -- JSON array of caveats that travel with the data
                fingerprint TEXT NOT NULL,     -- sha256 of kind + normalized content
                imported_at TEXT NOT NULL,
                imported_by TEXT,
                live INTEGER DEFAULT 0,        -- always 0: a file import is not a live feed
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_imports_account ON ds_imports(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_imports_kind ON ds_imports(kind);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_imports_fingerprint
                ON ds_imports(account_id, fingerprint);

            -- Normalized rows from imported reports. A missing column is NULL in
            -- every row, never 0.
            CREATE TABLE IF NOT EXISTS ds_search_terms (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                import_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                term TEXT NOT NULL,
                campaign TEXT,
                ad_group TEXT,
                match_type TEXT,
                targeting TEXT,
                currency TEXT,
                impressions REAL,
                clicks REAL,
                orders REAL,
                units REAL,
                spend REAL,
                sales REAL,
                search_frequency_rank REAL,
                search_query_score REAL,
                asin_click_share REAL,
                row_from TEXT,
                row_to TEXT,
                extras TEXT,                   -- JSON: parsed columns without a home
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_search_terms_account ON ds_search_terms(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_search_terms_import ON ds_search_terms(import_id);
            CREATE INDEX IF NOT EXISTS idx_ds_search_terms_term ON ds_search_terms(term);

            -- Creative variants + their performance metrics (Phase 6 item 6).
            -- Metrics are user-entered or file-imported only; nothing is
            -- inferred from a provider, and a missing metric is NULL.
            CREATE TABLE IF NOT EXISTS ds_variants (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                project_id TEXT,
                name TEXT NOT NULL,
                asset_id TEXT,                 -- uploaded asset id (ds_assets)
                format TEXT,
                status TEXT DEFAULT 'draft',   -- draft | in-review | approved | retired
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_variants_account ON ds_variants(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_variants_project ON ds_variants(project_id);

            CREATE TABLE IF NOT EXISTS ds_variant_metrics (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'user',  -- user | file
                import_id TEXT,
                observed_from TEXT,
                observed_to TEXT,
                impressions REAL,
                clicks REAL,
                orders REAL,
                spend REAL,
                sales REAL,
                note TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_variant_metrics_account ON ds_variant_metrics(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_variant_metrics_variant ON ds_variant_metrics(variant_id);

            -- Listing records (Phase 8 item 3): the tenant-store home for the
            -- listing context. Migrated one-shot from the browser-local
            -- ListingForge records, idempotent via a per-account legacy key.
            CREATE TABLE IF NOT EXISTS ds_listing_records (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                asin TEXT,
                title TEXT,
                bullets TEXT,            -- JSON array
                backend_terms TEXT,
                description TEXT,
                images TEXT,             -- JSON array of local asset metadata
                aplus_modules TEXT,      -- JSON array of module names
                source TEXT NOT NULL DEFAULT 'listingforge-local',
                observed_at TEXT,
                legacy_key TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_listing_records_account ON ds_listing_records(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_listing_records_asin ON ds_listing_records(asin);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_listing_records_legacy
                ON ds_listing_records(account_id, legacy_key) WHERE legacy_key IS NOT NULL;

            -- Amazon FILE uploads (file-only architecture, 2026-10-11): the
            -- seller's downloaded files, archived per tenant with checksum,
            -- detection, parsed rows and observed range. Read-only: nothing
            -- here ever talks to Amazon.
            CREATE TABLE IF NOT EXISTS ds_amazon_uploads (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                kind TEXT NOT NULL,
                checksum TEXT NOT NULL,
                content_b64 TEXT NOT NULL,   -- the original bytes (base64); never modified
                size_bytes INTEGER,
                row_count INTEGER DEFAULT 0,
                observed_from TEXT,
                observed_to TEXT,
                downloaded_at TEXT,
                uploaded_at TEXT NOT NULL,
                columns_found TEXT,          -- JSON
                missing_columns TEXT,        -- JSON
                notes TEXT,                  -- JSON
                detection TEXT,              -- JSON
                parsed TEXT,                 -- JSON: sheets with raw rows + mapped indices
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ds_amazon_uploads_account ON ds_amazon_uploads(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_amazon_uploads_kind ON ds_amazon_uploads(kind);

            -- Row-level change proposals against an uploaded file.
            CREATE TABLE IF NOT EXISTS ds_change_proposals (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                upload_id TEXT NOT NULL,
                payload TEXT NOT NULL,       -- JSON: before/after/reason/evidence/blocks/flags
                status TEXT DEFAULT 'proposed',  -- proposed | blocked | approved | rejected
                requires_second_confirmation INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                decided_at TEXT,
                decided_by TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ds_change_proposals_account ON ds_change_proposals(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_change_proposals_upload ON ds_change_proposals(upload_id);

            -- Written change files (new files; the originals are never modified).
            CREATE TABLE IF NOT EXISTS ds_change_files (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                upload_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                format TEXT NOT NULL,
                checksum TEXT NOT NULL,
                content_b64 TEXT NOT NULL,
                row_count INTEGER DEFAULT 0,
                approved TEXT,               -- JSON: the approved proposal ids
                roundtrip TEXT,              -- JSON: the validator report
                written_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ds_change_files_account ON ds_change_files(account_id);
            CREATE INDEX IF NOT EXISTS idx_ds_change_files_upload ON ds_change_files(upload_id);
        """ + CHAT_TABLES_SQL + SEO_TABLES_SQL + CORPUS_TABLES_SQL)

    def _create_sqlite_tables(self):
        """Create all tables for SQLite mode (idempotent)."""
        cur = self._conn.cursor()
        cur.executescript(self._schema_ddl())
        self._conn.commit()
        self._migrate_live_columns()

    def _create_postgres_tables(self):
        """Create all tables for Postgres mode (idempotent).

        The DDL is the same source as SQLite; only the timestamp default
        syntax differs (`datetime('now')` -> `CURRENT_TIMESTAMP`).
        """
        ddl = self._schema_ddl()
        # The SQLite-isms in the shared DDL, translated for Postgres.
        ddl = ddl.replace("datetime('now')", "CURRENT_TIMESTAMP")
        ddl = ddl.replace("id INTEGER PRIMARY KEY AUTOINCREMENT", "id BIGSERIAL PRIMARY KEY")
        # The supplier flag is declared BOOLEAN with an integer default and the
        # DAO compares it with 0/1 parameters on both backends; Postgres would
        # reject both the default and the comparisons, so it stays INTEGER here
        # (same semantics, consistent across backends).
        ddl = ddl.replace("requires_liftgate BOOLEAN DEFAULT 1", "requires_liftgate INTEGER DEFAULT 1")
        with self._lock:
            cur = self._pg_conn.cursor()
            try:
                cur.execute(ddl)
                self._pg_conn.commit()
            except Exception:
                self._pg_conn.rollback()
                raise
        self._migrate_live_columns_postgres()

    def _migrate_live_columns_postgres(self):
        """Idempotently add the live-data columns on Postgres.

        The existing columns are checked FIRST so a steady-state boot takes no
        ACCESS EXCLUSIVE lock on products (an ALTER waiting on another
        connection's lock is how the harness hung once; never again).
        """
        additions = {
            "data_kind": "TEXT DEFAULT 'demo'",
            "provider_id": "TEXT",
            "fetched_at": "TEXT",
            "fresh_until": "TEXT",
        }
        with self._lock:
            cur = self._pg_conn.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='northstar_data' AND table_name='products'"
            )
            existing = {r["column_name"] for r in cur.fetchall()}
            self._pg_conn.commit()
            for column, decl in additions.items():
                if column in existing:
                    continue
                try:
                    cur.execute(f"ALTER TABLE products ADD COLUMN IF NOT EXISTS {column} {decl}")
                except Exception:
                    self._pg_conn.rollback()
                    raise
            self._pg_conn.commit()

    def _migrate_live_columns(self):
        """Idempotently add live-data columns to an existing products table."""
        try:
            cur = self._conn.execute("PRAGMA table_info(products)")
            existing = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        additions = {
            "data_kind": "TEXT DEFAULT 'demo'",
            "provider_id": "TEXT",
            "fetched_at": "TEXT",
            "fresh_until": "TEXT",
        }
        for col, decl in additions.items():
            if col not in existing:
                try:
                    self._conn.execute(f"ALTER TABLE products ADD COLUMN {col} {decl}")
                except sqlite3.Error:
                    pass
        self._conn.commit()
        self._migrate_ds_columns()
        self._migrate_chat_columns()

    def _migrate_chat_columns(self):
        """Idempotently add V3 S5 columns to an existing chat_tool_calls table."""
        try:
            cur = self._conn.execute("PRAGMA table_info(chat_tool_calls)")
            existing = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not existing:
            return  # table not present; CREATE above already made it right
        if "step_index" not in existing:
            try:
                self._conn.execute("ALTER TABLE chat_tool_calls ADD COLUMN step_index INTEGER")
            except sqlite3.Error:
                pass
        self._conn.commit()

    def _migrate_ds_columns(self):
        """Idempotently bring an EXISTING ds_* table up to the current shape.

        ds_jobs shipped without a metadata column, so a migrated job had nowhere
        to record its legacy key and the import failed on every job. CREATE
        TABLE IF NOT EXISTS does not alter a table that already exists, so the
        column has to be added explicitly here.
        """
        try:
            cur = self._conn.execute("PRAGMA table_info(ds_jobs)")
            existing = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not existing:
            return  # table not present at all; CREATE above already made it right
        if "metadata" not in existing:
            try:
                self._conn.execute("ALTER TABLE ds_jobs ADD COLUMN metadata TEXT")
            except sqlite3.Error:
                pass
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()):
        """Execute SQL on the active backend.

        SQLite: exactly as before. Postgres: `?` placeholders are translated to
        `%s`; `SELECT changes()` is answered from the last statement's rowcount
        (the SQLite idiom the DAOs use to report affected rows); a driver
        IntegrityError is re-raised as sqlite3.IntegrityError so the existing
        idempotency handlers (duplicate fingerprints / legacy keys) work
        unchanged on both backends.
        """
        if self._mode == "sqlite":
            with self._lock:
                return self._conn.execute(sql, params)
        return self._execute_pg(sql, params)

    def _execute_pg(self, sql: str, params: tuple = ()):
        with self._lock:
            if sql.strip().lower().startswith("select changes()"):
                # SQLite reports affected rows via changes(); answer it here.
                return _PgChangesResult(self._pg_last_rowcount)
            # Literal percent signs (LIKE patterns) must be escaped for psycopg,
            # THEN the SQLite `?` placeholders become `%s`. Parameter VALUES are
            # never interpolated, so this cannot touch data.
            translated = sql.replace("%", "%%").replace("?", "%s")
            cur = self._pg_conn.cursor()
            try:
                cur.execute(translated, tuple(params))
                # A statement with a result set opens a transaction in psycopg.
                # Close it immediately: a connection left idle-in-transaction
                # holds locks that block schema creation elsewhere (found live:
                # an idle SELECT on ds_rechecks blocked ALTER TABLE products).
                if cur.description is not None:
                    self._pg_conn.commit()
                self._pg_last_rowcount = max(0, cur.rowcount if cur.rowcount is not None else 0)
                return cur
            except Exception as exc:
                try:
                    self._pg_conn.rollback()
                except Exception:
                    pass
                if _is_pg_integrity_error(exc):
                    raise sqlite3.IntegrityError(str(exc)) from exc
                raise

    def executemany(self, sql: str, params_list: list):
        """Execute many SQL statements."""
        if self._mode == "sqlite":
            with self._lock:
                return self._conn.executemany(sql, params_list)
        with self._lock:
            cur = self._pg_conn.cursor()
            try:
                cur.executemany(sql.replace("?", "%s"), [tuple(p) for p in params_list])
                self._pg_last_rowcount = max(0, cur.rowcount if cur.rowcount is not None else 0)
                return cur
            except Exception as exc:
                try:
                    self._pg_conn.rollback()
                except Exception:
                    pass
                if _is_pg_integrity_error(exc):
                    raise sqlite3.IntegrityError(str(exc)) from exc
                raise

    def commit(self):
        """Commit the current transaction."""
        with self._lock:
            if self._mode == "sqlite":
                self._conn.commit()
            else:
                self._pg_conn.commit()

    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._mode == "sqlite":
                if self._conn:
                    self._conn.close()
            elif getattr(self, "_pg_conn", None):
                self._pg_conn.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_db_instance: Optional[DataLayer] = None


def get_db() -> DataLayer:
    """Get or create the database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DataLayer()
    return _db_instance


# ---------------------------------------------------------------------------
# Products Data Access
# ---------------------------------------------------------------------------

class ProductsDB:
    """Data access for the products table."""

    def __init__(self, db: DataLayer):
        self.db = db

    def upsert(self, product: Dict[str, Any]) -> str:
        """Insert or update a product. Returns the product ID."""
        import uuid
        asin = product.get("asin", "")
        if not asin:
            raise ValueError("Product must have an ASIN")

        # Check if exists
        cur = self.db.execute("SELECT id FROM products WHERE asin = ?", (asin,))
        row = cur.fetchone()

        if row:
            # Update
            product_id = row["id"]
            fields = []
            values = []
            for key, value in product.items():
                if key in ("id", "asin"):
                    continue
                if key == "data_sources" and isinstance(value, (dict, list)):
                    value = json.dumps(value)
                fields.append(f"{key} = ?")
                values.append(value)
            fields.append("updated_at = ?")
            values.append(datetime.now(timezone.utc).isoformat())
            values.append(product_id)
            self.db.execute(
                f"UPDATE products SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )
        else:
            # Insert
            product_id = str(uuid.uuid4())
            product["id"] = product_id
            now = datetime.now(timezone.utc).isoformat()
            product.setdefault("created_at", now)
            product["updated_at"] = now
            if "data_sources" in product and isinstance(product["data_sources"], (dict, list)):
                product["data_sources"] = json.dumps(product["data_sources"])
            columns = list(product.keys())
            placeholders = ", ".join(["?"] * len(columns))
            col_names = ", ".join(columns)
            self.db.execute(
                f"INSERT INTO products ({col_names}) VALUES ({placeholders})",
                tuple(product.values()),
            )

        self.db.commit()
        return product_id

    def get_by_asin(self, asin: str) -> Optional[Dict[str, Any]]:
        """Get a single product by ASIN."""
        cur = self.db.execute("SELECT * FROM products WHERE asin = ?", (asin,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None

    def list_products(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "updated_at DESC",
    ) -> List[Dict[str, Any]]:
        """List products with optional filters."""
        sql = "SELECT * FROM products"
        params = []
        if category:
            sql += " WHERE category = ?"
            params.append(category)
        sql += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cur = self.db.execute(sql, tuple(params))
        return [dict(row) for row in cur.fetchall()]

    def count(self, category: Optional[str] = None) -> int:
        """Count products, optionally by category."""
        if category:
            cur = self.db.execute(
                "SELECT COUNT(*) as cnt FROM products WHERE category = ?",
                (category,),
            )
        else:
            cur = self.db.execute("SELECT COUNT(*) as cnt FROM products")
        return cur.fetchone()["cnt"]

    def delete_by_asin(self, asin: str) -> bool:
        """Delete a product by ASIN."""
        cur = self.db.execute("DELETE FROM products WHERE asin = ?", (asin,))
        self.db.commit()
        return cur.rowcount > 0

    # --- live-data warehouse (Phase A / A3) ---

    def upsert_live(self, product: Dict[str, Any], provider_id: str,
                    ttl_seconds: int = 86400) -> str:
        """Upsert a product as LIVE data with provenance + freshness window."""
        now = datetime.now(timezone.utc)
        row = dict(product)
        row["data_kind"] = "live"
        row["provider_id"] = provider_id
        row["fetched_at"] = now.isoformat()
        row["fresh_until"] = (now + timedelta(seconds=ttl_seconds)).isoformat()
        return self.upsert(row)

    def list_stocked(self, category: Optional[str] = None, limit: int = 500,
                     fresh_only: bool = True) -> List[Dict[str, Any]]:
        """List live-stocked products (fresh by default — the stock-first read)."""
        sql = "SELECT * FROM products WHERE data_kind = 'live'"
        params: list = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if fresh_only:
            sql += " AND (fresh_until IS NULL OR fresh_until > ?)"
            params.append(datetime.now(timezone.utc).isoformat())
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [dict(row) for row in cur.fetchall()]

    def count_live(self, fresh_only: bool = False) -> int:
        sql = "SELECT COUNT(*) as cnt FROM products WHERE data_kind = 'live'"
        params: tuple = ()
        if fresh_only:
            sql += " AND (fresh_until IS NULL OR fresh_until > ?)"
            params = (datetime.now(timezone.utc).isoformat(),)
        return self.db.execute(sql, params).fetchone()["cnt"]

    def mark_demo(self, asin: str) -> None:
        """Downgrade a row to demo provenance (fixture hygiene)."""
        self.db.execute("UPDATE products SET data_kind = 'demo' WHERE asin = ?", (asin,))
        self.db.commit()


class LivePullsDB:
    """Append-only audit of live provider pulls (Phase A / A3)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def record(self, query: str, task_type: str, provider_id: str,
               credits_used: float = 0, rows_returned: int = 0,
               account_id: str = "default", ok: bool = True,
               error: Optional[str] = None,
               started_at: Optional[str] = None,
               finished_at: Optional[str] = None) -> str:
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        pid = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO live_pulls
               (id, query, task_type, provider_id, credits_used, rows_returned,
                account_id, started_at, finished_at, ok, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, query, task_type, provider_id, credits_used, rows_returned,
             account_id, started_at or now, finished_at or now, 1 if ok else 0, error),
        )
        self.db.commit()
        return pid

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM live_pulls ORDER BY finished_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cur.fetchall()]

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) as cnt FROM live_pulls").fetchone()["cnt"]


# ---------------------------------------------------------------------------
# Keywords Data Access
# ---------------------------------------------------------------------------

class KeywordsDB:
    """Data access for the keywords table."""

    def __init__(self, db: DataLayer):
        self.db = db

    def upsert(self, keyword: Dict[str, Any]) -> str:
        """Insert or update a keyword."""
        import uuid
        kw_text = keyword.get("keyword", "")
        if not kw_text:
            raise ValueError("Keyword must have text")

        cur = self.db.execute("SELECT id FROM keywords WHERE keyword = ?", (kw_text,))
        row = cur.fetchone()

        if row:
            kid = row["id"]
            fields = []
            values = []
            for key, value in keyword.items():
                if key in ("id", "keyword"):
                    continue
                if key == "associated_asins" and isinstance(value, list):
                    value = json.dumps(value)
                fields.append(f"{key} = ?")
                values.append(value)
            values.append(kid)
            if fields:
                self.db.execute(
                    f"UPDATE keywords SET {', '.join(fields)} WHERE id = ?",
                    tuple(values),
                )
        else:
            kid = str(uuid.uuid4())
            keyword["id"] = kid
            if "associated_asins" in keyword and isinstance(keyword["associated_asins"], list):
                keyword["associated_asins"] = json.dumps(keyword["associated_asins"])
            columns = list(keyword.keys())
            placeholders = ", ".join(["?"] * len(columns))
            col_names = ", ".join(columns)
            self.db.execute(
                f"INSERT INTO keywords ({col_names}) VALUES ({placeholders})",
                tuple(keyword.values()),
            )

        self.db.commit()
        return kid

    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search keywords."""
        cur = self.db.execute(
            "SELECT * FROM keywords WHERE keyword LIKE ? ORDER BY search_volume DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_by_id(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get a keyword by ID."""
        cur = self.db.execute("SELECT * FROM keywords WHERE id = ?", (kid,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_by_asin(self, asin: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List keywords associated with a specific ASIN."""
        cur = self.db.execute(
            "SELECT * FROM keywords WHERE associated_asins LIKE ? ORDER BY search_volume DESC LIMIT ?",
            (f"%{asin}%", limit),
        )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Listings Data Access
# ---------------------------------------------------------------------------

class ListingsDB:
    """Data access for the listings table (versioned)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def create(self, listing: Dict[str, Any]) -> str:
        """Create a new listing version."""
        import uuid
        lid = str(uuid.uuid4())
        listing["id"] = lid
        now = datetime.now(timezone.utc).isoformat()
        listing.setdefault("created_at", now)
        listing["updated_at"] = now
        if "bullet_points" in listing and isinstance(listing["bullet_points"], list):
            listing["bullet_points"] = json.dumps(listing["bullet_points"])
        if "backend_terms" in listing and isinstance(listing["backend_terms"], list):
            listing["backend_terms"] = json.dumps(listing["backend_terms"])
        columns = list(listing.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        self.db.execute(
            f"INSERT INTO listings ({col_names}) VALUES ({placeholders})",
            tuple(listing.values()),
        )
        self.db.commit()
        return lid

    def get_latest(self, asin: str) -> Optional[Dict[str, Any]]:
        """Get the latest listing version for an ASIN."""
        cur = self.db.execute(
            "SELECT * FROM listings WHERE asin = ? ORDER BY version DESC LIMIT 1",
            (asin,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_versions(self, asin: str) -> List[Dict[str, Any]]:
        """List all versions for an ASIN."""
        cur = self.db.execute(
            "SELECT * FROM listings WHERE asin = ? ORDER BY version DESC",
            (asin,),
        )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Campaigns Data Access
# ---------------------------------------------------------------------------

class CampaignsDB:
    """Data access for the campaigns table."""

    def __init__(self, db: DataLayer):
        self.db = db

    def upsert(self, campaign: Dict[str, Any]) -> str:
        """Insert or update a campaign."""
        import uuid
        cid = campaign.get("id") or str(uuid.uuid4())
        campaign["id"] = cid
        now = datetime.now(timezone.utc).isoformat()
        campaign.setdefault("created_at", now)
        campaign["updated_at"] = now
        if "negative_keywords" in campaign and isinstance(campaign["negative_keywords"], list):
            campaign["negative_keywords"] = json.dumps(campaign["negative_keywords"])

        cur = self.db.execute("SELECT id FROM campaigns WHERE id = ?", (cid,))
        row = cur.fetchone()

        if row:
            fields = []
            values = []
            for key, value in campaign.items():
                if key == "id":
                    continue
                fields.append(f"{key} = ?")
                values.append(value)
            values.append(cid)
            self.db.execute(
                f"UPDATE campaigns SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )
        else:
            columns = list(campaign.keys())
            placeholders = ", ".join(["?"] * len(columns))
            col_names = ", ".join(columns)
            self.db.execute(
                f"INSERT INTO campaigns ({col_names}) VALUES ({placeholders})",
                tuple(campaign.values()),
            )

        self.db.commit()
        return cid

    def list_by_asin(self, asin: str) -> List[Dict[str, Any]]:
        """List campaigns for an ASIN."""
        cur = self.db.execute(
            "SELECT * FROM campaigns WHERE asin = ? ORDER BY created_at DESC",
            (asin,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_by_id(self, cid: str) -> Optional[Dict[str, Any]]:
        """Get a campaign by ID."""
        cur = self.db.execute("SELECT * FROM campaigns WHERE id = ?", (cid,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List all campaigns."""
        if status:
            cur = self.db.execute(
                "SELECT * FROM campaigns WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur = self.db.execute(
                "SELECT * FROM campaigns ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Transaction Data Access
# ---------------------------------------------------------------------------

class TransactionsDB:
    """Data access for the transactions table (financial tracking)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def insert(self, transaction: Dict[str, Any]) -> str:
        """Insert a financial transaction."""
        import uuid
        tid = str(uuid.uuid4())
        transaction["id"] = tid
        now = datetime.now(timezone.utc).isoformat()
        transaction.setdefault("created_at", now)
        columns = list(transaction.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        self.db.execute(
            f"INSERT INTO transactions ({col_names}) VALUES ({placeholders})",
            tuple(transaction.values()),
        )
        self.db.commit()
        return tid

    def summary_by_asin(self, asin: str) -> Dict[str, Any]:
        """Get financial summary for an ASIN."""
        cur = self.db.execute(
            """SELECT transaction_type, SUM(amount) as total_amount, SUM(quantity) as total_qty
               FROM transactions WHERE asin = ? GROUP BY transaction_type""",
            (asin,),
        )
        rows = cur.fetchall()
        summary = {}
        for row in rows:
            summary[row["transaction_type"]] = {
                "total_amount": row["total_amount"],
                "total_quantity": row["total_qty"],
            }
        return summary

    def list_by_asin(self, asin: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List transactions for an ASIN."""
        cur = self.db.execute(
            "SELECT * FROM transactions WHERE asin = ? ORDER BY created_at DESC LIMIT ?",
            (asin,),
        )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Memory Bank Data Access
# ---------------------------------------------------------------------------

class MemoryDB:
    """Data access for the memory_entries table (per-account learning)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def ingest(self, entry: Dict[str, Any]) -> str:
        """Add a memory entry."""
        import uuid
        eid = str(uuid.uuid4())
        entry["id"] = eid
        now = datetime.now(timezone.utc).isoformat()
        entry.setdefault("created_at", now)
        entry["updated_at"] = now
        if "tags" in entry and isinstance(entry["tags"], list):
            entry["tags"] = json.dumps(entry["tags"])
        if "provenance" in entry and isinstance(entry["provenance"], dict):
            entry["provenance"] = json.dumps(entry["provenance"])
        columns = list(entry.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        self.db.execute(
            f"INSERT INTO memory_entries ({col_names}) VALUES ({placeholders})",
            tuple(entry.values()),
        )
        self.db.commit()
        return eid

    def search(self, account_id: str, intent: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memory entries by account and content match."""
        cur = self.db.execute(
            """SELECT * FROM memory_entries
               WHERE account_id = ? AND content LIKE ? AND retired_at IS NULL
               ORDER BY confidence DESC, created_at DESC LIMIT ?""",
            (account_id, f"%{intent}%", limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def list_by_account(self, account_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List all active memory entries for an account."""
        cur = self.db.execute(
            """SELECT * FROM memory_entries
               WHERE account_id = ? AND retired_at IS NULL
               ORDER BY created_at DESC LIMIT ?""",
            (account_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def retire(self, eid: str) -> bool:
        """Retire (unlearn) a memory entry."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self.db.execute(
            "UPDATE memory_entries SET retired_at = ? WHERE id = ?",
            (now, eid),
        )
        self.db.commit()
        return cur.rowcount > 0

    def count(self, account_id: str) -> int:
        """Count active entries for an account."""
        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM memory_entries WHERE account_id = ? AND retired_at IS NULL",
            (account_id,),
        )
        return cur.fetchone()["cnt"]


# ---------------------------------------------------------------------------
# Audit Log Data Access
# ---------------------------------------------------------------------------

class AuditDB:
    """Data access for the audit_log table (append-only)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def log(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        account_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Append an audit log entry."""
        self.db.execute(
            "INSERT INTO audit_log (account_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
            (account_id, action, entity_type, entity_id,
             json.dumps(details) if details else None),
        )
        self.db.commit()

    def list_recent(self, limit: int = 100, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List recent audit entries."""
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM audit_log WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
                (account_id, limit),
            )
        else:
            cur = self.db.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Supplier Intelligence Data Access (Phase 1)
# ---------------------------------------------------------------------------

class SuppliersDB:
    """Data access for the suppliers / supplier_products / supplier_cost_analysis
    tables — the supplier intelligence module backing the "Find a Supplier"
    dashboard, catalog ingestion, and pre-account cost-benefit analysis.

    All methods accept/return plain dicts keyed by the table column names.
    IDs are operator/ingestion-supplied (stable across re-ingests) or
    generated as ASCII slugs.
    """

    def __init__(self, db: DataLayer):
        self.db = db

    # -- suppliers -----------------------------------------------------------

    _SUPPLIER_COLUMNS = [
        "id", "name", "public_catalog_url", "api_endpoint", "api_auth_type",
        "api_credentials_ref", "account_friction_level", "requires_liftgate",
        "liftgate_notes", "invoice_verified_status", "last_scraped_at",
        "scrape_success_rate", "categories_supplied", "logistics_notes",
        "decision_flag", "friction_notes", "contact_email", "contact_phone",
    ]

    def upsert(self, supplier: Dict[str, Any]) -> str:
        """Insert or replace a supplier by id. Returns the supplier id."""
        sup = dict(supplier)
        sup.setdefault("id", _slugify(sup.get("name") or "supplier"))
        sup.setdefault("account_friction_level", "medium")
        sup.setdefault("requires_liftgate", 1)
        sup.setdefault("invoice_verified_status", "unverified")
        sup.setdefault("decision_flag", "needs_manual_review")
        if isinstance(sup.get("requires_liftgate"), bool):
            sup["requires_liftgate"] = 1 if sup["requires_liftgate"] else 0
        if isinstance(sup.get("categories_supplied"), (list, tuple)):
            sup["categories_supplied"] = json.dumps(list(sup["categories_supplied"]))
        now = datetime.now(timezone.utc).isoformat()
        sup["updated_at"] = now
        cols = [c for c in self._SUPPLIER_COLUMNS if c in sup]
        insert_cols = cols + ["created_at"]
        placeholders = ", ".join("?" for _ in insert_cols)
        update_clause = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
        params = [sup[c] for c in insert_cols] if "created_at" not in insert_cols else \
            [sup[c] for c in insert_cols[:-1]] + [now]
        # created_at handled via COALESCE on upsert: use INSERT ... ON CONFLICT
        self.db.execute(
            f"""INSERT INTO suppliers ({", ".join(insert_cols)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET
                    {update_clause},
                    updated_at = excluded.updated_at""",
            tuple(params),
        )
        self.db.commit()
        return sup["id"]

    def get_by_id(self, sid: str) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM suppliers WHERE id = ?", (sid,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(
        self,
        decision_flag: Optional[str] = None,
        requires_liftgate: Optional[bool] = None,
        category_slug: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List suppliers with optional filters.

        ``category_slug`` matches a slug contained in the JSON
        ``categories_supplied`` column (LIKE match on the serialized array).
        """
        sql = "SELECT * FROM suppliers WHERE 1=1"
        params: List[Any] = []
        if decision_flag:
            sql += " AND decision_flag = ?"
            params.append(decision_flag)
        if requires_liftgate is not None:
            sql += " AND requires_liftgate = ?"
            params.append(1 if requires_liftgate else 0)
        if category_slug:
            sql += " AND categories_supplied LIKE ?"
            params.append(f"%{category_slug}%")
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]

    def update_flag(self, sid: str, decision_flag: str) -> bool:
        """Set a supplier's decision flag (viable/marginal/reject/review)."""
        cur = self.db.execute(
            "UPDATE suppliers SET decision_flag = ?, updated_at = ? WHERE id = ?",
            (decision_flag, datetime.now(timezone.utc).isoformat(), sid),
        )
        self.db.commit()
        return cur.rowcount > 0

    def delete(self, sid: str) -> bool:
        """Delete a supplier and all dependent rows (products + analyses)."""
        # Order matters: analyses reference products, products reference the
        # supplier (the FKs have no ON DELETE CASCADE).
        self.db.execute(
            """DELETE FROM supplier_cost_analysis
               WHERE supplier_product_id IN
                 (SELECT id FROM supplier_products WHERE supplier_id = ?)""",
            (sid,),
        )
        self.db.execute("DELETE FROM supplier_products WHERE supplier_id = ?", (sid,))
        cur = self.db.execute("DELETE FROM suppliers WHERE id = ?", (sid,))
        self.db.commit()
        return cur.rowcount > 0

    # -- supplier_products ---------------------------------------------------

    _SUPPLIER_PRODUCT_COLUMNS = [
        "id", "supplier_id", "supplier_sku", "product_name", "brand",
        "category_slug", "pack_size", "unit_count", "wholesale_price",
        "wholesale_currency", "moq", "availability", "weight_lbs",
        "scraped_at", "scrape_confidence", "source_file",
    ]

    def add_product(self, supplier_id: str, product: Dict[str, Any]) -> str:
        """Insert or update one supplier product. Returns the product id.

        Idempotent: the id is stable per (supplier_id, supplier_sku) when a
        SKU is present, else per (supplier_id, product_name). Re-importing
        the same catalog updates rows instead of failing on the primary key.
        """
        p = dict(product)
        sku = p.get("supplier_sku")
        p.setdefault(
            "id",
            _slugify(f"{supplier_id}-{sku or p.get('product_name') or p.get('id') or len(p)}"),
        )
        p["supplier_id"] = supplier_id
        p.setdefault("wholesale_currency", "USD")
        p.setdefault("availability", "in_stock")
        p.setdefault("scraped_at", datetime.now(timezone.utc).isoformat())
        cols = [c for c in self._SUPPLIER_PRODUCT_COLUMNS if c in p]
        placeholders = ", ".join("?" for _ in cols)
        update_clause = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
        self.db.execute(
            f"""INSERT INTO supplier_products ({", ".join(cols)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {update_clause}""",
            tuple(p[c] for c in cols),
        )
        self.db.commit()
        return p["id"]

    def add_products(self, supplier_id: str, products: List[Dict[str, Any]]) -> int:
        """Bulk-insert products for a supplier. Returns the count inserted."""
        for p in products:
            self.add_product(supplier_id, p)
        return len(products)

    def get_products(
        self,
        supplier_id: str,
        limit: int = 500,
        min_wholesale_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM supplier_products WHERE supplier_id = ?"
        params: List[Any] = [supplier_id]
        if min_wholesale_price is not None:
            sql += " AND wholesale_price >= ?"
            params.append(min_wholesale_price)
        sql += " ORDER BY scraped_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]

    def get_product_by_id(self, pid: str) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM supplier_products WHERE id = ?", (pid,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def count_products(self, supplier_id: str) -> int:
        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM supplier_products WHERE supplier_id = ?",
            (supplier_id,),
        )
        return cur.fetchone()["cnt"]

    def replace_products(self, supplier_id: str, products: List[Dict[str, Any]]) -> int:
        """Replace all products for a supplier (used after a fresh scrape)."""
        self.db.execute(
            """DELETE FROM supplier_cost_analysis
               WHERE supplier_product_id IN
                 (SELECT id FROM supplier_products WHERE supplier_id = ?)""",
            (supplier_id,),
        )
        self.db.execute(
            "DELETE FROM supplier_products WHERE supplier_id = ?", (supplier_id,)
        )
        self.db.commit()
        return self.add_products(supplier_id, products)

    # -- supplier_cost_analysis ----------------------------------------------

    _ANALYSIS_COLUMNS = [
        "id", "supplier_product_id", "amazon_asin", "amazon_price",
        "estimated_net_profit", "estimated_roi_pct", "landed_cost",
        "fba_fee_estimate", "referral_fee_estimate", "inbound_cost_estimate",
        "prep_cost_estimate", "unit_cogs", "min_roi_threshold",
        "meets_threshold", "decision_flag", "notes",
    ]

    def add_cost_analysis(self, product_id: str, analysis: Dict[str, Any]) -> str:
        """Append one cost-benefit analysis row. Returns the analysis id.

        Analyses are a time-series (every re-run is kept for history), so each
        call gets a unique id unless the caller supplies one explicitly.
        """
        a = dict(analysis)
        a.setdefault("id", f"ca-{product_id}-{uuid.uuid4().hex[:12]}")
        a["supplier_product_id"] = product_id
        if isinstance(a.get("notes"), list):
            a["notes"] = json.dumps(a["notes"])
        a.setdefault("analysis_date", datetime.now(timezone.utc).isoformat())
        a.setdefault("decision_flag", "needs_manual_review")
        cols = [c for c in self._ANALYSIS_COLUMNS if c in a] + ["analysis_date"]
        placeholders = ", ".join("?" for _ in cols)
        self.db.execute(
            f"""INSERT INTO supplier_cost_analysis ({", ".join(cols)})
                VALUES ({placeholders})""",
            tuple(a[c] for c in cols),
        )
        self.db.commit()
        return a["id"]

    def get_analyses(
        self,
        product_id: Optional[str] = None,
        decision_flag: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM supplier_cost_analysis WHERE 1=1"
        params: List[Any] = []
        if product_id:
            sql += " AND supplier_product_id = ?"
            params.append(product_id)
        if decision_flag:
            sql += " AND decision_flag = ?"
            params.append(decision_flag)
        sql += " ORDER BY analysis_date DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]


def _slugify(value: Any) -> str:
    """Deterministic ASCII slug id for supplier entity ids."""
    import re as _re
    s = str(value or "")
    s = _re.sub(r"[^a-zA-Z0-9_.-]+", "-", s).strip("-").lower()
    return s[:96] or "item"


# ---------------------------------------------------------------------------
# Design Studio Data Access (Phase 0)
# ---------------------------------------------------------------------------

class DesignStudioProjectsDB:
    """Projects are the top-level creative containers in Design Studio."""

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("metadata",):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def create(self, project: Dict[str, Any]) -> str:
        import uuid
        pid = project.get("id") or str(uuid.uuid4())
        project = dict(project)
        project["id"] = pid
        project.setdefault("account_id", "default")
        project.setdefault("state", "draft")
        now = datetime.now(timezone.utc).isoformat()
        project.setdefault("created_at", now)
        project.setdefault("updated_at", now)
        if "metadata" in project and isinstance(project["metadata"], dict):
            project["metadata"] = json.dumps(project["metadata"])
        cols = [c for c in project.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_projects ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(project.values()),
        )
        self.db.commit()
        return pid

    def get_by_id(self, pid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch a project. When ``account_id`` is given the read is
        TENANT-SCOPED: a project owned by another account returns None rather
        than leaking across tenants."""
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM ds_projects WHERE id = ? AND account_id = ?", (pid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_projects WHERE id = ?", (pid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_by_section(self, section: Optional[str] = None, account_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_projects WHERE 1=1"
        params: List[Any] = []
        if section:
            sql += " AND section = ?"
            params.append(section)
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]

    def update(self, pid: str, patch: Dict[str, Any], account_id: Optional[str] = None) -> bool:
        if not patch:
            return False
        patch = dict(patch)
        patch.pop("id", None)
        patch.pop("account_id", None)  # ownership is never reassignable by patch
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "metadata" in patch and isinstance(patch["metadata"], dict):
            patch["metadata"] = json.dumps(patch["metadata"])
        fields = ", ".join(f"{k} = ?" for k in patch.keys())
        if account_id:
            self.db.execute(
                f"UPDATE ds_projects SET {fields} WHERE id = ? AND account_id = ?",
                tuple(patch.values()) + (pid, account_id),
            )
        else:
            self.db.execute(
                f"UPDATE ds_projects SET {fields} WHERE id = ?",
                tuple(patch.values()) + (pid,),
            )
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def delete(self, pid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_projects WHERE id = ? AND account_id = ?", (pid, account_id))
        else:
            self.db.execute("DELETE FROM ds_projects WHERE id = ?", (pid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0


class DesignStudioAssetsDB:
    """Assets: images, videos, layer documents, renders, brand kit entries."""

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("metadata",):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def create(self, asset: Dict[str, Any]) -> str:
        import uuid
        aid = asset.get("id") or str(uuid.uuid4())
        asset = dict(asset)
        asset["id"] = aid
        asset.setdefault("account_id", "default")
        asset.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if "metadata" in asset and isinstance(asset["metadata"], dict):
            asset["metadata"] = json.dumps(asset["metadata"])
        cols = [c for c in asset.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_assets ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(asset.values()),
        )
        self.db.commit()
        return aid

    def get_by_id(self, aid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_assets WHERE id = ? AND account_id = ?", (aid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_assets WHERE id = ?", (aid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_by_project(self, project_id: Optional[str] = None, asset_type: Optional[str] = None, account_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_assets WHERE 1=1"
        params: List[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        if asset_type:
            sql += " AND asset_type = ?"
            params.append(asset_type)
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]

    def delete(self, aid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_assets WHERE id = ? AND account_id = ?", (aid, account_id))
        else:
            self.db.execute("DELETE FROM ds_assets WHERE id = ?", (aid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0


class DesignStudioJobsDB:
    """Jobs: generation, render, export and compliance-check tasks."""

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("cost_preview", "params", "result_ids", "metadata"):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def create(self, job: Dict[str, Any]) -> str:
        import uuid
        jid = job.get("id") or str(uuid.uuid4())
        job = dict(job)
        job["id"] = jid
        job.setdefault("account_id", "default")
        job.setdefault("status", "queued")
        now = datetime.now(timezone.utc).isoformat()
        job.setdefault("created_at", now)
        job.setdefault("updated_at", now)
        for k in ("cost_preview", "params", "result_ids", "metadata"):
            if k in job and isinstance(job[k], (dict, list)):
                job[k] = json.dumps(job[k])
        cols = [c for c in job.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_jobs ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(job.values()),
        )
        self.db.commit()
        return jid

    def update(self, jid: str, patch: Dict[str, Any], account_id: Optional[str] = None) -> bool:
        if not patch:
            return False
        patch = dict(patch)
        patch.pop("id", None)
        patch.pop("account_id", None)  # ownership is never reassignable by patch
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        for k in ("cost_preview", "params", "result_ids", "metadata"):
            if k in patch and isinstance(patch[k], (dict, list)):
                patch[k] = json.dumps(patch[k])
        fields = ", ".join(f"{k} = ?" for k in patch.keys())
        if account_id:
            self.db.execute(
                f"UPDATE ds_jobs SET {fields} WHERE id = ? AND account_id = ?",
                tuple(patch.values()) + (jid, account_id),
            )
        else:
            self.db.execute(
                f"UPDATE ds_jobs SET {fields} WHERE id = ?",
                tuple(patch.values()) + (jid,),
            )
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def get_by_id(self, jid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_jobs WHERE id = ? AND account_id = ?", (jid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_jobs WHERE id = ?", (jid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_by_project(self, project_id: Optional[str] = None, status: Optional[str] = None, account_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_jobs WHERE 1=1"
        params: List[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]

    def delete(self, jid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_jobs WHERE id = ? AND account_id = ?", (jid, account_id))
        else:
            self.db.execute("DELETE FROM ds_jobs WHERE id = ?", (jid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0


# ---------------------------------------------------------------------------
# Convenience: all DAOs accessible from one place
# ---------------------------------------------------------------------------

class DesignStudioRechecksDB:
    """Data access for the ds_rechecks table.

    The dated record of verifying a LIVE asset. Tenant-scoped like every other
    ds_* store, and a check that FAILED is stored as a failure.
    """

    _COLS = [
        "id", "account_id", "asset_id", "checked_at", "checked_by", "verdict",
        "passed", "detail", "surface", "tag_required", "legacy_key",
    ]

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if "passed" in d and d["passed"] is not None:
            d["passed"] = bool(d["passed"])
        if "tag_required" in d and d["tag_required"] is not None:
            d["tag_required"] = bool(d["tag_required"])
        return d

    def create(self, entry: Dict[str, Any]) -> str:
        import uuid
        rid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = rid
        rec.setdefault("checked_at", datetime.now(timezone.utc).isoformat())
        rec.setdefault("verdict", "unknown")
        # A boolean becomes 0/1 so SQLite stores it consistently.
        for k in ("passed", "tag_required"):
            if k in rec and isinstance(rec[k], bool):
                rec[k] = 1 if rec[k] else 0
        cols = [c for c in self._COLS if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        try:
            self.db.execute(
                f"INSERT INTO ds_rechecks ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(rec[c] for c in cols),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            # The unique legacy_key index makes the import idempotent. Return the
            # EXISTING id rather than raising, so a re-run is a no-op.
            row = self.db.execute(
                "SELECT id FROM ds_rechecks WHERE account_id = ? AND legacy_key = ?",
                (rec.get("account_id"), rec.get("legacy_key")),
            ).fetchone()
            return row["id"] if row else rid
        return rid

    def list_for_account(self, account_id: str, asset_id: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_rechecks WHERE account_id = ?"
        params: List[Any] = [account_id]
        if asset_id:
            sql += " AND asset_id = ?"
            params.append(asset_id)
        sql += " ORDER BY checked_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]

    def get_by_id(self, rid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_rechecks WHERE id = ? AND account_id = ?", (rid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_rechecks WHERE id = ?", (rid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def delete(self, rid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_rechecks WHERE id = ? AND account_id = ?", (rid, account_id))
        else:
            self.db.execute("DELETE FROM ds_rechecks WHERE id = ?", (rid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def existing_legacy_keys(self, account_id: str) -> set:
        cur = self.db.execute(
            "SELECT legacy_key FROM ds_rechecks WHERE account_id = ? AND legacy_key IS NOT NULL",
            (account_id,),
        )
        return {r["legacy_key"] for r in cur.fetchall()}


class DesignStudioImportsDB:
    """Data access for ds_imports — archived marketplace report imports.

    Tenant-scoped. Fingerprint idempotency: a UNIQUE index on
    (account_id, fingerprint) makes a re-import of the same file return the
    EXISTING import instead of creating a duplicate.
    """

    _COLS = [
        "id", "account_id", "kind", "source_label", "filename", "format",
        "observed_from", "observed_to", "observed_source", "row_count",
        "skipped_rows", "columns_found", "missing_columns", "notes",
        "fingerprint", "imported_at", "imported_by", "live",
    ]

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("columns_found", "missing_columns", "notes"):
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    d[k] = []
        if "live" in d:
            d["live"] = bool(d["live"])
        return d

    def create(self, entry: Dict[str, Any]) -> str:
        import uuid
        iid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = iid
        rec.setdefault("imported_at", datetime.now(timezone.utc).isoformat())
        rec.setdefault("row_count", 0)
        rec.setdefault("skipped_rows", 0)
        rec["live"] = 0
        for k in ("columns_found", "missing_columns", "notes"):
            if k in rec and not isinstance(rec[k], str):
                rec[k] = json.dumps(rec[k])
        cols = [c for c in self._COLS if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        try:
            self.db.execute(
                f"INSERT INTO ds_imports ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(rec[c] for c in cols),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            # Duplicate fingerprint: idempotent import, return the existing row.
            row = self.db.execute(
                "SELECT id FROM ds_imports WHERE account_id = ? AND fingerprint = ?",
                (rec.get("account_id"), rec.get("fingerprint")),
            ).fetchone()
            return row["id"] if row else iid
        return iid

    def get_by_fingerprint(self, account_id: str, fingerprint: str) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            "SELECT * FROM ds_imports WHERE account_id = ? AND fingerprint = ?",
            (account_id, fingerprint),
        ).fetchone()
        return self._serialize(row) if row else None

    def list_for_account(self, account_id: str, kind: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_imports WHERE account_id = ?"
        params: List[Any] = [account_id]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY imported_at DESC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]

    def get_by_id(self, iid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_imports WHERE id = ? AND account_id = ?", (iid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_imports WHERE id = ?", (iid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def delete(self, iid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_search_terms WHERE import_id = ? AND account_id = ?", (iid, account_id))
            self.db.execute("DELETE FROM ds_imports WHERE id = ? AND account_id = ?", (iid, account_id))
        else:
            self.db.execute("DELETE FROM ds_search_terms WHERE import_id = ?", (iid,))
            self.db.execute("DELETE FROM ds_imports WHERE id = ?", (iid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0


class DesignStudioSearchTermsDB:
    """Data access for ds_search_terms — normalized rows from imported files."""

    _COLS = [
        "id", "account_id", "import_id", "kind", "term", "campaign", "ad_group",
        "match_type", "targeting", "currency", "impressions", "clicks",
        "orders", "units", "spend", "sales", "search_frequency_rank",
        "search_query_score", "asin_click_share", "row_from", "row_to",
        "extras",
    ]

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if "extras" in d and isinstance(d["extras"], str):
            try:
                d["extras"] = json.loads(d["extras"])
            except ValueError:
                d["extras"] = {}
        return d

    def add_many(self, rows: List[Dict[str, Any]]) -> int:
        import uuid
        inserted = 0
        for row in rows:
            rec = dict(row)
            rec.setdefault("id", str(uuid.uuid4()))
            for k in ("extras",):
                if k in rec and rec[k] is not None and not isinstance(rec[k], str):
                    rec[k] = json.dumps(rec[k])
            cols = [c for c in self._COLS if c in rec]
            placeholders = ", ".join(["?"] * len(cols))
            self.db.execute(
                f"INSERT INTO ds_search_terms ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(rec[c] for c in cols),
            )
            inserted += 1
        self.db.commit()
        return inserted

    def list_for_account(
        self,
        account_id: str,
        kind: Optional[str] = None,
        import_id: Optional[str] = None,
        q: str = "",
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_search_terms WHERE account_id = ?"
        params: List[Any] = [account_id]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if import_id:
            sql += " AND import_id = ?"
            params.append(import_id)
        if q:
            sql += " AND lower(term) LIKE ?"
            params.append(f"%{q.lower()}%")
        sql += " ORDER BY COALESCE(clicks, -1) DESC, term ASC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]

    def count_for_import(self, account_id: str, import_id: str) -> int:
        cur = self.db.execute(
            "SELECT COUNT(*) AS cnt FROM ds_search_terms WHERE account_id = ? AND import_id = ?",
            (account_id, import_id),
        )
        return cur.fetchone()["cnt"]


class DesignStudioVariantsDB:
    """Data access for ds_variants + ds_variant_metrics (Phase 6 item 6)."""

    _COLS = [
        "id", "account_id", "project_id", "name", "asset_id", "format",
        "status", "notes", "updated_at",
    ]
    _METRIC_COLS = [
        "id", "account_id", "variant_id", "source", "import_id",
        "observed_from", "observed_to", "impressions", "clicks", "orders",
        "spend", "sales", "note",
    ]

    def __init__(self, db: DataLayer):
        self.db = db

    def create(self, entry: Dict[str, Any]) -> str:
        import uuid
        vid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = vid
        rec.setdefault("status", "draft")
        rec.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        cols = [c for c in self._COLS if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_variants ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(rec[c] for c in cols),
        )
        self.db.commit()
        return vid

    def update(self, vid: str, patch: Dict[str, Any], account_id: Optional[str] = None) -> bool:
        allowed = {c for c in self._COLS if c not in ("id", "account_id")}
        fields = {k: v for k, v in patch.items() if k in allowed}
        if not fields:
            return True
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        if account_id:
            self.db.execute(
                f"UPDATE ds_variants SET {sets} WHERE id = ? AND account_id = ?",
                (*fields.values(), vid, account_id),
            )
        else:
            self.db.execute(f"UPDATE ds_variants SET {sets} WHERE id = ?", (*fields.values(), vid))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def get_by_id(self, vid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_variants WHERE id = ? AND account_id = ?", (vid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_variants WHERE id = ?", (vid,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_for_account(self, account_id: str, project_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_variants WHERE account_id = ?"
        params: List[Any] = [account_id]
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.execute(sql, tuple(params)).fetchall()]

    def delete(self, vid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_variant_metrics WHERE variant_id = ? AND account_id = ?", (vid, account_id))
            self.db.execute("DELETE FROM ds_variants WHERE id = ? AND account_id = ?", (vid, account_id))
        else:
            self.db.execute("DELETE FROM ds_variant_metrics WHERE variant_id = ?", (vid,))
            self.db.execute("DELETE FROM ds_variants WHERE id = ?", (vid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def add_metric(self, entry: Dict[str, Any]) -> str:
        import uuid
        mid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = mid
        rec.setdefault("source", "user")
        cols = [c for c in self._METRIC_COLS if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_variant_metrics ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(rec[c] for c in cols),
        )
        self.db.commit()
        return mid

    def metrics_for_variant(self, account_id: str, variant_id: str) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_variant_metrics WHERE account_id = ? AND variant_id = ? ORDER BY created_at DESC",
            (account_id, variant_id),
        )
        return [dict(r) for r in cur.fetchall()]

    def metrics_for_account(self, account_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_variant_metrics WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


class DesignStudioListingRecordsDB:
    """Data access for ds_listing_records (Phase 8 item 3).

    Tenant-scoped; the one-shot migration from the browser-local ListingForge
    records is idempotent via a per-account legacy key (UNIQUE partial index).
    """

    _COLS = [
        "id", "account_id", "asin", "title", "bullets", "backend_terms",
        "description", "images", "aplus_modules", "source", "observed_at",
        "legacy_key", "updated_at",
    ]
    _JSON_COLS = ("bullets", "images", "aplus_modules")

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in self._JSON_COLS:
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    d[k] = None
        return d

    def create(self, entry: Dict[str, Any]) -> str:
        import uuid
        rid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = rid
        # `source` is NOT NULL in the schema. A caller that dumps its model includes
        # `source: null`, and setdefault left it null - the INSERT then failed and the
        # IntegrityError branch returned an id for a row that was never written
        # (measured 2026-11-14: the migration counted `created` with an empty store).
        if rec.get("source") in (None, ""):
            rec["source"] = "listingforge-local"
        rec.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        for k in self._JSON_COLS:
            if k in rec and rec[k] is not None and not isinstance(rec[k], str):
                rec[k] = json.dumps(rec[k])
        cols = [c for c in self._COLS if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        try:
            self.db.execute(
                f"INSERT INTO ds_listing_records ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(rec[c] for c in cols),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            row = self.db.execute(
                "SELECT id FROM ds_listing_records WHERE account_id = ? AND legacy_key = ?",
                (rec.get("account_id"), rec.get("legacy_key")),
            ).fetchone()
            if row:
                return row["id"]
            raise
        return rid

    def list_for_account(self, account_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_listing_records WHERE account_id = ? ORDER BY updated_at DESC LIMIT ?",
            (account_id, limit),
        )
        return [self._serialize(r) for r in cur.fetchall()]

    def get_by_id(self, rid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_listing_records WHERE id = ? AND account_id = ?", (rid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_listing_records WHERE id = ?", (rid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def get_by_asin(self, account_id: str, asin: str) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_listing_records WHERE account_id = ? AND asin = ? ORDER BY updated_at DESC LIMIT 1",
            (account_id, asin),
        )
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def update(self, rid: str, patch: Dict[str, Any], account_id: Optional[str] = None) -> bool:
        """Patch a record (2026-10-16). Only real columns; JSON columns are
        serialized the same way as create(). Returns False when nothing changed
        or the row is not the caller's."""
        rec = {k: v for k, v in (patch or {}).items()
               if k in self._COLS and k not in ("id", "account_id", "legacy_key")}
        for k in self._JSON_COLS:
            if k in rec and rec[k] is not None and not isinstance(rec[k], str):
                rec[k] = json.dumps(rec[k])
        if not rec:
            return False
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in rec)
        values = list(rec.values()) + [rid]
        q = f"UPDATE ds_listing_records SET {sets} WHERE id = ?"
        if account_id:
            q += " AND account_id = ?"
            values.append(account_id)
        cur = self.db.execute(q, tuple(values))
        self.db.commit()
        return bool(getattr(cur, "rowcount", 0))

    def delete(self, rid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_listing_records WHERE id = ? AND account_id = ?", (rid, account_id))
        else:
            self.db.execute("DELETE FROM ds_listing_records WHERE id = ?", (rid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def existing_legacy_keys(self, account_id: str) -> set:
        cur = self.db.execute(
            "SELECT legacy_key FROM ds_listing_records WHERE account_id = ? AND legacy_key IS NOT NULL",
            (account_id,),
        )
        return {r["legacy_key"] for r in cur.fetchall()}


class DesignStudioAmazonFilesDB:
    """Data access for ds_amazon_uploads + ds_change_proposals + ds_change_files.

    File-only architecture: uploads are archived read-only (checksum + the
    original bytes), proposals carry their before/after evidence, and written
    change files are new files stored alongside their round-trip report.
    """

    _UPLOAD_COLS = [
        "id", "account_id", "filename", "kind", "checksum", "content_b64",
        "size_bytes", "row_count", "observed_from", "observed_to",
        "downloaded_at", "uploaded_at", "columns_found", "missing_columns",
        "notes", "detection", "parsed",
    ]
    _JSON_UPLOAD = ("columns_found", "missing_columns", "notes", "detection", "parsed")

    def __init__(self, db: DataLayer):
        self.db = db

    # ── uploads ────────────────────────────────────────────────────────────
    def _serialize_upload(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in self._JSON_UPLOAD:
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    d[k] = None
        return d

    def create_upload(self, entry: Dict[str, Any]) -> str:
        import uuid
        uid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = uid
        rec.setdefault("uploaded_at", datetime.now(timezone.utc).isoformat())
        for k in self._JSON_UPLOAD:
            if k in rec and rec[k] is not None and not isinstance(rec[k], str):
                rec[k] = json.dumps(rec[k])
        cols = [c for c in self._UPLOAD_COLS if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_amazon_uploads ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(rec[c] for c in cols),
        )
        self.db.commit()
        return uid

    def get_upload(self, uid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_amazon_uploads WHERE id = ? AND account_id = ?", (uid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_amazon_uploads WHERE id = ?", (uid,))
        row = cur.fetchone()
        return self._serialize_upload(row) if row else None

    def list_uploads(self, account_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_amazon_uploads WHERE account_id = ? ORDER BY uploaded_at DESC LIMIT ?",
            (account_id, limit),
        )
        return [self._serialize_upload(r) for r in cur.fetchall()]

    def delete_upload(self, uid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute("DELETE FROM ds_change_proposals WHERE upload_id = ? AND account_id = ?", (uid, account_id))
            self.db.execute("DELETE FROM ds_change_files WHERE upload_id = ? AND account_id = ?", (uid, account_id))
            self.db.execute("DELETE FROM ds_amazon_uploads WHERE id = ? AND account_id = ?", (uid, account_id))
        else:
            self.db.execute("DELETE FROM ds_change_proposals WHERE upload_id = ?", (uid,))
            self.db.execute("DELETE FROM ds_change_files WHERE upload_id = ?", (uid,))
            self.db.execute("DELETE FROM ds_amazon_uploads WHERE id = ?", (uid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    # ── proposals ──────────────────────────────────────────────────────────
    def _serialize_proposal(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Return the FLAT proposal shape the UI works with: the payload fields
        (before/after/evidence/blocks/flags...) at the top level, plus the
        database's decision fields. Returning the raw row (payload nested)
        crashed the surface once; the flat shape is the contract."""
        d = dict(row)
        try:
            payload = json.loads(d["payload"]) if isinstance(d["payload"], str) else (d["payload"] or {})
        except ValueError:
            payload = {}
        out = dict(payload)
        out.update({
            "id": d.get("id"),
            "upload_id": d.get("upload_id"),
            "status": d.get("status"),
            "requires_second_confirmation": bool(d.get("requires_second_confirmation")),
            "created_at": d.get("created_at"),
            "decided_at": d.get("decided_at"),
            "decided_by": d.get("decided_by"),
        })
        return out

    def add_proposal(self, entry: Dict[str, Any]) -> str:
        import uuid
        pid = str(uuid.uuid4())
        payload = entry.get("payload") or {}
        payload["id"] = pid
        self.db.execute(
            "INSERT INTO ds_change_proposals (id, account_id, upload_id, payload, status, requires_second_confirmation, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (pid, entry.get("account_id"), entry.get("upload_id"), json.dumps(payload),
             payload.get("status") or "proposed",
             1 if payload.get("requires_second_confirmation") else 0,
             payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()
        return pid

    def get_proposal(self, pid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_change_proposals WHERE id = ? AND account_id = ?", (pid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_change_proposals WHERE id = ?", (pid,))
        row = cur.fetchone()
        return self._serialize_proposal(row) if row else None

    def list_proposals(self, account_id: str, upload_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_change_proposals WHERE account_id = ?"
        params: List[Any] = [account_id]
        if upload_id:
            sql += " AND upload_id = ?"
            params.append(upload_id)
        sql += " ORDER BY created_at ASC"
        return [self._serialize_proposal(r) for r in self.db.execute(sql, tuple(params)).fetchall()]

    def decide_proposal(self, pid: str, account_id: str, status: str, by: str = "operator") -> bool:
        self.db.execute(
            "UPDATE ds_change_proposals SET status = ?, decided_at = ?, decided_by = ? WHERE id = ? AND account_id = ?",
            (status, datetime.now(timezone.utc).isoformat(), by, pid, account_id),
        )
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    # ── change files ───────────────────────────────────────────────────────
    def _serialize_change(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("approved", "roundtrip"):
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    d[k] = None
        return d

    def add_change_file(self, entry: Dict[str, Any]) -> str:
        import uuid
        cid = entry.get("id") or str(uuid.uuid4())
        rec = dict(entry)
        rec["id"] = cid
        rec.setdefault("written_at", datetime.now(timezone.utc).isoformat())
        for k in ("approved", "roundtrip"):
            if k in rec and rec[k] is not None and not isinstance(rec[k], str):
                rec[k] = json.dumps(rec[k])
        cols = ["id", "account_id", "upload_id", "filename", "version", "format",
                "checksum", "content_b64", "row_count", "approved", "roundtrip", "written_at"]
        cols = [c for c in cols if c in rec]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO ds_change_files ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(rec[c] for c in cols),
        )
        self.db.commit()
        return cid

    def next_version(self, account_id: str, upload_id: str) -> int:
        cur = self.db.execute(
            "SELECT COUNT(*) AS cnt FROM ds_change_files WHERE account_id = ? AND upload_id = ?",
            (account_id, upload_id),
        )
        return int(cur.fetchone()["cnt"]) + 1

    def get_change_file(self, cid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM ds_change_files WHERE id = ? AND account_id = ?", (cid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM ds_change_files WHERE id = ?", (cid,))
        row = cur.fetchone()
        return self._serialize_change(row) if row else None

    def list_change_files(self, account_id: str, upload_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM ds_change_files WHERE account_id = ?"
        params: List[Any] = [account_id]
        if upload_id:
            sql += " AND upload_id = ?"
            params.append(upload_id)
        sql += " ORDER BY written_at DESC"
        return [self._serialize_change(r) for r in self.db.execute(sql, tuple(params)).fetchall()]


class ChatSessionsDB:
    """Chat sessions for the Simple-mode Master Brain (S1). Tenant-scoped."""

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("focus_json",):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def create(self, session: Dict[str, Any]) -> str:
        sid = session.get("id") or str(uuid.uuid4())
        session = dict(session)
        session["id"] = sid
        session.setdefault("account_id", "default")
        session.setdefault("title", "New chat")
        session.setdefault("mode", "simple")
        now = datetime.now(timezone.utc).isoformat()
        session.setdefault("created_at", now)
        session.setdefault("updated_at", now)
        if "focus_json" in session and isinstance(session["focus_json"], dict):
            session["focus_json"] = json.dumps(session["focus_json"])
        cols = [c for c in session.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO chat_sessions ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(session.values()),
        )
        self.db.commit()
        return sid

    def get_by_id(self, sid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Tenant-scoped read: a session owned by another account returns None."""
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM chat_sessions WHERE id = ? AND account_id = ?", (sid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM chat_sessions WHERE id = ?", (sid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_by_account(self, account_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM chat_sessions WHERE account_id = ? ORDER BY updated_at DESC LIMIT ?",
            (account_id, limit),
        )
        return [self._serialize(r) for r in cur.fetchall()]

    def update(self, sid: str, patch: Dict[str, Any], account_id: Optional[str] = None) -> bool:
        if not patch:
            return False
        patch = dict(patch)
        patch.pop("id", None)
        patch.pop("account_id", None)  # ownership is never reassignable by patch
        patch.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        if "focus_json" in patch and isinstance(patch["focus_json"], dict):
            patch["focus_json"] = json.dumps(patch["focus_json"])
        fields = ", ".join(f"{k} = ?" for k in patch.keys())
        if account_id:
            self.db.execute(
                f"UPDATE chat_sessions SET {fields} WHERE id = ? AND account_id = ?",
                tuple(patch.values()) + (sid, account_id))
        else:
            self.db.execute(
                f"UPDATE chat_sessions SET {fields} WHERE id = ?",
                tuple(patch.values()) + (sid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def delete(self, sid: str, account_id: Optional[str] = None) -> bool:
        if account_id:
            self.db.execute(
                "DELETE FROM chat_messages WHERE session_id = ? AND account_id = ?",
                (sid, account_id))
            self.db.execute(
                "DELETE FROM chat_sessions WHERE id = ? AND account_id = ?", (sid, account_id))
        else:
            self.db.execute("DELETE FROM chat_messages WHERE session_id = ?", (sid,))
            self.db.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def fork(self, sid: str, account_id: str, upto_message_id: Optional[str] = None,
             title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Branch a NEW session from `sid` (V3 S5 fork/rewind).

        Copies every message up to and including `upto_message_id` (or all
        messages when omitted). The parent is NEVER mutated — rewind is
        non-destructive. Returns {session, copied_messages, forked_from}, or None
        when the parent is not visible to this account. Raises ValueError when
        `upto_message_id` is not a message of the parent session.
        """
        parent = self.get_by_id(sid, account_id=account_id)
        if not parent:
            return None
        cur = self.db.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? AND account_id = ? "
            "ORDER BY created_at ASC",
            (sid, account_id))
        rows = [dict(r) for r in cur.fetchall()]
        cut = len(rows)
        if upto_message_id:
            idx = next((i for i, r in enumerate(rows) if r.get("id") == upto_message_id), None)
            if idx is None:
                raise ValueError("message not found in this session")
            cut = idx + 1
        now = datetime.now(timezone.utc).isoformat()
        child_id = str(uuid.uuid4())
        self.create({
            "id": child_id,
            "account_id": account_id,
            "title": (title or f"\u2937 {parent.get('title') or 'New chat'}")[:120],
            "ds_project_id": parent.get("ds_project_id"),
            "mode": parent.get("mode") or "simple",
            "model": parent.get("model"),
            "focus_json": parent.get("focus_json"),
            "created_at": now,
            "updated_at": now,
        })
        for r in rows[:cut]:
            self.db.execute(
                "INSERT INTO chat_messages (id, account_id, session_id, role, content, "
                "thinking, parts_json, model, usage_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), account_id, child_id, r.get("role") or "user",
                 r.get("content") or "", r.get("thinking") or "", r.get("parts_json"),
                 r.get("model"), r.get("usage_json"), r.get("created_at") or now))
        self.db.commit()
        return {
            "session": self.get_by_id(child_id, account_id=account_id),
            "copied_messages": cut,
            "forked_from": {"session_id": sid, "message_id": upto_message_id},
        }


class ChatMessagesDB:
    """Chat messages with separated thinking + ordered parts (S1)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("parts_json", "usage_json"):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def create(self, message: Dict[str, Any]) -> str:
        mid = message.get("id") or str(uuid.uuid4())
        message = dict(message)
        message["id"] = mid
        message.setdefault("account_id", "default")
        message.setdefault("role", "user")
        message.setdefault("content", "")
        message.setdefault("thinking", "")
        message.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        for k in ("parts_json", "usage_json"):
            if k in message and isinstance(message[k], (dict, list)):
                message[k] = json.dumps(message[k])
        cols = [c for c in message.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO chat_messages ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(message.values()),
        )
        self.db.commit()
        return mid

    def get_by_id(self, mid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM chat_messages WHERE id = ? AND account_id = ?", (mid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_by_session(self, sid: str, account_id: Optional[str] = None,
                        limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM chat_messages WHERE session_id = ?"
        params: List[Any] = [sid]
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]


class ChatToolCallsDB:
    """Tool-call ledger for chat turns (wire-ready; populated from S2)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("args_json", "result_json"):
            if d.get(k) and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def create(self, call: Dict[str, Any]) -> str:
        cid = call.get("id") or str(uuid.uuid4())
        call = dict(call)
        call["id"] = cid
        call.setdefault("account_id", "default")
        call.setdefault("status", "queued")
        call.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        for k in ("args_json", "result_json"):
            if k in call and isinstance(call[k], (dict, list)):
                call[k] = json.dumps(call[k])
        cols = [c for c in call.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO chat_tool_calls ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(call.values()),
        )
        self.db.commit()
        return cid

    def update(self, cid: str, patch: Dict[str, Any], account_id: Optional[str] = None) -> bool:
        if not patch:
            return False
        patch = dict(patch)
        patch.pop("id", None)
        patch.pop("account_id", None)
        for k in ("args_json", "result_json"):
            if k in patch and isinstance(patch[k], (dict, list)):
                patch[k] = json.dumps(patch[k])
        fields = ", ".join(f"{k} = ?" for k in patch.keys())
        if account_id:
            self.db.execute(
                f"UPDATE chat_tool_calls SET {fields} WHERE id = ? AND account_id = ?",
                tuple(patch.values()) + (cid, account_id))
        else:
            self.db.execute(
                f"UPDATE chat_tool_calls SET {fields} WHERE id = ?",
                tuple(patch.values()) + (cid,))
        self.db.commit()
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def list_by_session(self, sid: str, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM chat_tool_calls WHERE session_id = ?"
        params: List[Any] = [sid]
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY created_at ASC"
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]


class ChatAttachmentsDB:
    """Links chat messages to ds_assets (provenance travels with the link)."""

    def __init__(self, db: DataLayer):
        self.db = db

    def create(self, attachment: Dict[str, Any]) -> str:
        aid = attachment.get("id") or str(uuid.uuid4())
        attachment = dict(attachment)
        attachment["id"] = aid
        attachment.setdefault("account_id", "default")
        attachment.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if "provenance_json" in attachment and isinstance(attachment["provenance_json"], dict):
            attachment["provenance_json"] = json.dumps(attachment["provenance_json"])
        cols = [c for c in attachment.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO chat_attachments ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(attachment.values()),
        )
        self.db.commit()
        return aid

    def list_by_message(self, mid: str, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM chat_attachments WHERE message_id = ?"
        params: List[Any] = [mid]
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY created_at ASC"
        cur = self.db.execute(sql, tuple(params))
        out = []
        for row in cur.fetchall():
            d = dict(row)
            if d.get("provenance_json") and isinstance(d["provenance_json"], str):
                try:
                    d["provenance_json"] = json.loads(d["provenance_json"])
                except json.JSONDecodeError:
                    pass
            out.append(d)
        return out

    def list_by_session(self, sid: str, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every artifact attached to any message in a session (V3 S5 browser).

        Joins chat_messages so the session filter is authoritative, not inferred
        from a possibly-missing message row."""
        sql = ("SELECT a.* FROM chat_attachments a "
               "JOIN chat_messages m ON m.id = a.message_id "
               "WHERE m.session_id = ?")
        params: List[Any] = [sid]
        if account_id:
            sql += " AND a.account_id = ?"
            params.append(account_id)
        sql += " ORDER BY a.created_at ASC"
        cur = self.db.execute(sql, tuple(params))
        out = []
        for row in cur.fetchall():
            d = dict(row)
            if d.get("provenance_json") and isinstance(d["provenance_json"], str):
                try:
                    d["provenance_json"] = json.loads(d["provenance_json"])
                except json.JSONDecodeError:
                    pass
            out.append(d)
        return out


class DesignStudioContainer:
    """Namespace for the Design Studio stores."""

    def __init__(self, db: DataLayer):
        self.projects = DesignStudioProjectsDB(db)
        self.assets = DesignStudioAssetsDB(db)
        self.jobs = DesignStudioJobsDB(db)
        self.rechecks = DesignStudioRechecksDB(db)
        self.imports = DesignStudioImportsDB(db)
        self.search_terms = DesignStudioSearchTermsDB(db)
        self.variants = DesignStudioVariantsDB(db)
        self.listing_records = DesignStudioListingRecordsDB(db)
        self.amazon_files = DesignStudioAmazonFilesDB(db)


class ToolAuditDB:
    """Audit log for the Tool Execution Gateway (V3 REA inject). Append-only."""

    def __init__(self, db: DataLayer):
        self.db = db

    def create(self, entry: Dict[str, Any]) -> str:
        import uuid
        tid = entry.get("id") or str(uuid.uuid4())
        entry = dict(entry)
        entry["id"] = tid
        entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        cols = [c for c in entry.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO tool_audit ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(entry.values()),
        )
        self.db.commit()
        return tid

    def list_by_account(self, account_id: str, limit: int = 100) -> list:
        cur = self.db.execute(
            "SELECT * FROM tool_audit WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


class ChatForksDB:
    """Session lineage for V3 S5 fork/rewind. Append-only."""

    def __init__(self, db: DataLayer):
        self.db = db

    def create(self, entry: Dict[str, Any]) -> str:
        import uuid
        fid = entry.get("id") or str(uuid.uuid4())
        entry = dict(entry)
        entry["id"] = fid
        entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        cols = [c for c in entry.keys()]
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO chat_session_forks ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(entry.values()),
        )
        self.db.commit()
        return fid

    def get_by_child(self, session_id: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM chat_session_forks WHERE session_id = ? AND account_id = ?",
                (session_id, account_id))
        else:
            cur = self.db.execute(
                "SELECT * FROM chat_session_forks WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        return dict(row) if row else None


class ChatContainer:
    """Namespace for the Simple-mode chat stores (S1). Additive."""

    def __init__(self, db: DataLayer):
        self.sessions = ChatSessionsDB(db)
        self.messages = ChatMessagesDB(db)
        self.tool_calls = ChatToolCallsDB(db)
        self.attachments = ChatAttachmentsDB(db)
        self.tool_audit = ToolAuditDB(db)
        self.forks = ChatForksDB(db)
        self.runs = RunRegistryDB(db)


class RunRegistryDB:
    """Bounded run ledger for the V3 S5 AutothinK run panel. Tenant-scoped.

    NOT an arbitrary-code sandbox: the tool gateway's deny-list is the boundary.
    A run records something that actually ran (a chat turn or a tool execution)
    so the operator can watch status and cancel. `ref` carries the live handle
    (e.g. a turn_id) used to cancel an in-flight run.
    """

    def __init__(self, db: DataLayer):
        self.db = db

    def _serialize(self, row) -> Dict[str, Any]:
        d = dict(row)
        if d.get("detail_json") and isinstance(d["detail_json"], str):
            try:
                d["detail_json"] = json.loads(d["detail_json"])
            except json.JSONDecodeError:
                pass
        return d

    def create(self, entry: Dict[str, Any]) -> str:
        rid = entry.get("id") or str(uuid.uuid4())
        entry = dict(entry)
        entry["id"] = rid
        entry.setdefault("account_id", "default")
        entry.setdefault("kind", "chat_turn")
        entry.setdefault("status", "running")
        entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if "detail_json" in entry and isinstance(entry["detail_json"], (dict, list)):
            entry["detail_json"] = json.dumps(entry["detail_json"])
        cols = list(entry.keys())
        placeholders = ", ".join(["?"] * len(cols))
        self.db.execute(
            f"INSERT INTO chat_runs ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(entry.values()),
        )
        self.db.commit()
        return rid

    def finish(self, rid: str, status: str, *, progress: Optional[float] = None,
               detail: Optional[Dict[str, Any]] = None,
               account_id: Optional[str] = None) -> bool:
        patch: Dict[str, Any] = {"status": status, "ended_at": datetime.now(timezone.utc).isoformat()}
        if progress is not None:
            patch["progress"] = float(progress)
        if detail is not None:
            patch["detail_json"] = json.dumps(detail)
        fields = ", ".join(f"{k} = ?" for k in patch)
        params: List[Any] = list(patch.values())
        sql = f"UPDATE chat_runs SET {fields} WHERE id = ?"
        params.append(rid)
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        self.db.execute(sql, tuple(params))
        self.db.commit()
        return True

    def get(self, rid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute("SELECT * FROM chat_runs WHERE id = ? AND account_id = ?",
                                  (rid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM chat_runs WHERE id = ?", (rid,))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_by_account(self, account_id: str, *, status: Optional[str] = None,
                        session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM chat_runs WHERE account_id = ?"
        params: List[Any] = [account_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(int(limit), 1))
        cur = self.db.execute(sql, tuple(params))
        return [self._serialize(r) for r in cur.fetchall()]


class SeoProfilesDB:
    """Brand SEO Profiles (V3 S7) — one canonical, versioned profile per brand.

    Versions are immutable and append-only: editing a profile appends a new
    version and repoints `current_version`. History is never rewritten, so a
    rollback is always possible. Tenant-scoped on every read and write.
    """

    def __init__(self, db: DataLayer):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _version(self, row) -> Dict[str, Any]:
        d = dict(row)
        if isinstance(d.get("body_json"), str):
            try:
                d["body_json"] = json.loads(d["body_json"])
            except json.JSONDecodeError:
                pass
        return d

    def _row(self, pid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM brand_seo_profiles WHERE id = ? AND account_id = ?",
                (pid, account_id))
        else:
            cur = self.db.execute("SELECT * FROM brand_seo_profiles WHERE id = ?", (pid,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_by_brand_key(self, account_id: str, brand_key: str) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM brand_seo_profiles WHERE account_id = ? AND brand_key = ?",
            (account_id, brand_key))
        row = cur.fetchone()
        return dict(row) if row else None

    def create_profile(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        account_id = entry.get("account_id") or "default"
        brand_key = (entry.get("brand_key") or "").strip().lower()
        if not brand_key:
            raise ValueError("brand_key is required")
        name = (entry.get("name") or brand_key).strip() or brand_key
        ok, norm = normalize_seo_body(entry.get("body") or {})
        if not ok:
            raise ValueError(norm)
        if self.get_by_brand_key(account_id, brand_key):
            raise ValueError(f"a profile for brand '{brand_key}' already exists")
        pid = entry.get("id") or str(uuid.uuid4())
        now = self._now()
        self.db.execute(
            "INSERT INTO brand_seo_profiles "
            "(id, account_id, brand_key, name, current_version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pid, account_id, brand_key, name, 1, now, now))
        self.db.execute(
            "INSERT INTO brand_seo_profile_versions "
            "(id, account_id, profile_id, version, body_json, note, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), account_id, pid, 1, json.dumps(norm),
             entry.get("note"), entry.get("created_by"), now))
        self.db.commit()
        return self.get_profile(pid, account_id=account_id)

    def get_profile(self, pid: str, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        prof = self._row(pid, account_id)
        if not prof:
            return None
        v = int(prof.get("current_version") or 1)
        cur = self.db.execute(
            "SELECT * FROM brand_seo_profile_versions WHERE profile_id = ? AND version = ?",
            (pid, v))
        row = cur.fetchone()
        prof["body"] = self._version(row)["body_json"] if row else {}
        cur = self.db.execute(
            "SELECT COUNT(*) AS n FROM brand_seo_profile_versions WHERE profile_id = ?", (pid,))
        prof["version_count"] = int(cur.fetchone()["n"])
        return prof

    def list_profiles(self, account_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM brand_seo_profiles WHERE account_id = ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (account_id, limit))
        return [dict(r) for r in cur.fetchall()]

    def add_version(self, pid: str, account_id: str, body: Any,
                    note: Optional[str] = None,
                    created_by: Optional[str] = None) -> Optional[Dict[str, Any]]:
        prof = self._row(pid, account_id)
        if not prof:
            return None
        ok, norm = normalize_seo_body(body)
        if not ok:
            raise ValueError(norm)
        v = int(prof.get("current_version") or 1) + 1
        now = self._now()
        self.db.execute(
            "INSERT INTO brand_seo_profile_versions "
            "(id, account_id, profile_id, version, body_json, note, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), account_id, pid, v, json.dumps(norm), note, created_by, now))
        self.db.execute(
            "UPDATE brand_seo_profiles SET current_version = ?, updated_at = ? "
            "WHERE id = ? AND account_id = ?",
            (v, now, pid, account_id))
        self.db.commit()
        return self.get_profile(pid, account_id=account_id)

    def list_versions(self, pid: str, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = ("SELECT id, account_id, profile_id, version, note, created_by, created_at "
               "FROM brand_seo_profile_versions WHERE profile_id = ?")
        params: List[Any] = [pid]
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        sql += " ORDER BY version DESC"
        cur = self.db.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]

    def get_version(self, pid: str, version: int,
                    account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if account_id:
            cur = self.db.execute(
                "SELECT * FROM brand_seo_profile_versions "
                "WHERE profile_id = ? AND version = ? AND account_id = ?",
                (pid, version, account_id))
        else:
            cur = self.db.execute(
                "SELECT * FROM brand_seo_profile_versions "
                "WHERE profile_id = ? AND version = ?",
                (pid, version))
        row = cur.fetchone()
        return self._version(row) if row else None


class DsListingRevisionsDB:
    """Immutable listing revisions (V3 S7 §5.2). Append-only; tenant-scoped.

    A listing build/update APPENDS a revision (monotonic per listing_key); the
    newest is the only object SEO work targets, and prior revisions stay
    read-only. Does not touch ds_listing_records.
    """

    def __init__(self, db: DataLayer):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _serialize(self, row) -> Dict[str, Any]:
        d = dict(row)
        if isinstance(d.get("bullets"), str):
            try:
                d["bullets"] = json.loads(d["bullets"])
            except json.JSONDecodeError:
                pass
        return d

    def add_revision(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        account_id = entry.get("account_id") or "default"
        listing_key = (entry.get("listing_key") or entry.get("asin") or "").strip().lower()
        if not listing_key:
            raise ValueError("listing_key is required")
        cur = self.db.execute(
            "SELECT COALESCE(MAX(revision), 0) AS m FROM ds_listing_revisions "
            "WHERE account_id = ? AND listing_key = ?",
            (account_id, listing_key))
        rev = int(cur.fetchone()["m"]) + 1
        rid = entry.get("id") or str(uuid.uuid4())
        bullets = entry.get("bullets")
        if isinstance(bullets, (list, dict)):
            bullets = json.dumps(bullets)
        self.db.execute(
            "INSERT INTO ds_listing_revisions "
            "(id, account_id, listing_key, asin, revision, title, bullets, backend_terms, "
            "description, source, note, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rid, account_id, listing_key, entry.get("asin"), rev, entry.get("title"), bullets,
             entry.get("backend_terms"), entry.get("description"),
             entry.get("source") or "operator", entry.get("note"),
             entry.get("created_by"), self._now()))
        self.db.commit()
        return self.get(account_id, listing_key, rev)

    def get(self, account_id: str, listing_key: str, revision: int) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_listing_revisions "
            "WHERE account_id = ? AND listing_key = ? AND revision = ?",
            (account_id, (listing_key or "").strip().lower(), int(revision)))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def get_latest(self, account_id: str, listing_key: str) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_listing_revisions WHERE account_id = ? AND listing_key = ? "
            "ORDER BY revision DESC LIMIT 1",
            (account_id, (listing_key or "").strip().lower()))
        row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_revisions(self, account_id: str, listing_key: str) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM ds_listing_revisions WHERE account_id = ? AND listing_key = ? "
            "ORDER BY revision DESC",
            (account_id, (listing_key or "").strip().lower()))
        return [self._serialize(r) for r in cur.fetchall()]

    def list_latest(self, account_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT r.* FROM ds_listing_revisions r "
            "JOIN (SELECT listing_key, MAX(revision) AS m FROM ds_listing_revisions "
            "      WHERE account_id = ? GROUP BY listing_key) x "
            "ON r.listing_key = x.listing_key AND r.revision = x.m "
            "WHERE r.account_id = ? ORDER BY r.created_at DESC LIMIT ?",
            (account_id, account_id, limit))
        return [self._serialize(r) for r in cur.fetchall()]


class SeoContainer:
    """Namespace for the V3 S7 SEO stores. Additive."""
    def __init__(self, db: DataLayer):
        self.profiles = SeoProfilesDB(db)
        self.revisions = DsListingRevisionsDB(db)
        self.sqp = SqpPerformanceDB(db)


class SqpPerformanceDB:
    """Read-only access to imported Search Query Performance rows (V3 S7 §5.4).

    The Brand Analytics importer (`importers/brand_analytics_importer.py`) owns
    writes; this is the read side the learning step consumes. `search_query_
    performance` is a local import table with no account column, so callers MUST
    scope it explicitly (pass `asins`) — otherwise the rows are operator-global
    import data and not tenant-scoped.
    """

    def __init__(self, db: DataLayer):
        self.db = db

    def rows(self, *, asins: Optional[List[str]] = None, limit: int = 500) -> List[Dict[str, Any]]:
        sql = ("SELECT query, asin, impressions, clicks, purchases, "
               "search_frequency_rank, date_start FROM search_query_performance")
        params: List[Any] = []
        clean = [a for a in (asins or []) if a]
        if clean:
            sql += " WHERE asin IN (" + ",".join("?" for _ in clean) + ")"
            params.extend(clean)
        sql += (" ORDER BY COALESCE(search_frequency_rank, 999999999) ASC, "
                "COALESCE(impressions, 0) DESC LIMIT ?")
        params.append(max(int(limit), 1))
        cur = self.db.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]


class CorpusDB:
    """Local curated corpus index (V3 S8). Provenance + license per record.

    Curated records are shared/global (`account_id` is NULL). Writes are
    idempotent by `(source, source_id)` with a content hash, so a re-run of an
    ingest skips unchanged rows (resumable, honest counts). Search is deterministic
    LIKE + a light relevance rank — portable and dependency-free; a vector/FTS
    index is the documented upgrade, not a hard requirement.
    """

    def __init__(self, db: DataLayer):
        self.db = db

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _content_hash(record: Dict[str, Any]) -> str:
        tags = record.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        blob = "|".join(str(record.get(k) or "") for k in ("title", "summary", "content"))
        blob += "|" + "|".join(sorted(str(t) for t in tags))
        return hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()

    def get(self, source: str, source_id: str) -> Optional[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM corpus_records WHERE source = ? AND source_id = ?",
            (source, source_id))
        row = cur.fetchone()
        return dict(row) if row else None

    # -- writes -------------------------------------------------------------
    def upsert(self, record: Dict[str, Any]) -> str:
        """Insert or update one curated record. Returns inserted|updated|skipped."""
        rec = dict(record)
        source = str(rec.get("source") or "").strip()
        source_id = str(rec.get("source_id") or "").strip()
        if not source or not source_id:
            raise ValueError("corpus record needs source and source_id")
        rec["source"] = source
        rec["source_id"] = source_id
        rec["content_hash"] = self._content_hash(rec)

        existing = self.get(source, source_id)
        if existing and existing.get("content_hash") == rec["content_hash"]:
            return "skipped"

        if isinstance(rec.get("tags"), (list, dict)):
            rec["tags_json"] = json.dumps(rec.pop("tags"))
        if isinstance(rec.get("provenance"), (dict, list)):
            rec["provenance_json"] = json.dumps(rec.pop("provenance"))

        cols = [c for c in ("id", "account_id", "source", "source_id", "kind", "title",
                            "url", "license", "summary", "content", "tags_json",
                            "provenance_json", "content_hash") if c in rec]

        if existing:
            setcols = [c for c in cols if c != "id"]
            self.db.execute(
                f"UPDATE corpus_records SET {', '.join(c + ' = ?' for c in setcols)} "
                "WHERE source = ? AND source_id = ?",
                tuple([rec[c] for c in setcols] + [source, source_id]))
            self.db.commit()
            return "updated"

        rec.setdefault("id", str(uuid.uuid4()))
        if "id" not in cols:
            cols = ["id"] + cols
        self.db.execute(
            f"INSERT INTO corpus_records ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            tuple(rec.get(c) for c in cols))
        self.db.commit()
        return "inserted"

    # -- reads --------------------------------------------------------------
    def search(self, query: str, *, limit: int = 20, source: Optional[str] = None) -> List[Dict[str, Any]]:
        terms = [t for t in re.split(r"\s+", str(query or "").strip().lower()) if t]
        if not terms:
            return []
        where = " OR ".join(
            "(lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(content) LIKE ?)"
            for _ in terms)
        params: List[Any] = []
        for t in terms:
            params += [f"%{t}%"] * 3
        sql = f"SELECT * FROM corpus_records WHERE ({where})"
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " LIMIT ?"
        params.append(max(int(limit) * 10, 50))
        rows = [dict(r) for r in self.db.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            title = (r.get("title") or "").lower()
            hay = title + " " + (r.get("summary") or "").lower() + " " + (r.get("content") or "").lower()
            r["_score"] = sum((3 if t in title else 1) for t in terms if t in hay)
        rows = [r for r in rows if r["_score"] > 0]
        rows.sort(key=lambda r: (-r["_score"], str(r.get("title") or "")))
        return rows[:limit]

    def stats(self) -> Dict[str, Any]:
        total = self.db.execute("SELECT COUNT(*) FROM corpus_records").fetchone()[0]
        by_source = {r[0]: r[1] for r in self.db.execute(
            "SELECT source, COUNT(*) FROM corpus_records GROUP BY source").fetchall()}
        by_kind = {r[0]: r[1] for r in self.db.execute(
            "SELECT kind, COUNT(*) FROM corpus_records GROUP BY kind").fetchall()}
        return {"total": total, "by_source": by_source, "by_kind": by_kind}

    def list_records(self, source: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if source:
            cur = self.db.execute(
                "SELECT * FROM corpus_records WHERE source = ? ORDER BY title LIMIT ?",
                (source, max(int(limit), 1)))
        else:
            cur = self.db.execute(
                "SELECT * FROM corpus_records ORDER BY title LIMIT ?", (max(int(limit), 1),))
        return [dict(r) for r in cur.fetchall()]

    # -- ingest runs --------------------------------------------------------
    def start_run(self, source: str, source_path: str) -> str:
        rid = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO corpus_ingest_runs (id, source, source_path, status, started_at) "
            "VALUES (?, ?, ?, 'running', ?)",
            (rid, source, source_path, datetime.now(timezone.utc).isoformat()))
        self.db.commit()
        return rid

    def finish_run(self, rid: str, status: str, *, counts: Optional[Dict[str, Any]] = None,
                   errors: Optional[List[str]] = None) -> None:
        self.db.execute(
            "UPDATE corpus_ingest_runs SET status = ?, counts_json = ?, errors_json = ?, "
            "finished_at = ? WHERE id = ?",
            (status, json.dumps(counts or {}), json.dumps(errors or []),
             datetime.now(timezone.utc).isoformat(), rid))
        self.db.commit()

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self.db.execute(
            "SELECT * FROM corpus_ingest_runs ORDER BY created_at DESC LIMIT ?",
            (max(int(limit), 1),))
        out = []
        for row in cur.fetchall():
            d = dict(row)
            for k in ("counts_json", "errors_json"):
                if d.get(k) and isinstance(d[k], str):
                    try:
                        d[k] = json.loads(d[k])
                    except json.JSONDecodeError:
                        pass
            out.append(d)
        return out


class NorthstarDB:
    """Unified data access — one object to reach every table."""

    def __init__(self):
        self._layer = get_db()
        self.products = ProductsDB(self._layer)
        self.keywords = KeywordsDB(self._layer)
        self.listings = ListingsDB(self._layer)
        self.campaigns = CampaignsDB(self._layer)
        self.transactions = TransactionsDB(self._layer)
        self.memory = MemoryDB(self._layer)
        self.audit = AuditDB(self._layer)
        self.suppliers = SuppliersDB(self._layer)
        self.live_pulls = LivePullsDB(self._layer)
        self.design_studio = DesignStudioContainer(self._layer)
        self.chat = ChatContainer(self._layer)
        self.seo = SeoContainer(self._layer)
        self.corpus = CorpusDB(self._layer)

    @property
    def mode(self) -> str:
        return self._layer.mode


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def get_northstar_db() -> NorthstarDB:
    """Get the unified data access object."""
    return NorthstarDB()
