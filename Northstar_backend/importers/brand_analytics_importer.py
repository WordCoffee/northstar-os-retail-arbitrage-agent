"""Amazon Brand Analytics Data Importer

Downloads and parses Brand Analytics report data:
- Search Query Performance (SQP): query-level impressions, clicks, purchases
- Search Catalog Performance: ASIN-level performance within search results

Data source: Amazon Seller Central > Brand Analytics, either via manual CSV
download or the SP-API Brand Analytics report endpoints.

Store target: search_query_performance table.
"""

import os
import csv
import json
import logging
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Brand Analytics CSV column mappings (standard Amazon export format)
SQP_COLUMNS = {
    "Search Query": "query",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Cart Adds": "cart_adds",
    "Purchases": "purchases",
    "Click Share": "click_share",
    "Cart Share": "cart_share",
    "Purchase Share": "purchase_share",
    "Search Frequency Rank": "search_frequency_rank",
    "ASIN": "asin",
}

# Alternate column names (different export versions use different headers)
SQP_ALT_COLUMNS = {
    "search_query": "query",
    "impressions": "impressions",
    "clicks": "clicks",
    "cart_adds": "cart_adds",
    "purchases": "purchases",
    "click_share": "click_share",
    "cart_share": "cart_share",
    "purchase_share": "purchase_share",
    "search_frequency_rank": "search_frequency_rank",
    "searchFrequencyRank": "search_frequency_rank",
    "asin": "asin",
}

