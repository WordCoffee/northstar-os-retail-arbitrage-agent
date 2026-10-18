"""Focus modes for the V3 Simple shell — ONE definition, two consumers.

The Simple view is a single chat-first shell; a focus tells the Master Brain
which kind of task it is facing (create / grow / research / operate /
autothink) and restricts the tool set offered to the model. The catalogue lives
here so chat_router (tool subset enforcement) and shell_router (UI metadata +
capability gating) can never drift apart.

`tools=None` means "all registered tools". A list is filtered against
chat_tools.TOOLS at call time so an unregistered name can never be offered.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import chat_tools  # noqa: E402

FOCUS_MODES: List[Dict[str, Any]] = [
    {
        "id": "auto",
        "label": "Auto",
        "blurb": "The Master Brain routes by intent across every service.",
        "tools": None,
        "requires": None,
        "suggestions": [
            "What should I focus on today across my brands?",
            "Show status of the local engine and what is ready to run.",
            "Draft a plan for launching a new supplement SKU end to end.",
        ],
    },
    {
        "id": "create",
        "label": "Create",
        "blurb": "Packaging, product photos, listing images, ad creative.",
        "tools": ["list_templates", "design_brief", "create_dieline", "generate_image"],
        "requires": None,
        "suggestions": [
            "Draft three directions for a Lion's Mane pouch — kraft, botanical, premium shelf.",
            "Build a stand-up pouch dieline for a 6 oz powder.",
            "Give me a shot list for a warm-linen product photo of a stand-up pouch.",
        ],
    },
    {
        "id": "grow",
        "label": "Grow",
        "blurb": "Listings, keywords, ads and search visibility.",
        "tools": ["system_status", "design_brief", "seo_check"],
        "requires": None,
        "suggestions": [
            "SEO-check my latest listing revision and flag the gaps.",
            "Draft a title for a 53-card affirmation deck aimed at career gifting.",
            "What keyword gaps should I test next on the mushroom powder listing?",
        ],
    },
    {
        "id": "research",
        "label": "Research",
        "blurb": "Sourcing, competitors, market and provider reads.",
        "tools": ["system_status", "list_templates"],
        "requires": None,
        "suggestions": [
            "Summarize the state of my sourcing pipeline and what needs data.",
            "List the dieline templates available for a new carton test.",
        ],
    },
    {
        "id": "operate",
        "label": "Operate",
        "blurb": "Inventory, profitability, monitoring and account health.",
        "tools": ["system_status"],
        "requires": None,
        "suggestions": [
            "Give me a portfolio posture summary — what is known vs unknown.",
            "Which operating reports are waiting on data imports?",
        ],
    },
    {
        "id": "autothink",
        "label": "AutothinK",
        "blurb": "Premium build-anything workspace: agents, tools, files.",
        "tools": None,
        "requires": "autothink_workspace",
        "suggestions": [
            "Design and run an end-to-end playbook for a new product launch.",
            "Build me a weekly operating report across all brands.",
        ],
    },
]

FOCUS_PROMPTS: Dict[str, str] = {
    "auto": "No fixed focus — route by the operator's intent across the whole suite.",
    "create": ("Focus: creative production — packaging, dielines, product "
               "photography, listing images, ad creative."),
    "grow": ("Focus: growth — listing copy, keywords, SEO, ads and search "
             "visibility. Use the seo_check tool for real listing revisions."),
    "research": "Focus: research — sourcing, competitors, market and provider reads.",
    "operate": "Focus: operations — inventory, profitability, monitoring, account health.",
    "autothink": ("Focus: AutothinK workspace — build-anything agent runs, files, "
                  "and multi-step plans."),
}

VALID_FOCUS_IDS = tuple(f["id"] for f in FOCUS_MODES)


def focus_by_id(focus_id: Optional[str]) -> Dict[str, Any]:
    for f in FOCUS_MODES:
        if f["id"] == focus_id:
            return f
    return FOCUS_MODES[0]


def tools_for_focus(focus_id: Optional[str]) -> Optional[List[str]]:
    """Tool subset for a focus (None = all registered tools)."""
    tool_list = focus_by_id(focus_id).get("tools")
    if tool_list is None:
        return None
    return [t for t in tool_list if t in chat_tools.TOOLS]
