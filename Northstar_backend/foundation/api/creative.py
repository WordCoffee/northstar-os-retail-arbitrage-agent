"""Creative media readiness — READ-ONLY, provider-neutral.

This module answers ONE question truthfully: is media generation armed, and if
not, why? It never generates, uploads, publishes, transfers, or exports
anything, and it contacts no external provider. It returns only safe status
metadata (booleans and safe identifiers) — never secrets, tokens, raw
environment values, or provider configuration.

The only probe is a bounded localhost reachability check of the operator's own
engine (default ComfyUI at ``COMFYUI_URL``). It does not install, start, or load
anything. This is a *readiness* signal, not an activation: readiness does not
enable generation.
"""
from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from ..context import RequestContext
from .deps import get_context

router = APIRouter(prefix="/api/v1/foundation/creative", tags=["creative"])

_DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
_PROBE_TIMEOUT_S = 0.3
_CLOUD_MEDIA_PROVIDERS = ("fal", "openrouter", "replicate")


# ---- safe model_router accessors (single source of truth; no values leaked) ----

def _model_router():
    try:
        import model_router as mr  # Northstar_backend on sys.path
    except ImportError:  # pragma: no cover - repo-root sys.path variant
        from Northstar_backend import model_router as mr
    return mr


def _media_live_armed() -> bool:
    try:
        return bool(_model_router().media_live_armed())
    except Exception:  # noqa: BLE001 - readiness must never raise
        return False


def _cloud_key_present() -> bool:
    """Presence-only check. Never returns or logs the key itself."""
    try:
        mr = _model_router()
        return any(bool(mr.provider_key_present(p)) for p in _CLOUD_MEDIA_PROVIDERS)
    except Exception:  # noqa: BLE001
        return False


def _local_generation_configured() -> bool:
    try:
        tiers = (_model_router().SUITE.get("vision", {}) or {}).get("tiers", {}) or {}
        return any((t.get("generate") or {}).get("local") for t in tiers.values())
    except Exception:  # noqa: BLE001
        return False


def _media_providers():
    try:
        import media_providers as mp  # Northstar_backend on sys.path
    except ImportError:  # pragma: no cover - repo-root sys.path variant
        from Northstar_backend import media_providers as mp
    return mp


def _local_image_engine():
    try:
        import local_image_engine as lie  # Northstar_backend on sys.path
    except ImportError:  # pragma: no cover - repo-root sys.path variant
        from Northstar_backend import local_image_engine as lie
    return lie


def _parse_local_endpoint() -> Optional[Tuple[str, int]]:
    url = (os.getenv("COMFYUI_URL", "") or "").strip() or _DEFAULT_COMFY_URL
    try:
        p = urlparse(url)
        host = p.hostname
        port = p.port or (443 if p.scheme == "https" else 80)
        if not host:
            return None
        return host, int(port)
    except (ValueError, TypeError):
        return None


def probe_local_engine() -> str:
    """Bounded localhost reachability check. Returns
    ``reachable`` | ``unreachable`` | ``unknown``. Never raises, never installs,
    starts, or loads a model, and contacts no external provider."""
    endpoint = _parse_local_endpoint()
    if not endpoint:
        return "unknown"
    host, port = endpoint
    try:
        with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT_S):
            return "reachable"
    except (OSError, ValueError):
        return "unreachable"


def build_readiness(probe: Callable[[], str] = probe_local_engine) -> Dict[str, object]:
    """Pure, testable readiness contract. No secrets, no side effects, no writes."""
    armed = _media_live_armed()
    local_configured = _local_generation_configured()
    cloud_key = _cloud_key_present()

    try:
        local_state = probe()
    except Exception:  # noqa: BLE001 - a probe failure is a state, not a crash
        local_state = "unknown"
    if local_state not in ("reachable", "unreachable", "unknown"):
        local_state = "unknown"

    if local_configured:
        backend = "local"
    elif cloud_key:
        backend = "cloud"
    else:
        backend = "none"

    if not armed:
        generation, reason = "planned_not_armed", "media_gate_off"
    elif local_configured and local_state == "reachable":
        generation, reason = "local_available", "ok"
    elif cloud_key:
        generation, reason = "provider_gated", "cloud_key_present"
    elif local_state == "unreachable":
        generation, reason = "unavailable", "engine_unreachable"
    else:
        generation, reason = "unavailable", "no_backend"

    # Provider-neutral generation architecture (Path B): roster + capability->
    # cost routing hooks + planning spend caps. Metadata only — no provider is
    # contacted, nothing is armed by this, and no key value is ever returned.
    try:
        mp = _media_providers()
        providers = mp.list_providers()
        capabilities = mp.capabilities()
        spend_caps = dict(mp.SPEND_CAPS)
        routing_hooks = {
            "image_draft": mp.route("image", "draft"),
            "image_final": mp.route("image", "final"),
            "video_draft": mp.route("video", "draft"),
        }
    except Exception:  # noqa: BLE001 - readiness must never break
        providers, capabilities, spend_caps, routing_hooks = [], [], {}, {}

    # Local image-engine dev lane (read-only): what is installed vs the exact
    # owner-gated step still required. Never installs, downloads, or arms.
    try:
        local_setup = _local_image_engine().build_local_setup(engine_state=local_state)
    except Exception:  # noqa: BLE001
        local_setup = {}

    return {
        "generation": generation,
        "armed": armed,
        "media_live": armed,
        "backend": backend,
        "local_engine": {
            "state": local_state,
            "kind": "comfyui" if local_configured else "none",
        },
        "cloud_key_present": cloud_key,
        "provider_gated": generation == "provider_gated",
        "reason": reason,
        "probe": "performed",
        "providers": providers,
        "capabilities": capabilities,
        "routing_hooks": routing_hooks,
        "spend_caps": spend_caps,
        "local_setup": local_setup,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Readiness only — does not activate generation, publish, or transfer media.",
    }


@router.get("/readiness")
def readiness(ctx: RequestContext = Depends(get_context)) -> Dict[str, object]:
    """Read-only media-generation readiness (authenticated, no secrets, no
    generation). The ``ctx`` dependency enforces the standard auth posture."""
    return build_readiness(probe=probe_local_engine)
