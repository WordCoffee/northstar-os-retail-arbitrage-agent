"""Bojo tools for the open design.

The studio's canvas is autosaved server-side into a project row (`section="canvas"`,
`metadata.design`). This tool is the read half: Bojo can say what the seller is looking at —
the design name, its size, the layer list and the text it carries — without the seller pasting
anything into chat.

The newest canvas project for the account is the open design, because the canvas autosaves on
every edit. That is stated rather than implied: a second studio tab is the same account's newest
row, so the answer names the project it read.
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


def read_open_design(account_id: Optional[str] = None) -> Dict[str, Any]:
    """The newest canvas project, summarised. Answers a dict, never raises."""
    try:
        from data_layer import get_northstar_db
        from design_projects import newest_canvas_project, project_design
    except Exception as exc:  # noqa: BLE001 - a missing store is a refusal, not a crash
        return {"ok": False, "tool": "read_open_design",
                "reason": f"design store unavailable: {type(exc).__name__}: {exc}"}

    try:
        db = get_northstar_db()
        project = newest_canvas_project(db, account_id=account_id)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool": "read_open_design",
                "reason": f"could not read projects: {type(exc).__name__}: {exc}"}

    if not project:
        return {"ok": False, "tool": "read_open_design",
                "reason": "no canvas design has been saved yet, so there is nothing open to read"}

    design = project_design(project) or {}
    doc = design.get("doc") if isinstance(design.get("doc"), dict) else design
    meta = project.get("metadata") if isinstance(project.get("metadata"), str) else None
    if meta:
        try:
            parsed = json.loads(meta)
            design = parsed.get("design") or design
            doc = design.get("doc") if isinstance(design.get("doc"), dict) else design
        except ValueError:
            pass

    size = {"width": doc.get("width"), "height": doc.get("height")} if isinstance(doc, dict) else {}
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
