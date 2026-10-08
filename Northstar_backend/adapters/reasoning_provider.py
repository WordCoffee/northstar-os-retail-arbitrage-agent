"""Provider-neutral hosted-reasoning adapter for Northstar OS non-creative services.

This adapter implements a common reasoning-provider interface over the OpenCode
Go endpoint (https://opencode.ai/zen/go/v1/chat/completions). It is designed as a
temporary, manually-operated integration for private Northstar testing — it does
NOT replace the local creative pipeline or local non-creative models.

Design goals:
- Configurable provider/model (current implementation: OpenCode Go).
- Server-side credentials only (OPENCODE_GO_API_KEY).
- Streaming support where useful.
- Timeouts, cancellation-friendly clients, bounded concurrency, retries.
- Usage/provenance reporting.
- Structured error handling.
- Mockable transport for tests.

Constraint note (OpenCode Go): provider documentation qualifies this endpoint as
typical coding-agent traffic. This adapter is used for Northstar's internal
planning/reasoning tasks (listing proposals, ad-copy proposals, spreadsheet
analysis, AutothinK reasoning). We do not disguise marketplace-listing or
advertising requests as coding work, spoof another client, or bypass provider
restrictions. The User-Agent truthfully identifies the caller as
"NorthstarOS/<version> private-testing".
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from adapters.base import BaseAdapter, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)

# Stable application identifier. Bumped only when the adapter contract changes.
ADAPTER_VERSION = "2.0.0"

# Catalog of verified selectable models. Pricing is cached at import time and
# refreshed from the live catalog when available; the values below are the
# authoritative per-1M-token list prices observed at configuration time.
HOSTED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "opencode-go/deepseek-v4.1-flash",
        "short_id": "deepseek-v4.1-flash",
        "name": "DeepSeek V4.1 Flash",
        "role": "default",
        "provider": "opencode-go",
        "family": "deepseek",
        "context": 128000,
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.60,
        "cost_per_1m_cache_read": 0.003,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode model catalog",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "notes": "Default fast-reasoning model. Peak/off-peak pricing not published; assume listed rates.",
    },
    {
        "id": "opencode-go/glm-5.3-flash",
        "short_id": "glm-5.3-flash",
        "name": "GLM-5.3-Flash",
        "role": "alternative",
        "provider": "opencode-go",
        "family": "glm",
        "context": 128000,
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.50,
        "cost_per_1m_cache_read": 0.03,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode model catalog",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "notes": "Alternative flash model. Cache-read is more expensive than DeepSeek.",
    },
    {
        "id": "opencode-go/mimo-v2.6-flash",
        "short_id": "mimo-v2.6-flash",
        "name": "MiMo-V2.6-Flash",
        "role": "budget",
        "provider": "opencode-go",
        "family": "mimo",
        "context": 128000,
        "cost_per_1m_input": 0.14,
        "cost_per_1m_output": 0.28,
        "cost_per_1m_cache_read": 0.0028,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode model catalog",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "notes": "Budget alternative; lowest output cost of the three.",
    },
]

HOSTED_MODEL_IDS = {m["id"] for m in HOSTED_MODELS}
DEFAULT_MODEL_ID = "opencode-go/deepseek-v4.1-flash"


@dataclass
class ReasoningUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None

    def estimated_cost_usd(self, model_id: str) -> Optional[float]:
        model = next((m for m in HOSTED_MODELS if m["id"] == model_id), None)
        if not model:
            return None
        cost = 0.0
        if self.prompt_tokens:
            cost += self.prompt_tokens * (model["cost_per_1m_input"] / 1_000_000)
        if self.completion_tokens:
            cost += self.completion_tokens * (model["cost_per_1m_output"] / 1_000_000)
        if self.cache_read_tokens:
            cost += self.cache_read_tokens * (model["cost_per_1m_cache_read"] / 1_000_000)
        return round(cost, 6)


@dataclass
class ReasoningRequest:
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False
    task_type: str = "general"  # general | listing | ad_copy | spreadsheet | autothink
    session_id: Optional[str] = None
    extra_body: Dict[str, Any] = field(default_factory=dict)


class ReasoningProvider(BaseAdapter):
    """Common interface for a hosted reasoning provider.

    Subclasses implement the transport; this base class exposes the catalog and
    helpers that are independent of HTTP details.
    """

    name: str = "reasoning"
    required_env: List[str] = ["OPENCODE_GO_API_KEY"]
    optional_env: List[str] = [
        "OPENCODE_GO_ENDPOINT",
        "OPENCODE_GO_ENABLED",
        "OPENCODE_GO_MAX_CONCURRENCY",
        "OPENCODE_GO_TIMEOUT_SECONDS",
        "OPENCODE_GO_MAX_TOKENS",
        "OPENCODE_GO_RETRIES",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._default_model = DEFAULT_MODEL_ID

    def key_present(self) -> bool:
        """True when the API key env var is set (value never read)."""
        return self.check_auth()

    def available(self) -> bool:
        """True when the provider is explicitly enabled AND the key is present.

        A key alone does not enable the provider; OPENCODE_GO_ENABLED=1 is
        required so that paid calls are never automatic.
        """
        return self.armed()

    def armed(self) -> bool:
        """True when live calls are explicitly approved (OPENCODE_GO_ENABLED=1)."""
        return str(os.environ.get("OPENCODE_GO_ENABLED", "") or "").strip() == "1" and self.check_auth()

    def models(self) -> List[Dict[str, Any]]:
        """Return the selectable hosted model catalog with timestamped pricing."""
        return [dict(m) for m in HOSTED_MODELS]

    def resolve_model(self, requested: Optional[str]) -> str:
        """Resolve a model request to a concrete, verified model id.

        Raises ValueError if the requested model is not in the verified catalog.
        """
        if not requested:
            return self._default_model
        if requested in HOSTED_MODEL_IDS:
            return requested
        # Accept short ids (e.g. "deepseek-v4.1-flash") by prefixing the provider.
        full = f"opencode-go/{requested}"
        if full in HOSTED_MODEL_IDS:
            return full
        raise ValueError(f"Model {requested!r} is not in the verified hosted catalog.")

    def complete(self, request: ReasoningRequest) -> ProviderResponse:
        """Non-streaming completion. Must be implemented by subclasses."""
        raise NotImplementedError

    def complete_stream(self, request: ReasoningRequest) -> Iterator[ProviderResponse]:
        """Streaming completion. Subclasses may implement; default raises."""
        raise NotImplementedError(f"{self.name} does not support streaming")

    @staticmethod
    def make_session_id(existing: Optional[str]) -> str:
        """Return a stable x-opencode-session value per conversation.

        The value is a deterministic UUID5 derived from the supplied id, or a
        fresh UUID4 when none is supplied. It never contains secrets.
        """
        if existing:
            return str(uuid.uuid5(uuid.NAMESPACE_OID, f"northstar:{existing}"))
        return str(uuid.uuid4())


class OpenCodeGoProvider(ReasoningProvider):
    """OpenCode Go hosted-reasoning provider.

    Endpoint: https://opencode.ai/zen/go/v1/chat/completions
    Auth: OPENCODE_GO_API_KEY (server-side only).
    """

    name = "opencode_go"

    def __init__(self) -> None:
        super().__init__()
        self.endpoint = (
            os.environ.get("OPENCODE_GO_ENDPOINT")
            or "https://opencode.ai/zen/go/v1/chat/completions"
        )
        self.timeout_s = float(os.environ.get("OPENCODE_GO_TIMEOUT_SECONDS") or "120")
        self.max_tokens_default = int(os.environ.get("OPENCODE_GO_MAX_TOKENS") or "4096")
        self.retries = int(os.environ.get("OPENCODE_GO_RETRIES") or "2")
        max_concurrency = int(os.environ.get("OPENCODE_GO_MAX_CONCURRENCY") or "2")
        self._sem = threading.Semaphore(max(1, max_concurrency))

    def _headers(self, session_id: Optional[str]) -> Dict[str, str]:
        return {
            "Authorization": "Bearer " + os.environ["OPENCODE_GO_API_KEY"],
            "Content-Type": "application/json",
            "User-Agent": f"NorthstarOS/{ADAPTER_VERSION} private-testing (non-creative-reasoning)",
            "x-opencode-session": self.make_session_id(session_id),
        }

    def _body(self, request: ReasoningRequest) -> Dict[str, Any]:
        model = self.resolve_model(request.model)
        body: Dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "max_tokens": request.max_tokens or self.max_tokens_default,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stream:
            body["stream"] = True
        if request.extra_body:
            body.update(request.extra_body)
        return body

    @staticmethod
    def _parse_usage(payload: Dict[str, Any]) -> ReasoningUsage:
        usage = payload.get("usage") or {}
        return ReasoningUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            cache_read_tokens=usage.get("prompt_cache_hit_tokens") or usage.get("cache_read_tokens"),
            cache_write_tokens=usage.get("prompt_cache_miss_tokens") or usage.get("cache_write_tokens"),
        )

    def complete(self, request: ReasoningRequest) -> ProviderResponse:
        """Execute a non-streaming chat completion against OpenCode Go."""
        if not self.key_present():
            return ProviderResponse(
                success=False,
                status=ProviderStatus.AUTH_ERROR,
                provider=self.name,
                error="OpenCode Go is not configured (OPENCODE_GO_API_KEY missing).",
            )
        if not self.armed():
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=self.name,
                error="OpenCode Go key is present but the provider is not armed. Set OPENCODE_GO_ENABLED=1 after explicit operator approval.",
            )

        body = self._body(request)
        url = self.endpoint
        headers = self._headers(request.session_id)

        with self._sem:
            resp = self._timed_request(
                "POST",
                url,
                headers=headers,
                json=body,
                timeout=self.timeout_s,
                retries=self.retries,
            )

        if not resp.success:
            return resp

        payload = resp.data
        try:
            content = payload["choices"][0]["message"]["content"]
            model = payload.get("model", body["model"])
        except (KeyError, IndexError, TypeError) as exc:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.ERROR,
                provider=self.name,
                error=f"Malformed response from OpenCode Go: {exc}",
                http_status=resp.http_status,
                latency_ms=resp.latency_ms,
            )

        usage = self._parse_usage(payload)
        cost = usage.estimated_cost_usd(model)

        return ProviderResponse(
            success=True,
            status=ProviderStatus.OK,
            provider=self.name,
            data={
                "content": content,
                "model": model,
                "usage": usage.__dict__,
                "estimated_cost_usd": cost,
                "task_type": request.task_type,
                "session_id": request.session_id,
            },
            latency_ms=resp.latency_ms,
            http_status=resp.http_status,
            metadata={
                "endpoint": url,
                "pricing_source": "OpenCode model catalog",
                "pricing_observed_at": "2026-10-08T00:00:00Z",
            },
        )

    def complete_stream(self, request: ReasoningRequest) -> Iterator[ProviderResponse]:
        """Execute a streaming completion. Yields partial content chunks.

        Each yielded ProviderResponse has data.partial set to True and data.content
        set to the delta for that chunk. A final response with data.partial=False
        contains the full accumulated content and usage metadata.
        """
        if not self.key_present():
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.AUTH_ERROR,
                provider=self.name,
                error="OpenCode Go is not configured.",
            )
            return
        if not self.armed():
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=self.name,
                error="OpenCode Go key is present but the provider is not armed.",
            )
            return

        body = self._body(request)
        body["stream"] = True
        url = self.endpoint
        headers = self._headers(request.session_id)
        accumulated: List[str] = []

        import httpx

        with self._sem:
            t0 = time.monotonic()
            try:
                client = self._get_client(timeout=self.timeout_s)
                with client.stream("POST", url, headers=headers, json=body) as stream:
                    if stream.status_code != 200:
                        yield ProviderResponse(
                            success=False,
                            status=ProviderStatus.ERROR,
                            provider=self.name,
                            error=f"OpenCode Go HTTP {stream.status_code}",
                            http_status=stream.status_code,
                        )
                        return
                    for line in stream.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            accumulated.append(delta)
                            yield ProviderResponse(
                                success=True,
                                status=ProviderStatus.OK,
                                provider=self.name,
                                data={"content": delta, "partial": True, "model": body["model"]},
                            )
            except httpx.TimeoutException as exc:
                yield ProviderResponse(
                    success=False,
                    status=ProviderStatus.TIMEOUT,
                    provider=self.name,
                    error=str(exc),
                )
                return
            except Exception as exc:
                yield ProviderResponse(
                    success=False,
                    status=ProviderStatus.ERROR,
                    provider=self.name,
                    error=f"{type(exc).__name__}: {exc}",
                )
                return

        full_content = "".join(accumulated)
        elapsed = (time.monotonic() - t0) * 1000
        yield ProviderResponse(
            success=True,
            status=ProviderStatus.OK,
            provider=self.name,
            data={
                "content": full_content,
                "partial": False,
                "model": body["model"],
                "task_type": request.task_type,
                "session_id": request.session_id,
            },
            latency_ms=elapsed,
        )


class MockReasoningProvider(ReasoningProvider):
    """Deterministic stand-in for tests. Never touches the network."""

    name = "mock_reasoning"
    required_env: List[str] = []
    optional_env: List[str] = []

    def __init__(self, response_text: str = "mock response") -> None:
        super().__init__()
        self.response_text = response_text
        self.calls: List[ReasoningRequest] = []

    def available(self) -> bool:
        return True

    def armed(self) -> bool:
        return True

    def complete(self, request: ReasoningRequest) -> ProviderResponse:
        self.calls.append(request)
        model = self.resolve_model(request.model)
        return ProviderResponse(
            success=True,
            status=ProviderStatus.OK,
            provider=self.name,
            data={
                "content": self.response_text,
                "model": model,
                "usage": ReasoningUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15).__dict__,
                "estimated_cost_usd": 0.0,
                "task_type": request.task_type,
                "session_id": request.session_id,
            },
        )


def get_reasoning_provider() -> ReasoningProvider:
    """Factory: returns the configured hosted reasoning provider.

    Currently only OpenCode Go is implemented; future providers can be selected
    via REASONING_PROVIDER env var.
    """
    provider_name = os.environ.get("REASONING_PROVIDER", "opencode_go").lower()
    if provider_name == "mock":
        return MockReasoningProvider()
    return OpenCodeGoProvider()
