"""Structure before pixels: the UI Automation tree, and finding things in it.

Work order §5.1 layer 2. Structure is faster, cheaper and more reliable than vision, so
it is the primary read. Pixels are the fallback for what the tree cannot describe
(canvas apps, games, images, custom-drawn UI).

Every element carries `mask` from the privacy layer: a password or payment field is
identified by role, and its value is never returned.

    from vision.tree import window_tree, find
    elements = window_tree(hwnd)
    field = find(elements, "Search")
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import privacy

#: UIA control types that are worth keeping when a tree is flattened for a model. The
#: full tree is thousands of nodes on a real app; these are the ones a person can act on.
INTERACTIVE_ROLES = {
    "ButtonControl", "EditControl", "ComboBoxControl", "CheckBoxControl",
    "RadioButtonControl", "HyperlinkControl", "MenuItemControl", "TabItemControl",
    "ListItemControl", "TreeItemControl", "SliderControl", "DocumentControl",
    "TextControl", "WindowControl", "PaneControl", "GroupControl",
}


def _safe(call, default=None):
    try:
        return call()
    except Exception:  # noqa: BLE001 - a dead UIA node is data, not a crash
        return default


def _element(node, depth: int) -> Dict[str, Any]:
    rect = _safe(lambda: node.BoundingRectangle, None)
    return {
        "role": _safe(lambda: node.ControlTypeName, "") or "",
        "name": _safe(lambda: node.Name, "") or "",
        "value": _safe(lambda: node.GetValuePattern().Value, "") or "",
        "automation_id": _safe(lambda: node.AutomationId, "") or "",
        "class": _safe(lambda: node.ClassName, "") or "",
        "enabled": bool(_safe(lambda: node.IsEnabled, False)),
        "offscreen": bool(_safe(lambda: node.IsOffscreen, True)),
        "depth": depth,
        "rect": ([rect.left, rect.top, rect.right, rect.bottom]
                 if rect is not None else None),
    }


def walk(node, depth: int = 0, max_depth: int = 6, max_nodes: int = 400) -> List[Dict[str, Any]]:
    """Flatten a UIA subtree into interactive elements, breadth-first and bounded."""
    out: List[Dict[str, Any]] = []

    def visit(current, level: int) -> None:
        if len(out) >= max_nodes or level > max_depth:
            return
        entry = _element(current, level)
        if entry["role"] in INTERACTIVE_ROLES and not entry["offscreen"]:
            out.append(entry)
        children = _safe(lambda: current.GetChildren(), []) or []
        for child in children:
            visit(child, level + 1)
            if len(out) >= max_nodes:
                return

    visit(node, depth)
    return out


def window_tree(hwnd: Optional[int] = None, title_hint: str = "") -> Dict[str, Any]:
    """The interactive tree for one window, or for the window whose title matches."""
    try:
        import uiautomation as auto  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"uiautomation unavailable: {exc}", "elements": []}

    target = None
    try:
        if hwnd:
            target = auto.ControlFromHandle(int(hwnd))
        elif title_hint:
            for window in auto.GetRootControl().GetChildren():
                name = _safe(lambda: window.Name, "") or ""
                if title_hint.casefold() in name.casefold():
                    target = window
                    break
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "elements": []}
    if target is None:
        return {"ok": False, "error": "window not found", "elements": []}

    elements = walk(target)
    policy = privacy.classify(title=_safe(lambda: target.Name, "") or "", process="")
    if not policy["allow"]:
        # The window itself is refused, so its structure is refused too: element names
        # and values are content, and a blocklisted window's content is not ours to read.
        return {"ok": False, "blocked": True, "reason": policy["reason"], "elements": []}
    return {"ok": True, "blocked": False, "count": len(elements),
            "elements": privacy.mask_regions(elements)}


def find(elements: List[Dict[str, Any]], needle: str, *, role: str = "") -> Optional[Dict[str, Any]]:
    """First element matching `needle` by name, value or automation id.

    Name first, then automation id, then a substring of either: a native control often has
    an empty name and its identity lives in `AutomationId`, which is exactly what a caller
    who knows the app would search for.
    """
    low = str(needle).casefold()
    candidates = [e for e in elements or ()
                  if not role or str(e.get("role", "")).casefold() == role.casefold()]
    for element in candidates:
        if str(element.get("name", "")).casefold() == low:
            return element
    for element in candidates:
        if str(element.get("automation_id", "")).casefold() == low:
            return element
    for element in candidates:
        haystack = " ".join(str(element.get(key, "")) for key in ("name", "value",
                                                                  "automation_id"))
        if low in haystack.casefold():
            return element
    return None


def describe(elements: List[Dict[str, Any]], limit: int = 60) -> str:
    """A text-only rendering for a cloud model. Masked values never appear."""
    lines = []
    for element in (elements or [])[:limit]:
        value = "" if element.get("mask") else privacy.redact(str(element.get("value") or ""))
        name = privacy.redact(str(element.get("name") or ""))
        lines.append(f"{element.get('role', '?')}: {name}"
                     + (f" = {value}" if value else "")
                     + (" [masked]" if element.get("mask") else ""))
    return "\n".join(lines)
