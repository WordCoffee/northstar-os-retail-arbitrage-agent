"""Amazon APIs adapter — unified interface to SP-API and Ads API.

Wraps the importers layer behind the adapter contract so callers
can access Amazon data through the same interface as other providers.
"""

import os
import logging
from typing import Any, Dict, List, Optional

from .base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


class AmazonAPIAdapter(BaseAdapter):
    """Amazon SP-API and Ads API unified adapter."""

    @property
    def provider_name(self) -> str:
        return "amazon_api"

    def is_configured(self) -> bool:
        return bool(os.environ.get("SP_API_REFRESH_TOKEN"))

    def _run_importer(self, importer_class, method: str, **kwargs) -> ProviderResponse:
        """Run an importer method and wrap the result."""
        import time
        start = time.monotonic()
        try:
            importer = importer_class()
            if not importer.is_configured:
                return ProviderResponse(
                    success=False, status=ProviderStatus.BLOCKED,
                    provider=self.provider_name, data={},
                    error=f"{importer_class.__name__} not configured",
                )
            result = getattr(importer, method)(**kwargs)
            latency = int((time.monotonic() - start) * 1000)
            return ProviderResponse(
                success=True, status=ProviderStatus.OK,
                provider=self.provider_name, data=result,
                latency_ms=latency,
            )
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return ProviderResponse(
                success=False, status=ProviderStatus.ERROR,
                provider=self.provider_name, data={},
                error=str(e), latency_ms=latency,
            )

    def get_orders(self, days_back: int = 30) -> ProviderResponse:
        from importers.sp_api_importer import SPAPIImporter
        return self._run_importer(SPAPIImporter, "import_orders", days_back=days_back)

    def get_inventory(self) -> ProviderResponse:
        from importers.sp_api_importer import SPAPIImporter
        return self._run_importer(SPAPIImporter, "import_inventory")

    def estimate_fees(self, asin: str, price: float) -> ProviderResponse:
        from importers.sp_api_importer import SPAPIImporter
        try:
            importer = SPAPIImporter()
            result = importer.estimate_fees(asin, price)
            return ProviderResponse(
                success=True, status=ProviderStatus.OK,
                provider=self.provider_name, data=result or {},
            )
        except Exception as e:
            return ProviderResponse(
                success=False, status=ProviderStatus.ERROR,
                provider=self.provider_name, data={}, error=str(e),
            )

    def get_campaigns(self) -> ProviderResponse:
        from importers.ads_api_importer import AdsAPIImporter
        return self._run_importer(AdsAPIImporter, "import_campaigns")

    def get_search_terms(self, days_back: int = 30) -> ProviderResponse:
        from importers.ads_api_importer import AdsAPIImporter
        return self._run_importer(AdsAPIImporter, "import_search_terms", days_back=days_back)
