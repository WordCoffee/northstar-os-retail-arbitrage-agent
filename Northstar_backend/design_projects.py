"""Small helpers over the existing Design Studio project store.

There is already a project table (`db.design_studio.projects`, `ds_projects`) with create / get /
list / update. The canvas did not use it, so a design lived only in one browser's storage. These
helpers keep the read side in one place for Bojo's `read_open_design` tool and for anything else
that needs "the design the seller has open" without re-deriving the query.

`newest_canvas_project` is the definition of "open": the studio autosaves on every edit, so the most
recently updated canvas row is the one on screen. The tool names the project id it read, so the
answer is checkable rather than inferred.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

CANVAS_SECTION = "canvas"


def newest_canvas_project(db: Any, *, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    rows = db.design_studio.projects.list_by_section(
        section=CANVAS_SECTION, account_id=account_id, limit=1)
    return rows[0] if rows else None


def project_design(project: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The stored design payload, whether `metadata` came back as a dict or a JSON string."""
    if not isinstance(project, dict):
        return None
    meta = project.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            return None
    if not isinstance(meta, dict):
        return None
    design = meta.get("design")
    if isinstance(design, str):
        try:
            design = json.loads(design)
        except ValueError:
            return None
    return design if isinstance(design, dict) else None


__all__ = ["CANVAS_SECTION", "newest_canvas_project", "project_design"]
