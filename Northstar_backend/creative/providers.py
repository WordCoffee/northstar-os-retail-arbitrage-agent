"""Media provider readiness + capability policy (local *and* cloud).

Presence-only and honest: it never reads, prints, or returns a secret value — it
reports whether the *named* key is configured. Local (ComfyUI) and cloud
(fal / OpenRouter / Replicate) lanes are both first-class; each is used only when
configured/armed.

Arming:
* ``MEDIA_GEN_LIVE=1``            arms media generation (local + cloud finals).
* ``NORTHSTAR_SOCIAL_PUBLISH_ARMED=1``  arms the social publishing write path.
* ``NORTHSTAR_ADS_WRITE_ARMED=1``       arms the ads write path.

Even when armed, real money / public exposure is surfaced as a per-action
approval (see ``write_policy``), never executed silently.
"""

from __future__ import annotations

import os
from typing import Any, Dict

CLOUD_PROVIDERS: Dict[str, Dict[str, str]] = {
    "fal": {"env": "FAL_KEY", "role": "image + video generation (primary)"},
    "openrouter": {"env": "OPENROUTER_API_KEY", "role": "text + vision + GPT Image 2"},
    "replicate": {"env": "REPLICATE_API_TOKEN", "role": "FLUX.2 pro/edit mirror"},
}


def _env(name: str) -> str:
    return str(os.environ.get(name, "") or "").strip()


def key_present(env_name: str) -> bool:
    return bool(_env(env_name))


def flag(name: str) -> bool:
    return _env(name) == "1"


def media_live_armed() -> bool:
    return flag("MEDIA_GEN_LIVE")


def cloud_armed(provider: str) -> bool:
    cfg = CLOUD_PROVIDERS.get((provider or "").lower())
    return bool(cfg and key_present(cfg["env"]) and media_live_armed())


def local_status(*, probe: bool = True) -> Dict[str, Any]:
    from . import comfy_client
    if not probe:
        m = comfy_client.resolve_models(None)
        return {"kind": "comfyui", "url": m["comfyui_url"], "up": m["comfy_up"],
                "qwen_ready": m["qwen_ready"], "qwen_edit_ready": m["qwen_edit_ready"]}
    try:
        client = comfy_client.ComfyClient(timeout=1.5)
        m = comfy_client.resolve_models(client)
        return {"kind": "comfyui", "url": m["comfyui_url"], "up": m["comfy_up"],
                "gguf_node": m["gguf_node"], "qwen_ready": m["qwen_ready"],
                "qwen_edit_ready": m["qwen_edit_ready"],
                "clip": m["clip"], "vae": m["vae"]}
    except Exception as exc:  # pragma: no cover - defensive
        return {"kind": "comfyui", "up": False, "error": str(exc)[:160]}


def cloud_status() -> Dict[str, Any]:
    return {
        name: {"key_env": cfg["env"], "present": key_present(cfg["env"]),
               "role": cfg["role"], "armed": cloud_armed(name)}
        for name, cfg in CLOUD_PROVIDERS.items()
    }


def write_policy() -> Dict[str, Any]:
    """Write-action posture. Armed via env; real spend/exposure needs approval."""
    return {
        "publishing": {
            "env": "NORTHSTAR_SOCIAL_PUBLISH_ARMED",
            "armed": flag("NORTHSTAR_SOCIAL_PUBLISH_ARMED"),
            "requires_approval": True,
            "approval_kind": "public_exposure",
        },
        "ad_spend": {
            "env": "NORTHSTAR_ADS_WRITE_ARMED",
            "armed": flag("NORTHSTAR_ADS_WRITE_ARMED"),
            "requires_approval": True,
            "approval_kind": "real_money",
        },
    }


def provider_status(*, probe_local: bool = True) -> Dict[str, Any]:
    return {
        "media_live_armed": media_live_armed(),
        "local": local_status(probe=probe_local),
        "cloud": cloud_status(),
        "write": write_policy(),
    }


def policy() -> Dict[str, Any]:
    return {
        "prefer": "local",
        "allow_cloud": True,
        "media_live_armed": media_live_armed(),
        "video_in_scope": True,
        "write": write_policy(),
        "note": (
            "Local + cloud lanes are both available; cloud and write actions are "
            "armed only via explicit env flags, and real-money/public actions still "
            "require a fresh per-action operator approval."
        ),
    }
