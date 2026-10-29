"""Adaptive UI: a component tree generated from live agent state.

The UI is not hand-written per task. It is a **tree spec** built from the queue,
the lanes and the profile's habits, and the client renders it. That keeps the
personalisation rules testable here instead of buried in JSX.

Guarantees
----------
* ``render`` never raises. A partial or malformed state degrades to a complete
  tree with an explicit ``degraded`` alert — the interface never drops.
* Only whitelisted component types are emitted, so a client can switch on
  ``type`` without a fallback branch.
* Personalisation is deterministic: same state + same habits => same tree, with
  a ``version`` that only changes when the output changes.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

SCHEMA = "tys.ui.v1"

COMPONENT_TYPES = {
    "heading", "status_tiles", "table", "list", "alert", "action",
    "media_strip", "nav", "sparkline",
}

LANES = ("inspect", "coding", "browser", "creative")


def _component(kind: str, *, cid: Optional[str] = None, **props: Any) -> Dict[str, Any]:
    if kind not in COMPONENT_TYPES:
        raise ValueError(f"unknown component type {kind!r}")
    if cid is None:
        digest = hashlib.sha256(
            json.dumps(props, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:10]
        cid = f"{kind}-{digest}"
    return {"type": kind, "id": cid, **props}


def _safe(state: Any, *keys: str, default: Any = None) -> Any:
    current = state
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _habits(habits: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    habits = habits or {}
    lane_counts = habits.get("lane_counts") or {}
    actions = habits.get("actions") or {}
    return {
        "lane_counts": {lane: int(lane_counts.get(lane) or 0) for lane in LANES},
        "actions": {str(k): int(v or 0) for k, v in actions.items() if isinstance(v, (int, float))},
        "density": habits.get("density") if habits.get("density") in ("compact", "comfortable") else None,
        "pinned": [str(p) for p in (habits.get("pinned") or [])],
    }


def _lane_order(habit: Dict[str, Any]) -> List[str]:
    counts = habit["lane_counts"]
    return sorted(LANES, key=lambda lane: (-counts.get(lane, 0), LANES.index(lane)))


def _status_tiles(state: Dict[str, Any], habit: Dict[str, Any]) -> Dict[str, Any]:
    queue = _safe(state, "queue", default={}) or {}
    lanes = _safe(state, "lanes", default={}) or {}
    tiles = [
        {"label": "Queued", "value": int(queue.get("total") or 0),
         "tone": "neutral"},
        {"label": "Done", "value": int((queue.get("by_status") or {}).get("done") or 0),
         "tone": "good"},
        {"label": "Blocked", "value": int((queue.get("by_status") or {}).get("blocked") or 0),
         "tone": "bad"},
        {"label": "Lanes ready",
         "value": sum(1 for lane in LANES if (lanes.get(lane) or {}).get("available")),
         "tone": "neutral"},
    ]
    if habit["density"] == "compact":
        tiles = [tile for tile in tiles if tile["tone"] != "neutral"]
    return _component("status_tiles", cid="status-tiles", tiles=tiles,
                      density=habit["density"] or "comfortable")


def _queue_region(state: Dict[str, Any]) -> Dict[str, Any]:
    tasks = _safe(state, "tasks", default=None)
    if tasks is None:
        queue = _safe(state, "queue", default={}) or {}
        tasks = [{"id": tid, "status": status, "cursor": None}
                 for status, count in (queue.get("by_status") or {}).items()
                 for tid in [f"{status}:{count}"]]
    rows = []
    for task in tasks[:20]:
        rows.append({
            "id": str(task.get("id") or ""),
            "status": str(task.get("status") or "unknown"),
            "title": str(task.get("title") or "")[:80],
            "cursor": task.get("cursor"),
        })
    return _component("table", cid="queue-table", title="Queue",
                      columns=["id", "status", "title", "cursor"], rows=rows)


def _alerts_region(state: Dict[str, Any], storage: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    lanes = _safe(state, "lanes", default={}) or {}
    for lane in LANES:
        info = lanes.get(lane) or {}
        if info and not info.get("available"):
            alerts.append({"tone": "warn", "id": f"lane-{lane}",
                           "text": f"{lane} lane unavailable: {info.get('detail') or 'no detail'}"})
    blocked = int(((_safe(state, "queue", default={}) or {}).get("by_status") or {}).get("blocked") or 0)
    if blocked:
        alerts.append({"tone": "bad", "id": "blocked-tasks",
                       "text": f"{blocked} task(s) blocked and need attention"})
    if storage:
        pending = int(storage.get("pending_download_prompts") or 0)
        if pending:
            alerts.append({"tone": "warn", "id": "download-prompts",
                           "text": f"{pending} download prompt(s) awaiting the seller"})
    return alerts


def _actions_region(habit: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    base = [
        {"id": "submit-work-order", "label": "New work order"},
        {"id": "run-next", "label": "Run next task"},
        {"id": "drain", "label": "Drain queue"},
        {"id": "view-evidence", "label": "Evidence"},
    ]
    ranked = sorted(base, key=lambda a: -habit["actions"].get(a["id"], 0))
    if habit["pinned"]:
        pins = habit["pinned"]
        ranked = sorted(ranked, key=lambda a: (0 if a["id"] in pins else 1,
                                               -habit["actions"].get(a["id"], 0)))
    next_id = _safe(state, "queue", "next", default=None)
    return _component("action", cid="actions", actions=ranked[:4],
                      primary="run-next" if next_id else "submit-work-order")


def _media_region(storage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    storage = storage or {}
    items = [
        {"label": "Active bytes", "value": int(storage.get("active_bytes") or 0)},
        {"label": "Items", "value": int(storage.get("active_items") or 0)},
        {"label": "Profiles", "value": int(storage.get("profiles") or 0)},
    ]
    return _component("media_strip", cid="media-strip", items=items)


def build_tree(profile: str, state: Dict[str, Any],
               habits: Optional[Dict[str, Any]] = None,
               storage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    habit = _habits(habits)
    alerts = _alerts_region(state, storage)
    nav = [{"id": f"lane-{lane}", "label": lane.title(),
            "badge": int(habit["lane_counts"].get(lane, 0))}
           for lane in _lane_order(habit)]
    return {
        "schema": SCHEMA,
        "profile": profile,
        "generated_at": time.time(),
        "regions": {
            "header": _component("heading", cid="title",
                                 text=f"Tys Assistant — {profile}"),
            "status": _status_tiles(state, habit),
            "nav": _component("nav", cid="lane-nav", items=nav),
            "queue": _queue_region(state),
            "alerts": _component("alert", cid="alerts", alerts=alerts) if alerts
                      else _component("alert", cid="alerts", alerts=[]),
            "actions": _actions_region(habit, state),
            "media": _media_region(storage),
        },
        "degraded": False,
    }


def render(profile: str, state: Dict[str, Any],
           habits: Optional[Dict[str, Any]] = None,
           storage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Always returns a complete, validated tree. Never raises."""
    try:
        tree = build_tree(profile, state or {}, habits, storage)
        problems = validate_tree(tree)
        if problems:
            raise ValueError("; ".join(problems))
    except Exception as exc:
        tree = build_tree(profile, {}, None, storage)
        tree["degraded"] = True
        tree["regions"]["alerts"]["alerts"] = [{
            "tone": "bad", "id": "render-degraded",
            "text": f"Adaptive render degraded: {type(exc).__name__}: {exc}",
        }]
    tree["version"] = hashlib.sha256(
        json.dumps({k: v for k, v in tree.items() if k != "generated_at"},
                   sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return tree


def validate_tree(tree: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    if not isinstance(tree, dict) or tree.get("schema") != SCHEMA:
        return [f"schema must be {SCHEMA}"]
    regions = tree.get("regions")
    if not isinstance(regions, dict) or not regions:
        return ["regions missing"]
    ids: set = set()
    for name, component in regions.items():
        if not isinstance(component, dict):
            problems.append(f"region {name} is not a component")
            continue
        if component.get("type") not in COMPONENT_TYPES:
            problems.append(f"region {name} has unknown type {component.get('type')!r}")
        cid = component.get("id")
        if not cid or cid in ids:
            problems.append(f"region {name} has missing/duplicate id {cid!r}")
        ids.add(cid)
    return problems


def diff(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> Dict[str, Any]:
    """Which regions changed. Used to prove the UI updates without a reload."""
    if not previous:
        return {"changed": list((current.get("regions") or {}).keys()),
                "dropped": [], "version": current.get("version")}
    before = previous.get("regions") or {}
    after = current.get("regions") or {}
    changed = [name for name in after
               if json.dumps(before.get(name), sort_keys=True, default=str)
               != json.dumps(after.get(name), sort_keys=True, default=str)]
    dropped = [name for name in before if name not in after]
    return {"changed": changed, "dropped": dropped,
            "version": current.get("version")}
