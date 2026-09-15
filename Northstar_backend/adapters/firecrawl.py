"""Firecrawl structured data extraction adapter.

Supports structured data extraction from Amazon pages as a fallback
scraping provider. Auth via FIRECRAWL_API_KEY.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


class FirecrawlAdapter(BaseAdapter):
    """Firecrawl structured data extraction adapter."""

    @property
    def provider_name(self) -> str:
        return "firecrawl"

    def _get_config(self) -> Dict[str, Any]:
        api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        return {
            "api_key": api_key,
            "base_url": "https://api.firecrawl.dev/v1",
            "configured": bool(api_key),
        }

    def is_configured(self) -> bool:
        return self._get_config()["configured"]

    def _api_request(self, method: str, path: str, json_data: Dict = None) -> ProviderResponse:
        import requests as req

        cfg = self._get_config()
        if not cfg["configured"]:
            return ProviderResponse(
                success=False, status=ProviderStatus.BLOCKED,
                provider=self.provider_name, data={},
                error="FIRECRAWL_API_KEY not configured",
            )

        url = f"{cfg['base_url']}{path}"
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}

        start = time.monotonic()
        try:
            if method.upper() == "POST":
                resp = req.post(url, headers=headers, json=json_data or {}, timeout=60)
            else:
                resp = req.get(url, headers=headers, timeout=30)
            latency = int((time.monotonic() - start) * 1000)

            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True, status=ProviderStatus.OK,
                    provider=self.provider_name, data=resp.json(),
                    http_status=resp.status_code, latency_ms=latency,
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

    def scrape_url(self, url: str, formats: List[str] = None) -> ProviderResponse:
        """Scrape a URL and return structured data."""
        return self._api_request("POST", "/scrape", {
            "url": url,
            "formats": formats or ["markdown", "json"],
        })

    def scrape_product(self, asin: str, marketplace: str = "amazon.com") -> ProviderResponse:
        """Scrape an Amazon product page."""
        url = f"https://www.{marketplace}/dp/{asin}"
        return self.scrape_url(url)
