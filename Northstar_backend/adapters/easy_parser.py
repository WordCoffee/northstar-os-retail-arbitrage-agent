"""EasyParser seller roster adapter — enriches seller/buy box data.

Uses EasyParser API for Amazon seller rosters, buy box tracking,
and fulfillment detection. Auth via EASYPARSER_API_KEY.
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


class EasyParserAdapter(BaseAdapter):
    """EasyParser seller roster and buy box enrichment adapter."""

    @property
    def provider_name(self) -> str:
        return "easy_parser"

    def _get_config(self) -> Dict[str, Any]:
        api_key = os.environ.get("EASYPARSER_API_KEY", "")
        return {
            "api_key": api_key,
            "base_url": "https://api.easyparser.com",
            "configured": bool(api_key),
        }

    def is_configured(self) -> bool:
        return self._get_config()["configured"]

    def _api_request(self, path: str, params: Dict[str, Any] = None) -> ProviderResponse:
        """Make an authenticated API request to EasyParser."""
        import requests as req

        cfg = self._get_config()
        if not cfg["configured"]:
            return ProviderResponse(
                success=False, status=ProviderStatus.BLOCKED,
                provider=self.provider_name, data={},
                error="EASYPARSER_API_KEY not configured",
            )

        url = f"{cfg['base_url']}{path}"
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}

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
            elif resp.status_code == 402:
                return ProviderResponse(
                    success=False, status=ProviderStatus.CREDITS_EXHAUSTED,
                    provider=self.provider_name, data={},
                    error="Credits exhausted", http_status=402, latency_ms=latency,
                )
            elif resp.status_code == 429:
                return ProviderResponse(
                    success=False, status=ProviderStatus.RATE_LIMITED,
                    provider=self.provider_name, data={},
                    error="Rate limited", http_status=429, latency_ms=latency,
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

    def get_seller_roster(self, asin: str) -> ProviderResponse:
        """Get seller roster for an ASIN."""
        return self._api_request("/v1/amazon/sellers", {"asin": asin})

    def get_buy_box(self, asin: str) -> ProviderResponse:
        """Get buy box information for an ASIN."""
        return self._api_request("/v1/amazon/buybox", {"asin": asin})

    def get_balance(self) -> ProviderResponse:
        """Get current credit balance."""
        return self._api_request("/v1/account/balance")
