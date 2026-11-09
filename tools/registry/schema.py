"""Validation for the service registry and everything generated from it.

The registry is the single source of truth, so a malformed entry has to fail loudly
here rather than produce a quietly wrong workspace. ``validate_registry`` returns a
list of human-readable errors; an empty list means the document is acceptable.

    python -m tools.registry.schema ty/service_registry.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

INPUT_KINDS = ("query", "file", "selection", "setting")
OUTPUT_KINDS = ("table", "image", "file", "status", "text")
EFFECTS = ("read", "write", "external")
BOJO_STATUS = ("wired", "declared", "none")
VISION_KINDS = ("live", "screenshot", "audit", "backend")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
LAYOUTS = ("feed", "split", "canvas", "wizard", "board")

CITATION = re.compile(r"^Northstar_backend/[\w./-]+\.py:\d+$")
UI_CITATION = re.compile(r"northstar-os-ui/src/[\w./-]+\.jsx:\d+")
ENDPOINT = re.compile(r"^/api[\w./{}-]*$")

ENTRY_KEYS = (
    "id",
    "label",
    "group",
    "advanced_route",
    "purpose",
    "inputs",
    "outputs",
    "actions",
    "bojo_tool",
    "also_declares",
    "has_controls",
    "gap",
    "controls_evidence",
    "evidence",
)
EVIDENCE_KEYS = ("route", "vision", "vision_note", "backend", "declared_tools")


def _text(value: Any, key: str, errors: List[str], *, minimum: int = 1) -> None:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        errors.append(f"{key} must be a string of at least {minimum} characters")


def _tool_ref(tool: Any, where: str, errors: List[str]) -> None:
    if not isinstance(tool, dict):
        errors.append(f"{where} must be an object")
        return
    missing = [k for k in ("name", "status", "reason") if k not in tool]
    if missing:
        errors.append(f"{where} is missing {missing}")
        return
    if tool["status"] not in BOJO_STATUS:
        errors.append(f"{where}.status {tool['status']!r} not in {BOJO_STATUS}")
    if tool["status"] == "none" and tool["name"] != "none":
        errors.append(f"{where}.name must be 'none' when status is 'none'")
    if tool["status"] != "none" and not re.fullmatch(r"[a-z][a-z0-9_]*", str(tool["name"])):
        errors.append(f"{where}.name {tool['name']!r} is not a tool identifier")
    if len(str(tool.get("reason") or "")) < 20:
        errors.append(f"{where}.reason must explain the status in at least 20 characters")


def validate_entry(entry: Dict[str, Any], *, index: int = 0) -> List[str]:
    errors: List[str] = []
    name = entry.get("id") or f"#{index}"
    missing = [k for k in ENTRY_KEYS if k not in entry]
    if missing:
        return [f"{name}: missing keys {missing}"]

    _text(entry["id"], f"{name}.id", errors)
    _text(entry["label"], f"{name}.label", errors)
    _text(entry["group"], f"{name}.group", errors)
    _text(entry["purpose"], f"{name}.purpose", errors, minimum=25)

    route = entry["advanced_route"]
    if not isinstance(route, str) or not route.startswith("/"):
        errors.append(f"{name}.advanced_route must start with '/'")
    if entry["purpose"].strip().lower() == str(entry.get("label", "")).strip().lower():
        errors.append(f"{name}.purpose repeats the label")

    for item in entry["inputs"]:
        where = f"{name}.inputs[{item.get('name')}]"
        if not isinstance(item, dict) or set(item) != {"name", "kind", "source"}:
            errors.append(f"{where} must have exactly name/kind/source")
            continue
        if item["kind"] not in INPUT_KINDS:
            errors.append(f"{where}.kind {item['kind']!r} not in {INPUT_KINDS}")
        _text(item["source"], f"{where}.source", errors)

    if not entry["outputs"]:
        errors.append(f"{name}.outputs must not be empty")
    for item in entry["outputs"]:
        where = f"{name}.outputs[{item.get('name')}]"
        if not isinstance(item, dict) or set(item) != {"name", "kind", "where"}:
            errors.append(f"{where} must have exactly name/kind/where")
            continue
        if item["kind"] not in OUTPUT_KINDS:
            errors.append(f"{where}.kind {item['kind']!r} not in {OUTPUT_KINDS}")
        _text(item["where"], f"{where}.where", errors)

    for action in entry["actions"]:
        where = f"{name}.actions[{action.get('name')}]"
        if not isinstance(action, dict):
            errors.append(f"{where} must be an object")
            continue
        for key in ("name", "effect", "endpoint", "method", "source"):
            if key not in action:
                errors.append(f"{where} is missing {key}")
        if action.get("effect") not in EFFECTS:
            errors.append(f"{where}.effect {action.get('effect')!r} not in {EFFECTS}")
        if not ENDPOINT.match(str(action.get("endpoint") or "")):
            errors.append(f"{where}.endpoint {action.get('endpoint')!r} is not an /api path")
        if action.get("method") not in METHODS:
            errors.append(f"{where}.method {action.get('method')!r} not in {METHODS}")
        if not CITATION.match(str(action.get("source") or "")):
            errors.append(f"{where}.source must be a Northstar_backend/...py:line citation")

    _tool_ref(entry["bojo_tool"], f"{name}.bojo_tool", errors)
    for extra in entry["also_declares"]:
        _tool_ref(extra, f"{name}.also_declares[{extra.get('name') if isinstance(extra, dict) else '?'}]", errors)

    if not isinstance(entry["has_controls"], bool):
        errors.append(f"{name}.has_controls must be a boolean")
    if entry["has_controls"] and entry["gap"]:
        errors.append(f"{name}.gap must be null when has_controls is true")
    if not entry["has_controls"]:
        if not isinstance(entry["gap"], str) or len(entry["gap"]) < 25:
            errors.append(f"{name}.gap must describe what is missing (>=25 chars)")

    evidence_controls = str(entry["controls_evidence"])
    if not UI_CITATION.search(evidence_controls):        errors.append(f"{name}.controls_evidence must cite a northstar-os-ui/src/*.jsx:line")

    evidence = entry["evidence"]
    if not isinstance(evidence, dict):
        return errors + [f"{name}.evidence must be an object"]
    missing = [k for k in EVIDENCE_KEYS if k not in evidence]
    if missing:
        errors.append(f"{name}.evidence is missing {missing}")
    else:
        if not str(evidence["route"]).startswith("/ui"):
            errors.append(f"{name}.evidence.route must start with /ui")
        if evidence["vision"] not in VISION_KINDS:
            errors.append(f"{name}.evidence.vision {evidence['vision']!r} not in {VISION_KINDS}")
        if len(str(evidence["vision_note"])) < 10:
            errors.append(f"{name}.evidence.vision_note is empty")
        if not evidence["backend"]:
            errors.append(f"{name}.evidence.backend must cite at least one backend location")
        for ref in evidence["backend"]:
            if not CITATION.match(str(ref)):
                errors.append(f"{name}.evidence.backend entry {ref!r} is not a file:line citation")
        if not isinstance(evidence["declared_tools"], list):
            errors.append(f"{name}.evidence.declared_tools must be a list")
    return errors


def validate_registry(doc: Dict[str, Any], services: Optional[Iterable[Dict[str, Any]]] = None) -> List[str]:
    errors: List[str] = []
    if doc.get("schema") != "northstar.service_registry.v1":
        errors.append("schema must be northstar.service_registry.v1")
    entries = doc.get("services")
    if not isinstance(entries, list) or not entries:
        return errors + ["services must be a non-empty list"]
    if doc.get("count") != len(entries):
        errors.append(f"count {doc.get('count')!r} does not match {len(entries)} entries")

    seen: List[str] = []
    for index, entry in enumerate(entries):
        errors.extend(validate_entry(entry, index=index))
        seen.append(str(entry.get("id")))
    duplicates = {item for item in seen if seen.count(item) > 1}
    if duplicates:
        errors.append(f"duplicate service ids: {sorted(duplicates)}")

    if services is not None:
        wanted = {service["id"] for service in services}
        missing = sorted(wanted - set(seen))
        extra = sorted(set(seen) - wanted)
        if missing:
            errors.append(f"services with no registry entry: {missing}")
        if extra:
            errors.append(f"registry entries with no service: {extra}")
        by_id = {entry.get("id"): entry for entry in entries}
        for service in services:
            entry = by_id.get(service["id"]) or {}
            label = service.get("label")
            if entry.get("label") != label:
                errors.append(f"{service['id']}: label {entry.get('label')!r} != services.json {label!r}")
            if entry.get("group") != service.get("group"):
                errors.append(f"{service['id']}: group differs from services.json")
            if entry.get("advanced_route") != service.get("route"):
                errors.append(f"{service['id']}: advanced_route differs from services.json")
            declared = list(service.get("tools") or [])
            recorded = list((entry.get("evidence") or {}).get("declared_tools") or [])
            if declared != recorded:
                errors.append(f"{service['id']}: declared_tools {recorded} != services.json {declared}")
            owned = [entry["bojo_tool"]["name"]] + [t["name"] for t in entry.get("also_declares") or []]
            unrecorded = [tool for tool in declared if tool not in owned]
            if unrecorded:
                errors.append(f"{service['id']}: declared tools {unrecorded} appear in no bojo_tool/also_declares")
    return errors


def validate_workspaces(doc: Dict[str, Any], registry: Optional[Dict[str, Any]] = None) -> List[str]:
    errors: List[str] = []
    if doc.get("schema") != "northstar.northstar_workspaces.v1":
        errors.append("schema must be northstar.northstar_workspaces.v1")
    workspaces = doc.get("workspaces") or []
    if not workspaces:
        return errors + ["workspaces must be a non-empty list"]
    layouts: List[str] = []
    for item in workspaces:
        name = item.get("service") or "?"
        if item.get("layout") not in LAYOUTS:
            errors.append(f"{name}.layout {item.get('layout')!r} not in {LAYOUTS}")
        layouts.append(str(item.get("layout")))
        for key in ("primary_action", "empty_state", "why"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                errors.append(f"{name}.{key} must be populated")
        if not item.get("data_shown"):
            errors.append(f"{name}.data_shown must not be empty")
        why = str(item.get("why") or "")
        if len(why) < 40:
            errors.append(f"{name}.why must argue the shape in at least 40 characters")
        if str(item.get("label") or "").strip().lower() == why.strip().lower():
            errors.append(f"{name}.why repeats the label")
        if "why" in item and str(item.get("label") or "").lower() in why.lower() and len(why) < 60:
            errors.append(f"{name}.why is close to a copy of the label")
        if item.get("primary_action_source") != "local" and not item.get("primary_action_source"):
            errors.append(f"{name}.primary_action_source must name an action or be 'local'")
    if registry is not None:
        entries = {entry["id"]: entry for entry in registry.get("services", [])}
        seen = [item.get("service") for item in workspaces]
        missing = sorted(set(entries) - set(seen))
        extra = sorted(set(seen) - set(entries))
        if missing:
            errors.append(f"services with no workspace: {missing}")
        if extra:
            errors.append(f"workspaces with no service: {extra}")
        for item in workspaces:
            entry = entries.get(item.get("service")) or {}
            names = [action["name"] for action in entry.get("actions", [])]
            source = item.get("primary_action_source")
            if source != "local" and names and source not in names:
                errors.append(f"{item.get('service')}.primary_action_source {source!r} is not a registry action {names}")
            if source != "local" and not names:
                errors.append(f"{item.get('service')}.primary_action_source names an action but the registry has none")
            outputs = [o["name"] for o in entry.get("outputs", [])]
            for shown in item.get("data_shown") or []:
                if not isinstance(shown, dict) or not shown.get("name"):
                    errors.append(f"{item.get('service')}.data_shown entry {shown!r} is not an output object")
                elif shown["name"] not in outputs:
                    errors.append(f"{item.get('service')}.data_shown {shown['name']!r} is not one of the registry outputs")
    return errors


def validate_tool_list(doc: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if doc.get("schema") != "northstar.bojo_tool_list.v1":
        errors.append("schema must be northstar.bojo_tool_list.v1")
    tools = doc.get("tools")
    if not isinstance(tools, list):
        return errors + ["tools must be a list"]
    names: List[str] = []
    for tool in tools:
        if tool.get("status") not in ("wired", "declared"):
            errors.append(f"{tool.get('name')}.status {tool.get('status')!r} must be wired or declared")
        if not tool.get("service"):
            errors.append(f"{tool.get('name')} has no owning service")
        if tool.get("status") == "wired" and not tool.get("reason"):
            errors.append(f"{tool.get('name')} is wired but gives no reason")
        names.append(str(tool.get("name")))
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        errors.append(f"duplicate tool entries: {sorted(duplicates)}")
    if not isinstance(doc.get("unclaimed"), list):
        errors.append("unclaimed must be a list")
    return errors


def load(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m tools.registry.schema <file.json> [<services.json>]")
        return 2
    doc = load(Path(argv[0]))
    services = None
    if len(argv) > 1:
        services = load(Path(argv[1]))["services"]
    if doc.get("schema") == "northstar.service_registry.v1":
        errors = validate_registry(doc, services)
    elif doc.get("schema") == "northstar.northstar_workspaces.v1":
        errors = validate_workspaces(doc)
    elif doc.get("schema") == "northstar.bojo_tool_list.v1":
        errors = validate_tool_list(doc)
    else:
        errors = [f"unknown schema {doc.get('schema')!r}"]
    for error in errors:
        print("ERROR", error)
    print("ok" if not errors else f"{len(errors)} errors")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
