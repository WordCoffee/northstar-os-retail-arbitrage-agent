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
    "T1": "qwen3:4b",
    "T2": "northstar-qwen3:rev1",
    "T3": "northstar-qwen3:rev1",
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
    "V1": None,   # image gen is provider-side + deferred
    "V2": None,
    "V3": None,
}
CLOUD_PROVIDER_PINS = {
    "T2": "relace/fp4",
    "T3": "deepinfra/fp8",
}

PROVIDERS = ("local", "cloud")


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
            "pins": dict(CLOUD_PROVIDER_PINS),
            "key_present": cloud_key_present(),
            "live_armed": cloud_live_armed(),
        },
        "consent": "escalating tiers (T1→T2→T3) prompts once; never silent.",
    }
