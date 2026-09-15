"""Northstar OS - Automated Data Refresh Orchestrator

Coordinates all data importers and refreshes data from all configured sources.
Runs enabled importers in parallel (ThreadPoolExecutor), respects rate limits,
produces refresh reports, and tracks timestamps for incremental refresh.

Providers checked:
  - SP-API (Amazon Selling Partner API)
  - Bright Data (web scraping)
  - EasyParser (Amazon seller data)
  - DataForSEO (keyword/search data)
  - RapidAPI (product search)
  - ScrapeDo (fallback scraping)
  - Costco API / Browser Scraper

Usage:
    python data_refresh.py --full          Full refresh from all sources
    python data_refresh.py --incremental   Only pull new data since last refresh
    python data_refresh.py --status        Show refresh status and timestamps
    python data_refresh.py --providers     List configured providers
    python data_refresh.py --dry-run       Show what would run without executing

Requires: data_layer.py, env_flags.py, data_migration.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent

sys.path.insert(0, str(_BACKEND_DIR))
from data_layer import DataLayer, get_db, AuditDB  # noqa: E402
from data_migration import DataMigration  # noqa: E402

try:
    from env_flags import env_flag  # noqa: E402
except ImportError:
    def env_flag(name: str, default: bool = False) -> bool:  # type: ignore[misc]
        raw = (os.getenv(name) or "").strip().lower()
        if not raw:
            return default
        return raw in ("1", "true", "yes", "on")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("data_refresh")

# ---------------------------------------------------------------------------
# Metadata table for refresh tracking
# ---------------------------------------------------------------------------

_REFRESH_META_DDL = """
CREATE TABLE IF NOT EXISTS refresh_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    refresh_type TEXT NOT NULL DEFAULT 'full',
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    records_imported INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    credits_used INTEGER DEFAULT 0,
    credits_remaining INTEGER,
    error_message TEXT,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_refresh_provider ON refresh_metadata(provider);
CREATE INDEX IF NOT EXISTS idx_refresh_started ON refresh_metadata(started_at);
"""


def _ensure_refresh_meta_table(db: DataLayer) -> None:
    """Create refresh_metadata table if it doesn't exist."""
    # SQLite requires executescript for multiple statements
    if db.mode == "sqlite":
        db._conn.executescript(_REFRESH_META_DDL)
    else:
        for stmt in _REFRESH_META_DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                db.execute(stmt + ";")
    db.commit()


# ---------------------------------------------------------------------------
# Provider detection and configuration
# ---------------------------------------------------------------------------

class ProviderConfig:
    """Describes a data provider and whether it is configured."""

    def __init__(
        self,
        name: str,
        env_keys: List[str],
        module_name: Optional[str] = None,
        credit_cost: int = 0,
        rate_limit_rpm: int = 60,
        description: str = "",
    ):
        self.name = name
        self.env_keys = env_keys
        self.module_name = module_name
        self.credit_cost = credit_cost
        self.rate_limit_rpm = rate_limit_rpm
        self.description = description

    @property
    def is_configured(self) -> bool:
        """Check if at least one env key is set."""
        return any(os.environ.get(k) for k in self.env_keys)

    def __repr__(self) -> str:
        status = "configured" if self.is_configured else "missing keys"
        return f"Provider({self.name}: {status})"


