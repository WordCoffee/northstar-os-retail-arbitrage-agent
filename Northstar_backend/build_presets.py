"""BUILD presets (Thorn v5.0 §User Work Presets) — additive, never a replacement.

The plan names four presets: **Product Design, Coding, System Architecture, General
Chat**. This product's operator-facing surface is retail ops, and its six focus
modes (auto/create/grow/research/operate/autothink) are the WORK presets.

So the Thorn presets are added as a separate **BUILD family** — the brain working
on its own materials, its own code and its own architecture — which is what the
reconciliation recommended and which is the only framing in which "recursive
self-improvement" is coherent for this product.

They are deliberately **not** pushed into `shell_focus.FOCUS_MODES`: the V3 shell
gate asserts exactly six focus chips, and a preset is not a room. A preset is a
bundle of (system addendum, tool subset, memory retention, model family) that a
surface may adopt. Exposure is read-only, here and through the `build_preset`
chat tool.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import chat_tools  # noqa: E402

RETENTIONS = ("session", "project", "global")
FAMILIES = ("local", "cloud", "auto")

PRESETS: Dict[str, Dict[str, Any]] = {
    "product_design": {
        "label": "Product Design",
        "blurb": "UX/UI topology, design-system consistency, layout synthesis, user journeys.",
        "addendum": (
            "You are in the Product Design preset. Work on the design system as a system: "
            "name the tokens and components you are changing, keep layout synthesis "
            "dimension-true, and state the user journey each change serves. Never invent a "
            "colour, font or measurement — read them from the design tokens or say they are "
            "unknown."
        ),
        "tools": ["system_status", "design_brief", "create_dieline", "list_templates",
                  "generate_image", "voice_tts"],
        "memory_retention": "project",
        "model_family": "auto",
    },
    "coding": {
        "label": "Coding",
        "blurb": "Deterministic logic, static analysis, tests, repository-wide refactors.",
        "addendum": (
            "You are in the Coding preset. Prefer deterministic transformations over prose. "
            "Read the tree before claiming anything about it (purpose_command parses it). "
            "Propose changes as diffs with the failing test that would catch a regression. "
            "Never claim a change is verified unless a gate actually ran and passed."
        ),
        "tools": ["system_status", "purpose_command"],
        "memory_retention": "project",
        "model_family": "local",
    },
    "system_architecture": {
        "label": "System Architecture",
        "blurb": "Coupling, interfaces, threat modelling, latency and topology planning.",
        "addendum": (
            "You are in the System Architecture preset. Argue from measured structure — "
            "import edges, cycle membership, fan-in/fan-out — not from intuition. Separate "
            "what is measured from what is inferred, and name the trade-off each option "
            "buys. A threat you cannot point at in the code is a hypothesis, and must be "
            "labelled one."
        ),
        "tools": ["system_status", "purpose_command"],
        "memory_retention": "global",
        "model_family": "auto",
    },
    "general_chat": {
        "label": "General Chat",
        "blurb": "Low-latency conversation on the local lane.",
        "addendum": (
            "You are in the General Chat preset. Answer briefly on the local lane. If the "
            "question needs live data you do not have, say so plainly instead of guessing."
        ),
        "tools": ["system_status"],
        "memory_retention": "session",
        "model_family": "local",
    },
}

# AutothinK's router already classifies a task into a track; map those tracks onto
# BUILD presets so the two catalogues cannot drift apart silently.
TRACK_PRESETS = {
    "build": "coding",
    "code": "coding",
    "research": "system_architecture",
    "design": "product_design",
    "chat": "general_chat",
}


def preset_ids() -> List[str]:
    return sorted(PRESETS)


def resolve(preset_id: str) -> Dict[str, Any]:
    """Validate a preset, filtering its tools against what is actually registered."""
    spec = PRESETS.get(preset_id)
    if spec is None:
        return {"ok": False, "error": f"unknown preset {preset_id!r}", "known": preset_ids()}
    tools = [t for t in spec["tools"] if t in chat_tools.TOOLS]
    return {
        "ok": True,
        "id": preset_id,
        "label": spec["label"],
        "blurb": spec["blurb"],
        "system_addendum": spec["addendum"],
        "tools": tools,
        "tools_available": sorted(chat_tools.TOOLS),
        "memory_retention": spec["memory_retention"],
        "model_family": spec["model_family"],
        "family": "build",
    }


def for_track(track: Optional[str]) -> Dict[str, Any]:
    """Map an AutothinK router track onto a BUILD preset (falls back to general_chat)."""
    key = str(track or "").lower()
    pid = TRACK_PRESETS.get(key, "general_chat")
    out = resolve(pid)
    out["track"] = key or None
    out["mapped_from_track"] = pid if key in TRACK_PRESETS else None
    return out


def catalogue() -> Dict[str, Any]:
    """The whole BUILD family, for a surface that wants to offer it."""
    return {
        "family": "build",
        "presets": [resolve(p) for p in preset_ids()],
        "note": ("BUILD presets are separate from the six WORK focus modes: they shape the "
                 "brain's own work (design system, code, architecture) and do not replace "
                 "the operator's retail-ops foci."),
    }
