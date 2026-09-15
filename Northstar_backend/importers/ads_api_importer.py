"""Amazon Ads API Data Importer

Pulls advertising data from Amazon Ads API:
- Sponsored Products campaigns
- Sponsored Brands campaigns
- Keyword performance data
- Search term reports

Auth: OAuth2 (client_id, client_secret, refresh_token) — separate from SP-API.
Base URL: https://advertising-api.amazon.com
Rate limits: Varies by endpoint (typically 10 req/min for reports).
"""

import os
import csv
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Amazon Ads API configuration
ADS_API_BASE = "https://advertising-api.amazon.com"
ADS_AUTH_URL = "https://api.amazon.com/auth/o2/token"

# Ad types
SPONSORED_PRODUCTS = "sp"
SPONSORED_BRANDS = "sb"

# Endpoint templates
ADS_ENDPOINTS = {
    "profiles": "/v2/profiles",
    "campaigns": "/v2/campaigns",
    "ad_groups": "/v2/adGroups",
    "keywords": "/v2/keywords",
    "negative_keywords": "/v2/negativeKeywords",
    "product_ads": "/v2/productAds",
    "reports": "/v2/reports",
    "report_status": "/v2/reports/{reportId}",
    "search_terms": "/v2/searchTerms",
}


class AdsAPIAuth:
    """OAuth2 token management for Amazon Ads API.

    Uses a separate OAuth flow from SP-API. Requires:
    - ADS_CLIENT_ID
    - ADS_CLIENT_SECRET
    - ADS_REFRESH_TOKEN
    """

    def __init__(self):
        self._client_id = os.environ.get("ADS_CLIENT_ID", "")
        self._client_secret = os.environ.get("ADS_CLIENT_SECRET", "")
        self._refresh_token = os.environ.get("ADS_REFRESH_TOKEN", "")
        self._access_token = None
        self._token_expiry = None

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret and self._refresh_token)

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if needed."""
        if self._token_expired():
            self._refresh()
        return self._access_token

    def _token_expired(self) -> bool:
        if not self._access_token or not self._token_expiry:
            return True
        return datetime.now(timezone.utc) >= self._token_expiry

    def _refresh(self):
        """Refresh the OAuth access token."""
        try:
            import httpx

            resp = httpx.post(
                ADS_AUTH_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expiry = datetime.now(timezone.utc) + timedelta(
                seconds=data.get("expires_in", 3600) - 60
            )
            logger.info("Ads API token refreshed successfully")
        except Exception as e:
            logger.error(f"Ads API token refresh failed: {e}")
            self._access_token = None
            self._token_expiry = None


class AdsAPIImporter:
    """Import data from Amazon Ads API.

    Handles Sponsored Products and Sponsored Brands campaigns, keyword
    performance, and search term reports.

    Usage:
        importer = AdsAPIImporter(db)
        result = importer.import_campaigns()
        result = importer.import_keywords()
        result = importer.run_search_term_report()
    """

    def __init__(self, db=None):
        from data_layer import get_db, NorthstarDB

        if db is None:
            db = get_db()
        self.db = db
        self.nsdb = NorthstarDB()
        self.auth = AdsAPIAuth()
        self._enabled = self.auth.is_configured
        self._profile_id = None
        if not self._enabled:
            logger.warning("Ads API not configured — import will return empty results")

    @property
    def is_configured(self) -> bool:
        return self._enabled

    def _get_headers(self, ad_type: str = SPONSORED_PRODUCTS) -> Dict[str, str]:
        """Build request headers for Ads API calls."""
        token = self.auth.get_access_token()
        if not token:
            raise RuntimeError("Ads API not authenticated")
        return {
            "Amazon-Advertising-API-ClientId": self.auth._client_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Amazon-Advertising-API-Scope": str(self._get_profile_id()),
        }

    def _get_profile_id(self) -> Optional[int]:
        """Fetch and cache the first available profile ID."""
        if self._profile_id:
            return self._profile_id

        try:
            data = self._api_get(ADS_ENDPOINTS["profiles"])
            profiles = data if isinstance(data, list) else []
            # Prefer a Sponsored Products profile
            for p in profiles:
                if p.get("profileType") == "SELLER":
                    self._profile_id = p["profileId"]
                    return self._profile_id
            # Fall back to any profile
            if profiles:
                self._profile_id = profiles[0].get("profileId")
            return self._profile_id
        except Exception as e:
            logger.error(f"Failed to fetch Ads API profiles: {e}")
            return None

    def _api_get(
        self, endpoint: str, params: Dict[str, Any] = None
    ) -> Optional[Any]:
        """Make a GET request with retry and throttling."""
        import httpx

        url = f"{ADS_API_BASE}{endpoint}"
        headers = self._get_headers()

        for attempt in range(3):
            try:
                resp = httpx.get(url, headers=headers, params=params or {}, timeout=30)
                if resp.status_code == 429:
                    wait = 2 ** attempt * 5  # Exponential backoff: 5, 10, 20s
                    logger.warning(f"Ads API throttled, waiting {wait}s")
                    time.sleep(wait)
                    continue
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(
                    f"Ads API GET {endpoint} attempt {attempt+1} failed: {e}"
                )
                if attempt == 2:
                    return None
                time.sleep(2 ** attempt)
        return None

    def _api_post(
        self, endpoint: str, body: Dict[str, Any]
    ) -> Optional[Dict]:
        """Make a POST request with retry."""
        import httpx

        url = f"{ADS_API_BASE}{endpoint}"
        headers = self._get_headers()

        for attempt in range(3):
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=30)
                if resp.status_code == 429:
                    wait = 2 ** attempt * 5
                    logger.warning(f"Ads API throttled, waiting {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(
                    f"Ads API POST {endpoint} attempt {attempt+1} failed: {e}"
                )
                if attempt == 2:
                    return None
                time.sleep(2 ** attempt)
        return None

    # ---- Campaigns ----

    def import_campaigns(
        self, ad_type: str = SPONSORED_PRODUCTS
    ) -> Dict[str, Any]:
        """Import campaign data from Ads API.

        Args:
            ad_type: "sp" for Sponsored Products, "sb" for Sponsored Brands.

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        if not self._enabled:
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": "not_configured",
            }

        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        # Fetch campaigns from Ads API
        endpoint = ADS_ENDPOINTS["campaigns"]
        params = {"stateFilter": "enabled,paused,archived"}

        data = self._api_get(endpoint, params)
        if not data:
            logger.warning("No campaigns returned from Ads API")
            return result

        campaigns = data if isinstance(data, list) else data.get("campaigns", [])

        for camp in campaigns:
            try:
                camp_id = str(camp.get("campaignId", ""))
                if not camp_id:
                    continue

                # Extract ASIN from targeting (if available)
                asin = ""
                entities = camp.get("targetingExpression", [])
                if isinstance(entities, list):
                    for expr in entities:
                        if isinstance(expr, dict) and "asin" in expr:
                            asin = expr["asin"]
                            break

                campaign_record = {
                    "id": camp_id,
                    "campaign_type": ad_type,
                    "campaign_name": camp.get("name", ""),
                    "status": camp.get("state", "paused").lower(),
                    "daily_budget": float(camp.get("dailyBudget", 0)),
                    "targeting_type": camp.get("targetingType", "manual"),
                    "bid_strategy": camp.get("bidStrategy", ""),
                }

                # Only add ASIN if we have one
                if asin:
                    campaign_record["asin"] = asin

                # Check for existing record
                existing = self.db.execute(
                    "SELECT id FROM campaigns WHERE id = ?", (camp_id,)
                ).fetchone()

                if existing:
                    # Update metrics only (don't overwrite local config)
                    self.nsdb.campaigns.upsert(campaign_record)
                    result["skipped"] += 1
                else:
                    self.nsdb.campaigns.upsert(campaign_record)
                    result["imported"] += 1

                result["details"].append(
                    {"campaign_id": camp_id, "name": camp.get("name", "")}
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing campaign {camp.get('campaignId')}: {e}")

        logger.info(
            f"Ads API campaigns import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    # ---- Keywords ----

    def import_keywords(
        self, campaign_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import keyword data from Ads API.

        Args:
            campaign_id: Optional filter to a specific campaign.

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        if not self._enabled:
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": "not_configured",
            }

        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        # Get campaigns to iterate
        if campaign_id:
            campaigns = [{"campaignId": campaign_id}]
        else:
            camp_data = self.nsdb.campaigns.list_all()
            campaigns = [{"campaignId": c["id"]} for c in camp_data]

        for camp in campaigns:
            cid = camp["campaignId"]

            # Fetch ad groups for this campaign
            ag_data = self._api_get(
                ADS_ENDPOINTS["ad_groups"],
                {"campaignIdFilter": cid},
            )
            ad_groups = ag_data if isinstance(ag_data, list) else []

            for ag in ad_groups:
                ag_id = ag.get("adGroupId", "")

                # Fetch keywords for this ad group
                kw_data = self._api_get(
                    ADS_ENDPOINTS["keywords"],
                    {"adGroupIdFilter": ag_id},
                )
                keywords = kw_data if isinstance(kw_data, list) else []

                for kw in keywords:
                    try:
                        kw_id = str(kw.get("keywordId", ""))
                        kw_text = kw.get("keywordText", "")
                        if not kw_id or not kw_text:
                            continue

                        # Insert into keywords table
                        self.nsdb.keywords.upsert({
                            "keyword": kw_text,
                            "source": f"ads-api:campaign:{cid}",
                            "search_volume": kw.get("impressions"),
                        })

                        # Insert performance record
                        record_id = f"kw-{kw_id}"
                        self.db.execute(
                            """INSERT OR REPLACE INTO keyword_performance
                               (id, keyword_id, campaign_id, impressions, clicks,
                                spend, orders, revenue, acos, recorded_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                record_id,
                                kw_id,
                                cid,
                                int(kw.get("impressions", 0)),
                                int(kw.get("clicks", 0)),
                                float(kw.get("spend", 0)),
                                int(kw.get("orders", 0)),
                                float(kw.get("sales", 0)),
                                float(kw.get("acos", 0)),
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                        self.db.commit()

                        result["imported"] += 1
                        result["details"].append(
                            {"keyword": kw_text, "campaign_id": cid}
                        )

                    except Exception as e:
                        result["errors"] += 1
                        logger.error(f"Error processing keyword {kw.get('keywordId')}: {e}")

        logger.info(
            f"Ads API keywords import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    # ---- Search Term Report ----

    def run_search_term_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request, download, and process a search term report.

        This submits a report request to the Ads API, polls for completion,
        downloads the results, and imports them into keyword_performance.

        Args:
            start_date: Report start date (YYYY-MM-DD). Defaults to 30 days ago.
            end_date: Report end date (YYYY-MM-DD). Defaults to today.

        Returns:
            {"imported": int, "errors": int, "details": [...]}
        """
        if not self._enabled:
            return {
                "imported": 0,
                "errors": 0,
                "details": [],
                "reason": "not_configured",
            }

        if not start_date:
            start_date = (
                datetime.now(timezone.utc) - timedelta(days=30)
            ).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        result = {"imported": 0, "errors": 0, "details": []}

        # Submit report request
        report_body = {
            "reportType": "searchTerm",
            "metrics": (
                "impressions,clicks,spend,orders,sales,"
                "acos,ctr,conversionRate"
            ),
            "groupBy": "searchTerm",
            "startDate": start_date,
            "endDate": end_date,
        }

        report_resp = self._api_post(ADS_ENDPOINTS["reports"], report_body)
        if not report_resp or "reportId" not in report_resp:
            logger.error("Failed to submit search term report request")
            result["errors"] = 1
            return result

        report_id = report_resp["reportId"]
        logger.info(f"Search term report submitted: {report_id}")

        # Poll for completion (max 10 minutes)
        status_url = ADS_ENDPOINTS["report_status"].format(reportId=report_id)
        for _ in range(60):
            time.sleep(10)
            status_data = self._api_get(status_url)
            if not status_data:
                continue

            status = status_data.get("status", "")
            if status == "COMPLETED":
                break
            elif status in ("FAILED", "CANCELLED"):
                logger.error(f"Report {report_id} failed with status: {status}")
                result["errors"] = 1
                return result
        else:
            logger.error(f"Report {report_id} timed out waiting for completion")
            result["errors"] = 1
            return result

        # Download and process the report
        download_url = status_data.get("url")
        if not download_url:
            logger.error("Report completed but no download URL found")
            result["errors"] = 1
            return result

        try:
            import httpx

            dl_resp = httpx.get(download_url, timeout=60)
            dl_resp.raise_for_status()

            # Report may be gzip-compressed or plain CSV
            content = dl_resp.text
            if not content:
                logger.warning("Report downloaded but content is empty")
                return result

            rows = self._parse_search_term_report(content)

            for row in rows:
                try:
                    asin = row.get("advertisedAsin", row.get("asin", ""))
                    query = row.get("searchTerm", row.get("query", ""))
                    if not query:
                        continue

                    record_id = f"st-{report_id}-{hash(query + asin)[:12]}"
                    self.db.execute(
                        """INSERT OR REPLACE INTO keyword_performance
                           (id, keyword_id, asin, impressions, clicks, spend,
                            orders, revenue, acos, tier, recorded_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            record_id,
                            None,
                            asin,
                            int(row.get("impressions", 0)),
                            int(row.get("clicks", 0)),
                            float(row.get("spend", 0)),
                            int(row.get("orders", 0)),
                            float(row.get("sales", 0)),
                            float(row.get("acos", 0)),
                            "search_term",
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    self.db.commit()
                    result["imported"] += 1
                    result["details"].append({"query": query, "asin": asin})

                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Error processing search term row: {e}")

        except Exception as e:
            logger.error(f"Failed to download/process report: {e}")
            result["errors"] += 1

        logger.info(
            f"Ads API search term report: {result['imported']} imported, "
            f"{result['errors']} errors"
        )
        return result

    def _parse_search_term_report(self, csv_content: str) -> List[Dict[str, Any]]:
        """Parse a search term report CSV into a list of dicts."""
        import io

        rows = []
        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            rows.append(
                {
                    "searchTerm": row.get("Search Term", row.get("searchTerm", "")),
                    "advertisedAsin": row.get(
                        "Advertised Product", row.get("advertisedAsin", "")
                    ),
                    "impressions": row.get("Impressions", row.get("impressions", 0)),
                    "clicks": row.get("Clicks", row.get("clicks", 0)),
                    "spend": row.get("Spend", row.get("spend", 0)),
                    "orders": row.get("7 Day Total Orders (#)",
                                       row.get("orders", 0)),
                    "sales": row.get("7 Day Total Sales",
                                     row.get("sales", 0)),
                    "acos": row.get("ACoS", row.get("acos", 0)),
                }
            )
        return rows

    # ---- Aggregate Import ----

    def import_all(
        self,
        campaign_days_back: int = 90,
        run_search_terms: bool = True,
        search_term_days_back: int = 30,
    ) -> Dict[str, Any]:
        """Run all Ads API importers.

        Args:
            campaign_days_back: Days of campaign history to pull.
            run_search_terms: Whether to run the search term report.
            search_term_days_back: Days of search term data.

        Returns:
            Combined results dict.
        """
        results = {}
        results["campaigns"] = self.import_campaigns()
        results["keywords"] = self.import_keywords()
        if run_search_terms:
            start = (
                datetime.now(timezone.utc) - timedelta(days=search_term_days_back)
            ).strftime("%Y-%m-%d")
            results["search_terms"] = self.run_search_term_report(start_date=start)

        total_imported = sum(r.get("imported", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        return {
            "results": results,
            "total_imported": total_imported,
            "total_errors": total_errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
