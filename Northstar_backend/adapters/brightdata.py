"""Bright Data Web Unlocker adapter — primary scraping provider.

Uses Bright Data Web Unlocker for Amazon product pages, Costco pages,
and other protected sites. Auth via BRIGHTDATA_UNLOCKER_API_KEY.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


class BrightDataAdapter(BaseAdapter):
    """Bright Data Web Unlocker scraping adapter."""

    @property
    def provider_name(self) -> str:
        return "bright_data"

    def _get_config(self) -> Dict[str, Any]:
        api_key = os.environ.get("BRIGHTDATA_UNLOCKER_API_KEY", "")
        return {
            "api_key": api_key,
            "host": "brd.superproxy.io",
            "port": 33335,
            "configured": bool(api_key),
        }

    def is_configured(self) -> bool:
        return self._get_config()["configured"]

    def _make_request(self, url: str, method: str = "GET", **kwargs) -> ProviderResponse:
        """Make a request through Bright Data Web Unlocker proxy."""
        import requests as req

        cfg = self._get_config()
        if not cfg["configured"]:
            return ProviderResponse(
                success=False, status=ProviderStatus.BLOCKED,
                provider=self.provider_name, data={},
                error="BRIGHTDATA_UNLOCKER_API_KEY not configured",
            )

        proxy_url = f"http://{cfg['api_key']}@{cfg['host']}:{cfg['port']}"
        proxies = {"http": proxy_url, "https": proxy_url}

        start = time.monotonic()
        try:
            if method.upper() == "POST":
                resp = req.post(url, proxies=proxies, timeout=60, **kwargs)
            else:
                resp = req.get(url, proxies=proxies, timeout=60, **kwargs)
            latency = int((time.monotonic() - start) * 1000)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except (json.JSONDecodeError, ValueError):
                    data = {"html": resp.text[:50000]}
                return ProviderResponse(
                    success=True, status=ProviderStatus.OK,
                    provider=self.provider_name, data=data,
                    http_status=resp.status_code, latency_ms=latency,
                )
            else:
                return ProviderResponse(
                    success=False, status=ProviderStatus.ERROR,
                    provider=self.provider_name, data={},
                    error=f"HTTP {resp.status_code}",
                    http_status=resp.status_code, latency_ms=latency,
                )
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return ProviderResponse(
                success=False, status=ProviderStatus.ERROR,
                provider=self.provider_name, data={},
                error=str(e), latency_ms=latency,
            )

    def scrape_product(self, asin: str, marketplace: str = "amazon.com") -> ProviderResponse:
        """Scrape an Amazon product page."""
        url = f"https://www.{marketplace}/dp/{asin}"
        resp = self._make_request(url)
        if not resp.success:
            return resp

        html = resp.data.get("html", "")
        extracted = self._extract_json_ld(html)
        if extracted:
            resp.data = extracted
        return resp

    def scrape_costco(self, item_number: str) -> ProviderResponse:
        """Scrape a Costco product page."""
        url = f"https://www.costco.com/CatalogSearch?dept=All&keyword={item_number}"
        return self._make_request(url)

    def _extract_json_ld(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract JSON-LD product data from HTML."""
        import re
        match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        return None
