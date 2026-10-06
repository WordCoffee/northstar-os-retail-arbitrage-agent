"""Northstar reusable image/text generation lane.

Two halves that must never be confused:

1. **Scene lane** (``comfy_client``) — a local Qwen/FLUX image model generates
   or edits the visual scene. It is *not* the source of truth for text.
2. **Exact-text lane** (``exact_text``) — a deterministic compositor draws the
   final brand copy, product name, descriptor, net weight, CTA, etc.

``presets`` holds reusable brand/container/product/surface definitions and
``mogra_mockup`` wires the two lanes into one pipeline. ``routes`` exposes it
over ``/api/creative/*`` for any Northstar service or UI.

See ``docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md`` for the standard.
"""

from __future__ import annotations

__all__ = [
    "presets",
    "exact_text",
    "comfy_client",
    "mogra_mockup",
    "routes",
]

__version__ = "1.0.0"