# All known providers
PROVIDERS: List[ProviderConfig] = [
    ProviderConfig(
        name="sp_api",
        env_keys=["SP_API_REFRESH_TOKEN", "SP_API_CLIENT_ID", "SP_API_CLIENT_SECRET"],
        module_name="sp_api_client",
        credit_cost=0,
        rate_limit_rpm=30,
        description="Amazon Selling Partner API - product data, inventory, orders",
    ),
    ProviderConfig(
        name="bright_data",
        env_keys=["BRIGHTDATA_API_KEY", "BRIGHT_DATA_API_KEY", "BRIGHTDATA_UNLOCKER_API_KEY"],
        module_name="bright_data_client",
        credit_cost=1,
        rate_limit_rpm=10,
        description="Bright Data - web scraping, Amazon product pages",
    ),
    ProviderConfig(
        name="easyparser",
        env_keys=["EASYPARSER_API_KEY"],
        module_name="easyparser_client",
        credit_cost=2,
        rate_limit_rpm=20,
        description="EasyParser - Amazon seller offers, BSR, pricing",
    ),
    ProviderConfig(
        name="dataforseo",
        env_keys=["DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"],
        module_name="dataforseo_adapter",
        credit_cost=1,
        rate_limit_rpm=30,
        description="DataForSEO - keyword rankings, search volume, SERP data",
    ),
    ProviderConfig(
        name="rapidapi",
        env_keys=["RAPIDAPI_KEY"],
        module_name="rapidapi_client",
        credit_cost=1,
        rate_limit_rpm=30,
        description="RapidAPI - Amazon product search, pricing",
    ),
    ProviderConfig(
        name="scrapedo",
        env_keys=["SCRAPEDO_API_KEY"],
        module_name="scrapedo_amazon",
        credit_cost=1,
        rate_limit_rpm=10,
        description="ScrapeDo - fallback Amazon scraping",
    ),
    ProviderConfig(
        name="costco_online",
        env_keys=["COSTCO_API_KEY", "PILOTERR_API_KEY"],
        module_name="costco_client",
        credit_cost=0,
        rate_limit_rpm=5,
        description="Costco online catalog - product prices and availability",
    ),
]


def _detect_configured_providers() -> List[ProviderConfig]:
    """Return list of providers that have API keys configured."""
    return [p for p in PROVIDERS if p.is_configured]


# ---------------------------------------------------------------------------
# Refresh result tracking
# ---------------------------------------------------------------------------

