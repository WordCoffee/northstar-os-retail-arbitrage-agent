"""TaskRouter — deterministic classification + execution-plan selection for
AutoThink commands.

Reuses the Master Brain Gateway classifier (master_brain_gateway.classify_task)
so AutoThink and Northstar OS agree on what kind of work a command is, then maps
the class to an execution plan label and a human-readable plan. Pure and
deterministic — zero network, zero LLM.
"""

import sys
import os
from typing import Dict, List, Optional

# Master brain gateway lives in Northstar_backend/. Make it importable without
# forcing a sys.path mutation that would shadow unrelated modules.
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Northstar_backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

try:
    from master_brain_gateway import classify_task as _mbg_classify, write_audit_entry, TRACKS

    _GATEWAY_AVAILABLE = True
    _VALID_TRACKS = TRACKS
except ImportError:  # pragma: no cover - fallback if backend layout changes
    _GATEWAY_AVAILABLE = False
    _VALID_TRACKS = (
        "AUTOTHINK_RESEARCH",
        "AUTOTHINK_CODE",
        "AUTOTHINK_COMPUTER",
        "NORTHSTAR_OS_COMMERCE",
        "NORTHSTAR_OS_PROVIDER",
        "T2_OPERATIONS",
        "PLATFORM_ADMIN",
    )

    def _mbg_classify(task: str) -> str:
        return "AUTOTHINK_RESEARCH"

    def write_audit_entry(*_args, **_kwargs):  # type: ignore
        return None


_PLAN_TEMPLATES = {
    "AUTOTHINK_RESEARCH": {
        "label": "research",
        "plan": ["Classify intent", "Gather available local data", "Reason step-by-step", "Deliver findings"],
    },
    "AUTOTHINK_CODE": {
        "label": "build",
        "plan": ["Classify intent", "Inspect relevant code paths", "Implement change", "Run offline tests"],
    },
    "AUTOTHINK_COMPUTER": {
        "label": "operate",
        "plan": ["Classify intent", "Dry-run command", "Execute (autonomous zone only)", "Report result"],
    },
    "NORTHSTAR_OS_COMMERCE": {
        "label": "analyze",
        "plan": ["Classify intent", "Pull cached product data", "Apply thresholds", "Rank opportunities"],
    },
    "GENERAL_QUERY": {
        "label": "general",
        "plan": ["Classify intent", "Answer from model knowledge"],
    },
}


def route_task(task: str) -> Dict:
    """Return execution plan metadata for a task string."""
    task_cls = _mbg_classify(task) if _GATEWAY_AVAILABLE else "AUTOTHINK_RESEARCH"
    plan = _PLAN_TEMPLATES.get(task_cls, _PLAN_TEMPLATES["GENERAL_QUERY"])
    return {
        "task_class": task_cls,
        "label": plan["label"],
        "plan": plan["plan"],
        "gateway_backend": _GATEWAY_AVAILABLE,
    }


def build_context(task: str, route: Dict, data_sources: Optional[List[str]] = None) -> Dict:
    """Assemble the context bundle sent to the LLM adapter."""
    return {
        "task": task,
        "task_class": route["task_class"],
        "plan": route["plan"],
        "data_sources": data_sources or [],
    }


def audit(entry: Dict, log_path: Optional[str] = None) -> None:
    """Persist an append-only audit entry (never overwritten)."""
    if not entry or not _GATEWAY_AVAILABLE:
        return
    track = entry.get("track") or entry.get("task_class") or "AUTOTHINK_RESEARCH"
    if track not in _VALID_TRACKS:
        track = "AUTOTHINK_RESEARCH"
    scoped = {k: v for k, v in entry.items()}
    write_audit_entry(
        track,
        files_touched=scoped.pop("files_touched", None) or [],
        live_action_requested=bool(scoped.pop("live_action_requested", False)),
        approval_status=scoped.pop("approval_status", "not_requested"),
        metadata=scoped,
        log_path=log_path,
    )