# Search Catalog Performance columns
SCP_COLUMNS = {
    "ASIN": "asin",
    "Search Query": "query",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Cart Adds": "cart_adds",
    "Purchases": "purchases",
    "Click Share": "click_share",
    "Cart Share": "cart_share",
    "Purchase Share": "purchase_share",
    "Click Rank": "click_rank",
    "Cart Rank": "cart_rank",
    "Purchase Rank": "purchase_rank",
}

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class BrandAnalyticsImporter:
    """Import Brand Analytics data into the Northstar data layer.

    Supports both manual CSV uploads and programmatic report downloads.

    Usage:
        importer = BrandAnalyticsImporter(db)

        # From CSV file
        result = importer.import_sqp_csv("path/to/sqp_report.csv")

        # From CSV string (e.g., from API download)
        result = importer.import_sqp_from_string(csv_text)

        # List available CSV files in data directory
        files = importer.list_available_reports()
    """

    def __init__(self, db=None, data_dir: Optional[str] = None):
        from data_layer import get_db, NorthstarDB

        if db is None:
            db = get_db()
        self.db = db
        self.nsdb = NorthstarDB()
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    @property
    def is_configured(self) -> bool:
        """Brand Analytics doesn't require API keys, just data files."""
        return True

    def list_available_reports(self) -> List[Dict[str, str]]:
        """List Brand Analytics CSV files in the data directory.

        Returns:
            List of dicts with 'path', 'name', 'size', 'modified' keys.
        """
        reports = []
        if not self.data_dir.exists():
            return reports

        for p in self.data_dir.glob("*.csv"):
            name_lower = p.name.lower()
            if any(
                kw in name_lower
                for kw in ["brand_analytics", "sqp", "search_query", "catalog_performance"]
            ):
                stat = p.stat()
                reports.append(
                    {
                        "path": str(p),
                        "name": p.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
        return reports

    def import_sqp_csv(
        self,
        file_path: str,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        asin_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Search Query Performance from a CSV file.

        Args:
            file_path: Path to the CSV file.
            date_start: Start date of the report period (YYYY-MM-DD).
            date_end: End date of the report period (YYYY-MM-DD).
            asin_override: Force all rows to this ASIN (if not in CSV).

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        path = Path(file_path)
        if not path.exists():
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"file_not_found: {file_path}",
            }

        try:
            content = path.read_text(encoding="utf-8-sig")  # Handle BOM
            return self.import_sqp_from_string(
                content, date_start, date_end, asin_override
            )
        except Exception as e:
            logger.error(f"Failed to read Brand Analytics CSV: {e}")
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"read_error: {e}",
            }

    def import_sqp_from_string(
        self,
        csv_content: str,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        asin_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Search Query Performance from a CSV string.

        Automatically detects column format (title-case or snake_case) and
        normalizes all fields.

        Args:
            csv_content: Raw CSV text.
            date_start: Report period start.
            date_end: Report period end.
            asin_override: Force all rows to this ASIN.

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
            result["errors"] = 1
            result["details"].append({"error": str(e)})
            return result

        # Detect column mapping
        if not reader.fieldnames:
            result["errors"] = 1
            result["details"].append({"error": "CSV has no header row"})
            return result

        col_map = self._detect_column_map(reader.fieldnames)

        for row_num, raw_row in enumerate(reader, start=2):
            try:
                row = self._normalize_row(raw_row, col_map)

                query = row.get("query", "")
                asin = asin_override or row.get("asin", "")

                if not query:
                    result["skipped"] += 1
                    continue

                # Build dedup key
                dedup_source = f"brand-analytics:sqp:{asin}:{query}:{date_start or 'unknown'}"

                existing = self.db.execute(
                    "SELECT id FROM search_query_performance WHERE query = ? AND asin = ? AND date_start = ?",
                    (query, asin, date_start or ""),
                ).fetchone()

                if existing:
                    result["skipped"] += 1
                    continue

                record_id = f"sqp-{hash(dedup_source)[:16]}"

                self.db.execute(
                    """INSERT OR REPLACE INTO search_query_performance
                       (id, query, asin, date_start, date_end, impressions,
                        clicks, cart_adds, purchases, impression_share,
                        click_share, cart_share, purchase_share,
                        search_frequency_rank, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        query,
                        asin,
                        date_start or "",
                        date_end or "",
                        self._parse_int(row.get("impressions", 0)),
                        self._parse_int(row.get("clicks", 0)),
                        self._parse_int(row.get("cart_adds", 0)),
                        self._parse_int(row.get("purchases", 0)),
                        self._parse_float(row.get("impression_share")),
                        self._parse_float(row.get("click_share")),
                        self._parse_float(row.get("cart_share")),
                        self._parse_float(row.get("purchase_share")),
                        self._parse_int(row.get("search_frequency_rank")),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                self.db.commit()

                result["imported"] += 1
                result["details"].append(
                    {"row": row_num, "query": query, "asin": asin}
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing SQP row {row_num}: {e}")

        logger.info(
            f"Brand Analytics SQP import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    def import_catalog_performance_csv(
        self,
        file_path: str,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Search Catalog Performance from a CSV file.

        This is the ASIN-centric view (which ASINs appear for each search query).

        Args:
            file_path: Path to the CSV file.
            date_start: Report period start.
            date_end: Report period end.

        Returns:
            Import result dict.
        """
        path = Path(file_path)
        if not path.exists():
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"file_not_found: {file_path}",
            }

        try:
            content = path.read_text(encoding="utf-8-sig")
            return self.import_catalog_performance_from_string(
                content, date_start, date_end
            )
        except Exception as e:
            logger.error(f"Failed to read Catalog Performance CSV: {e}")
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"read_error: {e}",
            }

    def import_catalog_performance_from_string(
        self,
        csv_content: str,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Search Catalog Performance from a CSV string.

        Args:
            csv_content: Raw CSV text.
            date_start: Report period start.
            date_end: Report period end.

        Returns:
            Import result dict.
        """
        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            result["errors"] = 1
            result["details"].append({"error": str(e)})
            return result

        if not reader.fieldnames:
            result["errors"] = 1
            result["details"].append({"error": "CSV has no header row"})
            return result

        col_map = self._detect_column_map(reader.fieldnames, column_set=SCP_COLUMNS)

        for row_num, raw_row in enumerate(reader, start=2):
            try:
                row = self._normalize_row(raw_row, col_map)
                query = row.get("query", "")
                asin = row.get("asin", "")

                if not query or not asin:
                    result["skipped"] += 1
                    continue

                record_id = f"scp-{hash(f'{asin}:{query}:{date_start}')[:16]}"

                existing = self.db.execute(
                    "SELECT id FROM search_query_performance WHERE query = ? AND asin = ? AND date_start = ?",
                    (query, asin, date_start or ""),
                ).fetchone()

                if existing:
                    result["skipped"] += 1
                    continue

                self.db.execute(
                    """INSERT OR REPLACE INTO search_query_performance
                       (id, query, asin, date_start, date_end, impressions,
                        clicks, cart_adds, purchases, impression_share,
                        click_share, cart_share, purchase_share,
                        search_frequency_rank, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        query,
                        asin,
                        date_start or "",
                        date_end or "",
                        self._parse_int(row.get("impressions", 0)),
                        self._parse_int(row.get("clicks", 0)),
                        self._parse_int(row.get("cart_adds", 0)),
                        self._parse_int(row.get("purchases", 0)),
                        self._parse_float(row.get("impression_share")),
                        self._parse_float(row.get("click_share")),
                        self._parse_float(row.get("cart_share")),
                        self._parse_float(row.get("purchase_share")),
                        self._parse_int(row.get("search_frequency_rank")),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                self.db.commit()
                result["imported"] += 1
                result["details"].append(
                    {"row": row_num, "query": query, "asin": asin}
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing SCP row {row_num}: {e}")

        logger.info(
            f"Brand Analytics SCP import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    # ---- Helpers ----

    def _detect_column_map(
        self,
        fieldnames: List[str],
        column_set: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Detect which column mapping to use based on header names.

        Returns a dict mapping CSV header -> internal field name.
        """
        all_maps = [SQP_COLUMNS, SQP_ALT_COLUMNS, SCP_COLUMNS]
        if column_set:
            all_maps.append(column_set)

        best_map = {}
        best_score = 0

        for col_map in all_maps:
            score = sum(1 for header in fieldnames if header in col_map)
            if score > best_score:
                best_score = score
                best_map = col_map

        return best_map

    def _normalize_row(
        self, raw_row: Dict[str, str], col_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """Normalize a CSV row using the detected column map."""
        normalized = {}
        for csv_header, value in raw_row.items():
            if csv_header in col_map:
                field_name = col_map[csv_header]
                normalized[field_name] = value.strip() if isinstance(value, str) else value
        return normalized

    @staticmethod
    def _parse_int(val: Any) -> int:
        """Safely parse an integer from various formats."""
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        try:
            cleaned = str(val).replace(",", "").strip()
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_float(val: Any) -> Optional[float]:
        """Safely parse a float from various formats."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            cleaned = str(val).replace(",", "").replace("%", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None
