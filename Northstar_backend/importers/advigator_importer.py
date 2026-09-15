"""Advigator PPC Export Data Importer

Imports campaign performance data exported from the Advigator PPC
management dashboard. Advigator is a third-party Amazon PPC tool that
provides campaign optimization, bid management, and keyword tracking.

Advigator CSV exports contain:
- Campaign-level performance (impressions, clicks, spend, sales, ACOS)
- Keyword-level performance (bid history, search term triggers)
- Daily metrics over custom date ranges

Supported file patterns:
- `advigator_campaigns_*.csv`
- `advigator_keywords_*.csv`
- `advigator_search_terms_*.csv`
- `advigator_*.csv` (generic)

Usage:
    importer = AdvigatorImporter(db)
    result = importer.import_from_files()
    result = importer.import_campaigns_csv("path/to/campaigns.csv")
    result = importer.import_keywords_csv("path/to/keywords.csv")
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

# Column name variations across Advigator export formats
CAMPAIGN_COLUMNS = {
    # Advigator standard export
    "Campaign Name": "campaign_name",
    "Campaign": "campaign_name",
    "Campaign ID": "campaign_id",
    "CampaignStatus": "status",
    "Status": "status",
    "State": "status",
    "Daily Budget": "daily_budget",
    "Budget": "daily_budget",
    "Targeting Type": "targeting_type",
    "TargetingType": "targeting_type",
    "Impressions": "impressions",
    "Impression": "impressions",
    "Clicks": "clicks",
    "Click": "clicks",
    "Spend": "spend",
    "Cost": "spend",
    "Orders": "orders",
    "Total Orders": "orders",
    "7 Day Total Orders (#)": "orders",
    "Sales": "revenue",
    "Total Sales": "revenue",
    "7 Day Total Sales": "revenue",
    "ACoS": "acos",
    "acos": "acos",
    "ROAS": "roas",
    "Bid Strategy": "bid_strategy",
    "BidStrategy": "bid_strategy",
    "Date": "date",
}

KEYWORD_COLUMNS = {
    # Advigator keyword export
    "Campaign Name": "campaign_name",
    "Campaign": "campaign_name",
    "Ad Group": "ad_group",
    "AdGroup": "ad_group",
    "Keyword": "keyword",
    "Keyword Text": "keyword",
    "Match Type": "match_type",
    "MatchType": "match_type",
    "Bid": "bid",
    "Current Bid": "bid",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Spend": "spend",
    "Orders": "orders",
    "Sales": "revenue",
    "ACoS": "acos",
    "CTR": "ctr",
    "CVR": "cvr",
    "Status": "status",
    "State": "status",
    "Date": "date",
}

SEARCH_TERM_COLUMNS = {
    "Campaign Name": "campaign_name",
    "Campaign": "campaign_name",
    "Ad Group": "ad_group",
    "Targeting": "targeting",
    "Search Term": "search_term",
    "Match Type": "match_type",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Spend": "spend",
    "Orders": "orders",
    "Sales": "revenue",
    "ACoS": "acos",
    "Date": "date",
}

# Mapping from file pattern to column set
FILE_TYPE_MAP = {
    "campaign": CAMPAIGN_COLUMNS,
    "keyword": KEYWORD_COLUMNS,
    "search_term": SEARCH_TERM_COLUMNS,
    "search-term": SEARCH_TERM_COLUMNS,
    "st": SEARCH_TERM_COLUMNS,
}


class AdvigatorImporter:
    """Import Advigator PPC export data into the Northstar data layer.

    Supports campaign-level, keyword-level, and search term CSV files.

    Usage:
        importer = AdvigatorImporter(db)

        # Import all Advigator files from data directory
        result = importer.import_from_files()

        # Import specific file types
        result = importer.import_campaigns_csv("path/to/campaigns.csv")
        result = importer.import_keywords_csv("path/to/keywords.csv")

        # Import a generic Advigator CSV (auto-detect type)
        result = importer.import_csv("path/to/advigator_export.csv")
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
        """Advigator imports don't require API keys."""
        return True

    # ---- Batch Import ----

    def import_from_files(self) -> Dict[str, Any]:
        """Auto-discover and import all Advigator CSV files.

        Looks for files with names containing 'advigator'.

        Returns:
            Combined results dict.
        """
        if not self.data_dir.exists():
            return {
                "results": {},
                "total_imported": 0,
                "total_errors": 0,
                "reason": f"directory_not_found: {self.data_dir}",
            }

        advigator_files = sorted(self.data_dir.glob("*advigator*.csv"))

        if not advigator_files:
            return {
                "results": {},
                "total_imported": 0,
                "total_errors": 0,
                "reason": "no_advigator_files_found",
            }

        results = {}
        for file_path in advigator_files:
            result = self.import_csv(str(file_path))
            results[file_path.name] = result

        total_imported = sum(r.get("imported", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        return {
            "results": results,
            "total_imported": total_imported,
            "total_errors": total_errors,
            "files_processed": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ---- Generic CSV Import ----

    def import_csv(self, file_path: str) -> Dict[str, Any]:
        """Import an Advigator CSV file (auto-detects type).

        Detects whether the file is campaign-level, keyword-level, or
        search term data based on column headers and filename.

        Args:
            file_path: Path to the CSV file.

        Returns:
            Import result dict.
        """
        path = Path(file_path)
        if not path.exists():
            return {
                "imported": 0,
                "errors": 0,
                "details": [],
                "reason": f"file_not_found: {file_path}",
            }

        try:
            content = path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))

            if not reader.fieldnames:
                return {
                    "imported": 0,
                    "errors": 0,
                    "details": [],
                    "reason": "empty_csv",
                }

            # Auto-detect file type
            file_type = self._detect_file_type(path.name, reader.fieldnames)
            logger.info(f"Advigator file detected as: {file_type}")

            if file_type == "campaign":
                return self.import_campaigns_from_string(content)
            elif file_type == "keyword":
                return self.import_keywords_from_string(content)
            elif file_type == "search_term":
                return self.import_search_terms_from_string(content)
            else:
                # Default to keyword import
                logger.warning(f"Unknown Advigator file type, treating as keywords")
                return self.import_keywords_from_string(content)

        except Exception as e:
            logger.error(f"Error importing Advigator CSV {file_path}: {e}")
            return {"imported": 0, "errors": 1, "details": [{"error": str(e)}]}

    def _detect_file_type(
        self, filename: str, headers: List[str]
    ) -> str:
        """Detect the type of Advigator CSV from filename and headers."""
        name_lower = filename.lower()

        # Check filename first
        for type_key in FILE_TYPE_MAP:
            if type_key in name_lower:
                return type_key

        # Fall back to column detection
        header_set = set(h.strip() for h in headers)

        if "Campaign Name" in header_set or "Campaign" in header_set:
            if "Keyword" in header_set or "Keyword Text" in header_set:
                return "keyword"
            if "Search Term" in header_set:
                return "search_term"
            if "Impressions" in header_set and "Spend" in header_set:
                return "campaign"

        return "unknown"

    # ---- Campaign Import ----

    def import_campaigns_csv(self, file_path: str) -> Dict[str, Any]:
        """Import campaign data from a CSV file.

        Args:
            file_path: Path to the campaigns CSV.

        Returns:
            Import result dict.
        """
        path = Path(file_path)
        if not path.exists():
            return {"imported": 0, "errors": 0, "reason": f"file_not_found: {file_path}"}

        content = path.read_text(encoding="utf-8-sig")
        return self.import_campaigns_from_string(content)

    def import_campaigns_from_string(
        self, csv_content: str
    ) -> Dict[str, Any]:
        """Import campaign data from a CSV string.

        Maps Advigator campaign data to the campaigns table and creates
        daily performance snapshots as keyword_performance records.

        Returns:
            {"imported": int, "errors": int, "details": [...]}
        """
        result = {"imported": 0, "errors": 0, "details": []}

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            result["errors"] = 1
            result["details"].append({"error": str(e)})
            return result

        if not reader.fieldnames:
            result["errors"] = 1
            result["details"].append({"error": "No headers"})
            return result

        col_map = self._detect_column_map(reader.fieldnames, CAMPAIGN_COLUMNS)

        for row_num, raw_row in enumerate(reader, start=2):
            try:
                row = self._normalize_row(raw_row, col_map)

                camp_name = row.get("campaign_name", "").strip()
                if not camp_name:
                    continue

                # Generate a stable ID from campaign name
                import hashlib
                camp_id = f"adv-{hashlib.md5(camp_name.encode()).hexdigest()[:12]}"

                impressions = self._parse_int(row.get("impressions", 0))
                clicks = self._parse_int(row.get("clicks", 0))
                spend = self._parse_float(row.get("spend", 0)) or 0.0
                orders = self._parse_int(row.get("orders", 0))
                revenue = self._parse_float(row.get("revenue", 0)) or 0.0

                acos = (spend / revenue * 100) if revenue > 0 else None
                roas = (revenue / spend) if spend > 0 else None

                campaign = {
                    "id": camp_id,
                    "campaign_type": "sp",
                    "campaign_name": camp_name,
                    "status": row.get("status", "active").lower(),
                    "daily_budget": self._parse_float(row.get("daily_budget", 0)) or 0,
                    "targeting_type": row.get("targeting_type", ""),
                    "bid_strategy": row.get("bid_strategy", ""),
                    "impressions": impressions,
                    "clicks": clicks,
                    "spend": spend,
                    "orders": orders,
                    "revenue": revenue,
                    "acos": acos,
                    "roas": roas,
                }

                self.nsdb.campaigns.upsert(campaign)
                result["imported"] += 1
                result["details"].append(
                    {"campaign": camp_name, "spend": spend, "revenue": revenue}
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing Advigator campaign row {row_num}: {e}")

        logger.info(
            f"Advigator campaigns import: {result['imported']} imported, "
            f"{result['errors']} errors"
        )
        return result

    # ---- Keyword Import ----

    def import_keywords_csv(self, file_path: str) -> Dict[str, Any]:
        """Import keyword data from a CSV file.

        Args:
            file_path: Path to the keywords CSV.

        Returns:
            Import result dict.
        """
        path = Path(file_path)
        if not path.exists():
            return {"imported": 0, "errors": 0, "reason": f"file_not_found: {file_path}"}

        content = path.read_text(encoding="utf-8-sig")
        return self.import_keywords_from_string(content)

    def import_keywords_from_string(
        self, csv_content: str
    ) -> Dict[str, Any]:
        """Import keyword data from a CSV string.

        Maps Advigator keyword data to the keywords and keyword_performance
        tables. Creates keyword records and daily performance snapshots.

        Returns:
            {"imported": int, "errors": int, "details": [...]}
        """
        result = {"imported": 0, "errors": 0, "details": []}

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            result["errors"] = 1
            result["details"].append({"error": str(e)})
            return result

        if not reader.fieldnames:
            result["errors"] = 1
            result["details"].append({"error": "No headers"})
            return result

        col_map = self._detect_column_map(reader.fieldnames, KEYWORD_COLUMNS)

        for row_num, raw_row in enumerate(reader, start=2):
            try:
                row = self._normalize_row(raw_row, col_map)

                kw_text = row.get("keyword", "").strip()
                if not kw_text:
                    continue

                campaign_name = row.get("campaign_name", "")
                match_type = row.get("match_type", "")
                ad_group = row.get("ad_group", "")
                date = row.get("date", "")

                impressions = self._parse_int(row.get("impressions", 0))
                clicks = self._parse_int(row.get("clicks", 0))
                spend = self._parse_float(row.get("spend", 0)) or 0.0
                orders = self._parse_int(row.get("orders", 0))
                revenue = self._parse_float(row.get("revenue", 0)) or 0.0
                bid = self._parse_float(row.get("bid"))
                acos = self._parse_float(row.get("acos"))

                if acos is None and revenue > 0:
                    acos = spend / revenue * 100

                # Upsert keyword record
                kw_data = {
                    "keyword": kw_text,
                    "source": f"advigator:{match_type}",
                }
                kw_id = self.nsdb.keywords.upsert(kw_data)

                # Generate stable campaign ID
                import hashlib
                camp_id = f"adv-{hashlib.md5(campaign_name.encode()).hexdigest()[:12]}" if campaign_name else None

                # Insert performance record
                record_id = f"adv-kw-{hashlib.md5(f'{kw_text}:{campaign_name}:{date}'.encode()).hexdigest()[:16]}"

                self.db.execute(
                    """INSERT OR REPLACE INTO keyword_performance
                       (id, keyword_id, campaign_id, impressions, clicks,
                        spend, orders, revenue, acos, tier, movement,
                        recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        kw_id,
                        camp_id,
                        impressions,
                        clicks,
                        spend,
                        orders,
                        revenue,
                        acos,
                        "advigator",
                        match_type,
                        date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    ),
                )
                self.db.commit()

                result["imported"] += 1
                result["details"].append(
                    {
                        "keyword": kw_text,
                        "campaign": campaign_name,
                        "impressions": impressions,
                        "spend": spend,
                    }
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing Advigator keyword row {row_num}: {e}")

        logger.info(
            f"Advigator keywords import: {result['imported']} imported, "
            f"{result['errors']} errors"
        )
        return result

    # ---- Search Term Import ----

    def import_search_terms_csv(self, file_path: str) -> Dict[str, Any]:
        """Import search term data from a CSV file.

        Args:
            file_path: Path to the search terms CSV.

        Returns:
            Import result dict.
        """
        path = Path(file_path)
        if not path.exists():
            return {"imported": 0, "errors": 0, "reason": f"file_not_found: {file_path}"}

        content = path.read_text(encoding="utf-8-sig")
        return self.import_search_terms_from_string(content)

    def import_search_terms_from_string(
        self, csv_content: str
    ) -> Dict[str, Any]:
        """Import search term data from a CSV string.

        Stores in keyword_performance with tier="advigator_search_term".

        Returns:
            {"imported": int, "errors": int, "details": [...]}
        """
        result = {"imported": 0, "errors": 0, "details": []}

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            result["errors"] = 1
            result["details"].append({"error": str(e)})
            return result

        if not reader.fieldnames:
            result["errors"] = 1
            result["details"].append({"error": "No headers"})
            return result

        col_map = self._detect_column_map(
            reader.fieldnames, SEARCH_TERM_COLUMNS
        )

        for row_num, raw_row in enumerate(reader, start=2):
            try:
                row = self._normalize_row(raw_row, col_map)

                search_term = (
                    row.get("search_term") or row.get("targeting", "")
                ).strip()
                if not search_term:
                    continue

                campaign_name = row.get("campaign_name", "")
                match_type = row.get("match_type", "")
                date = row.get("date", "")

                impressions = self._parse_int(row.get("impressions", 0))
                clicks = self._parse_int(row.get("clicks", 0))
                spend = self._parse_float(row.get("spend", 0)) or 0.0
                orders = self._parse_int(row.get("orders", 0))
                revenue = self._parse_float(row.get("revenue", 0)) or 0.0

                acos = (spend / revenue * 100) if revenue > 0 else None

                # Upsert keyword
                kw_data = {
                    "keyword": search_term,
                    "source": f"advigator:search-term:{match_type}",
                }
                kw_id = self.nsdb.keywords.upsert(kw_data)

                # Stable record ID
                import hashlib
                record_id = f"adv-st-{hashlib.md5(f'{search_term}:{campaign_name}:{date}'.encode()).hexdigest()[:16]}"

                self.db.execute(
                    """INSERT OR REPLACE INTO keyword_performance
                       (id, keyword_id, impressions, clicks, spend, orders,
                        revenue, acos, tier, movement, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        kw_id,
                        impressions,
                        clicks,
                        spend,
                        orders,
                        revenue,
                        acos,
                        "advigator_search_term",
                        match_type,
                        date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    ),
                )
                self.db.commit()

                result["imported"] += 1
                result["details"].append(
                    {"search_term": search_term, "campaign": campaign_name}
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing Advigator search term row {row_num}: {e}")

        logger.info(
            f"Advigator search terms import: {result['imported']} imported, "
            f"{result['errors']} errors"
        )
        return result

    # ---- Helpers ----

    def _detect_column_map(
        self, fieldnames: List[str], primary_map: Dict[str, str]
    ) -> Dict[str, str]:
        """Detect the column mapping, trying the primary map first."""
        all_maps = [primary_map, CAMPAIGN_COLUMNS, KEYWORD_COLUMNS, SEARCH_TERM_COLUMNS]

        best_map = {}
        best_score = 0

        for col_map in all_maps:
            score = sum(1 for h in fieldnames if h in col_map)
            if score > best_score:
                best_score = score
                best_map = col_map

        return best_map if best_score >= 2 else primary_map

    def _normalize_row(
        self, raw_row: Dict[str, str], col_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """Normalize a CSV row."""
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
            cleaned = str(val).replace(",", "").replace("%", "").replace("$", "").strip()
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None
