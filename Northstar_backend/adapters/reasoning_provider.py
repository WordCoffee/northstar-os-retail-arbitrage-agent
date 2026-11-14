"""Provider-neutral hosted-reasoning adapter for Northstar OS non-creative services.

This adapter implements a common reasoning-provider interface over the
**OpenCode Go** endpoints. It is designed as a temporary, manually-operated
integration for private Northstar testing — it does NOT replace the local
creative pipeline or local non-creative models.

OpenCode Go contract (exact):
- Base URL:       https://opencode.ai/zen/go/v1
- Chat endpoint:  https://opencode.ai/zen/go/v1/chat/completions
- Auth:           Authorization: Bearer <OPENCODE_GO_API_KEY>
- Model IDs:      bare IDs, e.g. ``beam-free``
- Credential env: OPENCODE_GO_API_KEY
- Enable flag:    OPENCODE_GO_ENABLED=1

This is the OpenCode Go transport. The generic OpenCode pay-as-you-go route
(/zen/v1/...) is a DIFFERENT surface with different billing and routing
behaviour and is intentionally NOT used here.

Design goals:
- Configurable provider/model (current implementation: OpenCode Go).
- Server-side credentials only.
- Streaming support where useful.
- Timeouts, cancellation-friendly clients, bounded concurrency, retries.
- Usage/provenance reporting.
- Structured error handling.
- Mockable transport for tests.

Availability rule: a model is only reported as usable once a real completion has
succeeded through the corrected Go endpoint. Unverified models are never made a
runtime default, and never auto-substituted.

Constraint note: we do not disguise listing/ad requests as coding work, spoof
another client, or bypass provider restrictions. The User-Agent truthfully
identifies the caller as "NorthstarOS/<version> private-testing".
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

# ---------------------------------------------------------------------------
# OpenCode Go transport contract
# ---------------------------------------------------------------------------

GO_BASE_URL = "https://opencode.ai/zen/go/v1"
GO_CHAT_ENDPOINT = f"{GO_BASE_URL}/chat/completions"
GO_PROVIDER_ID = "opencode-go"

# Environment contract
KEY_ENV_VARS = ("OPENCODE_GO_API_KEY",)          # credential (never logged)
ENABLED_ENV_VAR = "OPENCODE_GO_ENABLED"          # "1" arms live execution

# ---------------------------------------------------------------------------
# Selectable model catalog (bare Go model IDs)
# ---------------------------------------------------------------------------

# TEMPORARY MODEL-ROUTING POLICY (see docs/HOSTED_REASONING.md):
#   Beam Free is the verified *preferred* model for non-creative internal
#   engineering / management work only (owner-authorized 2026-11-13, replacing
#   step-5-preview-free, which the provider withdrew).
#   Non-creative = listings workflows, backend logic, APIs, database work,
#   admin/dashboard work, integrations, test writing, debugging, service
#   orchestration, logging, implementation planning.
#   Creative remodel rendering, visual staging, landscaping renders, image
#   editing and the property-image generation pipeline MUST NOT use Step 5 as
#   their primary model; they stay on the specialised image pipeline.
#
# AVAILABILITY GUARDRAIL: no model is treated as usable, and none becomes a
# runtime default, until a real completion succeeds through the Go endpoint.
# ``verified_usability`` is therefore False until a live completion is proven.
# Nothing is auto-substituted when a model is unavailable.

HOSTED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "beam-free",
        "short_id": "beam-free",
        "name": "Beam Free",
        "role": "default",
        "intended_role": "default",
        "allowed_for_creative": False,
        "provider": GO_PROVIDER_ID,
        "family": "beam",
        "context": 1048576,
        "cost_per_1m_input": 0.0,
        "cost_per_1m_output": 0.0,
        "cost_per_1m_cache_read": 0.0,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode Go live catalog (2026-11-13): input $0, output $0",
        "pricing_observed_at": "2026-11-13T00:00:00Z",
        "verified_usability": True,
        "verified_at": "2026-11-13T00:00:00Z",
        "availability_note": "VERIFIED through the OpenCode Go endpoint: a real completion returned HTTP 200 in 622 ms, model id echoed 'beam-free', usage cost 0.",
        "notes": "Owner-authorized free replacement (2026-11-13) for step-5-preview-free, which the provider withdrew. Non-creative hosted reasoning only.",
    },
    {
        "id": "step-5-preview-free",
        "short_id": "step-5-preview-free",
        "name": "Step 5 Preview Free",
        "role": "retired",
        "intended_role": "retired",
        "allowed_for_creative": False,
        "provider": GO_PROVIDER_ID,
        "family": "step",
        "context": 128000,
        "cost_per_1m_input": 0.0,
        "cost_per_1m_output": 0.0,
        "cost_per_1m_cache_read": 0.0,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "not applicable (free tier)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "verified_usability": False,
        "verified_at": "2026-10-08T00:00:00Z",
        "availability_note": "RETIRED upstream 2026-11-13: no longer in the provider catalog; a completion answers HTTP 400 'Upstream request failed: Model is unavailable.' Not usable, never selected.",
        "notes": "Kept for provenance only. The verified runtime default moved to beam-free on 2026-11-13.",
    },
    {
        "id": "deepseek-v4.1-flash",
        "short_id": "deepseek-v4.1-flash",
        "name": "DeepSeek V4.1 Flash",
        "role": "fallback",
        "intended_role": "fallback",
        "allowed_for_creative": False,
        "provider": GO_PROVIDER_ID,
        "family": "deepseek",
        "context": 128000,
        "cost_per_1m_input": 0.30,
        "cost_per_1m_output": 1.20,
        "cost_per_1m_cache_read": 0.006,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode published per-1M-token rates",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "verified_usability": False,
        "availability_note": "Not independently verified through the OpenCode Go endpoint. FALLBACK role only: usable after its own successful real completion, never automatically.",
        "notes": "Lower-cost fallback candidate for lightweight, repetitive engineering work.",
    },
    {
        "id": "glm-5.3-flash",
        "short_id": "glm-5.3-flash",
        "name": "GLM-5.3-Flash",
        "role": "experimental",
        "intended_role": "experimental",
        "allowed_for_creative": False,
        "provider": GO_PROVIDER_ID,
        "family": "glm",
        "context": 128000,
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.50,
        "cost_per_1m_cache_read": 0.03,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode published per-1M-token rates",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "verified_usability": False,
        "availability_note": "Not yet verified through the OpenCode Go endpoint.",
        "notes": "Alternative model.",
    },
    {
        "id": "mimo-v2.6-flash-free",
        "short_id": "mimo-v2.6-flash-free",
        "name": "MiMo-V2.6-Flash Free",
        "role": "experimental",
        "intended_role": "experimental",
        "allowed_for_creative": False,
        "provider": GO_PROVIDER_ID,
        "family": "mimo",
        "context": 128000,
        "cost_per_1m_input": 0.0,
        "cost_per_1m_output": 0.0,
        "cost_per_1m_cache_read": 0.0,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "not applicable (free tier)",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "verified_usability": False,
        "availability_note": "Not yet verified through the OpenCode Go endpoint.",
        "notes": "Budget candidate.",
    },
]

# Escalation models — NEVER selected automatically. Used only via explicit
# configuration or an operator action when the working model loops, stalls,
# loses context, or produces weak code quality.
HOSTED_ESCALATION_MODELS: List[Dict[str, Any]] = [
    {
        "id": "kimi-k2.7-code",
        "short_id": "kimi-k2.7-code",
        "name": "Kimi K2.7 Code",
        "role": "escalation",
        "intended_role": "escalation",
        "allowed_for_creative": False,
        "provider": GO_PROVIDER_ID,
        "family": "kimi",
        "context": 128000,
        "cost_per_1m_input": 0.95,
        "cost_per_1m_output": 4.00,
        "cost_per_1m_cache_read": 0.19,
        "cost_per_1m_cache_write": 0.0,
        "pricing_source": "OpenCode published per-1M-token rates",
        "pricing_observed_at": "2026-10-08T00:00:00Z",
        "verified_usability": False,
        "availability_note": "Not independently verified through the OpenCode Go endpoint. ESCALATION role only: usable after its own successful real completion, never automatically.",
        "notes": "Escalation target for quality/stall recovery.",
    },
]

HOSTED_MODEL_IDS = {m["id"] for m in HOSTED_MODELS} | {m["id"] for m in HOSTED_ESCALATION_MODELS}

# Intended roles (spec vocabulary). A role is descriptive intent only — it never
# grants usability. ``verified_usability`` is the sole gate.
INTENDED_ROLES = {
    "beam-free": "default",                # verified 2026-11-13; non-creative only
    "step-5-preview-free": "retired",      # withdrawn upstream 2026-11-13
    "deepseek-v4.1-flash": "fallback",     # usable only after its own verification
    "glm-5.3-flash": "experimental",
    "mimo-v2.6-flash-free": "experimental",
    "kimi-k2.7-code": "escalation",       # usable only after its own verification
}

# Creative separation: hosted reasoning models are NOT the creative remodel
# renderer. No hosted text model may be used for image/video generation.
HOSTED_REASONING_IS_CREATIVE_RENDERER = False


class ModelNotUsableError(ValueError):
    """A specifically requested model is not verified usable.

    Subclasses ValueError so existing ``assertRaises(ValueError)`` callers and
    callers that treat unknown ids uniformly keep working.
    """

    def __init__(self, model_id: str, reason: str) -> None:
        self.model_id = model_id
        self.reason = reason
        super().__init__(f"{model_id}: {reason}")


class NoVerifiedModelError(ValueError):
    """No hosted reasoning model has a verified real completion."""


def intended_role(model_id: str) -> str:
    return INTENDED_ROLES.get(model_id, "experimental")


def model_is_usable(model_id: str) -> bool:
    """True only when the model carries verified_usability=True."""
    m = next((x for x in HOSTED_MODELS + HOSTED_ESCALATION_MODELS if x["id"] == model_id), None)
    return bool(m and m.get("verified_usability"))


def verified_models() -> List[str]:
    return [
        m["id"] for m in HOSTED_MODELS + HOSTED_ESCALATION_MODELS
        if m.get("verified_usability")
    ]


# The temporary *policy* preference for non-creative internal work. This is a
# display/selection hint only — it is NOT a runtime default until verified.
POLICY_PREFERRED_MODEL = "beam-free"

# Verified 2026-11-13: one minimal non-destructive completion
# (model=beam-free, max_tokens=64) returned HTTP 200 through
# https://opencode.ai/zen/go/v1/chat/completions, model id echoed, usage cost 0.
# It replaces step-5-preview-free, which is no longer in the provider catalog
# and answers HTTP 400 "Upstream request failed: Model is unavailable.".
VERIFIED_GO_MODEL: Optional[str] = "beam-free"

# The runtime default is the verified model. No other model is a default.
RUNTIME_DEFAULT_MODEL: Optional[str] = VERIFIED_GO_MODEL


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

@dataclass
class ReasoningUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None

    def estimated_cost_usd(self, model_id: str) -> Optional[float]:
        cost = self._cost_for(model_id)
        return None if cost is None else round(cost, 8)

    def _cost_for(self, model_id: str) -> Optional[float]:
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
        return cost


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
    """Common interface for a hosted reasoning provider."""

    name: str = "reasoning"
    # Credential names only — values are never read into logs.
    required_env: List[str] = []
    optional_env: List[str] = [
        "OPENCODE_GO_ENDPOINT",
        ENABLED_ENV_VAR,
        "OPENCODE_GO_MODEL",
        "OPENCODE_GO_MAX_CONCURRENCY",
        "OPENCODE_GO_TIMEOUT_SECONDS",
        "OPENCODE_GO_MAX_TOKENS",
        "OPENCODE_GO_RETRIES",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._default_model = POLICY_PREFERRED_MODEL

    # ------------------------------------------------------------------
    # Credential presence (never reads a value into logs)
    # ------------------------------------------------------------------

    def key_present(self) -> bool:
        """True when the OpenCode Go API key env var is set (value never read)."""
        return any(str(os.environ.get(k, "") or "").strip() for k in KEY_ENV_VARS)

    def _api_key(self) -> Optional[str]:
        """Read the API key (never logged, never returned by any public API)."""
        for k in KEY_ENV_VARS:
            val = str(os.environ.get(k, "") or "").strip()
            if val:
                return val
        return None

    def enabled(self) -> bool:
        """True only when OPENCODE_GO_ENABLED is explicitly '1'."""
        return str(os.environ.get(ENABLED_ENV_VAR, "") or "").strip() == "1"

    def armed(self) -> bool:
        """Live execution requires BOTH the flag and a key present."""
        return self.enabled() and self.key_present()

    def available(self) -> bool:
        """Configured = key present and flag set. Closed by default."""
        return self.armed()

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def models(self) -> List[Dict[str, Any]]:
        """Selectable hosted model catalog (bare Go model IDs)."""
        return [dict(m) for m in HOSTED_MODELS]

    def escalation_models(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in HOSTED_ESCALATION_MODELS]

    def all_models(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in HOSTED_MODELS] + [dict(m) for m in HOSTED_ESCALATION_MODELS]

    def verified_model(self) -> Optional[str]:
        """The model proven usable by a real completion, or None."""
        return VERIFIED_GO_MODEL if VERIFIED_GO_MODEL in HOSTED_MODEL_IDS else None

    def models_status(self) -> List[Dict[str, Any]]:
        """Per-model status for the API.

        Each entry carries provider id, base URL, endpoint, configured/enabled
        state, verified usability, and intended role, so the UI can distinguish
        configured vs verified vs active default without guessing.
        """
        configured = self.key_present()
        enabled = self.enabled()
        runtime_default = self.verified_model()
        entries: List[Dict[str, Any]] = []
        for m in self.all_models():
            entry = dict(m)
            entry.update({
                "provider": GO_PROVIDER_ID,
                "base_url": GO_BASE_URL,
                "endpoint": self.endpoint,
                "configured": configured,
                "enabled": enabled,
                "armed": self.armed(),
                "verified_usability": bool(m.get("verified_usability")),
                "intended_role": intended_role(m["id"]),
                "allowed_for_creative": False,
                "is_runtime_default": m["id"] == runtime_default,
                "policy_preferred": m["id"] == POLICY_PREFERRED_MODEL,
                "usable": bool(m.get("verified_usability")) and self.armed(),
            })
            entries.append(entry)
        return entries

    def status(self) -> Dict[str, Any]:
        """Top-level hosted-reasoning status (no secrets)."""
        return {
            "provider": GO_PROVIDER_ID,
            "base_url": GO_BASE_URL,
            "chat_endpoint": GO_CHAT_ENDPOINT,
            "endpoint": self.endpoint,
            "credential_env": KEY_ENV_VARS[0],
            "enable_env": ENABLED_ENV_VAR,
            "configured": self.key_present(),
            "enabled": self.enabled(),
            "armed": self.armed(),
            "policy_preferred_model": POLICY_PREFERRED_MODEL,
            "verified_model": self.verified_model(),
            "runtime_default_model": self.verified_model() if self.armed() else None,
            "verified_usability": self.verified_model() is not None,
            "verified_models": verified_models(),
            "unverified_models": [
                m["id"] for m in HOSTED_MODELS + HOSTED_ESCALATION_MODELS
                if not m.get("verified_usability")
            ],
            "hosted_reasoning_is_creative_renderer": HOSTED_REASONING_IS_CREATIVE_RENDERER,
            "note": (
                "OpenCode Go configured, but no runtime model verified."
                if self.verified_model() is None
                else "One model has a verified completion through OpenCode Go."
            ),
        }

    def resolve_model(self, requested: Optional[str]) -> Optional[str]:
        """Resolve a model request to a verified, bare Go model id.

        Fail-closed rules:
        - Nothing requested -> the verified model (or None if none is verified).
        - Explicit request that is not in the Go catalog -> ValueError.
        - Explicit request that is in the catalog but NOT verified ->
          ModelNotUsableError. No silent substitution of another model.
        """
        if requested is None or not str(requested).strip():
            vm = self.verified_model()
            if vm is None:
                raise NoVerifiedModelError(
                    "No hosted reasoning model is verified usable; none was substituted."
                )
            return vm

        requested = str(requested).strip()
        if requested not in HOSTED_MODEL_IDS:
            # Tolerate the earlier provider-prefixed form so stored selections work.
            for prefix in ("opencode-go/", "opencode/"):
                if requested.startswith(prefix):
                    bare = requested[len(prefix):]
                    if bare in HOSTED_MODEL_IDS:
                        requested = bare
                        break
        if requested not in HOSTED_MODEL_IDS:
            raise ValueError(f"Model {requested!r} is not in the OpenCode Go catalog.")
        if not model_is_usable(requested):
            raise ModelNotUsableError(
                requested,
                "not verified usable through OpenCode Go; no model was substituted.",
            )
        return requested

    def complete(self, request: ReasoningRequest) -> ProviderResponse:
        """Non-streaming completion. Implemented by subclasses."""
        raise NotImplementedError

    def complete_stream(self, request: ReasoningRequest) -> Iterator[ProviderResponse]:
        """Streaming completion. Subclasses may implement; default raises."""
        raise NotImplementedError(f"{self.name} does not support streaming")

    @staticmethod
    def make_session_id(existing: Optional[str]) -> str:
        """A stable, non-secret session identifier per conversation."""
        if existing:
            return str(uuid.uuid5(uuid.NAMESPACE_OID, f"northstar:{existing}"))
        return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# OpenCode Go provider
# ---------------------------------------------------------------------------

class OpenCodeGoProvider(ReasoningProvider):
    """OpenCode Go hosted-reasoning provider.

    Transport contract:
        base:      https://opencode.ai/zen/go/v1
        chat:      https://opencode.ai/zen/go/v1/chat/completions
        auth:      Authorization: Bearer <OPENCODE_GO_API_KEY>
        models:    bare Go model IDs

    This is the OpenCode Go surface. The generic pay-as-you-go OpenCode route
    (/zen/v1/...) is a different provider surface with different billing and
    routing; it is not used here. Authorization headers are never logged.
    """

    name = GO_PROVIDER_ID

    def __init__(self) -> None:
        super().__init__()
        self.endpoint = (
            os.environ.get("OPENCODE_GO_ENDPOINT")
            or GO_CHAT_ENDPOINT
        )
        self.timeout_s = float(os.environ.get("OPENCODE_GO_TIMEOUT_SECONDS") or "120")
        self.max_tokens_default = int(os.environ.get("OPENCODE_GO_MAX_TOKENS") or "4096")
        self.retries = int(os.environ.get("OPENCODE_GO_RETRIES") or "2")
        max_concurrency = int(os.environ.get("OPENCODE_GO_MAX_CONCURRENCY") or "2")
        self._sem = threading.Semaphore(max(1, max_concurrency))

    # -- transport helpers ------------------------------------------------

    def _headers(self, session_id: Optional[str]) -> Dict[str, str]:
        key = self._api_key()
        return {
            "Authorization": "Bearer " + (key or ""),
            "Content-Type": "application/json",
            "User-Agent": f"NorthstarOS/{ADAPTER_VERSION} private-testing (non-creative-reasoning)",
            "x-opencode-session": self.make_session_id(session_id),
        }

    def _body(self, request: ReasoningRequest) -> Dict[str, Any]:
        # Fail-closed: raises on unverified / unknown / no-verified-model.
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
        """Translate a Go error body into a clear, structured response.

        Returns None when the error is not one of the known conditions. The
        provider message is summarised, never quoted verbatim with payload.
        """
        text = (body_text or "").lower()
        if status_code == 403 or "freetiererror" in text or "free tier" in text:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=(
                    "OpenCode Go refused this free-tier model: the provider states the free "
                    "tier can only be used from inside OpenCode. The requested free model is "
                    "unavailable to this external runtime provider path. "
                    "No model was substituted."
                ),
                http_status=status_code,
            )
        if status_code == 402 or "insufficient" in text or "funds" in text or "balance" in text:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.CREDITS_EXHAUSTED,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go reports insufficient balance for this model.",
                http_status=status_code,
            )
        if status_code == 401:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.AUTH_ERROR,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go rejected the API key (HTTP 401).",
                http_status=status_code,
            )
        if status_code == 404:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.NOT_FOUND,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go route not found (HTTP 404) - check the base URL.",
                http_status=status_code,
            )
        if status_code == 429 or "rate limit" in text:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.RATE_LIMITED,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go rate/usage limit reached. Wait before retrying.",
                http_status=status_code,
            )
        return None

    # -- completion -------------------------------------------------------

    def complete(self, request: ReasoningRequest) -> ProviderResponse:
        """Execute a non-streaming chat completion against OpenCode Go."""
        if not self.key_present():
            return ProviderResponse(
                success=False,
                status=ProviderStatus.AUTH_ERROR,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go is not configured (OPENCODE_GO_API_KEY missing).",
            )
        if not self.enabled():
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go key is present but the provider is not armed. Set OPENCODE_GO_ENABLED=1 after explicit operator approval.",
            )

        try:
            body = self._body(request)
        except ModelNotUsableError as exc:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=(
                    f"Requested hosted reasoning model {exc.model_id!r} is not verified "
                    f"usable through OpenCode Go ({exc.reason}). Select the verified "
                    f"model ({self.verified_model() or 'none available'})."
                ),
            )
        except NoVerifiedModelError as exc:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=str(exc),
            )
        except ValueError as exc:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=str(exc),
            )

        with self._sem:
            resp = self._timed_request(
                "POST",
                self.endpoint,
                headers=self._headers(request.session_id),
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

        payload = resp.data if isinstance(resp.data, dict) else {}
        try:
            content = payload["choices"][0]["message"]["content"]
            model = payload.get("model", body["model"])
        except (KeyError, IndexError, TypeError) as exc:
            return ProviderResponse(
                success=False,
                status=ProviderStatus.ERROR,
                provider=GO_PROVIDER_ID,
                error=f"Malformed response from OpenCode Go: {type(exc).__name__}",
                http_status=resp.http_status,
                latency_ms=resp.latency_ms,
            )

        usage = self._parse_usage(payload)
        cost = usage.estimated_cost_usd(model)

        return ProviderResponse(
            success=True,
            status=ProviderStatus.OK,
            provider=GO_PROVIDER_ID,
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
                "base_url": GO_BASE_URL,
                "endpoint": self.endpoint,
                "provider": GO_PROVIDER_ID,
                "pricing_source": "OpenCode published per-1M-token rates",
                "pricing_observed_at": "2026-10-08T00:00:00Z",
            },
        )

    @staticmethod
    def _parse_usage(payload: Dict[str, Any]) -> "ReasoningUsage":
        usage = payload.get("usage") or {}
        return ReasoningUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            cache_read_tokens=usage.get("prompt_cache_hit_tokens") or usage.get("cache_read_tokens"),
            cache_write_tokens=usage.get("prompt_cache_miss_tokens") or usage.get("cache_write_tokens"),
        )

    def complete_stream(self, request: ReasoningRequest) -> Iterator[ProviderResponse]:
        """Streaming completion against OpenCode Go."""
        if not self.key_present():
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.AUTH_ERROR,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go is not configured (OPENCODE_GO_API_KEY missing).",
            )
            return
        if not self.enabled():
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error="OpenCode Go key is present but the provider is not armed.",
            )
            return

        try:
            body = self._body(request)
        except ModelNotUsableError as exc:
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=(
                    f"Requested hosted reasoning model {exc.model_id!r} is not verified "
                    f"usable through OpenCode Go ({exc.reason}). No model was substituted."
                ),
            )
            return
        except NoVerifiedModelError as exc:
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=str(exc),
            )
            return
        except ValueError as exc:
            yield ProviderResponse(
                success=False,
                status=ProviderStatus.BLOCKED,
                provider=GO_PROVIDER_ID,
                error=str(exc),
            )
            return

        import httpx

        accumulated: List[str] = []
        with self._sem:
            t0 = time.monotonic()
            try:
                client = self._get_client(timeout=self.timeout_s)
                with client.stream("POST", self.endpoint, headers=self._headers(request.session_id), json=body) as stream:
                    if stream.status_code != 200:
                        try:
                            raw = stream.read().decode("utf-8", "replace")
                        except Exception:
                            raw = ""
                        classified = self._classify_provider_error(stream.status_code, raw)
                        if classified is None:
                            classified = ProviderResponse(
                                success=False,
                                status=ProviderStatus.ERROR,
                                provider=GO_PROVIDER_ID,
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
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            accumulated.append(delta)
                            yield ProviderResponse(
                                success=True,
                                status=ProviderStatus.OK,
                                provider=GO_PROVIDER_ID,
                                data={"content": delta, "partial": True, "model": body["model"]},
                            )
            except httpx.TimeoutException as exc:
                yield ProviderResponse(
                    success=False,
                    status=ProviderStatus.TIMEOUT,
                    provider=GO_PROVIDER_ID,
                    error=f"OpenCode Go timed out: {type(exc).__name__}",
                )
                return
            except Exception as exc:
                yield ProviderResponse(
                    success=False,
                    status=ProviderStatus.ERROR,
                    provider=GO_PROVIDER_ID,
                    error=f"OpenCode Go request failed: {type(exc).__name__}",
                )
                return

        yield ProviderResponse(
            success=True,
            status=ProviderStatus.OK,
            provider=GO_PROVIDER_ID,
            data={
                "content": "".join(accumulated),
                "partial": False,
                "model": body["model"],
                "task_type": request.task_type,
                "session_id": request.session_id,
            },
            latency_ms=(time.monotonic() - t0) * 1000,
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

    def key_present(self) -> bool:
        return True

    def enabled(self) -> bool:
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
    """Factory. Currently only the OpenCode Go provider is implemented."""
    provider_name = os.environ.get("REASONING_PROVIDER", "opencode_go").lower()
    if provider_name == "mock":
        return MockReasoningProvider()
    return OpenCodeGoProvider()
