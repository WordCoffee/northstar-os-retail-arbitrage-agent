"""Regenerate ``ty/visual_views.json`` from ``ty/services.json``.

Every service route becomes a view, plus the two routes that exist outside the
service catalogue (``/`` and ``/home``). Seeding is deterministic
(:func:`freeze.seed_from_id`), so regenerating the registry after a service is
added produces one reviewable diff and no churn on the other views.

    python -m tools.visual_regression.build_registry            # write
    python -m tools.visual_regression.build_registry --check    # verify only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .freeze import seed_from_id
from .views import REGISTRY_PATH, SERVICES_PATH, ROOT

VIEWPORTS: Dict[str, Dict[str, Any]] = {
    "desktop": {
        "width": 1440,
        "height": 900,
        "browser": "chromium",
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
    },
    "iphone12-webkit": {
        "width": 390,
        "height": 844,
        "browser": "webkit",
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    },
}

READY = {
    "selector": "#root",
    "wait_until": "networkidle",
    "min_text_chars": 40,
    "settle_ms": 200,
}

EXTRA_VIEWS = [
    {"id": "root", "label": "Northstar", "group": "Public", "scene": "default", "theme": "default", "route": "/"},
    {"id": "home", "label": "Command Center", "group": "Workspace", "scene": "default", "theme": "neutral", "route": "/home"},
]


def _view(entry: Dict[str, Any]) -> Dict[str, Any]:
    seed = seed_from_id(entry["id"])
    return {
        "id": entry["id"],
        "route": entry["route"],
        "label": entry["label"],
        "group": entry["group"],
        "scene": entry.get("scene", "default"),
        "theme": entry.get("theme", "default"),
        "viewports": ["desktop", "iphone12-webkit"],
        "ready": dict(READY),
        "freeze": {"still": "1", "seed": seed},
    }


def build() -> Dict[str, Any]:
    services = json.loads(SERVICES_PATH.read_text(encoding="utf-8"))
    views: List[Dict[str, Any]] = [_view(v) for v in EXTRA_VIEWS]
    seen = {v["route"] for v in views}
    for service in services["services"]:
        if service["route"] in seen:
            continue
        seen.add(service["route"])
        views.append(_view(service))
    return {
        "schema": "northstar.visual_views.v1",
        "generated": "2026-11-08",
        "source": "ty/services.json",
        "note": (
            "Every service route from ty/services.json plus / and /home. "
            "still=1&seed=<n> is the freeze contract; the UI should honour it "
            "directly, and the gate also injects it via an init script."
        ),
        "viewports": VIEWPORTS,
        "defaults": {
            "ready": dict(READY),
            "freeze": {"still": "1"},
            "full_page": False,
        },
        "views": views,
    }


def render(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2) + "\n"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = parser.parse_args(argv)

    text = render(build())
    if args.check:
        current = REGISTRY_PATH.read_text(encoding="utf-8") if REGISTRY_PATH.exists() else ""
        if current != text:
            print("STALE: ty/visual_views.json does not match ty/services.json", file=sys.stderr)
            return 1
        print(f"OK: {REGISTRY_PATH.relative_to(ROOT)} matches the service catalogue")
        return 0

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(text, encoding="utf-8")
    data = json.loads(text)
    print(f"wrote {REGISTRY_PATH.relative_to(ROOT)}: {len(data['views'])} views")
    Path(REGISTRY_PATH).exists()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
