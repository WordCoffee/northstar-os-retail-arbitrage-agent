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
import sqlite3
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from env_flags import env_flag

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
        """Connect to Postgres, or refuse.

        Never silently degrades: if a URL is configured but the connection
        fails, the caller is told loudly. An operator who genuinely wants the
        SQLite fallback sets ``NORTHSTAR_ALLOW_SQLITE_FALLBACK=1`` explicitly.
        """
        if allow_sqlite_fallback is None:
            allow_sqlite_fallback = env_flag("NORTHSTAR_ALLOW_SQLITE_FALLBACK")
        try:
            import psycopg2  # noqa: F401  (driver presence check)
        except ImportError:
            raise RuntimeError(
                "POSTGRES CONFIGURED BUT DRIVER MISSING: "
                f"{_redact_url(self._pg_url)} was configured but psycopg2 is "
                "not installed. Set NORTHSTAR_ALLOW_SQLITE_FALLBACK=1 to run "
                "on SQLite instead, or install the Postgres driver."
            )
        try:
            conn = psycopg2.connect(self._pg_url, connect_timeout=5)
        except Exception as exc:
            raise RuntimeError(
                "POSTGRES CONFIGURED BUT UNREACHABLE: "
                f"{_redact_url(self._pg_url)} did not accept a connection "
                f"({exc.__class__.__name__}). Set "
                "NORTHSTAR_ALLOW_SQLITE_FALLBACK=1 to run on SQLite instead."
            ) from exc
        self._pg_conn = conn

    @property
    def mode(self) -> str:
        return self._mode

    def _init_sqlite(self):
        """Create SQLite database and tables if they don't exist."""
        _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the FastAPI app runs sync handlers in a
        # threadpool, so one process-wide connection must be usable across
        # threads. All access is serialized by self._lock.
        self._conn = sqlite3.connect(str(_SQLITE_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_sqlite_tables()

    def _create_sqlite_tables(self):
        """Create all tables for SQLite mode."""
        cur = self._conn.cursor()
        cur.executescript("""
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
        """)
        self._conn.commit()
        self._migrate_live_columns()

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

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL (SQLite mode only for now)."""
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """Execute many SQL statements."""
        with self._lock:
            return self._conn.executemany(sql, params_list)

    def commit(self):
        """Commit the current transaction."""
        with self._lock:
            self._conn.commit()

    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()


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


class DesignStudioContainer:
    """Namespace for the Design Studio stores."""

    def __init__(self, db: DataLayer):
        self.projects = DesignStudioProjectsDB(db)
        self.assets = DesignStudioAssetsDB(db)
        self.jobs = DesignStudioJobsDB(db)
        self.rechecks = DesignStudioRechecksDB(db)


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

    @property
    def mode(self) -> str:
        return self._layer.mode


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def get_northstar_db() -> NorthstarDB:
    """Get the unified data access object."""
    return NorthstarDB()