class RefreshResult:
    """Result of a single provider refresh."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.status = "running"
        self.records_imported = 0
        self.records_updated = 0
        self.records_failed = 0
        self.credits_used = 0
        self.credits_remaining: Optional[int] = None
        self.error_message: Optional[str] = None
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None
        self.details: Dict[str, Any] = {}

    def mark_success(self) -> None:
        self.status = "success"
        self.finished_at = datetime.now(timezone.utc)

    def mark_partial(self, error: str) -> None:
        self.status = "partial"
        self.error_message = error
        self.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error_message = error
        self.finished_at = datetime.now(timezone.utc)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": self.status,
            "records_imported": self.records_imported,
            "records_updated": self.records_updated,
            "records_failed": self.records_failed,
            "credits_used": self.credits_used,
            "credits_remaining": self.credits_remaining,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Individual refresh runners
# ---------------------------------------------------------------------------

def _refresh_seller_cache(
    db: DataLayer, since: Optional[datetime] = None
) -> RefreshResult:
    """Refresh seller offer data from cached files + EasyParser."""
    result = RefreshResult("seller_cache")
    try:
        from data_migration import migrate_seller_offer_cache
        migration_result = migrate_seller_offer_cache(db)
        result.records_imported = migration_result.inserted
        result.records_updated = migration_result.updated
        result.records_failed = len(migration_result.errors)
        if migration_result.errors:
            result.mark_partial(f"{len(migration_result.errors)} errors during import")
        else:
            result.mark_success()
    except Exception as exc:
        result.mark_failed(str(exc))
    return result


def _refresh_market_data(
    db: DataLayer, since: Optional[datetime] = None
) -> RefreshResult:
    """Refresh market snapshot data."""
    result = RefreshResult("market_data")
    try:
        from data_migration import migrate_market_snapshots, migrate_scored_snapshots

        snap_result = migrate_market_snapshots(db)
        result.records_imported += snap_result.inserted
        result.records_updated += snap_result.updated
        result.records_failed += len(snap_result.errors)

        scored_result = migrate_scored_snapshots(db)
        result.records_imported += scored_result.inserted
        result.records_updated += scored_result.updated
        result.records_failed += len(scored_result.errors)

        total_errors = len(snap_result.errors) + len(scored_result.errors)
        if total_errors:
            result.mark_partial(f"{total_errors} errors during import")
        else:
            result.mark_success()
    except Exception as exc:
        result.mark_failed(str(exc))
    return result


def _refresh_costco_catalog(
    db: DataLayer, since: Optional[datetime] = None
) -> RefreshResult:
    """Refresh Costco catalog data."""
    result = RefreshResult("costco_catalog")
    try:
        from data_migration import (
            migrate_costco_csv,
            migrate_costco_api_catalog,
            migrate_asin_mapping,
        )

        migrate_asin_mapping(db)
        csv_result = migrate_costco_csv(db)
        catalog_result = migrate_costco_api_catalog(db)

        result.records_imported = csv_result.inserted + catalog_result.inserted
        result.records_updated = csv_result.updated + catalog_result.updated
        result.records_failed = len(csv_result.errors) + len(catalog_result.errors)

        total_errors = result.records_failed
        if total_errors:
            result.mark_partial(f"{total_errors} errors during import")
        else:
            result.mark_success()
    except Exception as exc:
        result.mark_failed(str(exc))
    return result


def _refresh_enrichment_data(
    db: DataLayer, since: Optional[datetime] = None
) -> RefreshResult:
    """Refresh enriched offer cache data."""
    result = RefreshResult("enrichment")
    try:
        from data_migration import migrate_enriched_offer_cache
        migration_result = migrate_enriched_offer_cache(db)
        result.records_imported = migration_result.inserted
        result.records_updated = migration_result.updated
        result.records_failed = len(migration_result.errors)
        if migration_result.errors:
            result.mark_partial(f"{len(migration_result.errors)} errors")
        else:
            result.mark_success()
    except Exception as exc:
        result.mark_failed(str(exc))
    return result


# Registry of refresh tasks
_REFRESH_TASKS: List[Tuple[str, Callable[[DataLayer, Optional[datetime]], RefreshResult]]] = [
    ("costco_catalog", _refresh_costco_catalog),
    ("seller_cache", _refresh_seller_cache),
    ("enrichment", _refresh_enrichment_data),
    ("market_data", _refresh_market_data),
]


# ---------------------------------------------------------------------------
# Post-refresh: recompute derived fields
# ---------------------------------------------------------------------------

def _update_product_scores(db: DataLayer) -> int:
    """Recompute net_profit, roi_pct, and risk_score for all products.

    Returns the number of products updated.
    """
    updated = 0

    cur = db.execute(
        """SELECT asin, amazon_price, costco_cost, fba_fee_estimate,
                  review_count, rating, monthly_sales_estimate
           FROM products
           WHERE amazon_price IS NOT NULL AND costco_cost IS NOT NULL"""
    )
    products = cur.fetchall()

    for row in products:
        asin = row["asin"]
        price = float(row["amazon_price"])
        cost = float(row["costco_cost"])
        fba_fee = float(row["fba_fee_estimate"]) if row["fba_fee_estimate"] else 0.0

        # Amazon referral fee (~15%)
        referral_fee = price * 0.15

        # Net profit
        net_profit = price - cost - fba_fee - referral_fee
        roi_pct = (net_profit / cost * 100) if cost > 0 else 0.0

        # Risk score (0-100, higher = riskier)
        risk = _compute_risk_score(row)

        db.execute(
            """UPDATE products
               SET net_profit = ?, roi_pct = ?, risk_score = ?,
                   updated_at = datetime('now')
               WHERE asin = ?""",
            (round(net_profit, 2), round(roi_pct, 1), risk, asin),
        )
        updated += 1

    db.commit()
    return updated


def _compute_risk_score(row: Any) -> int:
    """Compute a 0-100 risk score for a product.

    Higher score = riskier. Factors:
    - No price data        +30
    - Low review count     +15
    - Low rating           +15
    - Low monthly sales    +10
    """
    risk = 0
    if not row["amazon_price"]:
        risk += 30
    if row["review_count"] is not None and row["review_count"] < 10:
        risk += 15
    if row["rating"] is not None and row["rating"] < 3.5:
        risk += 15
    if row["monthly_sales_estimate"] is not None and row["monthly_sales_estimate"] < 10:
        risk += 10
    return min(risk, 100)


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

class DataRefreshOrchestrator:
    """Coordinates all data importers, runs them, and produces reports.

    Features:
    - Auto-detects configured providers
    - Parallel execution with ThreadPoolExecutor
    - Rate limit awareness
    - Incremental refresh (skip recently refreshed sources)
    - Refresh metadata tracking
    - Post-refresh score computation

    Attributes:
        db: Database layer.
        configured_providers: Providers with valid API keys.
        results: Refresh results from last run.
    """

    INCREMENTAL_GAP_HOURS = 6

    def __init__(self, db: Optional[DataLayer] = None):
        self.db = db or get_db()
        self.configured_providers = _detect_configured_providers()
        self.results: List[RefreshResult] = []
        _ensure_refresh_meta_table(self.db)

    def run_full(self, max_workers: int = 3) -> List[RefreshResult]:
        """Run a full refresh from all configured sources."""
        log.info(
            f"Starting FULL data refresh "
            f"({len(self.configured_providers)} providers configured, "
            f"{len(_REFRESH_TASKS)} tasks)"
        )
        self.results.clear()
        started = datetime.now(timezone.utc)

        AuditDB(self.db).log(
            action="refresh_started",
            entity_type="system",
            details={"mode": "full", "tasks": len(_REFRESH_TASKS)},
        )

        self._run_refresh_tasks(max_workers)

        log.info("Recomputing product scores...")
        scored = _update_product_scores(self.db)
        log.info(f"Updated scores for {scored} products")

        finished = datetime.now(timezone.utc)
        duration = (finished - started).total_seconds()

        self._persist_results()

        AuditDB(self.db).log(
            action="refresh_completed",
            entity_type="system",
            details={
                "mode": "full",
                "duration_seconds": round(duration, 2),
                "tasks_run": len(self.results),
                "success": sum(1 for r in self.results if r.status == "success"),
                "partial": sum(1 for r in self.results if r.status == "partial"),
                "failed": sum(1 for r in self.results if r.status == "failed"),
                "total_imported": sum(r.records_imported for r in self.results),
                "total_updated": sum(r.records_updated for r in self.results),
                "products_scored": scored,
            },
        )

        return self.results

    def run_incremental(self, max_workers: int = 3) -> List[RefreshResult]:
        """Run incremental refresh - only sources not recently refreshed."""
        log.info("Starting INCREMENTAL data refresh")
        self.results.clear()

        skip_tasks = self._get_recently_refreshed_tasks()
        if skip_tasks:
            log.info(f"Skipping recently refreshed: {', '.join(skip_tasks)}")

        tasks_to_run = [
            (name, fn) for name, fn in _REFRESH_TASKS if name not in skip_tasks
        ]

        if not tasks_to_run:
            log.info("All sources recently refreshed - nothing to do")
            return self.results

        self._run_refresh_tasks(max_workers, tasks=tasks_to_run)

        scored = _update_product_scores(self.db)

        self._persist_results()

        AuditDB(self.db).log(
            action="refresh_incremental",
            entity_type="system",
            details={
                "mode": "incremental",
                "tasks_run": len(self.results),
                "tasks_skipped": len(skip_tasks),
                "products_scored": scored,
            },
        )

        return self.results

    def get_status(self) -> Dict[str, Any]:
        """Get current refresh status and metadata."""
        cur = self.db.execute("""
            SELECT provider, status, started_at, finished_at,
                   records_imported, records_updated, records_failed
            FROM refresh_metadata
            WHERE id IN (
                SELECT MAX(id) FROM refresh_metadata
                WHERE status = 'success'
                GROUP BY provider
            )
            ORDER BY finished_at DESC
        """)
        latest = [dict(row) for row in cur.fetchall()]

        cur = self.db.execute(
            "SELECT COUNT(*) as cnt FROM refresh_metadata WHERE status = 'success'"
        )
        total_refreshes = cur.fetchone()["cnt"]

        cur2 = self.db.execute("""
            SELECT started_at, finished_at
            FROM refresh_metadata
            WHERE status = 'success'
            ORDER BY finished_at DESC LIMIT 1
        """)
        last_row = cur2.fetchone()
        last_refresh = dict(last_row) if last_row else None

        return {
            "configured_providers": [p.name for p in self.configured_providers],
            "total_refreshes": total_refreshes,
            "last_refresh": last_refresh,
            "latest_by_provider": latest,
            "incremental_gap_hours": self.INCREMENTAL_GAP_HOURS,
        }

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all providers with configuration status."""
        return [
            {
                "name": p.name,
                "configured": p.is_configured,
                "env_keys": p.env_keys,
                "credit_cost": p.credit_cost,
                "rate_limit_rpm": p.rate_limit_rpm,
                "description": p.description,
            }
            for p in PROVIDERS
        ]

    # --- Internal helpers ---

    def _run_refresh_tasks(
        self,
        max_workers: int,
        tasks: Optional[List[Tuple[str, Callable]]] = None,
    ) -> None:
        """Execute refresh tasks, optionally in parallel."""
        if tasks is None:
            tasks = _REFRESH_TASKS

        if len(tasks) == 1:
            name, fn = tasks[0]
            result = fn(self.db, since=None)
            self.results.append(result)
            return

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}
            for name, fn in tasks:
                future = executor.submit(fn, self.db, since=None)
                future_map[future] = name

            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    result = future.result(timeout=300)
                    self.results.append(result)
                    log.info(
                        f"[{name}] {result.status} - "
                        f"imported={result.records_imported} "
                        f"updated={result.records_updated} "
                        f"failed={result.records_failed}"
                    )
                except Exception as exc:
                    result = RefreshResult(name)
                    result.mark_failed(f"Thread exception: {exc}")
                    self.results.append(result)
                    log.error(f"[{name}] Failed: {exc}")

    def _get_recently_refreshed_tasks(self) -> set:
        """Return set of task names refreshed within the incremental gap."""
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=self.INCREMENTAL_GAP_HOURS)
        ).isoformat()

        cur = self.db.execute(
            """SELECT DISTINCT provider FROM refresh_metadata
               WHERE status = 'success' AND finished_at > ?""",
            (cutoff,),
        )
        return {row["provider"] for row in cur.fetchall()}

    def _persist_results(self) -> None:
        """Save refresh results to the metadata table."""
        for result in self.results:
            self.db.execute(
                """INSERT INTO refresh_metadata
                   (provider, refresh_type, status, started_at, finished_at,
                    records_imported, records_updated, records_failed,
                    credits_used, credits_remaining, error_message, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.provider_name,
                    "full",
                    result.status,
                    result.started_at.isoformat(),
                    result.finished_at.isoformat() if result.finished_at else None,
                    result.records_imported,
                    result.records_updated,
                    result.records_failed,
                    result.credits_used,
                    result.credits_remaining,
                    result.error_message,
                    json.dumps(result.details, default=str),
                ),
            )
        self.db.commit()

    def print_summary(self) -> None:
        """Print a human-readable refresh summary."""
        print("\n" + "=" * 60)
        print("DATA REFRESH SUMMARY")
        print("=" * 60)

        for r in self.results:
            icon = {"success": "[OK]", "partial": "[~~]", "failed": "[!!]"}.get(r.status, "?")
            print(
                f"  {icon} {r.provider_name:25s} {r.status:10s} "
                f"ins={r.records_imported} upd={r.records_updated} "
                f"fail={r.records_failed} ({r.duration_seconds:.1f}s)"
            )
            if r.error_message:
                print(f"    Error: {r.error_message}")

        print()
        total_ins = sum(r.records_imported for r in self.results)
        total_upd = sum(r.records_updated for r in self.results)
        total_fail = sum(r.records_failed for r in self.results)
        total_credits = sum(r.credits_used for r in self.results)
        print(
            f"  TOTAL: imported={total_ins} updated={total_upd} "
            f"failed={total_fail} credits={total_credits}"
        )
        print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for data refresh."""
    parser = argparse.ArgumentParser(
        description="Northstar OS - Data Refresh Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_refresh.py --full           Full refresh from all sources
  python data_refresh.py --incremental   Only new data since last refresh
  python data_refresh.py --status        Show refresh status
  python data_refresh.py --providers     List all providers and config status
  python data_refresh.py --dry-run       Show what would run
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="Full refresh")
    group.add_argument("--incremental", action="store_true", help="Incremental refresh")
    group.add_argument("--status", action="store_true", help="Show refresh status")
    group.add_argument("--providers", action="store_true", help="List providers")
    group.add_argument("--dry-run", action="store_true", help="Show what would run")

    parser.add_argument(
        "--workers", "-w", type=int, default=3,
        help="Max parallel workers (default: 3)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    orchestrator = DataRefreshOrchestrator()

    if args.status:
        status = orchestrator.get_status()
        print("\n" + "=" * 60)
        print("DATA REFRESH STATUS")
        print("=" * 60)
        print(f"  Configured providers: {', '.join(status['configured_providers']) or 'none'}")
        print(f"  Total successful refreshes: {status['total_refreshes']}")
        print(f"  Incremental gap: {status['incremental_gap_hours']}h")
        if status["last_refresh"]:
            print(f"  Last refresh: {status['last_refresh']['finished_at']}")
        print()
        print("  Latest per provider:")
        for entry in status["latest_by_provider"]:
            print(
                f"    {entry['provider']:25s} {entry['status']:10s} "
                f"ins={entry['records_imported']} upd={entry['records_updated']} "
                f"@ {entry['finished_at']}"
            )
        print("=" * 60)
        return

    if args.providers:
        providers = orchestrator.list_providers()
        print("\n" + "=" * 60)
        print("DATA PROVIDERS")
        print("=" * 60)
        for p in providers:
            icon = "[OK]" if p["configured"] else "[--]"
            print(f"  {icon} {p['name']:20s} credits={p['credit_cost']} "
                  f"rpm={p['rate_limit_rpm']}")
            print(f"    {p['description']}")
            keys_status = ", ".join(
                f"{k}={'SET' if os.environ.get(k) else 'MISSING'}"
                for k in p["env_keys"]
            )
            print(f"    Keys: {keys_status}")
        print("=" * 60)
        return

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - What would execute:")
        print("=" * 60)
        print(f"  Configured providers: {[p.name for p in orchestrator.configured_providers]}")
        print(f"  Refresh tasks: {[name for name, _ in _REFRESH_TASKS]}")
        if args.incremental:
            skip = orchestrator._get_recently_refreshed_tasks()
            print(f"  Would skip (recently refreshed): {skip}")
            run = [name for name, _ in _REFRESH_TASKS if name not in skip]
            print(f"  Would run: {run}")
        print("=" * 60)
        return

    if args.full:
        orchestrator.run_full(max_workers=args.workers)
    elif args.incremental:
        orchestrator.run_incremental(max_workers=args.workers)

    orchestrator.print_summary()


if __name__ == "__main__":
    main()
