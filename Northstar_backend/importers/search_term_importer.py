"""Search Term Report Importer

Imports Amazon Search Term Reports from:
1. Manual CSV uploads (Seller Central > Advertising > Search Term Report)
2. Amazon Ads API report downloads (via AdsAPIImporter)

Standard CSV columns:
  Date, Targeting, Match Type, Impression, Click,
  7 Day Total Orders (#), 7 Day Total Sales, ACoS, etc.

Deduplicates by (query, asin, report_date).
Stores into keyword_performance table.
"""

import os
import csv
import json
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Column name variations across different report formats
COLUMN_MAPPINGS = [
    # Seller Central standard format
    {
        "Date": "date",
        "Targeting": "targeting",
        "Match Type": "match_type",
        "Impressions": "impressions",
        "Impression": "impressions",
        "Clicks": "clicks",
        "Click": "clicks",
        "Spend": "spend",
        "7 Day Total Orders (#)": "orders_7d",
        "Orders (#)": "orders_7d",
        "Total Orders (#)": "orders_7d",
        "7 Day Total Sales": "sales_7d",
        "Total Sales": "sales_7d",
        "Sales": "sales_7d",
        "ACoS": "acos",
        "CTR": "ctr",
        "CVR": "cvr",
        "CPC": "cpc",
        "Bid": "bid",
        "Ad Group": "ad_group",
        "Campaign": "campaign",
        "Advertised ASIN": "asin",
        "Advertised Product": "asin",
        "SKU": "sku",
    },
    # snake_case format (API exports)
    {
        "date": "date",
        "targeting": "targeting",
        "match_type": "match_type",
        "impressions": "impressions",
        "clicks": "clicks",
        "spend": "spend",
        "orders_7d": "orders_7d",
        "orders": "orders_7d",
        "sales_7d": "sales_7d",
        "sales": "sales_7d",
        "acos": "acos",
        "ctr": "ctr",
        "cvr": "cvr",
        "cpc": "cpc",
        "bid": "bid",
        "ad_group": "ad_group",
        "campaign": "campaign",
        "asin": "asin",
        "sku": "sku",
        "query": "targeting",
        "search_term": "targeting",
    },
    # camelCase format
    {
        "date": "date",
        "targeting": "targeting",
        "matchType": "match_type",
        "impressions": "impressions",
        "clicks": "clicks",
        "spend": "spend",
        "orders7d": "orders_7d",
        "sales7d": "sales_7d",
        "acos": "acos",
        "asin": "asin",
        "query": "targeting",
        "searchTerm": "targeting",
    },
]


