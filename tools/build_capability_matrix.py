"""Build the acceptance capability matrix (denominator) from the real sources.

Sources of truth, not guesses:
  • SPA routes            northstar-os-ui/src/App.jsx  (<Route path=... element={...}>)
  • nav visibility        App.jsx NAV_GROUPS labels
  • chat tools            Northstar_backend/chat_tools.py  (TOOLS registry)
  • backend service APIs  Northstar_backend/main.py  (include_router calls)

Writes reports/northstar_acceptance_20261023/capability_matrix.{json,csv}
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "northstar-os-ui" / "src" / "App.jsx"
BACKEND = ROOT / "Northstar_backend"
OUT = ROOT / "reports" / "northstar_acceptance_20261023"

sys.path.insert(0, str(BACKEND))


def spa_routes() -> list[dict]:
    src = UI.read_text(encoding="utf-8")
    rows = []
    for m in re.finditer(r'<Route\s+path="([^"]*)"\s+element=\{<(.+?)\s*/>\}', src):
        rows.append({"route": m.group(1) or "/", "component": m.group(2)})
    seen, out = set(), []
    for r in rows:
        key = (r["route"], r["component"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def nav_labels() -> list[str]:
    src = UI.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'label:\s*"([^"]+)"', src)))


def chat_tools() -> list[dict]:
    import chat_tools as ct
    out = []
    for name, spec in ct.TOOLS.items():
        out.append({"name": name,
                    "writes": name in {"generate_image", "apply_label", "create_dieline"},
                    "description": spec["description"][:160]})
    return out


def backend_routers() -> list[str]:
    src = (BACKEND / "main.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"from\s+(\w+)\s+import\s+router\s+as\s+\w+_router", src)))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    routes = spa_routes()
    tools = chat_tools()
    routers = backend_routers()
    labels = nav_labels()

    caps = []
    for i, r in enumerate(routes, 1):
        caps.append({
            "id": f"UI-{i:03d}",
            "kind": "ui_route",
            "name": r["component"],
            "route": r["route"],
            "surface": "spa",
            "expected": "renders for an authorized operator; primary controls respond",
            "status": "not_run",
        })
    for i, t in enumerate(tools, 1):
        caps.append({
            "id": f"TOOL-{i:03d}",
            "kind": "chat_tool",
            "name": t["name"],
            "route": "chat",
            "surface": "master_brain",
            "expected": "callable from chat; returns a truthful result",
            "risk": "writes" if t["writes"] else "read_only",
            "status": "not_run",
        })
    for i, r in enumerate(routers, 1):
        caps.append({
            "id": f"API-{i:03d}",
            "kind": "service_api",
            "name": r,
            "route": f"/api/* ({r})",
            "surface": "backend",
            "expected": "router mounted; endpoints answered under auth",
            "status": "not_run",
        })

    matrix = {
        "generated_at": "2026-10-23",
        "denominator": {
            "ui_routes": len(routes),
            "chat_tools": len(tools),
            "service_routers": len(routers),
            "total": len(caps),
        },
        "nav_labels": labels,
        "capabilities": caps,
    }
    (OUT / "capability_matrix.json").write_text(
        json.dumps(matrix, indent=2), encoding="utf-8")
    with (OUT / "capability_matrix.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "kind", "name", "route", "surface",
                                           "expected", "risk", "status"])
        w.writeheader()
        for c in caps:
            w.writerow({k: c.get(k, "") for k in w.fieldnames})
    print(json.dumps(matrix["denominator"], indent=2))
    print(f"routes={len(routes)} tools={len(tools)} routers={len(routers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
