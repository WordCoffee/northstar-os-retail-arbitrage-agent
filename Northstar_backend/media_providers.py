"""Provider-neutral media-generation architecture — UNARMED, no provider calls.

This module declares the hosted image/video generation *interface* the creative
cluster will use once a provider is approved: provider registry, capability
descriptors, capability→cost routing hooks, and planning spend caps. It is a
blueprint, not an engine.

Hard guarantees (Path B):
  * It NEVER contacts a provider, reads a credential *value*, generates, uploads,
    publishes, or transfers anything, and consumes no credits.
  * ``MEDIA_GEN_LIVE`` remains the single arming gate. Until it is set (and a
    provider key is present) every generation plan is ``not_armed`` /
    ``provider_required``.
  * The registry is derived from ``shared/model-suite.json`` so provider/model/
    cost metadata stays config-driven and provider-neutral.

Provider key *presence* is checked; key values are never read, returned, or
logged.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Provider key env var NAMES only (presence check; values never read here).
_PROVIDER_ENV = {
    "fal": "FAL_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "replicate": "REPLICATE_API_TOKEN",
}
_PROVIDER_LABELS = {
    "fal": "fal.ai",
    "openrouter": "OpenRouter",
    "replicate": "Replicate",
}

# Planning-only spend caps (USD). NOT enforced by this module and never written
# to a ledger — the authoritative ledger is the foundation credit ledger, which
# only records real provider-returned usage. These are conservative planning
# defaults for a future routing/policy layer.
SPEND_CAPS = {
    "per_call_usd": 5.00,
    "per_image_usd": 0.25,
    "per_video_clip_usd": 5.00,
    "per_day_usd": 25.00,
    "enforced": False,
}

_DEFAULT_VIDEO_SECONDS = 15


def _mr():
    try:
        import model_router as mr  # Northstar_backend on sys.path
    except ImportError:  # pragma: no cover - repo-root sys.path variant
        from Northstar_backend import model_router as mr
    return mr


def media_live_armed() -> bool:
    try:
        return bool(_mr().media_live_armed())
    except Exception:  # noqa: BLE001
        return False


def key_present(provider: str) -> bool:
    """Presence-only. The key value is never read, returned, or logged."""
    try:
        return bool(_mr().provider_key_present((provider or "").lower()))
    except Exception:  # noqa: BLE001
        return False


def _cloud_entries() -> List[Dict[str, object]]:
    """Flatten the suite's cloud image/video generate entries into one list."""
    try:
        suite = _mr().SUITE or {}
    except Exception:  # noqa: BLE001
        return []
    out: List[Dict[str, object]] = []
    vision = suite.get("vision", {}) or {}
    for tier, cfg in (vision.get("tiers") or {}).items():
        for quality, entry in (cfg.get("generate") or {}).items():
            if isinstance(entry, dict) and entry.get("provider"):
                out.append({
                    "kind": "image", "tier": tier, "quality": quality,
                    "provider": entry.get("provider"), "model": entry.get("model"),
                    "unit": "per_image", "unit_cost": entry.get("cost_per_img"),
                    "watermarked": bool(entry.get("watermarked")),
                })
    video = (vision.get("video") or {}).get("generate") or {}
    for quality, entry in video.items():
        if isinstance(entry, dict) and entry.get("provider"):
            unit, unit_cost = ("per_second", entry.get("cost_per_s"))
            if unit_cost is None and entry.get("cost_per_15s") is not None:
                unit, unit_cost = "per_15s", entry.get("cost_per_15s")
            out.append({
                "kind": "video", "tier": "VIDEO", "quality": quality,
                "provider": entry.get("provider"), "model": entry.get("model"),
                "unit": unit, "unit_cost": unit_cost,
                "watermarked": bool(entry.get("watermarked")),
            })
    return out


def estimate_cost(unit: str, unit_cost: Optional[float], seconds: int = _DEFAULT_VIDEO_SECONDS) -> Optional[float]:
    if unit_cost is None:
        return None
    if unit == "per_image":
        return round(float(unit_cost), 4)
    if unit == "per_second":
        return round(float(unit_cost) * seconds, 4)
    if unit == "per_15s":
        return round(float(unit_cost) * (seconds / 15.0), 4)
    return None


