"""Scrape.do fallback scraping adapter.

Used when Bright Data fails or is unavailable. Supports Amazon
product page scraping with basic HTML extraction.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


class ScrapeDoAdapter(BaseAdapter):
    """Scrape.do fallback scraping adapter."""

    @property
    def provider_name(self) -> str:
        return "scrape_do"

    def _get_config(self) -> Dict[str, Any]:
        api_key = os.environ.get("SCRAPE_DO_API_KEY", "")
        return {
            "api_key": api_key,
            "base_url": "https://api.scrape.do",
            "configured": bool(api_key),
        }

    def is_configured(self) -> bool:
        return self._get_config()["configured"]

    def _make_request(self, url: str, **kwargs) -> ProviderResponse:
        import requests as req

        cfg = self._get_config()
        if not cfg["configured"]:
            return ProviderResponse(
                success=False, status=ProviderStatus.BLOCKED,
                provider=self.provider_name, data={},
                error="SCRAPE_DO_API_KEY not configured",
            )

        params = {"url": url, "token": cfg["api_key"], **kwargs}

        start = time.monotonic()
        try:
            resp = req.get(cfg["base_url"], params=params, timeout=60)
            latency = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except (json.JSONDecodeError, ValueError):
                    data = {"html": resp.text[:50000]}
                return ProviderResponse(
                    success=True, status=ProviderStatus.OK,
                    provider=self.provider_name, data=data,
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

    def scrape_product(self, asin: str, marketplace: str = "amazon.com") -> ProviderResponse:
        url = f"https://www.{marketplace}/dp/{asin}"
        return self._make_request(url)
