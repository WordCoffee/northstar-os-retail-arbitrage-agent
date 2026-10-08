"""Capability-based routing for the shared creative pipeline.

The router answers one question: *given a requested capability, quality mode,
references and the approved-component registry, which lane should run, and what
is the explicit fallback chain?* It never silently falls back and never routes a
quarantined (non-commercial) component for production output.

Modes
-----
* ``draft``    — fastest acceptable: Z-Image-Turbo (8 steps, CFG 1) if present,
                 else SDXL at low steps, else the existing Qwen lane.
* ``standard`` — balanced: SDXL Base 1.0 (25 steps, CFG 7) if present.
* ``high``     — best local quality: existing Qwen-Image lane.

Every plan carries ``fallbacks`` (ordered, explicit) and ``quarantined`` (what was
deliberately excluded and why).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import registry

CAPABILITIES = [
    "generate", "edit", "inpaint", "condition", "mask", "upscale", "control", "compose_text",
]

MODES = ("draft", "standard", "high")

# Mode presets per family. width/height are the *defaults*; callers may override.
_FAMILY_PRESETS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "z-image": {
        "draft": {"steps": 8, "cfg": 1.0, "width": 1024, "height": 1024, "sampler": "euler", "scheduler": "simple"},
        "standard": {"steps": 8, "cfg": 1.0, "width": 1024, "height": 1024, "sampler": "euler", "scheduler": "simple"},
        "high": {"steps": 8, "cfg": 1.0, "width": 1024, "height": 1024, "sampler": "euler", "scheduler": "simple"},
    },
    "sdxl": {
        "draft": {"steps": 14, "cfg": 7.0, "width": 1024, "height": 1024, "sampler": "dpmpp_2m", "scheduler": "karras"},
        "standard": {"steps": 25, "cfg": 7.0, "width": 1024, "height": 1024, "sampler": "dpmpp_2m", "scheduler": "karras"},
        "high": {"steps": 32, "cfg": 7.0, "width": 1280, "height": 1280, "sampler": "dpmpp_2m", "scheduler": "karras"},
    },
    "qwen-image": {
        "draft": {"steps": 12, "cfg": 4.0, "width": 1024, "height": 1024, "sampler": "euler", "scheduler": "simple", "shift": 3.1},
        "standard": {"steps": 20, "cfg": 4.0, "width": 1024, "height": 1024, "sampler": "euler", "scheduler": "simple", "shift": 3.1},
        "high": {"steps": 30, "cfg": 4.0, "width": 1024, "height": 1024, "sampler": "euler", "scheduler": "simple", "shift": 3.1},
    },
}

# Ordered preference per capability+mode. Each entry is (lane_id, component_id, family).
#
# Design note (owner review pending): "high" is NOT "use Qwen". SDXL stays the
# provisional standard-generation candidate; "high" is SDXL at a larger size and
# step budget. Z-Image-Turbo is a separately selectable fast candidate. Qwen is
# routed by the *editing* capability (and by explicit opt-in), never as a generic
# quality label.
_PREFERENCE: Dict[str, Dict[str, List[tuple]]] = {
    "generate": {
        "draft": [("z-image-draft", "z-image-turbo", "z-image"),
                  ("sdxl-draft", "sdxl-base-1.0", "sdxl")],
        "standard": [("sdxl-standard", "sdxl-base-1.0", "sdxl"),
                     ("z-image-draft", "z-image-turbo", "z-image")],
        "high": [("sdxl-high", "sdxl-base-1.0", "sdxl"),
                 ("z-image-draft", "z-image-turbo", "z-image")],
    },
    "edit": {
        "draft": [("qwen-edit", "qwen-image-edit-2511", "qwen-image")],
        "standard": [("qwen-edit", "qwen-image-edit-2511", "qwen-image")],
        "high": [("qwen-edit", "qwen-image-edit-2511", "qwen-image")],
    },
    "inpaint": {
        "draft": [("sdxl-inpaint", "sdxl-base-1.0", "sdxl")],
        "standard": [("sdxl-inpaint", "sdxl-base-1.0", "sdxl")],
        "high": [("sdxl-inpaint", "sdxl-base-1.0", "sdxl")],
    },
}

# Installed, approved lanes that are available only by explicit request (`lane=`)
# or by their capability, never as an implicit default for a different capability.
_SELECTABLE: List[tuple] = [
    ("qwen-t2i", "qwen-image-2512", "qwen-image"),
]

_LANE_WORKFLOW = {
    "z-image-draft": "z_image_t2i",
    "sdxl-draft": "sdxl_t2i",
    "sdxl-standard": "sdxl_t2i",
    "sdxl-high": "sdxl_t2i",
    "sdxl-inpaint": "sdxl_inpaint",
    "qwen-t2i": "qwen_t2i",
    "qwen-edit": "qwen_edit",
}


def _runtime_ready(component_id: str) -> bool:
    comp = registry.component(component_id)
    if not comp or not registry.is_approved(comp):
        return False
    return registry.installed(comp)


def lane_presets(lane_id: str, mode: str) -> Dict[str, Any]:
    family = None
    for modes in _PREFERENCE.values():
        for chain in modes.values():
            for lid, _cid, fam in chain:
                if lid == lane_id:
                    family = fam
    if family is None:
        family = "qwen-image"
    return dict(_FAMILY_PRESETS.get(family, {}).get(mode, {}))


def _make_lane(lane_id: str, cid: str, family: str, mode: str,
               reasons: Optional[List[str]] = None) -> Dict[str, Any]:
    comp = registry.component(cid) or {}
    preset = lane_presets(lane_id, mode)
    return {
        "lane": lane_id,
        "component": cid,
        "family": family,
        "workflow": _LANE_WORKFLOW.get(lane_id),
        "mode": mode,
        "preset": preset,
        "model_file": comp.get("filename"),
        "model_path": comp.get("install_path"),
        "license": comp.get("license"),
        "commercial_use": comp.get("commercial_use"),
        "reasons": reasons or [],
    }


def route(capability: str, mode: str = "standard", *,
          has_reference: bool = False) -> Dict[str, Any]:
    """Return a routing plan with a primary lane and an explicit fallback chain."""
    capability = (capability or "generate").lower()
    mode = (mode or "standard").lower()
    if mode not in MODES:
        mode = "standard"

    if capability not in CAPABILITIES:
        return {"ok": False, "error": f"unknown capability: {capability}",
                "capabilities": CAPABILITIES}

    chain = _PREFERENCE.get(capability, {}).get(mode, [])
    if not chain:
        return {"ok": False, "error": f"no lanes for {capability}/{mode}"}

    available: List[Dict[str, Any]] = []
    unavailable: List[Dict[str, Any]] = []
    for lane_id, cid, family in chain:
        entry = _make_lane(lane_id, cid, family, mode)
        if _runtime_ready(cid):
            entry["reasons"].append("component installed + approved")
            available.append(entry)
        else:
            comp = registry.component(cid)
            entry["reasons"].append(
                "not installed" if comp else "not in registry")
            unavailable.append(entry)

    # ComfyUI must be up for the local diffusion lanes.
    comfy_up = _comfy_up()
    if not comfy_up:
        for e in available:
            e["reasons"].append("ComfyUI not reachable")

    explicit: List[Dict[str, Any]] = []
    for lane_id, cid, family in _SELECTABLE:
        if _runtime_ready(cid):
            e = _make_lane(lane_id, cid, family, mode)
            e["reasons"].append("explicit opt-in (lane=) only; not an implicit default")
            explicit.append(e)

    primary = available[0] if (available and comfy_up) else None
    plan = {
        "ok": bool(primary),
        "capability": capability,
        "mode": mode,
        "primary": primary,
        "fallbacks": available[1:] if primary else available,
        "explicit_lanes": explicit,
        "unavailable": unavailable,
        "quarantined": [
            {"id": c["id"], "license": c.get("license"),
             "reason": "non-commercial / not approved for production"}
            for c in registry.quarantined()
        ] if capability in ("generate", "edit") else [],
        "comfyui_up": comfy_up,
        "policy": {
            "no_silent_fallback": True,
            "heavy_concurrency": 1,
            "unload_between_stages": True,
        },
        "note": (
            "Fallbacks are explicit and ordered. A quarantined component is never "
            "used as a default; requesting it must be an explicit opt-in."
        ),
    }
    if not primary:
        plan["error"] = (
            "no approved, installed, reachable lane for "
            f"{capability}/{mode}. ComfyUI up={comfy_up}. "
            "Install an approved model or start ComfyUI."
        )
    return plan


def _comfy_up() -> bool:
    try:
        from . import comfy_client
        return comfy_client.ComfyClient(timeout=1.5).is_up()
    except Exception:
        return False


def capabilities() -> Dict[str, Any]:
    """Report each capability with its available approved lanes per mode."""
    out: Dict[str, Any] = {}
    for cap in CAPABILITIES:
        out[cap] = {m: route(cap, m) for m in MODES}
    return out


def lane_catalog() -> Dict[str, Any]:
    """Compact catalog of lanes and the components they depend on."""
    return {
        "modes": list(MODES),
        "capabilities": CAPABILITIES,
        "presets": _FAMILY_PRESETS,
        "preference": _PREFERENCE,
        "registry": registry.status(),
    }