def capabilities() -> List[Dict[str, object]]:
    """Provider-neutral capability descriptors (no provider-specific detail)."""
    return [
        {"capability": "image.generate", "label": "Image generation",
         "aspects": ["1:1", "4:5", "9:16", "16:9", "3:2"], "text_in_image": True},
        {"capability": "image.edit", "label": "Image edit / composite",
         "aspects": ["1:1", "4:5", "9:16", "16:9"], "text_in_image": True},
        {"capability": "video.generate", "label": "Video / short clip",
         "aspects": ["9:16", "1:1", "16:9"], "durations_s": [5, 15, 30], "audio": True},
    ]


def list_providers() -> List[Dict[str, object]]:
    """Safe, secret-free provider roster: names, capabilities, models, planning
    costs, key presence (bool), and armed state (bool). No values."""
    armed = media_live_armed()
    by_provider: Dict[str, Dict[str, object]] = {}
    for e in _cloud_entries():
        p = str(e["provider"]).lower()
        rec = by_provider.setdefault(p, {
            "provider": p,
            "label": _PROVIDER_LABELS.get(p, p),
            "key_present": key_present(p),
            "armed": armed and key_present(p),
            "kinds": set(),
            "models": [],
        })
        rec["kinds"].add(e["kind"])
        rec["models"].append({
            "kind": e["kind"], "tier": e["tier"], "quality": e["quality"],
            "model": e["model"], "unit": e["unit"], "unit_cost_usd": e["unit_cost"],
            "estimated_15s_usd": estimate_cost(e["unit"], e["unit_cost"]) if e["kind"] == "video" else None,
            "watermarked": e["watermarked"],
        })
    out = []
    for rec in by_provider.values():
        rec["kinds"] = sorted(rec["kinds"])
        out.append(rec)
    return sorted(out, key=lambda r: r["provider"])


def route(kind: str, quality: str = "draft") -> Optional[Dict[str, object]]:
    """Capability→cost routing hook. Returns the cheapest matching provider entry
    for (kind, quality). Never calls a provider."""
    kind = (kind or "image").lower()
    matches = [e for e in _cloud_entries() if e["kind"] == kind and e["quality"] == quality]
    if not matches:
        matches = [e for e in _cloud_entries() if e["kind"] == kind and e["quality"] in ("final", "capped", "draft")]
    if not matches:
        return None
    # Cheapest first — a routing hook, not a policy decision.
    matches.sort(key=lambda e: (e["unit_cost"] is None, e["unit_cost"] or 0.0))
    best = matches[0]
    return {
        "kind": best["kind"], "quality": best["quality"], "provider": best["provider"],
        "model": best["model"], "unit": best["unit"], "unit_cost_usd": best["unit_cost"],
        "watermarked": best["watermarked"],
    }


def plan_generation(kind: str = "image", quality: str = "draft",
                    seconds: int = _DEFAULT_VIDEO_SECONDS) -> Dict[str, object]:
    """A generation PLAN — never a call. Reports the honest status only.

    status: 'not_armed' (gate off) | 'provider_required' (no key) | 'ready'
    (gate on + key present) — 'ready' still performs no generation here.
    """
    armed = media_live_armed()
    route_info = route(kind, quality)
    if route_info is None:
        return {"status": "unsupported", "kind": kind, "quality": quality, "armed": armed,
                "reason": "no_route"}
    provider = str(route_info["provider"]).lower()
    key = key_present(provider)
    est = estimate_cost(route_info["unit"], route_info["unit_cost_usd"], seconds)
    cap = SPEND_CAPS["per_video_clip_usd"] if kind == "video" else SPEND_CAPS["per_image_usd"]
    within_cap = (est is None) or (est <= cap)
    if not armed:
        status, reason = "not_armed", "media_gate_off"
    elif not key:
        status, reason = "provider_required", "provider_key_absent"
    else:
        status, reason = "ready", "ok"
    return {
        "status": status, "reason": reason, "kind": kind, "quality": quality,
        "provider": provider, "model": route_info["model"], "armed": armed,
        "key_present": key, "unit": route_info["unit"], "unit_cost_usd": route_info["unit_cost_usd"],
        "estimated_cost_usd": est, "watermarked": route_info["watermarked"],
        "within_spend_cap": within_cap, "spend_cap_usd": cap,
        "note": "Plan only — no provider is contacted, nothing is generated, no credits are spent.",
    }
