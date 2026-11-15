"""Local/mesh model routing: a config hook, a health check, and an explicit cloud fallback.

No endpoint is assumed healthy. A local node is chosen only when the config enables it and the
injected health check says it is up; otherwise the free cloud model answers, with the reason.

    python -m tools.ty_toolkit.mesh_route --task classify
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "local_models.json"
EXAMPLE = ROOT / "config" / "local_models.example.json"
TASKS = ("classify", "extract", "summarise", "embed")
DEFAULT_CLOUD = {"provider": "opencode-go", "model": "beam-free",
                 "reason": "the verified free hosted model"}

Health = Callable[[Dict[str, Any]], bool]


def load(path: str | Path | None = None) -> Dict[str, Any]:
    target = Path(path or (CONFIG if CONFIG.is_file() else EXAMPLE))
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema": "northstar.local_models.v1", "enabled": False, "endpoints": [],
                "cloud_fallback": dict(DEFAULT_CLOUD), "source": str(target), "loaded": False}
    if not isinstance(data, dict):
        return {"schema": "northstar.local_models.v1", "enabled": False, "endpoints": [],
                "cloud_fallback": dict(DEFAULT_CLOUD), "source": str(target), "loaded": False}
    data.setdefault("endpoints", [])
    data.setdefault("cloud_fallback", dict(DEFAULT_CLOUD))
    data["source"] = str(target)
    data["loaded"] = True
    return data


def choose(task: str, config: Optional[Dict[str, Any] | str | Path] = None, *,
           health: Optional[Health] = None) -> Dict[str, Any]:
    name = str(task or "").strip().lower()
    if name not in TASKS:
        return {"ok": False, "reason": f"task must be one of {list(TASKS)}"}
    data = (config if isinstance(config, dict) else load(config)) if config is not None else load()
    cloud = dict(data.get("cloud_fallback") or DEFAULT_CLOUD)
    if not data.get("enabled"):
        return {"ok": True, "task": name, "route": "cloud", "model": cloud.get("model"),
                "provider": cloud.get("provider"), "reason": "local routing is disabled",
                "source": data.get("source")}
    candidates = [row for row in data.get("endpoints") or []
                  if isinstance(row, dict) and name in (row.get("tasks") or [])]
    if not candidates:
        return {"ok": True, "task": name, "route": "cloud", "model": cloud.get("model"),
                "provider": cloud.get("provider"), "reason": "no local endpoint declares this task",
                "source": data.get("source")}
    if health is None:
        return {"ok": True, "task": name, "route": "cloud", "model": cloud.get("model"),
                "provider": cloud.get("provider"),
                "reason": "local health is unknown; not assumed healthy", "source": data.get("source")}
    for row in candidates:
        try:
            alive = bool(health(row))
        except Exception:  # noqa: BLE001 - an unreachable probe is not a healthy node
            alive = False
        if alive:
            return {"ok": True, "task": name, "route": "local", "model": row.get("model"),
                    "provider": row.get("provider") or "local", "base_url": row.get("base_url"),
                    "reason": "local endpoint healthy", "source": data.get("source")}
    return {"ok": True, "task": name, "route": "cloud", "model": cloud.get("model"),
            "provider": cloud.get("provider"),
            "reason": "no local endpoint answered its health check", "source": data.get("source")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose a local or cloud model route")
    parser.add_argument("--task", required=True, choices=list(TASKS))
    parser.add_argument("--config", default="")
    ns = parser.parse_args(argv)
    print(json.dumps(choose(ns.task, ns.config or None), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
