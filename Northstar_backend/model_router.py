"""Model router — provider + tier resolution for the dual-engine Brain
(Phase H / H2).

Two engines, one switch:
  * LOCAL  — Ollama on the operator's machine (free, private)
  * CLOUD  — the locked OpenRouter DeepSeek lane (paid, gated)

Three text tiers (T1 fast / T2 core / T3 seam) and three vision tiers
(V1/V2/V3). The router resolves ``(provider, tier)`` to a concrete model id,
enforces the Master Brain consent policy (no silent tier change), returns the
credit weight for the ledger, and refuses cloud execution unless the live
gate is armed.

Pure and offline: this module never makes a network call. Callers (the LLM
adapter / AutothinK) do the actual generation behind their own gates.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --- tiers ------------------------------------------------------------------

TEXT_TIERS = ("T1", "T2", "T3")
VISION_TIERS = ("V1", "V2", "V3")
ALL_TIERS = TEXT_TIERS + VISION_TIERS

TIER_LABELS = {
    "T1": "T1 Fast — cheap, quick (routing, extraction, summaries, drafts)",
    "T2": "T2 Core — main reasoning / copy / analysis",
    "T3": "T3 Seam — audit-grade, high-stakes escalation",
    "V1": "V1 Vision — standard images",
    "V2": "V2 Vision — pro images (text-heavy)",
    "V3": "V3 Vision — studio (product/ad photography)",
}

# Credit weight per tier (display meter; action caps are the enforcement).
TIER_CREDIT_WEIGHT = {
    "T1": 1,
    "T2": 60,
    "T3": 300,
    "V1": 12,
    "V2": 40,
    "V3": 125,
}

# --- model catalog ----------------------------------------------------------

# LOCAL (Ollama on the operator machine). rev1 is the Master Brain primary.
LOCAL_MODELS = {
    "T1": "northstaros-qwen3.8:27b",
    "T2": "northstaros-qwen3.8:27b",
    "T3": "northstaros-qwen3.8:27b",
    "V1": "qwen2.5vl:7b",
    "V2": "qwen2.5vl:7b",
    "V3": "qwen2.5vl:7b",
}
LOCAL_ALTERNATES = {
    "T2": ["qwen3:14b"],
    "T3": ["qwen3:14b"],
}

# CLOUD (OpenRouter DeepSeek lane — locked D1–D6 strategy §17).
CLOUD_MODELS = {
    "T1": "deepseek/deepseek-v4-flash-0731:free",
    "T2": "deepseek/deepseek-v4-flash-0731",
    "T3": "deepseek/deepseek-v4.1-flash",
    "V1": None,   # vision generation resolved via resolve_vision(); not a text lane
    "V2": None,
    "V3": None,
}
CLOUD_VISION_MODELS: Dict[str, str] = {}   # V-tier understanding model ids (OpenRouter)
CLOUD_PROVIDER_PINS = {
    "T2": "relace/fp4",
    "T3": "deepinfra/fp8",
}

PROVIDERS = ("local", "cloud")

# --- config-driven suite (Phase A / A2) -------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SUITE_PATH = os.path.join(_REPO_ROOT, "shared", "model-suite.json")
_SERVICE_MAP_PATH = os.path.join(_REPO_ROOT, "shared", "service-model-map.json")

# Provider key env vars (presence-only; values are never read/logged).
_PROVIDER_KEY_ENV = {
    "openrouter": "OPENROUTER_API_KEY",
    "fal": "FAL_KEY",
    "replicate": "REPLICATE_API_TOKEN",
}


def _load_json(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


SUITE = _load_json(_SUITE_PATH)
SERVICE_MAP = _load_json(_SERVICE_MAP_PATH)

# Overlay the config onto the literal defaults so resolve() stays identical
# when the config matches, and follows the config when it changes.
for _tier, _cfg in (SUITE.get("text", {}).get("tiers", {}) or {}).items():
    if _cfg.get("local"):
        LOCAL_MODELS[_tier] = _cfg["local"]
    if _cfg.get("cloud"):
        CLOUD_MODELS[_tier] = _cfg["cloud"]
    if _cfg.get("cloud_pin"):
        CLOUD_PROVIDER_PINS[_tier] = _cfg["cloud_pin"]

for _tier, _cfg in (SUITE.get("vision", {}).get("tiers", {}) or {}).items():
    _u = _cfg.get("understand") or {}
    if _u.get("local"):
        LOCAL_MODELS[_tier] = _u["local"]
    if _u.get("cloud") and _u.get("cloud_provider") == "openrouter":
        # Cloud vision understanding is an OpenRouter text-tier model id.
        CLOUD_VISION_MODELS[_tier] = _u["cloud"]


def cloud_live_armed() -> bool:
    """Cloud execution requires BOTH the key presence and the live flag.

    Presence-only checks — credential values are never read or logged.
    """
    key_present = bool(str(os.getenv("OPENROUTER_API_KEY", "") or "").strip())
    armed = str(os.getenv("CLOUD_MODEL_LIVE", "") or "").strip() == "1"
    return key_present and armed


def cloud_key_present() -> bool:
    return bool(str(os.getenv("OPENROUTER_API_KEY", "") or "").strip())


@dataclass(frozen=True)
class Resolution:
    provider: str
    tier: str
    model: Optional[str]
    credit_weight: int
    available: bool
    reason: str
    pin: Optional[str] = None


def resolve(provider: str, tier: str, model: Optional[str] = None) -> Resolution:
    """Resolve a (provider, tier[, model]) request to a concrete plan.

    ``available=False`` means the caller must fall back or report honestly;
    the router never silently substitutes a different tier.
    """
    provider = (provider or "local").strip().lower()
    tier = (tier or "T2").strip().upper()

    if provider not in PROVIDERS:
        return Resolution(provider, tier, None, 0, False, "unknown_provider")
    if tier not in ALL_TIERS:
        return Resolution(provider, tier, None, 0, False, "unknown_tier")

    weight = TIER_CREDIT_WEIGHT[tier]

    if provider == "local":
        chosen = model or LOCAL_MODELS.get(tier)
        if not chosen:
            return Resolution(provider, tier, None, weight, False, "no_local_model_for_tier")
        return Resolution(provider, tier, chosen, weight, True, "ok")

    # cloud
    chosen = model or CLOUD_MODELS.get(tier)
    if not chosen:
        return Resolution(provider, tier, None, weight, False, "cloud_tier_unavailable")
    if not cloud_live_armed():
        return Resolution(provider, tier, chosen, weight, False, "cloud_not_armed")
    return Resolution(provider, tier, chosen, weight, True, "ok", pin=CLOUD_PROVIDER_PINS.get(tier))


# --- vision + service resolution (Phase A / A2) -----------------------------

@dataclass(frozen=True)
class VisionResolution:
    tier: str
    provider: str
    role: str               # understand | generate
    backend: Optional[str]  # comfyui | openrouter | fal | replicate
    model: Optional[str]
    cost_per_unit: Optional[float]
    available: bool
    reason: str


def provider_key_present(provider: str) -> bool:
    env = _PROVIDER_KEY_ENV.get((provider or "").lower())
    return bool(env and str(os.getenv(env, "") or "").strip())


def media_live_armed() -> bool:
    """Media generation (image/video) requires the media live gate."""
    return str(os.getenv("MEDIA_GEN_LIVE", "") or "").strip() == "1"


def provider_armed(provider: str) -> bool:
    p = (provider or "").lower()
    if p == "local":
        return True
    if p == "openrouter":
        return cloud_live_armed()
    return provider_key_present(p) and media_live_armed()


def _vision_gen_entry(cfg: Dict, quality: Optional[str]) -> Tuple[Optional[str], Dict]:
    g = cfg.get("generate", {}) or {}
    for key in (quality, "final", "flat", "draft"):
        if key and isinstance(g.get(key), dict):
            return key, g[key]
    return None, {}


def resolve_vision(tier: str, provider: str = "cloud", role: str = "generate",
                   quality: Optional[str] = None,
                   installed: Optional[List[str]] = None) -> VisionResolution:
    """Resolve a vision tier for understanding (image->text) or generation.

    ``installed`` is the list of local model ids Ollama actually reports (the
    same list ``catalog()`` receives). When supplied, a local tier whose model
    is not installed resolves to ``available=False`` with
    ``local_model_not_installed`` instead of claiming a capability that has no
    weights behind it. Omit it to keep the pure config view.
    """
    tier = (tier or "V1").upper()
    provider = (provider or "cloud").lower()
    cfg = (SUITE.get("vision", {}).get("tiers", {}) or {}).get(tier)
    if not cfg:
        return VisionResolution(tier, provider, role, None, None, None, False, "unknown_vision_tier")

    if role == "understand":
        u = cfg.get("understand", {}) or {}
        model = u.get("local") if provider == "local" else u.get("cloud")
        backend = "local" if provider == "local" else u.get("cloud_provider", "openrouter")
        if not model:
            return VisionResolution(tier, provider, role, backend, None, None, False, "no_understanding_model")
        if provider == "local" and installed is not None and model not in installed:
            return VisionResolution(tier, provider, role, backend, model, None, False,
                                    "local_model_not_installed")
        armed = provider_armed(backend)
        return VisionResolution(tier, provider, role, backend, model, None, armed,
                                "ok" if armed else "not_armed")

    # generation
    g = cfg.get("generate", {}) or {}
    if provider == "local":
        model = g.get("local")
        return VisionResolution(tier, provider, role, "comfyui", model, None, bool(model),
                                "ok" if model else "no_local_generator")
    key, entry = _vision_gen_entry(cfg, quality)
    if not entry:
        return VisionResolution(tier, provider, role, "fal", None, None, False, "no_cloud_generator")
    backend = entry.get("provider", "fal")
    cost = entry.get("cost_per_img", entry.get("cost_per_15s", entry.get("cost_per_s")))
    armed = provider_armed(backend)
    return VisionResolution(tier, provider, role, backend, entry.get("model"), cost, armed,
                            "ok" if armed else "not_armed")


def resolve_for_service(service: str, provider: Optional[str] = None,
                        tier: Optional[str] = None) -> Dict[str, object]:
    """Resolve a service -> (provider, tier) -> concrete model plan.

    Returns a dict with the service metadata and the underlying ``Resolution``
    (or ``None`` if the service is unknown, fail-closed).
    """
    services = SERVICE_MAP.get("services", {}) or {}
    svc = services.get(service)
    if not svc:
        return {"service": service, "known": False, "reason": "unknown_service"}
    defaults = SERVICE_MAP.get("default_provider", {}) or {}
    prov = (provider or defaults.get("customer") or "cloud").lower()
    t = (tier or svc.get("tier") or "T2").upper()
    res = resolve(prov, t)
    return {
        "service": service,
        "known": True,
        "display": svc.get("display"),
        "provider": prov,
        "tier": t,
        "media": list(svc.get("media", []) or []),
        "escalation_tier": svc.get("escalation_tier"),
        "resolution": res,
    }


# --- consent policy (no silent tier change) ---------------------------------

_TIER_RANK = {"T1": 0, "T2": 1, "T3": 2}
_ESCALATION_NOTE = {
    "T2": "This moves the task to the core reasoning tier (higher cost).",
    "T3": "This escalates to the audit-grade seam tier (highest cost).",
}


def tier_rank(tier: str) -> int:
    return _TIER_RANK.get((tier or "").upper(), -1)


def requires_consent(from_tier: Optional[str], to_tier: str) -> bool:
    """True when moving tiers upward (T1→T2→T3). Downgrades never prompt."""
    if not from_tier:
        return False
    return tier_rank(to_tier) > tier_rank(from_tier)


def consent_prompt(from_tier: Optional[str], to_tier: str) -> Optional[Dict[str, str]]:
    """The minimal, skippable prompt shown when escalating tiers."""
    if not requires_consent(from_tier, to_tier):
        return None
    return {
        "code": "tier_change_consent",
        "from_tier": (from_tier or "").upper(),
        "to_tier": (to_tier or "").upper(),
        "message": _ESCALATION_NOTE.get((to_tier or "").upper(), "Tier change requires approval."),
        "skippable": "true",
    }


# --- unified catalog ---------------------------------------------------------

def catalog(installed_local: Optional[List[str]] = None) -> Dict[str, object]:
    """The unified model catalog served to the UI (no secrets)."""
    installed = installed_local or []
    return {
        "providers": list(PROVIDERS),
        "tiers": list(ALL_TIERS),
        "tier_labels": dict(TIER_LABELS),
        "credit_weights": dict(TIER_CREDIT_WEIGHT),
        "local": {
            "defaults": dict(LOCAL_MODELS),
            "alternates": {k: list(v) for k, v in LOCAL_ALTERNATES.items()},
            "installed": list(installed),
        },
        "cloud": {
            "defaults": dict(CLOUD_MODELS),
            "vision_defaults": dict(CLOUD_VISION_MODELS),
            "pins": dict(CLOUD_PROVIDER_PINS),
            "key_present": cloud_key_present(),
            "live_armed": cloud_live_armed(),
        },
        "vision": SUITE.get("vision", {}),
        # Truthful local-vision check: "ok" only when the configured model is
        # actually installed on this machine; otherwise the reason code.
        "vision_local_status": {
            t: resolve_vision(t, "local", "understand", installed=installed).reason
            for t in VISION_TIERS
        },
        "services": SERVICE_MAP.get("services", {}),
        "service_default_provider": SERVICE_MAP.get("default_provider", {}),
        "media_key_present": {p: provider_key_present(p) for p in ("openrouter", "fal", "replicate")},
        "media_armed": media_live_armed(),
        "consent": "escalating tiers (T1\u2192T2\u2192T3) prompts once; never silent.",
    }
