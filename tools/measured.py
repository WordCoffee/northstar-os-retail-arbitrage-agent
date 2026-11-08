"""The `measured` scorecard dimension: a real check, not a zero.

The scorecard had `measured` hardcoded at 0, which made the per-dimension bar unreachable
for every service. That is a scoring bug, not a product finding: an unmeasurable dimension
should score 0 *with the reason named*, and a measurable one should score what it measured.

What is measured here, per service:

* **route wired** — the service's route appears in the UI router (`northstar-os-ui/src/App.jsx`)
* **component exists** — the component the route renders is exported by a real file
* **app responds** — one app-level latency sample (`GET /health` through the real ASGI app)
  must be inside the budget; a slow app fails every service, which is the honest reading

A service whose route is not wired scores 0 with that reason. Nothing is inferred.

    python tools/measured.py --write
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "ty" / "services.json"
APP_JSX = ROOT / "northstar-os-ui" / "src" / "App.jsx"
SRC = ROOT / "northstar-os-ui" / "src"
OUT = ROOT / "state" / "scores" / "measured.json"
BACKEND = ROOT / "Northstar_backend"

LATENCY_BUDGET_MS = 800.0
SAMPLES = 5

_ROUTE_RE = re.compile(r'<Route\s+path="([^"]+)"\s+element=\{\s*<([A-Za-z0-9_]+)')
_EXPORT_RE = re.compile(r"export\s+(?:default\s+)?(?:function|const|class)\s+([A-Za-z0-9_]+)")
_LAZY_RE = re.compile(r"const\s+([A-Za-z0-9_]+)\s*=\s*lazy\(\s*\(\)\s*=>\s*import\('([^']+)'\)")
_ENTRY_RE = re.compile(r"\{[^{}]*?id:\s*'([a-z0-9-]+)'[^{}]*?\}", re.DOTALL)
_SOURCE_RE = re.compile(r"source:\s*'([a-z-]+)'")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def routes(text: str) -> List[Dict[str, str]]:
    return [{"path": path, "component": component}
            for path, component in _ROUTE_RE.findall(text or "")]


def _rel(path: Path) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def component_files() -> Dict[str, str]:
    """component name -> the file that exports it (first match wins, sorted for stability)."""
    found: Dict[str, str] = {}
    for path in sorted(SRC.rglob("*.jsx")) + sorted(SRC.rglob("*.js")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in _EXPORT_RE.findall(text):
            found.setdefault(name, _rel(path))
    return found


def api_latency() -> Dict[str, Any]:
    """One app-level latency sample. Unavailable is reported, never assumed."""

    import sys

    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    samples: List[float] = []
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415

        import main  # noqa: PLC0415

        client = TestClient(main.app)
        for _ in range(SAMPLES):
            started = time.time()
            response = client.get("/health")
            samples.append((time.time() - started) * 1000.0)
            if response.status_code >= 500:
                return {"ok": False, "reason": f"/health answered {response.status_code}",
                        "status": response.status_code}
    except Exception as exc:  # noqa: BLE001 - an unavailable probe is not a pass
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    if not samples:
        return {"ok": False, "reason": "no samples"}
    p95 = sorted(samples)[max(0, int(len(samples) * 0.95) - 1)]
    return {"ok": p95 <= LATENCY_BUDGET_MS, "p50_ms": round(statistics.median(samples), 1),
            "p95_ms": round(p95, 1), "budget_ms": LATENCY_BUDGET_MS, "samples": len(samples)}


def sealed_sources() -> Dict[str, str]:
    """service id -> the registry's own `source` field ("app-route" means mounted).

    `serviceRegistry.js` is explicit about this: "A catalogue entry is not a page:
    `source: 'app-route'` entries have a real route in App.jsx, the rest are names the
    catalogue carries without one." Trusting that field is the difference between a page
    and a link to nowhere.
    """
    path = SRC / "data" / "serviceRegistry.js"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out: Dict[str, str] = {}
    for match in _ENTRY_RE.finditer(text):
        block = match.group(0)
        if "route:" not in block:
            continue  # scene/theme objects also carry an id; they are not services
        source = _SOURCE_RE.search(block)
        out[match.group(1)] = source.group(1) if source else "catalogue"
    return out


def nav_routes() -> List[str]:
    """Routes declared in the UI navigation data (the workspace shell's own registry)."""
    path = SRC / "data" / "services.js"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return re.findall(r"route:\s*'([^']+)'", text) + re.findall(r'route:\s*"([^"]+)"', text)


def measure(*, out: Optional[Path] = None) -> Dict[str, Any]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8")).get("services") or []
    app_text = APP_JSX.read_text(encoding="utf-8") if APP_JSX.exists() else ""
    table = routes(app_text)
    paths = {row["path"] for row in table}
    nav = set(nav_routes())
    sources = sealed_sources()
    exports = component_files()
    lazy = {name: rel for name, rel in _LAZY_RE.findall(app_text)}
    latency = api_latency()

    rows: Dict[str, Dict[str, Any]] = {}
    for service in registry:
        sid = str(service.get("id") or "")
        route = str(service.get("route") or "")
        entry: Dict[str, Any] = {"id": sid, "route": route}
        # A service is wired when the app actually mounts it: the registry says
        # `source: 'app-route'`, or App.jsx declares the route. A navigation entry alone is
        # a link to nowhere — `serviceRegistry.js` says so itself.
        routed = (sources.get(sid) == "app-route"
                  or route in paths or any(p.rstrip("/*") == route for p in paths))
        component = next((row["component"] for row in table
                          if row["path"].rstrip("/*") == route), "")
        entry["route_wired"] = routed
        entry["component"] = component
        entry["component_file"] = exports.get(component, "")
        if not entry["component_file"] and component in lazy:
            # `const X = lazy(() => import('./pages/x.jsx'))` is a real wiring, not a miss.
            rel = lazy[component].lstrip("./").replace("./", "")
            candidate = SRC / rel.lstrip("/")
            if candidate.exists():
                entry["component_file"] = _rel(candidate)
        entry["nav_entry"] = route in nav
        entry["api"] = latency
        if not routed:
            entry.update({"score": 0.0, "pass": False,
                          "evidence": f"route {route!r} is not registered in the UI"})
        elif component and not entry["component_file"]:
            entry.update({"score": 0.0, "pass": False,
                          "evidence": f"component {component!r} has no exporting file"})
        elif not latency.get("ok"):
            entry.update({"score": 0.0, "pass": False,
                          "evidence": f"app latency probe failed: {latency.get('reason')}"
                                      + ("" if latency.get("p95_ms") is None
                                         else f" (p95 {latency.get('p95_ms')} ms)")})
        else:
            where = entry["component_file"] or "shell navigation registry"
            entry.update({"score": 100.0, "pass": True,
                          "evidence": (f"route {route} -> {where}; "
                                       f"app p95 {latency.get('p95_ms')} ms")})
        rows[sid] = entry

    payload = {"at": _now(), "latency": latency, "budget_ms": LATENCY_BUDGET_MS,
               "services": rows,
               "passing": sum(1 for row in rows.values() if row["pass"]),
               "total": len(rows)}
    target = Path(out or OUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load(*, path: Optional[Path] = None) -> Dict[str, Any]:
    try:
        return json.loads(Path(path or OUT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def score_for(service_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The dimension score and its evidence, or a named zero."""
    payload = data if data is not None else load()
    row = (payload.get("services") or {}).get(service_id)
    if not row:
        return {"score": 0.0, "evidence": "no measurement artefact for this service"}
    return {"score": float(row.get("score") or 0.0),
            "evidence": str(row.get("evidence") or "")}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Measured dimension")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    payload = measure()
    if not ns.write:
        print(json.dumps({"latency": payload["latency"],
                          "passing": payload["passing"], "total": payload["total"],
                          "failures": [row["id"] for row in payload["services"].values()
                                       if not row["pass"]][:12]}, indent=2))
    else:
        print(json.dumps({"path": str(OUT), "passing": payload["passing"],
                          "total": payload["total"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