class SearchTermImporter:
    """Import Search Term Reports into the Northstar data layer.

    Usage:
        importer = SearchTermImporter(db)

        # Import from a CSV file
        result = importer.import_csv("path/to/search_term_report.csv")

        # Import from a CSV string
        result = importer.import_from_string(csv_text, campaign_id="camp-123")

        # Auto-discover and import all search term files in data dir
        result = importer.import_all_from_directory()

        # Import from Ads API report (delegates to AdsAPIImporter)
        result = importer.import_from_ads_api(start_date="2026-01-01")
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
        return True  # No API keys needed for CSV imports

    # ---- CSV File Import ----

    def import_csv(
        self,
        file_path: str,
        campaign_id: Optional[str] = None,
        asin_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import a Search Term Report from a CSV file.

        Args:
            file_path: Path to the CSV file.
            campaign_id: Optional campaign ID to associate all rows with.
            asin_override: Force all rows to this ASIN.

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

        if not path.suffix.lower() == ".csv":
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"not_a_csv: {file_path}",
            }

        try:
            content = path.read_text(encoding="utf-8-sig")
            return self.import_from_string(content, campaign_id, asin_override)
        except Exception as e:
            logger.error(f"Failed to read search term CSV {file_path}: {e}")
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"read_error: {e}",
            }

    # ---- String Import ----

    def import_from_string(
        self,
        csv_content: str,
        campaign_id: Optional[str] = None,
        asin_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Search Term Report from a CSV string.

        Detects the column format automatically and parses all rows.

        Args:
            csv_content: Raw CSV text.
            campaign_id: Optional campaign ID.
            asin_override: Force all rows to this ASIN.

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            result["errors"] = 1
            result["details"].append({"error": f"CSV parse error: {e}"})
            return result

        if not reader.fieldnames:
            result["errors"] = 1
            result["details"].append({"error": "No header row found in CSV"})
            return result

        # Detect column mapping
        col_map = self._detect_column_map(reader.fieldnames)
        if not col_map:
            result["errors"] = 1
            result["details"].append(
                {
                    "error": "Unrecognized CSV format",
                    "headers": reader.fieldnames,
                }
            )
            return result

        logger.info(f"Search term CSV detected with {len(col_map)} mapped columns")

        for row_num, raw_row in enumerate(reader, start=2):
            try:
                row = self._normalize_row(raw_row, col_map)

                # Extract key fields
                targeting = row.get("targeting", "").strip()
                if not targeting:
                    result["skipped"] += 1
                    continue

                asin = asin_override or row.get("asin", "").strip()
                report_date = row.get("date", "").strip()
                match_type = row.get("match_type", "").strip()

                impressions = self._parse_int(row.get("impressions", 0))
                clicks = self._parse_int(row.get("clicks", 0))
                spend = self._parse_float(row.get("spend", 0)) or 0.0
                orders = self._parse_int(row.get("orders_7d", 0))
                sales = self._parse_float(row.get("sales_7d", 0)) or 0.0
                acos = self._parse_float(row.get("acos"))
                bid = self._parse_float(row.get("bid"))

                # Deduplication key: query + asin + date
                dedup_key = f"st:{targeting}:{asin}:{report_date}"

                # Check for existing record
                existing = self.db.execute(
                    """SELECT id FROM keyword_performance
                       WHERE asin = ? AND keyword_id IN (
                           SELECT id FROM keywords WHERE keyword = ?
                       ) AND recorded_at LIKE ?""",
                    (asin, targeting, f"{report_date}%"),
                ).fetchone()

                if existing:
                    result["skipped"] += 1
                    continue

                # Upsert the keyword itself
                kw_data = {
                    "keyword": targeting,
                    "source": f"search-term-report:{match_type}",
                }
                if impressions > 0:
                    kw_data["search_volume"] = impressions
                kw_id = self.nsdb.keywords.upsert(kw_data)

                # Calculate derived metrics
                ctr = (clicks / impressions * 100) if impressions > 0 else 0.0
                cvr = (orders / clicks * 100) if clicks > 0 else 0.0
                cpc = (spend / clicks) if clicks > 0 else 0.0

                # Insert performance record
                record_id = f"st-{hash(dedup_key)[:16]}"
                self.db.execute(
                    """INSERT OR REPLACE INTO keyword_performance
                       (id, keyword_id, asin, campaign_id, impressions, clicks,
                        spend, orders, revenue, acos, tier, movement, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        kw_id,
                        asin,
                        campaign_id,
                        impressions,
                        clicks,
                        spend,
                        orders,
                        sales,
                        acos,
                        "search_term",
                        match_type,
                        report_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    ),
                )
                self.db.commit()

                result["imported"] += 1
                result["details"].append(
                    {
                        "row": row_num,
                        "query": targeting,
                        "asin": asin,
                        "impressions": impressions,
                        "clicks": clicks,
                        "orders": orders,
                        "sales": sales,
                    }
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing search term row {row_num}: {e}")

        logger.info(
            f"Search term import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    # ---- Batch Import from Directory ----

    def import_all_from_directory(
        self,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Auto-discover and import all search term CSVs in data dir.

        Looks for files with names containing 'search_term', 'search-term',
        'st_report', or similar patterns.

        Args:
            campaign_id: Optional campaign ID to associate.

        Returns:
            Combined results from all files.
        """
        if not self.data_dir.exists():
            return {
                "results": {},
                "total_imported": 0,
                "total_errors": 0,
                "reason": f"directory_not_found: {self.data_dir}",
            }

        patterns = ["*search*term*", "*st_report*", "*st-report*", "*SearchTerm*"]
        files_found = set()
        for pattern in patterns:
            files_found.update(self.data_dir.glob(f"{pattern}.csv"))

        if not files_found:
            return {
                "results": {},
                "total_imported": 0,
                "total_errors": 0,
                "reason": "no_search_term_files_found",
            }

        results = {}
        for file_path in sorted(files_found):
            file_result = self.import_csv(str(file_path), campaign_id=campaign_id)
            results[file_path.name] = file_result

        total_imported = sum(r.get("imported", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        return {
            "results": results,
            "total_imported": total_imported,
            "total_errors": total_errors,
            "files_processed": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ---- Ads API Delegation ----

    def import_from_ads_api(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import search terms via the Ads API report endpoint.

        Delegates to AdsAPIImporter.run_search_term_report().

        Args:
            start_date: Report start date (YYYY-MM-DD).
            end_date: Report end date (YYYY-MM-DD).

        Returns:
            Import result dict.
        """
        try:
            from .ads_api_importer import AdsAPIImporter
            ads_importer = AdsAPIImporter(self.db)
            return ads_importer.run_search_term_report(start_date, end_date)
        except ImportError:
            logger.error("AdsAPIImporter not available")
            return {
                "imported": 0,
                "errors": 0,
                "details": [],
                "reason": "ads_api_importer_not_available",
            }

    # ---- Helpers ----

    def _detect_column_map(self, fieldnames: List[str]) -> Optional[Dict[str, str]]:
        """Detect the best column mapping for the given headers.

        Returns:
            Dict mapping CSV header -> internal field name, or None.
        """
        best_map = None
        best_score = 0

        for candidate_map in COLUMN_MAPPINGS:
            score = sum(1 for h in fieldnames if h in candidate_map)
            if score > best_score:
                best_score = score
                best_map = candidate_map

        # Require at least 3 matching columns
        if best_score < 3:
            return None

        return best_map

    def _normalize_row(
        self, raw_row: Dict[str, str], col_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """Normalize a CSV row using the column map."""
        normalized = {}
        for csv_header, value in raw_row.items():
            if csv_header in col_map:
                field_name = col_map[csv_header]
                normalized[field_name] = (
                    value.strip() if isinstance(value, str) else value
                )
        return normalized

    @staticmethod
    def _parse_int(val: Any) -> int:
        """Safely parse an integer."""
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        try:
            cleaned = str(val).replace(",", "").replace("%", "").strip()
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_float(val: Any) -> Optional[float]:
        """Safely parse a float."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            cleaned = str(val).replace(",", "").replace("%", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None
