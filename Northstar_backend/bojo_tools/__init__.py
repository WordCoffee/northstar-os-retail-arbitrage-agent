"""In-process tools that Bojo (the Master Brain assistant) may call.

Each module in this package exposes plain functions with typed signatures and
JSON-serialisable results, plus a ``TOOLS`` dict mapping tool name -> function.
Bojo's surface registry (``chat_tools``) is wired to these by the Director; this
package deliberately does not import ``chat_tools`` so the dependency runs one
way only.

Result contract::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<human-readable reason>"}

Business failures (empty catalog, nothing above threshold, dependency error)
are returned as ``ok=False``; programmer errors in the caller's arguments raise.
"""

from __future__ import annotations

from .sourcing import TOOLS, catalog_pull, golden_goose_scan

__all__ = ["TOOLS", "catalog_pull", "golden_goose_scan"]
