"""View registry: which routes are screenshotted, at which viewports, frozen how.

The registry is a file in the repo (``ty/visual_views.json``) rather than a
Python constant, so the set of views under regression is reviewable in a diff
and every route is traceable to ``ty/services.json``.

Nothing here touches a browser or the network.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "ty" / "visual_views.json"
SERVICES_PATH = ROOT / "ty" / "services.json"

REQUIRED_VIEWPOINTS = ("desktop", "iphone12-webkit")
EXTRA_ROUTES = ("/", "/home")

REQUIRED_VIEW_FIELDS = ("id", "route", "viewports", "ready", "freeze")


class RegistryError(ValueError):
    """The registry is malformed or out of step with the service catalogue."""


@dataclass(frozen=True)
class Viewport:
    id: str
    width: int
    height: int
    browser: str
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
    user_agent: str | None = None

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)


@dataclass(frozen=True)
class View:
    id: str
    route: str
    label: str
    group: str
    scene: str
    theme: str
    viewports: Tuple[str, ...]
    ready: Mapping[str, Any]
    freeze: Mapping[str, Any]

    @property
    def seed(self) -> int:
        return int(self.freeze["seed"])

    @property
    def still(self) -> str:
        return str(self.freeze.get("still", "1"))

    @property
    def ready_selector(self) -> str | None:
        return self.ready.get("selector") or None

    @property
    def wait_until(self) -> str:
        return str(self.ready.get("wait_until", "networkidle"))

    @property
    def min_text_chars(self) -> int:
        return int(self.ready.get("min_text_chars", 40))

    @property
    def settle_ms(self) -> int:
        return int(self.ready.get("settle_ms", 150))


@dataclass(frozen=True)
class Registry:
    schema: str
    viewports: Mapping[str, Viewport]
    views: Tuple[View, ...]

    def view(self, view_id: str) -> View:
        for view in self.views:
            if view.id == view_id:
                return view
        raise RegistryError(f"unknown view id: {view_id}")

    def ids(self) -> List[str]:
        return [v.id for v in self.views]


def _parse_viewport(key: str, raw: Mapping[str, Any]) -> Viewport:
    try:
        return Viewport(
            id=key,
            width=int(raw["width"]),
            height=int(raw["height"]),
            browser=str(raw["browser"]),
            device_scale_factor=float(raw.get("device_scale_factor", 1.0)),
            is_mobile=bool(raw.get("is_mobile", False)),
            has_touch=bool(raw.get("has_touch", False)),
            user_agent=raw.get("user_agent"),
        )
    except KeyError as exc:
        raise RegistryError(f"viewport {key!r} is missing {exc.args[0]!r}") from exc


def load_registry(path: str | Path = REGISTRY_PATH) -> Registry:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        viewports = {k: _parse_viewport(k, v) for k, v in data["viewports"].items()}
        views = tuple(
            View(
                id=str(v["id"]),
                route=str(v["route"]),
                label=str(v.get("label", v["id"])),
                group=str(v.get("group", "")),
                scene=str(v.get("scene", "default")),
                theme=str(v.get("theme", "default")),
                viewports=tuple(v["viewports"]),
                ready=dict(v["ready"]),
                freeze=dict(v["freeze"]),
            )
            for v in data["views"]
        )
        schema = str(data.get("schema", ""))
    except KeyError as exc:
        raise RegistryError(f"registry is missing key {exc.args[0]!r}") from exc
    return Registry(schema=schema, viewports=viewports, views=views)


def service_routes(path: str | Path = SERVICES_PATH) -> List[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [str(service["route"]) for service in data["services"]]


def validate(registry: Registry, services_path: str | Path = SERVICES_PATH) -> List[str]:
    """Return a list of problems; empty means the registry is coherent."""
    problems: List[str] = []

    if len({v.id for v in registry.views}) != len(registry.views):
        problems.append("duplicate view ids")

    for required in REQUIRED_VIEWPOINTS:
        if required not in registry.viewports:
            problems.append(f"missing required viewport {required}")

    if registry.viewports:
        if registry.viewports.get("desktop") and registry.viewports["desktop"].size != (1440, 900):
            problems.append("desktop viewport must be 1440x900")
        if registry.viewports.get("iphone12-webkit"):
            iphone = registry.viewports["iphone12-webkit"]
            if iphone.size != (390, 844):
                problems.append("iphone12-webkit viewport must be 390x844")
            if iphone.browser != "webkit":
                problems.append("iphone12-webkit must use the webkit engine")

    routes = {v.route for v in registry.views}
    for route in service_routes(services_path):
        if route not in routes:
            problems.append(f"service route missing from registry: {route}")
    for route in EXTRA_ROUTES:
        if route not in routes:
            problems.append(f"required route missing from registry: {route}")

    for view in registry.views:
        if not view.route.startswith("/"):
            problems.append(f"{view.id}: route must start with '/': {view.route!r}")
        if not view.viewports:
            problems.append(f"{view.id}: no viewports")
        for vp in view.viewports:
            if vp not in registry.viewports:
                problems.append(f"{view.id}: unknown viewport {vp!r}")
        for required in REQUIRED_VIEWPOINTS:
            if required not in view.viewports:
                problems.append(f"{view.id}: missing viewport {required}")
        if not (view.ready_selector or view.ready.get("wait_until")):
            problems.append(f"{view.id}: ready condition needs a selector or wait_until")
        if str(view.freeze.get("still", "")) != "1":
            problems.append(f"{view.id}: freeze.still must be '1'")
        try:
            if int(view.freeze["seed"]) <= 0:
                problems.append(f"{view.id}: freeze.seed must be a positive integer")
        except (KeyError, TypeError, ValueError):
            problems.append(f"{view.id}: freeze.seed must be a positive integer")

    return problems


def filter_views(
    registry: Registry,
    view_ids: Iterable[str] | None = None,
    viewport_ids: Sequence[str] | None = None,
) -> List[Tuple[View, Tuple[Viewport, ...]]]:
    """Resolve requested ids to (view, viewports) pairs, preserving registry order."""
    wanted_views = set(view_ids) if view_ids else None
    wanted_vps = list(viewport_ids) if viewport_ids else None

    if wanted_views:
        unknown = wanted_views - set(registry.ids())
        if unknown:
            raise RegistryError(f"unknown view ids: {sorted(unknown)}")
    if wanted_vps:
        unknown_vps = set(wanted_vps) - set(registry.viewports)
        if unknown_vps:
            raise RegistryError(f"unknown viewports: {sorted(unknown_vps)}")

    out: List[Tuple[View, Tuple[Viewport, ...]]] = []
    for view in registry.views:
        if wanted_views and view.id not in wanted_views:
            continue
        ids = wanted_vps or list(view.viewports)
        chosen = tuple(registry.viewports[vp] for vp in ids if vp in registry.viewports)
        if chosen:
            out.append((view, chosen))
    if not out:
        raise RegistryError("no views selected")
    return out
