"""Amazon SP-API Data Importer

Pulls data from Amazon Seller Partner API:
- Orders & order items (for revenue tracking)
- Catalog items (for product data)
- Financial events (for fees and settlements)
- Inventory summaries (for stock levels)

Auth: Uses LWA (Login with Amazon) refresh token flow.
Rate limits: SP-API has strict throttling (1 req/sec typical).
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# SP-API endpoints
SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"
SP_API_ENDPOINTS = {
    "orders": "/orders/v0/orders",
    "order_items": "/orders/v0/orders/{orderId}/orderItems",
    "catalog": "/catalog/2022-04-01/items",
    "inventory": "/fba/inventory/v1/summaries",
    "financial_events": "/finances/v0/financialEvents",
    "fees_estimates": "/products/fees/v0/listings/{asin}/feesEstimate",
}


class SPAPIAuth:
    """LWA token management with automatic refresh."""

    def __init__(self):
        self._client_id = os.environ.get("SP_API_CLIENT_ID", "")
        self._client_secret = os.environ.get("SP_API_CLIENT_SECRET", "")
        self._refresh_token = os.environ.get("SP_API_REFRESH_TOKEN", "")
        self._access_token = None
        self._token_expiry = None

    @property
    def is_configured(self) -> bool:
        return all([self._client_id, self._client_secret, self._refresh_token])

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
        """Refresh the LWA access token."""
        try:
            import httpx
            resp = httpx.post(
                "https://api.amazon.com/auth/o2/token",
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
            logger.info("SP-API token refreshed successfully")
        except Exception as e:
            logger.error(f"SP-API token refresh failed: {e}")
            self._access_token = None
            self._token_expiry = None


class SPAPIImporter:
    """Import data from Amazon SP-API.

    Usage:
        importer = SPAPIImporter(db)
        result = importer.import_orders(days_back=30)
        result = importer.import_inventory()
    """

    def __init__(self, db=None):
        from data_layer import get_db, NorthstarDB

        if db is None:
            db = get_db()
        self.db = db
        self.nsdb = NorthstarDB()
        self.auth = SPAPIAuth()
        self._enabled = self.auth.is_configured
        if not self._enabled:
            logger.warning("SP-API not configured — import will return empty results")

    @property
    def is_configured(self) -> bool:
        return self._enabled

    def _get_headers(self) -> Dict[str, str]:
        token = self.auth.get_access_token()
        if not token:
            raise RuntimeError("SP-API not authenticated")
        return {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
        }

    def _api_get(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """Make a GET request to SP-API with retry on throttling."""
        import httpx

        url = f"{SP_API_BASE}{endpoint}"
        headers = self._get_headers()

        for attempt in range(3):
            try:
                resp = httpx.get(url, headers=headers, params=params or {}, timeout=30)
                if resp.status_code == 429:
                    import time
                    wait = int(resp.headers.get("x-amzn-RateLimit-Limit", 1))
                    logger.warning(f"SP-API throttled, waiting {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"SP-API GET {endpoint} attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    return None
        return None

    # ---- Orders ----

    def import_orders(
        self, days_back: int = 30, marketplace_id: str = "ATVPDKIKX0DER"
    ) -> Dict[str, Any]:
        """Import orders from SP-API.

        Args:
            days_back: How many days of orders to pull.
            marketplace_id: Amazon marketplace (default: US).

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

        created_after = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "MarketplaceIds": marketplace_id,
            "CreatedAfter": created_after,
            "MaxResultsPerPage": 50,
        }

        next_token = None
        while True:
            if next_token:
                params["NextToken"] = next_token

            data = self._api_get(SP_API_ENDPOINTS["orders"], params)
            if not data:
                break

            orders_payload = data.get("payload", {})
            orders = orders_payload.get("Orders", [])

            for order in orders:
                try:
                    order_id = order.get("AmazonOrderId", "")

                    # Get order items
                    items_data = self._api_get(
                        SP_API_ENDPOINTS["order_items"].format(orderId=order_id)
                    )
                    items = (
                        items_data.get("payload", {}).get("OrderItems", [])
                        if items_data
                        else []
                    )

                    for item in items:
                        asin = item.get("ASIN", "")
                        if not asin:
                            continue

                        transaction = {
                            "asin": asin,
                            "transaction_type": "sale",
                            "amount": float(
                                item.get("ItemPrice", {}).get("Amount", 0)
                            ),
                            "quantity": int(item.get("QuantityOrdered", 1)),
                            "source": f"sp-api:order:{order_id}",
                            "report_date": order.get("PurchaseDate", "")[:10],
                        }

                        # Check for duplicate
                        existing = self.db.execute(
                            "SELECT id FROM transactions WHERE source = ?",
                            (transaction["source"],),
                        ).fetchone()

                        if existing:
                            result["skipped"] += 1
                            continue

                        self.nsdb.transactions.insert(transaction)
                        result["imported"] += 1
                        result["details"].append(
                            {
                                "asin": asin,
                                "order_id": order_id,
                                "amount": transaction["amount"],
                            }
                        )

                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Error processing order item: {e}")

            next_token = orders_payload.get("NextToken")
            if not next_token:
                break

        logger.info(
            f"SP-API orders import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    # ---- Inventory ----

    def import_inventory(
        self, marketplace_id: str = "ATVPDKIKX0DER"
    ) -> Dict[str, Any]:
        """Import FBA inventory summaries."""
        if not self._enabled:
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "reason": "not_configured",
            }

        result = {"imported": 0, "errors": 0, "details": []}

        params = {
            "details": "true",
            "granularityType": "Marketplace",
            "granularityId": marketplace_id,
            "marketplaceIds": marketplace_id,
        }

        next_token = None
        while True:
            if next_token:
                params["nextToken"] = next_token

            data = self._api_get(SP_API_ENDPOINTS["inventory"], params)
            if not data:
                break

            summaries = data.get("payload", {}).get("inventorySummaries", [])

            for item in summaries:
                try:
                    asin = item.get("asin", "")
                    if not asin:
                        continue

                    inventory_details = item.get("inventoryDetails", {})
                    total_qty = inventory_details.get("fulfillableQuantity", 0)

                    # Store inventory as a snapshot record
                    if total_qty > 0:
                        self.nsdb.transactions.insert(
                            {
                                "asin": asin,
                                "transaction_type": "inventory_snapshot",
                                "amount": 0,
                                "quantity": total_qty,
                                "source": "sp-api:inventory",
                                "report_date": datetime.now(timezone.utc).strftime(
                                    "%Y-%m-%d"
                                ),
                            }
                        )

                    result["imported"] += 1
                    result["details"].append(
                        {
                            "asin": asin,
                            "fulfillable": total_qty,
                            "inbound": inventory_details.get("inboundQuantity", 0),
                        }
                    )

                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Error processing inventory item: {e}")

            next_token = data.get("pagination", {}).get("nextToken")
            if not next_token:
                break

        logger.info(f"SP-API inventory import: {result['imported']} items")
        return result

    # ---- Fees Estimate ----

    def estimate_fees(
        self,
        asin: str,
        price: float,
        marketplace_id: str = "ATVPDKIKX0DER",
    ) -> Optional[Dict]:
        """Get fee estimate for a product.

        Args:
            asin: The product ASIN.
            price: The selling price.
            marketplace_id: Amazon marketplace (default: US).

        Returns:
            Dict with fee breakdown or None if unavailable.
        """
        if not self._enabled:
            return None

        endpoint = SP_API_ENDPOINTS["fees_estimates"].format(asin=asin)
        params = {
            "MarketplaceId": marketplace_id,
            "Price": price,
            "ItemCondition": "NewItem",
        }

        data = self._api_get(endpoint, params)
        if not data:
            return None

        fee_estimate = data.get("payload", {}).get("feesEstimate", {})
        fees = {}
        total = 0
        for fee in fee_estimate.get("feeList", []):
            fee_name = fee.get("feeType", "unknown")
            fee_amount = fee.get("feeAmount", {}).get("amount", 0)
            fees[fee_name] = float(fee_amount)
            total += float(fee_amount)

        return {
            "asin": asin,
            "price": price,
            "fees": fees,
            "total_fees": total,
            "net_payout": price - total,
        }

    # ---- Summary ----

    def import_all(self, days_back: int = 30) -> Dict[str, Any]:
        """Run all importers and return combined results.

        Args:
            days_back: How many days of data to pull.

        Returns:
            Combined results from all import sub-routines.
        """
        results = {}
        results["orders"] = self.import_orders(days_back=days_back)
        results["inventory"] = self.import_inventory()

        total_imported = sum(r.get("imported", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        return {
            "results": results,
            "total_imported": total_imported,
            "total_errors": total_errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
