"""The service registry is the source of truth; these tests hold it to that.

What is asserted, and why each one matters:

* **coverage** — every service in ``ty/services.json`` has exactly one entry, so a
  new room cannot exist without being described.
* **schema** — every entry carries purpose/inputs/outputs/actions/bojo_tool/
  has_controls/evidence in the agreed shapes.
* **tool honesty** — a tool is either ``wired`` in ``chat_tools.TOOLS`` (or the
  Bojo domain registry) or ``declared``/``none`` with a reason. A declared tool
  that is actually wired, or a wired tool that does not exist, fails here.
* **generation** — ``ty/bojo_tool_list.json`` and ``ty/northstar_workspaces.json``
  are byte-identical to what the builder derives from the registry, so the
  generated files cannot drift into a second source of truth.
* **workspaces** — every service has a spec with a layout from the small set, a
  populated primary action, and a ``why`` that argues the shape from the
  service's own inputs and outputs rather than repeating its label.
* **gaps** — ``ty/registry_gaps.json`` names exactly the services whose entry
  says ``has_controls: false``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.registry import backend_index, build, schema  # noqa: E402

TY = ROOT / "ty"


def _load(name: str) -> dict:
    return json.loads((TY / name).read_text(encoding="utf-8"))


STOPWORDS = {"their", "which", "these", "there", "other", "where", "every", "about"}


def _words(text: str) -> set:
    import re

    return {word for word in re.findall(r"[a-z]{5,}", str(text).lower()) if word not in STOPWORDS}


@pytest.fixture(scope="module")
def registry() -> dict:
    return _load("service_registry.json")


@pytest.fixture(scope="module")
def services() -> list:
    return _load("services.json")["services"]


@pytest.fixture(scope="module")
def tool_list() -> dict:
    return _load("bojo_tool_list.json")


@pytest.fixture(scope="module")
def workspaces() -> dict:
    return _load("northstar_workspaces.json")


@pytest.fixture(scope="module")
def gaps() -> dict:
    return _load("registry_gaps.json")


# -- coverage and shape ------------------------------------------------------


def test_registry_covers_every_service(registry, services):
    ids = [entry["id"] for entry in registry["services"]]
    assert len(ids) == len(set(ids)), "duplicate service ids in the registry"
    assert set(ids) == {service["id"] for service in services}
    assert registry["count"] == len(services)
    # The walk covered today's 29 services. A later addition must be described too,
    # so the registry may grow but never shrink below the set that was walked.
    assert len(services) >= 29


def test_every_entry_validates(registry, services):
    errors = schema.validate_registry(registry, services)
    assert errors == []


def test_every_action_citation_still_resolves(registry):
    routes = backend_index.routes()
    dead = []
    for entry in registry["services"]:
        for action in entry["actions"]:
            route = backend_index.find(action["method"], action["endpoint"], routes)
            if route is None:
                dead.append(f"{entry['id']}: {action['method']} {action['endpoint']} not mounted")
            elif route.ref != action["source"]:
                dead.append(f"{entry['id']}: {action['endpoint']} moved to {route.ref}")
    assert dead == []


def test_vision_evidence_is_recorded_for_every_route(registry):
    counts = {}
    for entry in registry["services"]:
        vision = entry["evidence"]["vision"]
        note = entry["evidence"]["vision_note"]
        assert vision in schema.VISION_KINDS
        assert entry["evidence"]["route"].endswith(entry["advanced_route"])
        assert len(note) >= 10
        if vision == "live":
            assert "blocked" not in note, "a blocked route cannot be recorded as live"
        elif vision == "screenshot":
            assert ".png" in note, "screenshot evidence must name the capture"
        elif vision == "audit":
            assert "ux_audit.json" in note, "audit evidence must name the committed walk"
        else:
            assert "no live page" in note, "backend-only evidence must say so"
        counts[vision] = counts.get(vision, 0) + 1
    assert sum(counts.values()) == len(registry["services"])


# -- Bojo tools --------------------------------------------------------------


def test_bojo_tool_status_is_truthful(registry):
    tools = set(backend_index.tools())
    bojo = set(backend_index.bojo_tools())
    problems = []
    for entry in registry["services"]:
        for ref in [entry["bojo_tool"]] + list(entry.get("also_declares") or []):
            name, status = ref["name"], ref["status"]
            if status == "none":
                problems.append(f"{entry['id']}: 'none' recorded as a tool name") if name != "none" else None
                continue
            if status == "wired" and name not in tools:
                problems.append(f"{entry['id']}: {name} is marked wired but absent from chat_tools.TOOLS")
            if status == "declared" and name in tools:
                problems.append(f"{entry['id']}: {name} is marked declared but chat_tools.TOOLS has it")
            if status == "declared" and not ref["reason"]:
                problems.append(f"{entry['id']}: {name} is declared with no reason")
            if status == "wired" and name in bojo and name not in tools:
                problems.append(f"{entry['id']}: {name} lives only in the Bojo domain registry")
    assert problems == []


def test_declared_tools_from_services_json_are_all_recorded(registry, services):
    by_id = {entry["id"]: entry for entry in registry["services"]}
    missing = []
    for service in services:
        entry = by_id[service["id"]]
        recorded = [entry["bojo_tool"]["name"]] + [t["name"] for t in entry["also_declares"]]
        for tool in service.get("tools") or []:
            if tool not in recorded:
                missing.append(f"{service['id']}: {tool}")
    assert missing == []


def test_tool_list_agrees_with_chat_tools(tool_list):
    tools = set(backend_index.tools())
    listed = {tool["name"] for tool in tool_list["tools"]}
    wired = {tool["name"] for tool in tool_list["tools"] if tool["status"] == "wired"}
    declared = {tool["name"] for tool in tool_list["tools"] if tool["status"] == "declared"}

    assert wired <= tools, f"wired tools not in chat_tools.TOOLS: {sorted(wired - tools)}"
    assert not (declared & tools), f"declared tools that are actually wired: {sorted(declared & tools)}"
    # Every chat tool is either owned by a service or recorded as unclaimed, and a
    # declared-but-unwired tool is neither.
    assert wired | set(tool_list["unclaimed"]) == tools
    assert tool_list["count"] == len(tool_list["tools"]) == len(listed)
    assert len(tool_list["unclaimed"]) == len(set(tool_list["unclaimed"]))


def test_tool_list_is_derived_from_the_registry(registry, tool_list):
    expected = build.build_tool_list(
        registry, sorted(backend_index.tools()), backend_index.bojo_tools()
    )
    assert tool_list == expected


def test_tool_list_names_an_owning_service(tool_list, registry):
    ids = {entry["id"] for entry in registry["services"]}
    for tool in tool_list["tools"]:
        assert tool["service"] in ids
        assert all(other in ids for other in tool["also_used_by"])
        assert tool["service"] not in tool["also_used_by"]


# -- workspaces --------------------------------------------------------------


def test_every_service_has_a_workspace(workspaces, registry):
    assert workspaces["count"] == len(registry["services"])
    assert {w["service"] for w in workspaces["workspaces"]} == {e["id"] for e in registry["services"]}


def test_workspace_specs_validate(workspaces, registry):
    assert schema.validate_workspaces(workspaces, registry) == []


def test_workspaces_are_purpose_built_not_copies(workspaces, registry):
    by_id = {entry["id"]: entry for entry in registry["services"]}
    seen_why = set()
    for workspace in workspaces["workspaces"]:
        assert workspace["layout"] in schema.LAYOUTS
        assert workspace["primary_action"].strip()
        assert workspace["empty_state"].strip()
        why = workspace["why"].strip()
        assert len(why) >= 40
        # Not a copy of the label: the spec must argue a shape, not restate a name.
        assert why.lower().strip(".") != workspace["label"].strip().lower().strip(".")
        assert why.lower() not in seen_why, "two services share one justification"
        seen_why.add(why.lower())
        # The shape must be argued from the service's own inputs and outputs.
        entry = by_id[workspace["service"]]
        vocabulary = set()
        for source in entry["outputs"]:
            vocabulary |= _words(f"{source['name']} {source['where']}")
        for source in entry["inputs"]:
            vocabulary |= _words(source["name"])
        assert vocabulary & _words(why), (
            f"{workspace['service']}.why never names any of its own inputs/outputs"
        )
        assert workspace["data_shown"], "a workspace with nothing to show is not a workspace"
    assert set(workspaces["layout_distribution"]) <= set(schema.LAYOUTS)
    assert sum(workspaces["layout_distribution"].values()) == len(registry["services"])


def test_workspace_data_and_inputs_come_from_the_registry(workspaces, registry):
    by_id = {entry["id"]: entry for entry in registry["services"]}
    for workspace in workspaces["workspaces"]:
        entry = by_id[workspace["service"]]
        assert [item["name"] for item in workspace["data_shown"]] == [
            output["name"] for output in entry["outputs"]
        ]
        assert workspace["inputs_required"] == [item["name"] for item in entry["inputs"]]
        source = workspace["primary_action_source"]
        if source != "local":
            assert source in [action["name"] for action in entry["actions"]]


# -- gaps --------------------------------------------------------------------


def test_gaps_match_services_without_controls(registry, gaps):
    expected = [entry["id"] for entry in registry["services"] if not entry["has_controls"]]
    assert [gap["id"] for gap in gaps["gaps"]] == expected
    assert gaps["count"] == len(expected)
    for gap in gaps["gaps"]:
        assert gap["reason"].strip(), f"{gap['id']} gives no reason"
        assert "northstar-os-ui/src/" in gap["evidence"]


def test_control_less_entries_say_what_is_missing(registry):
    for entry in registry["services"]:
        if entry["has_controls"]:
            assert entry["gap"] is None
        else:
            assert entry["gap"] and len(entry["gap"]) >= 25
            assert entry["controls_evidence"]


# -- generated files are current --------------------------------------------


def test_generated_files_are_current(registry):
    services = _load("services.json")["services"]
    assert schema.validate_registry(registry, services) == []
    assert build.check_actions(registry) == []
    assert build.check_evidence(registry) == []

    expected = {
        "bojo_tool_list.json": build.build_tool_list(
            registry, sorted(backend_index.tools()), backend_index.bojo_tools()
        ),
        "northstar_workspaces.json": build.build_workspaces(registry),
        "registry_gaps.json": build.build_gaps(registry),
    }
    stale = []
    for name, doc in expected.items():
        path = TY / name
        # `expected_doc` merges the generated keys with any hand-authored block the file
        # carries (block3 added `scene_workspaces`). Comparing against the bare document
        # made a legitimate additive block look like drift, and a plain regeneration would
        # have deleted it.
        if path.read_text(encoding="utf-8") != build._dump(build.expected_doc(path, doc)):
            stale.append(name)
    assert stale == [], f"run python -m tools.registry.build (stale: {stale})"


# --- generated files keep hand-authored blocks -------------------------------
# block3 added a `scene_workspaces` block to ty/northstar_workspaces.json. A plain
# regeneration would have deleted it, and the byte-comparison above would have called the
# block "drift" forever. Both now go through `expected_doc`, which keeps keys the
# generator does not own.


def test_a_hand_authored_block_survives_a_regeneration(tmp_path):
    path = tmp_path / "workspaces.json"
    path.write_text(json.dumps({"schema": "v1", "workspaces": [],
                                "scene_workspaces": {"design": {"route": "/design-studio"}}}),
                    encoding="utf-8")
    merged = build.expected_doc(path, {"schema": "v1", "workspaces": []})
    assert merged["scene_workspaces"] == {"design": {"route": "/design-studio"}}
    assert merged["workspaces"] == []


def test_a_generated_key_is_never_taken_from_the_old_file(tmp_path):
    path = tmp_path / "workspaces.json"
    path.write_text(json.dumps({"schema": "v1", "count": 999}), encoding="utf-8")
    merged = build.expected_doc(path, {"schema": "v1", "count": 3})
    assert merged["count"] == 3, "a generated key must come from the code, not the file"


def test_a_missing_or_corrupt_file_is_not_a_reason_to_fail(tmp_path):
    assert build.expected_doc(tmp_path / "absent.json", {"a": 1}) == {"a": 1}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert build.expected_doc(broken, {"a": 1}) == {"a": 1}
