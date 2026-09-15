"""Base adapter contract and registry for the Northstar OS provider layer.

Every provider adapter extends BaseAdapter and returns ProviderResponse
objects.  AdapterRegistry is a simple name→class map that supports
auto-discovery via a registry module.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ProviderResponse — the universal return type
# ---------------------------------------------------------------------------

class ProviderStatus(str, Enum):
    """Terminal status of a provider call."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    CREDITS_EXHAUSTED = "credits_exhausted"
    BLOCKED = "blocked"
    PARTIAL = "partial"


@dataclass
class ProviderResponse:
    """Standardized response returned by every adapter method.

    Attributes:
        success:  True when the call completed without transport/config errors.
        status:   Terminal status enum value.
        provider: Adapter name that produced this response.
        data:     Payload dict (structure varies per method).
        error:    Human-readable error string, or None.
        http_status:  HTTP status code from the upstream, or None.
        request_id:  Upstream request / trace id, or None.
        latency_ms:  Wall-clock round-trip in milliseconds, or None.
        metadata:  Extra provider-specific diagnostic fields.
    """
    success: bool
    status: ProviderStatus
    provider: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    http_status: Optional[int] = None
    request_id: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# BaseAdapter
# ---------------------------------------------------------------------------

class BaseAdapter:
    """Abstract base for every provider adapter.

    Subclasses must set ``name`` as a class attribute and implement the
    methods relevant to their provider.  Common infrastructure (auth check,
    timed request helper, retry wrapper) lives here so every adapter stays
    DRY.
    """

    name: str = "base"

    # Subclasses override these to declare env-var keys they need.
    required_env: List[str] = []
    optional_env: List[str] = []

    def __init__(self) -> None:
        self._log = logging.getLogger(f"adapter.{self.name}")
        self._http = None  # lazily created httpx client

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def check_auth(self) -> bool:
        """Return True when every required env var is set and non-empty."""
        missing = [k for k in self.required_env if not os.getenv(k)]
        if missing:
            self._log.warning("Missing required env vars: %s", ", ".join(missing))
            return False
        return True

    def _get_api_key(self, env_var: str) -> Optional[str]:
        """Read an API key from the environment (value is never logged)."""
        return os.getenv(env_var) or None

    # ------------------------------------------------------------------
    # HTTP helpers (httpx)
    # ------------------------------------------------------------------

    def _get_client(self, **kwargs):
        """Lazily create an httpx.Client with sane defaults."""
        if self._http is None or self._http.is_closed:
            import httpx
            self._http = httpx.Client(
                timeout=kwargs.pop("timeout", 60.0),
                follow_redirects=True,
                **kwargs,
            )
        return self._http

    def _timed_request(
        self,
        method: str,
        url: str,
        *,
        retries: int = 3,
        backoff: float = 1.5,
        timeout: float = 60.0,
        **kwargs,
    ) -> ProviderResponse:
        """Execute an HTTP request with retry/backoff and return ProviderResponse.

        This is the recommended low-level primitive for adapter methods.
        It handles timing, retries, exception classification, and response
        construction so subclasses only need to call it and interpret the
        result.
        """
        import httpx

        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            t0 = time.monotonic()
            try:
                client = self._get_client(timeout=timeout)
                resp = client.request(method, url, **kwargs)
                elapsed = (time.monotonic() - t0) * 1000
                self._log.info(
                    "%s %s → %s (%.0f ms, attempt %d/%d)",
                    method.upper(), url, resp.status_code, elapsed, attempt, retries,
                )

                if resp.status_code == 401 or resp.status_code == 403:
                    return ProviderResponse(
                        success=False,
                        status=ProviderStatus.AUTH_ERROR,
                        provider=self.name,
                        error=f"HTTP {resp.status_code}",
                        http_status=resp.status_code,
                        latency_ms=elapsed,
                    )
                if resp.status_code == 429:
                    if attempt < retries:
                        wait = backoff ** attempt
                        self._log.warning("Rate limited, sleeping %.1fs", wait)
                        time.sleep(wait)
                        continue
                    return ProviderResponse(
                        success=False,
                        status=ProviderStatus.RATE_LIMITED,
                        provider=self.name,
                        error="Rate limited after retries",
                        http_status=resp.status_code,
                        latency_ms=elapsed,
                    )
                if resp.status_code == 402:
                    return ProviderResponse(
                        success=False,
                        status=ProviderStatus.CREDITS_EXHAUSTED,
                        provider=self.name,
                        error="Credits exhausted",
                        http_status=resp.status_code,
                        latency_ms=elapsed,
                    )
                if resp.status_code == 404:
                    return ProviderResponse(
                        success=False,
                        status=ProviderStatus.NOT_FOUND,
                        provider=self.name,
                        error="Not found",
                        http_status=resp.status_code,
                        latency_ms=elapsed,
                    )

                return ProviderResponse(
                    success=resp.is_success,
                    status=ProviderStatus.OK if resp.is_success else ProviderStatus.ERROR,
                    provider=self.name,
                    data=resp.json() if "json" in (resp.headers.get("content-type") or "") else {"raw": resp.text},
                    error=None if resp.is_success else f"HTTP {resp.status_code}",
                    http_status=resp.status_code,
                    latency_ms=elapsed,
                )

            except httpx.TimeoutException as exc:
                elapsed = (time.monotonic() - t0) * 1000
                last_exc = exc
                self._log.warning("Timeout on attempt %d/%d: %s", attempt, retries, exc)
                if attempt < retries:
                    time.sleep(backoff ** attempt)
                    continue
                return ProviderResponse(
                    success=False,
                    status=ProviderStatus.TIMEOUT,
                    provider=self.name,
                    error=str(exc),
                    latency_ms=elapsed,
                )
            except httpx.HTTPError as exc:
                elapsed = (time.monotonic() - t0) * 1000
                last_exc = exc
                self._log.warning("HTTP error on attempt %d/%d: %s", attempt, retries, exc)
                if attempt < retries:
                    time.sleep(backoff ** attempt)
                    continue
                return ProviderResponse(
                    success=False,
                    status=ProviderStatus.ERROR,
                    provider=self.name,
                    error=str(exc),
                    latency_ms=elapsed,
                )
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000
                last_exc = exc
                self._log.error("Unexpected error on attempt %d/%d: %s", attempt, retries, exc)
                if attempt < retries:
                    time.sleep(backoff ** attempt)
                    continue
                return ProviderResponse(
                    success=False,
                    status=ProviderStatus.ERROR,
                    provider=self.name,
                    error=f"{type(exc).__name__}: {exc}",
                    latency_ms=elapsed,
                )

        # Should not reach here, but safety net.
        return ProviderResponse(
            success=False,
            status=ProviderStatus.ERROR,
            provider=self.name,
            error=str(last_exc) or "Exhausted retries",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release HTTP client resources."""
        if self._http and not self._http.is_closed:
            self._http.close()
            self._http = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------------------
# AdapterRegistry
# ---------------------------------------------------------------------------

class AdapterRegistry:
    """Name→class map for adapter auto-discovery.

    Usage::

        registry = AdapterRegistry()
        registry.register("bright_data", BrightDataAdapter)
        adapter = registry.create("bright_data")
    """

    def __init__(self) -> None:
        self._classes: Dict[str, type] = {}

    def register(self, name: str, cls: type) -> None:
        """Register an adapter class under *name*."""
        if not (isinstance(cls, type) and issubclass(cls, BaseAdapter)):
            raise TypeError(f"{cls!r} is not a BaseAdapter subclass")
        self._classes[name] = cls
        logger.debug("Registered adapter %r → %s", name, cls.__name__)

    def create(self, name: str) -> BaseAdapter:
        """Instantiate a registered adapter by name."""
        cls = self._classes.get(name)
        if cls is None:
            raise KeyError(f"No adapter registered under {name!r}")
        return cls()

    def list_adapters(self) -> List[str]:
        """Return sorted list of registered adapter names."""
        return sorted(self._classes.keys())

    def has(self, name: str) -> bool:
        return name in self._classes


# Module-level singleton — adapters register here via registry.py.
registry = AdapterRegistry()
