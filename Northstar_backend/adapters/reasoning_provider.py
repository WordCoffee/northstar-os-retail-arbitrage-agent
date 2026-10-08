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

# Catalog of verified selectable models, configured against the documented
# OpenCode Zen endpoints (https://opencode.ai/docs/zen/). Pricing values are the
# Zen published per-1M-token rates observed at configuration time.
#
# TEMPORARY ROUTING POLICY (see docs/HOSTED_REASONING.md):
# Step 5 Preview Free is the DEFAULT for all non-creative operational work
# while it remains free AND usable. PROVIDER CONSTRAINT: Zen free-tier
# models return 403 FreeTierError ("can only be used from within OpenCode") for
# external callers, so the policy default is currently provider-blocked and the
# integration reports that honestly instead of silently substituting.
# DeepSeek V4.1 Flash is the intentional lower-cost fallback (requires balance).
# Escalation models are listed separately and are NEVER auto-selected.
HOSTED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "step-5-preview-free",
        "short_id": "step-5-preview-free",
        "name": "Step 5 Preview Free",
        "role": "default",
        "provider": "opencode-go",
        "family": "step",
        "context": 128000,
        "cost_per_1m_input": 0.0,
        "cost_per_1m_output": 0.0,
        "cost_per_1m_cache_read": 0.0,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode Zen docs (https://opencode.ai/docs/zen/)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "provider_blocked": True,
        "availability_note": "Zen free tier returns 403 FreeTierError for callers outside OpenCode, so this model cannot be used by this integration.",
        "notes": "TEMPORARY default for all non-creative operational work while free AND usable.",
    },
    {
        "id": "deepseek-v4.1-flash",
        "short_id": "deepseek-v4.1-flash",
        "name": "DeepSeek V4.1 Flash",
        "role": "standard",
        "provider": "opencode-go",
        "family": "deepseek",
        "context": 128000,
        "cost_per_1m_input": 0.30,
        "cost_per_1m_output": 1.20,
        "cost_per_1m_cache_read": 0.006,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode Zen docs (https://opencode.ai/docs/zen/)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "provider_blocked": False,
        "availability_note": "Requires a positive Zen balance (live probe returned 402 Insufficient account funds).",
        "notes": "Intentional lower-cost fallback when Step 5 is unavailable.",
    },
    {
        "id": "glm-5.3-flash",
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
        "pricing_source": "OpenCode Zen docs (https://opencode.ai/docs/zen/)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "provider_blocked": False,
        "availability_note": "Requires a positive Zen balance (live probe returned 402 Insufficient account funds).",
        "notes": "Alternative flash model. Cache-read is more expensive than DeepSeek.",
    },
    {
        "id": "mimo-v2.6-flash-free",
        "short_id": "mimo-v2.6-flash-free",
        "name": "MiMo-V2.6-Flash Free",
        "role": "budget",
        "provider": "opencode-go",
        "family": "mimo",
        "context": 128000,
        "cost_per_1m_input": 0.0,
        "cost_per_1m_output": 0.0,
        "cost_per_1m_cache_read": 0.0,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode Zen docs (https://opencode.ai/docs/zen/)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "provider_blocked": True,
        "availability_note": "Zen free tier returns 403 FreeTierError for callers outside OpenCode, so this model cannot be used by this integration.",
        "notes": "Budget alternative (free tier), currently provider-blocked for external callers.",
    },
]

# Escalation models — NEVER selected automatically. Used only via explicit
# configuration or an operator action when the default model loops, stalls,
# loses context, or produces weak code quality.
HOSTED_ESCALATION_MODELS: List[Dict[str, Any]] = [
    {
        "id": "kimi-k2.7-code",
        "short_id": "kimi-k2.7-code",
        "name": "Kimi K2.7 Code",
        "role": "escalation",
        "provider": "opencode-go",
        "family": "kimi",
        "context": 128000,
        "cost_per_1m_input": 0.95,
        "cost_per_1m_output": 4.00,
        "cost_per_1m_cache_read": 0.19,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode Zen docs (https://opencode.ai/docs/zen/)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "provider_blocked": False,
        "availability_note": "Requires a positive Zen balance.",
        "notes": "Escalation target for quality/stall recovery. Explicit operator action only — never automatic.",
    },
]

HOSTED_MODEL_IDS = {m["id"] for m in HOSTED_MODELS} | {m["id"] for m in HOSTED_ESCALATION_MODELS}
DEFAULT_MODEL_ID = "step-5-preview-free"

# Documented Zen endpoint (https://opencode.ai/docs/zen/#endpoints).
# Models under the openai-compatible family use /chat/completions.
DEFAULT_ENDPOINT = "https://opencode.ai/zen/v1/chat/completions"

# Credential env var names, in priority order. Zen documents OPENCODE_API_KEY;
# OPENCODE_GO_API_KEY is the Northstar-local alias used in .env.
KEY_ENV_VARS = ("OPENCODE_GO_API_KEY", "OPENCODE_API_KEY")


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
    # Accept either the Northstar-local alias or the Zen-documented name.
    required_env: List[str] = []
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
        """True when any accepted API key env var is set (value never read)."""
        return any(str(os.environ.get(k, "") or "").strip() for k in KEY_ENV_VARS)

    def _api_key(self) -> Optional[str]:
        """Read the API key from the first configured env var (never logged)."""
        for k in KEY_ENV_VARS:
            val = str(os.environ.get(k, "") or "").strip()
            if val:
                return val
        return None

    def available(self) -> bool:
        """True when the provider is explicitly enabled AND the key is present.

        A key alone does not enable the provider; OPENCODE_GO_ENABLED=1 is
        required so that paid calls are never automatic.
        """
        return self.armed()

    def armed(self) -> bool:
        """True when live calls are explicitly approved (OPENCODE_GO_ENABLED=1)."""
        return str(os.environ.get("OPENCODE_GO_ENABLED", "") or "").strip() == "1" and self.key_present()

    def models(self) -> List[Dict[str, Any]]:
        """Return the selectable hosted model catalog with timestamped pricing."""
        return [dict(m) for m in HOSTED_MODELS]

    def escalation_models(self) -> List[Dict[str, Any]]:
        """Escalation models. Never auto-selected — explicit operator action only."""
        return [dict(m) for m in HOSTED_ESCALATION_MODELS]

    def all_models(self) -> List[Dict[str, Any]]:
        """Primary + escalation models (for UI display)."""
        return [dict(m) for m in HOSTED_MODELS] + [dict(m) for m in HOSTED_ESCALATION_MODELS]

    def resolve_model(self, requested: Optional[str]) -> str:
        """Resolve a model request to a concrete, verified model id.

        Raises ValueError if the requested model is not in the verified catalog.
        The legacy ``opencode-go/<id>`` prefix is accepted and stripped so
        existing stored selections keep working.
        """
        if not requested:
            return self._default_model
        if requested in HOSTED_MODEL_IDS:
            return requested
        if requested.startswith("opencode-go/"):
            bare = requested[len("opencode-go/"):]
            if bare in HOSTED_MODEL_IDS:
                return bare
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
    """OpenCode Go / Zen hosted-reasoning provider.

    Endpoint: https://opencode.ai/zen/v1/chat/completions (documented).
    Auth: OPENCODE_GO_API_KEY (or OPENCODE_API_KEY), server-side only.

    Provider constraint: Zen free-tier models return 403 FreeTierError for
    callers outside OpenCode. Paid models require a positive Zen balance.
    Both are surfaced as clear, structured errors — never silently substituted.
    """

    name = "opencode_go"

    def __init__(self) -> None:
        super().__init__()
        self.endpoint = (
            os.environ.get("OPENCODE_GO_ENDPOINT")
            or DEFAULT_ENDPOINT
        )
        self.timeout_s = float(os.environ.get("OPENCODE_GO_TIMEOUT_SECONDS") or "120")
        self.max_tokens_default = int(os.environ.get("OPENCODE_GO_MAX_TOKENS") or "4096")
        self.retries = int(os.environ.get("OPENCODE_GO_RETRIES") or "2")
        max_concurrency = int(os.environ.get("OPENCODE_GO_MAX_CONCURRENCY") or "2")
        self._sem = threading.Semaphore(max(1, max_concurrency))

    def _headers(self, session_id: Optional[str]) -> Dict[str, str]:
        return {
            "Authorization": "Bearer " + (self._api_key() or ""),
            "Content-Type": "application/json",
            "User-Agent": f"NorthstarOS/{ADAPTER_VERSION} private-testing (non-creative-reasoning)",
            "x-opencode-session": self.make_session_id(session_id),
        }

    @staticmethod
    def _error_text(resp: ProviderResponse) -> str:
        """Best-effort error body text for classification (never a secret)."""
        data = getattr(resp, "data", None)
        if isinstance(data, dict):
            if "raw" in data:
                return str(data.get("raw") or "")
            return json.dumps(data, default=str)
        return str(getattr(resp, "error", "") or "")

    @classmethod
    def _classify_provider_error(cls, status_code: int, body_text: str):
        """Translate a Zen error body into a clear, structured ProviderResponse.

        Returns None when the error is not one of the known provider conditions.
        """
        text = (body_text or "").lower()
        if status_code == 403 or "freetiererror" in text or "free tier" in text:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider="opencode_go",
                error=(
                    "Zen free-tier model refused: OpenCode's free tier can only be used "
                    "from within OpenCode. Select a paid model (DeepSeek V4.1 Flash) "
                    "after adding Zen balance. No model was substituted."
                ),
                http_status=status_code,
            )
        if status_code == 402 or "insufficient" in text or "funds" in text:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.CREDITS_EXHAUSTED,
                provider="opencode_go",
                error="Zen balance is insufficient for this paid model. Add credits or select a free-tier model (provider-restricted).",
                http_status=status_code,
            )
        if status_code == 401:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.AUTH_ERROR,
                provider="opencode_go",
                error="Zen rejected the API key (HTTP 401).",
                http_status=status_code,
            )
        if status_code == 429 or "rate limit" in text:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.RATE_LIMITED,
                provider="opencode_go",
                error="Zen rate/usage limit reached. Wait before retrying.",
                http_status=status_code,
            )
        return None

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
            classified = self._classify_provider_error(resp.http_status or 0, self._error_text(resp))
            if classified is not None:
                classified.latency_ms = resp.latency_ms
                return classified
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
                        try:
                            stream_body = stream.read().decode("utf-8", "replace")
                        except Exception:
                            stream_body = ""
                        classified = self._classify_provider_error(stream.status_code, stream_body)
                        if classified is None:
                            classified = ProviderResponse(
                                success=False,
                                status=ProviderStatus.ERROR,
                                provider=self.name,
                                error=f"OpenCode Go HTTP {stream.status_code}",
                                http_status=stream.status_code,
                            )
                        yield classified
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
