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

from .campaigns import TOOLS as _CAMPAIGN_TOOLS
from .campaigns import plan_campaign
from .competitors import TOOLS as _COMPETITOR_TOOLS
from .competitors import watch_competitor
from .economics import TOOLS as _ECONOMICS_TOOLS
from .economics import margin_report
from .keywords import TOOLS as _KEYWORD_TOOLS
from .keywords import track_keywords
from .publishing import TOOLS as _PUBLISHING_TOOLS
from .publishing import build_dieline, compose_listing
from .research_toolkit import TOOLS as _RESEARCH_TOOLKIT_TOOLS
from .research_toolkit import (find_reference_media, generate_api_client,
                               propose_improvements, route_local_model)
from .sourcing import TOOLS as _SOURCING_TOOLS
from .sourcing import catalog_pull, golden_goose_scan
from .sourcing_extra import TOOLS as _SOURCING_EXTRA_TOOLS
from .sourcing_extra import scan_products

#: Every handler in this package, keyed by tool name. The registry loads each
#: module's own ``TOOLS`` dict, so this is only a convenience for callers that
#: already hold the package.
TOOLS = {
    **_SOURCING_TOOLS,
    **_SOURCING_EXTRA_TOOLS,
    **_PUBLISHING_TOOLS,
    **_KEYWORD_TOOLS,
    **_COMPETITOR_TOOLS,
    **_ECONOMICS_TOOLS,
    **_CAMPAIGN_TOOLS,
    **_RESEARCH_TOOLKIT_TOOLS,
}

__all__ = [
    "TOOLS",
    "catalog_pull",
    "golden_goose_scan",
    "scan_products",
    "compose_listing",
    "build_dieline",
    "track_keywords",
    "watch_competitor",
    "margin_report",
    "plan_campaign",
    "generate_api_client",
    "find_reference_media",
    "propose_improvements",
    "route_local_model",
]
