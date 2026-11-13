"""Bojo tools for the open design.

The studio's canvas is autosaved server-side into a project row (`section="canvas"`,
`metadata.design`). This tool is the read half: Bojo can say what the seller is looking at — the
design name, its size, the layer list and the text it carries — without the seller pasting anything
into chat.

**Scope is the point.** A design is org-owned data. The tool reads the project the caller names, or
the newest canvas project **for the caller's organisation**, and it refuses to answer without an
organisation rather than reading the most recent row in the database. The chat surface supplies
both from the verified session and the open tab's published canvas; a tool argument can never pick
another tenant.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _layers(design: Dict[str, Any]) -> List[Dict[str, Any]]:
    layers = design.get("layers")
    if not isinstance(layers, list):
        return []
    out = []
    for layer in layers[:40]:
        if not isinstance(layer, dict):
            continue
        row = {"id": layer.get("id"), "kind": layer.get("type") or layer.get("kind"),
               "name": layer.get("name")}
        text = layer.get("text")
        if isinstance(text, str) and text.strip():
            row["text"] = text.strip()[:200]
        out.append(row)
    return out


def _design_of(project: Dict[str, Any]) -> Dict[str, Any]:
    meta = project.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            return {}
    if not isinstance(meta, dict):
        return {}
    design = meta.get("design")
    if isinstance(design, str):
        try:
            design = json.loads(design)
        except ValueError:
            return {}
    return design if isinstance(design, dict) else {}


def read_open_design(account_id: Optional[str] = None,
                     project_id: Optional[str] = None) -> Dict[str, Any]:
    """The caller's design (named, or that org's newest canvas project), summarised."""
    if not account_id:
        return {"ok": False, "tool": "read_open_design",
                "reason": ("no organisation in the call context: refusing to read a design that "
                           "may belong to another account")}

    try:
        from data_layer import get_northstar_db
        from design_projects import project_design
    except Exception as exc:  # noqa: BLE001 - a missing store is a refusal, not a crash
        return {"ok": False, "tool": "read_open_design",
                "reason": f"design store unavailable: {type(exc).__name__}: {exc}"}

    try:
        db = get_northstar_db()
        if project_id:
            project = db.design_studio.projects.get_by_id(project_id, account_id=account_id)
            if not project:
                return {"ok": False, "tool": "read_open_design",
                        "reason": (f"no design {project_id!r} in this organisation: a project "
                                   "belongs to the account that saved it")}
        else:
            rows = db.design_studio.projects.list_by_section(
                section="canvas", account_id=account_id, limit=1)
            project = rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool": "read_open_design",
                "reason": f"could not read projects: {type(exc).__name__}: {exc}"}

    if not project:
        return {"ok": False, "tool": "read_open_design",
                "reason": "no canvas design has been saved in this organisation yet"}

    design = _design_of(project) or (project_design(project) or {})
    doc = design.get("doc") if isinstance(design.get("doc"), dict) else design
    size = ({"width": doc.get("width"), "height": doc.get("height")}
            if isinstance(doc, dict) else {})
    layers = _layers(doc if isinstance(doc, dict) else {})
    texts = [row["text"] for row in layers if row.get("text")]
    summary = (f'"{project.get("name") or "untitled"}" — {size.get("width")}x{size.get("height")}, '
               f'{len(layers)} layer(s)' + (f'; text: {texts[0][:60]}' if texts else ""))
    return {"ok": True, "tool": "read_open_design",
            "data": {"project_id": project.get("id"), "name": project.get("name"),
                     "section": project.get("section"), "size": size,
                     "layers": layers, "text_count": len(texts),
                     "updated_at": project.get("updated_at") or project.get("created_at")},
            "summary": summary}


TOOLS = {"read_open_design": read_open_design}

__all__ = ["TOOLS", "read_open_design"]
