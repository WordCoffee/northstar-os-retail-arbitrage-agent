"""OpenWebNinja Costco catalog adapter — Costco product data provider.

Uses OpenWebNinja API for Costco product search, catalog refresh,
and store-specific pricing. Auth via OPENWEBNINJA_API_KEY.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


class OpenWebNinjaAdapter(BaseAdapter):
    """OpenWebNinja Costco catalog and search adapter."""

    @property
    def provider_name(self) -> str:
        return "openwebninja"

    def _get_config(self) -> Dict[str, Any]:
        api_key = os.environ.get("OPENWEBNINJA_API_KEY", "")
        return {
            "api_key": api_key,
            "base_url": "https://api.openwebninja.com/v1",
            "configured": bool(api_key),
        }

    def is_configured(self) -> bool:
        return self._get_config()["configured"]

    def _api_request(self, path: str, params: Dict[str, Any] = None) -> ProviderResponse:
        """Make an authenticated API request."""
        import requests as req

        cfg = self._get_config()
        if not cfg["configured"]:
            return ProviderResponse(
                success=False, status=ProviderStatus.BLOCKED,
                provider=self.provider_name, data={},
                error="OPENWEBNINJA_API_KEY not configured",
            )

        url = f"{cfg['base_url']}{path}"
        headers = {"Authorization": f"Bearer {cfg['api_key']}"}

        start = time.monotonic()
        try:
            resp = req.get(url, headers=headers, params=params or {}, timeout=30)
            latency = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                return ProviderResponse(
                    success=True, status=ProviderStatus.OK,
                    provider=self.provider_name, data=resp.json(),
                    http_status=200, latency_ms=latency,
                )
            else:
                return ProviderResponse(
                    success=False, status=ProviderStatus.ERROR,
                    provider=self.provider_name, data={},
                    error=f"HTTP {resp.status_code}", http_status=resp.status_code, latency_ms=latency,
                )
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return ProviderResponse(
                success=False, status=ProviderStatus.ERROR,
                provider=self.provider_name, data={}, error=str(e), latency_ms=latency,
            )

    def search_costco(self, query: str, store_id: Optional[str] = None) -> ProviderResponse:
        """Search Costco catalog."""
        params = {"q": query}
        if store_id:
            params["store_id"] = store_id
        return self._api_request("/costco/search", params)

    def get_product(self, item_number: str) -> ProviderResponse:
        """Get a specific Costco product by item number."""
        return self._api_request(f"/costco/product/{item_number}")

    def refresh_catalog(self, store_id: Optional[str] = None) -> ProviderResponse:
        """Trigger a catalog refresh."""
        params = {}
        if store_id:
            params["store_id"] = store_id
        return self._api_request("/costco/refresh", params)
