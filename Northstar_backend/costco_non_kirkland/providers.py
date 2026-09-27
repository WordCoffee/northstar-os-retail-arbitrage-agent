"""Provider adapters (generic contract) with SellerAmp SAS registered.

OFFLINE / DISABLED BY DEFAULT. Follows the repo's provider-adapter discipline:

* Adapters never make network calls on their own.
* `provider_not_configured` is returned unless a SANCTIONED access mechanism
  exists (official API, approved export file, sanctioned repo adapter, or an
  explicitly approved live-enrichment decision).
* Mock/fixture mode is available for tests and local dry-runs.
* Deep links are generated ONLY for user-initiated navigation and NEVER imply
  that data has been fetched.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import CaptureStatus

# ---------------------------------------------------------------------------
# Sanctioned-access registry (documented in docs/costco-non-kirkland-pipeline.md)
# ---------------------------------------------------------------------------

SANCTIONED_ACCESS_MECHANISMS = (
    "official_api",
    "approved_export",
    "sanctioned_repository_adapter",
    "explicitly_approved_live_enrichment",
    "user_initiated_deep_link",
)


class ProviderNotConfigured(Exception):
    """Raised when a provider has no sanctioned access mechanism."""


@dataclass
class ProviderStatus:
    configured: bool
    reason: str
    mode: str  # mock | sanctioned_export | sanctioned_api | deep_link_only
    deep_link: Optional[str] = None


# ---------------------------------------------------------------------------
# Common evidence envelope for a normalized provider field
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence(source_name: str, field_name: str, value: Any, *, evidence_class: str,
              freshness: str = "unknown", capture_status: str = "unavailable",
              limitations: Optional[str] = None, captured_at: Optional[str] = None) -> Dict[str, Any]:
    return {
        "source_name": source_name,
        "field_name": field_name,
        "value": value,
        "captured_at": captured_at or _now(),
        "evidence_class": evidence_class,
        "freshness_status": freshness,
        "field_capture_status": capture_status,
        "limitations": limitations,
    }


# ---------------------------------------------------------------------------
# Shared base (mirrors proof_batch_contracts.ProviderAdapter.freeze contract)
# ---------------------------------------------------------------------------

class ProviderAdapter:
    """Narrow adapter contract: `fetch(...)` never raises; every outcome is a dict."""

    provider_key: str = "base"
    source_name: str = "base"

    def is_configured(self) -> ProviderStatus:
        raise NotImplementedError

    def deep_link(self, asin: str) -> Optional[str]:
        raise NotImplementedError

    def fetch(self, asin: str, *, mock: bool = False) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# SellerAmp SAS
# ---------------------------------------------------------------------------

class SellerAmpProvider(ProviderAdapter):
    """SellerAmp SAS adapter.

    Source: https://sas.selleramp.com/ (authorized research source ONLY via a
    sanctioned mechanism). Disabled by default. Never scrapes the SAS dashboard
    and never automates its interactive session.
    """

    provider_key = "selleramp"
    source_name = "selleramp"
    DEFAULT_ENABLED = False
    ENABLE_ENV = "NORTHSTAR_SELLERAMP_ENABLED"
    BASE_URL = "https://sas.selleramp.com/"

    def __init__(self, *, enabled: Optional[bool] = None,
                 approved_export_path: Optional[str] = None,
                 mock_data: Optional[Dict[str, Any]] = None):
        self._enabled = self.DEFAULT_ENABLED if enabled is None else bool(enabled)
        self._approved_export_path = approved_export_path
        self._mock_data = mock_data or {}

    def is_configured(self) -> ProviderStatus:
        env_enabled = (os.getenv(self.ENABLE_ENV) or "").strip().lower() in ("1", "true", "yes", "on")
        if self._enabled and env_enabled:
            return ProviderStatus(True, "Sanctioned SAS access enabled via explicit opt-in.",
                                  "sanctioned_api", None)
        if self._approved_export_path and os.path.exists(self._approved_export_path):
            return ProviderStatus(True, "Approved SellerAmp export present.",
                                  "sanctioned_export", None)
        return ProviderStatus(False,
                              "provider_not_configured: no sanctioned SellerAmp access "
                              "(official API, approved export, or explicit live approval).",
                              "deep_link_only", None)

    def deep_link(self, asin: str) -> Optional[str]:
        """User-initiated SAS deep link. Does NOT imply fetched data."""
        return f"{self.BASE_URL}r/sas/lookup?search_term={asin}"

    def fetch(self, asin: str, *, mock: bool = False) -> Dict[str, Any]:
        status = self.is_configured()
        if mock:
            return self._mock_fetch(asin)
        if not status.configured:
            return {
                "provider": self.provider_key, "configured": False,
                "result_status": "provider_not_configured",
                "reason": status.reason, "data": {},
            }
        if status.mode == "sanctioned_export":
            return self._read_export(asin)
        return {
            "provider": self.provider_key, "configured": True,
            "result_status": "requires_explicit_approval",
            "reason": "Sanctioned API present but live enrichment requires explicit "
                      "operator approval (see pipeline.plan_enrichment).",
            "data": {},
        }

    def _mock_fetch(self, asin: str) -> Dict[str, Any]:
        now = _now()
        fields = [
            _evidence(self.source_name, "sale_price", 29.99, evidence_class="cached_provider_snapshot",
                      capture_status=CaptureStatus.CAPTURED.value, freshness="unknown",
                      limitations="Mock fixture; not a real SAS observation."),
            _evidence(self.source_name, "estimated_monthly_sales", 12000, evidence_class="provider_estimate",
                      capture_status=CaptureStatus.CAPTURED.value,
                      limitations="Mock fixture sales estimate; not verified."),
            _evidence(self.source_name, "fba_fee", 6.50, evidence_class="provider_estimate",
                      capture_status=CaptureStatus.CAPTURED.value, limitations="Mock fixture."),
        ]
        return {
            "provider": self.provider_key, "configured": True, "result_status": "fixture",
            "asin": asin, "captured_at": now, "fields": fields,
            "evidence_class": "fixture", "freshness_status": "unknown",
            "note": "MOCK DATA ONLY — never presented as live provider data.",
        }

    def _read_export(self, asin: str) -> Dict[str, Any]:
        # Sanctioned-export reading. Data comes from an operator-provided file,
        # never from a live fetch. Parse failure -> parse_error capture status.
        try:
            import csv
            rows = []
            with open(self._approved_export_path, "r", encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    if row.get("asin", "").strip().upper() == asin.upper():
                        rows.append(dict(row))
            if not rows:
                return {"provider": self.provider_key, "configured": True,
                        "result_status": "unavailable", "asin": asin,
                        "reason": "ASIN not found in approved export."}
            return {"provider": self.provider_key, "configured": True,
                    "result_status": "available", "asin": asin, "rows": rows,
                    "evidence_class": "approved_export", "captured_at": _now()}
        except Exception as e:  # pragma: no cover - defensive
            return {"provider": self.provider_key, "configured": True,
                    "result_status": "parse_error", "asin": asin, "reason": str(e)}


# ---------------------------------------------------------------------------
# Provider registry (generic) + retired-provider record
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY = {
    "selleramp": SellerAmpProvider,
}

# Retired providers are kept as an explicit, clearly-labeled historical record so
# they fail closed by name instead of being silently unknown. SellerSprite was
# retired 2026-09-27 when its trial expired; it is NOT a supported provider and
# has no adapter, importer, CLI command, schema, or sign-in service.
RETIRED_PROVIDERS = {
    "sellersprite": "Retired 2026-09-27 — trial expired. Not a supported provider.",
}


class ProviderRetired(Exception):
    """Raised when a retired provider is requested by name."""

    def __init__(self, name: str, reason: str):
        super().__init__(f"Provider {name!r} is retired: {reason}")
        self.name = name
        self.reason = reason


def provider_factory(name: str, **kwargs) -> ProviderAdapter:
    key = (name or "").lower()
    if key in RETIRED_PROVIDERS:
        raise ProviderRetired(key, RETIRED_PROVIDERS[key])
    cls = PROVIDER_REGISTRY.get(key)
    if cls is None:
        raise KeyError(f"No provider registered under {name!r}")
    return cls(**kwargs)