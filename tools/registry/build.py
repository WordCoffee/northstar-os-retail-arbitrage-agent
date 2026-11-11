"""Generate the derived artefacts from ``ty/service_registry.json``.

The registry is authored; the tool list, the Northstar workspaces and the gap
record are generated, so they cannot drift. The builder also walks the mounted
FastAPI route table and fails if any action citation has rotted — a service whose
endpoint moved is a build error, not a stale note.

    python -m tools.registry.build            # write the three files
    python -m tools.registry.build --check    # verify only; nonzero on drift

Write scope: ty/bojo_tool_list.json, ty/northstar_workspaces.json,
ty/registry_gaps.json. The registry itself is never rewritten here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from tools.registry import backend_index, schema

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "ty" / "service_registry.json"
SERVICES = ROOT / "ty" / "services.json"
TOOLS_OUT = ROOT / "ty" / "bojo_tool_list.json"
WORKSPACES_OUT = ROOT / "ty" / "northstar_workspaces.json"
GAPS_OUT = ROOT / "ty" / "registry_gaps.json"

#: How each service should present itself in Northstar. The shape is chosen from the
#: service's own inputs and outputs, never copied from the advanced page.
WORKSPACE_PLAN: Dict[str, Dict[str, str]] = {
    "hub": {
        "layout": "feed",
        "primary_action": "open the service that is reporting a problem",
        "primary_action_source": "local",
        "empty_state": "Every probe answered; no service is reporting a problem.",
        "why": "Hub answers 'is anything wrong right now', so it is one scannable column of status cards with the service list inline; a split form would promise an input the room does not have.",
    },
    "ledger": {
        "layout": "split",
        "primary_action": "compare this period's consumption with the remaining balance",
        "primary_action_source": "read credit balance",
        "empty_state": "No credit read returned; the statement shows UNKNOWN rather than zero.",
        "why": "A ledger reconciles two columns - what was consumed against what remains - so the split shape puts period totals beside the line items they explain.",
    },
    "prospector": {
        "layout": "split",
        "primary_action": "run a live scan and keep the rows above the ROI floor",
        "primary_action_source": "run / read scanner",
        "empty_state": "Scanner returned no rows; show the cached-match fallback with its own source badge.",
        "why": "Prospecting is filter-in and ranked-table-out, so one side holds the filter and the run control while the other holds the ranking it produced.",
    },
    "goldengoose": {
        "layout": "feed",
        "primary_action": "raise the deal-score floor until the list is short enough to act on",
        "primary_action_source": "local",
        "empty_state": "No deal clears the floor at this score; name the floor that would return one.",
        "why": "The room answers one question per item - is this deal worth a look - so the deals read as a ranked stream and a single score floor is the whole control surface.",
    },
    "offerchisel": {
        "layout": "wizard",
        "primary_action": "generate title, bullets and keywords for the named product",
        "primary_action_source": "generate listing copy",
        "empty_state": "No product named yet; the first step is the product name, not an empty result table.",
        "why": "One deliverable is produced in a fixed order (name, style, generate, accept), so a wizard keeps the operator on the steps that actually exist.",
    },
    "towncrier": {
        "layout": "wizard",
        "primary_action": "write the caption for a brief and a platform",
        "primary_action_source": "generate caption",
        "empty_state": "No brief typed; the composer opens on the brief, because a caption cannot exist before it.",
        "why": "Caption generation is brief, platform, caption, reminder; a wizard shows that order and keeps the closed publish gate visible at the last step.",
    },
    "auctioneer": {
        "layout": "split",
        "primary_action": "compute break-even ACoS from the campaign numbers",
        "primary_action_source": "compute economics",
        "empty_state": "No numbers entered; outputs stay blank, never zero.",
        "why": "The page is arithmetic-in and break-even-out - eight entered campaign numbers on one side, the canonical verdict on the other - so every input stays visible next to the result it produced.",
    },
    "autothink": {
        "layout": "feed",
        "primary_action": "run a prompt against the chosen model and keep the answer in history",
        "primary_action_source": "run prompt",
        "empty_state": "No run yet; the composer is the only thing on the page until the first answer arrives.",
        "why": "AutothinK is a run log with a composer, so the answer and every earlier answer belong in one vertical stream rather than in a dashboard of tiles.",
    },
    "thewatch": {
        "layout": "feed",
        "primary_action": "read the watchlist for signals",
        "primary_action_source": "read scanner",
        "empty_state": "Scanner unread; the watchlist says so instead of showing an empty list.",
        "why": "A watchlist is a short stream of things to glance at - one line per product with its signal state - not a form and not a board.",
    },
    "rankledger": {
        "layout": "board",
        "primary_action": "read which band a product's score places it in",
        "primary_action_source": "read scanner",
        "empty_state": "No scored rows; the board shows empty bands rather than a fabricated ranking.",
        "why": "The row's job is its standing, so three score bands read as board columns (strong, competitive, weak) and a product's position carries the message.",
    },
    "rivalboard": {
        "layout": "board",
        "primary_action": "read which products sit in the price-saturated lane",
        "primary_action_source": "read scanner",
        "empty_state": "No posture rows; the lanes stay empty and labelled.",
        "why": "Risk is a lane, not a number: grouping each product into high-margin, benign or price-saturated makes the saturated lane the thing the eye lands on.",
    },
    "account": {
        "layout": "feed",
        "primary_action": "read what the plan allows",
        "primary_action_source": "read entitlements",
        "empty_state": "Entitlements unreadable; show the failure instead of a default plan.",
        "why": "Account is a short statement of permissions and usage, so it reads as a vertical list of what this org may run rather than a settings form.",
    },
    "foundation": {
        "layout": "feed",
        "primary_action": "read the failing subsystem and its evidence",
        "primary_action_source": "read providers",
        "empty_state": "Foundation unreachable; every section says UNKNOWN with the reason.",
        "why": "Foundation health is many independent probes - providers, marketplaces, approvals, audit - so one column of probe cards, each with its own state, beats a grid that implies the numbers are comparable.",
    },
    "jobs": {
        "layout": "board",
        "primary_action": "create a durable job or flip a schedule",
        "primary_action_source": "create durable job",
        "empty_state": "No durable jobs; the board starts empty with the create form attached, because the first job is the operator's own.",
        "why": "A job has a state and a state is a column; the create form belongs beside the board because every job is born from it.",
    },
    "keywords": {
        "layout": "split",
        "primary_action": "search the store, then submit an import",
        "primary_action_source": "submit import",
        "empty_state": "No keyword-store match; the panel says the store is empty rather than showing zero coverage.",
        "why": "Keyword work is find-then-import, so search and its results stay on one side while the import batch and its rejected rows stay on the other.",
    },
    "beta": {
        "layout": "wizard",
        "primary_action": "accept the invitation or sign in",
        "primary_action_source": "local",
        "empty_state": "The landing is always the first step; there is no empty variant.",
        "why": "A landing page has one job - send the visitor to accept or sign in - so it is a two-step gate rather than a dashboard of programme detail.",
    },
    "beta-support": {
        "layout": "feed",
        "primary_action": "read who handles beta support",
        "primary_action_source": "local",
        "empty_state": "The section renders only when the #support hash is present; otherwise the landing stands alone.",
        "why": "Support here is two sentences and a pointer to the ticket queue, so a single short card is the honest shape and anything larger would be padding.",
    },
    "beta-signup": {
        "layout": "wizard",
        "primary_action": "submit the invite code and email",
        "primary_action_source": "create beta account",
        "empty_state": "No code yet; the form waits rather than pre-filling a guess.",
        "why": "Redemption is one form and one result, so the wizard is a single step whose only required evidence is the code.",
    },
    "beta-ops": {
        "layout": "board",
        "primary_action": "open the organisation that needs attention",
        "primary_action_source": "read admin dashboard",
        "empty_state": "No organisations in the cohort; the board stays empty rather than showing sample rows.",
        "why": "An organisation moves through lifecycle states, so a board keyed by state shows the cohort's shape at a glance and the drill-down is one click from the column.",
    },
    "design-studio": {
        "layout": "canvas",
        "primary_action": "upload a source asset, then compose the surface it belongs to",
        "primary_action_source": "upload asset",
        "empty_state": "No project open; the canvas offers a surface picker before an empty sheet.",
        "why": "The studio's output is a picture or a dieline, so the workspace is the canvas itself; picking a surface replaces the form instead of sitting beside it.",
    },
    "product-finder": {
        "layout": "split",
        "primary_action": "stage an ASIN and read the gates it still owes",
        "primary_action_source": "local",
        "empty_state": "No ASIN staged; the evidence panels stay empty and the gates stay UNKNOWN.",
        "why": "Research is ASIN-in and evidence-out, so the ASIN field owns the left side while every unread gate stays UNKNOWN on the right instead of being filled with a guess.",
    },
    "golden-goose": {
        "layout": "split",
        "primary_action": "evaluate the candidate against the gates",
        "primary_action_source": "evaluate candidate",
        "empty_state": "No candidate; the gate list is visible but the verdict stays blank.",
        "why": "A verdict only means something next to the gates that produced it, so gates sit left and the checklist plus verified commission sit right.",
    },
    "listings": {
        "layout": "board",
        "primary_action": "read the highest-severity alert",
        "primary_action_source": "read listing health",
        "empty_state": "No local listing records; the board says the source is empty, not that listings are healthy.",
        "why": "Alerts already carry a severity, so severity is the column and review is a movement; a board shows both without inventing a control the service lacks.",
    },
    "keyword-tracker": {
        "layout": "feed",
        "primary_action": "read coverage for one keyword",
        "primary_action_source": "search keyword store",
        "empty_state": "No keyword rows; the feed says the store is empty.",
        "why": "Tracking is a per-keyword read with a coverage badge, so each keyword is one row in a stream that can be scanned for movement.",
    },
    "competitor-monitor": {
        "layout": "feed",
        "primary_action": "read the cached observation and its quantity match",
        "primary_action_source": "read competitor observations",
        "empty_state": "No observations; the panel labels the catalog cached instead of implying live tracking.",
        "why": "Observations are independent snapshots, so they stack as labelled rows rather than pretending to be a live competitor grid.",
    },
    "listingforge": {
        "layout": "wizard",
        "primary_action": "draft, edit, then save the listing record",
        "primary_action_source": "save listing record",
        "empty_state": "No brief; the wizard starts at the product name.",
        "why": "Composition is brief, proposal, edit, saved record, and the save is a distinct step, so a wizard makes the persistence boundary visible.",
    },
    "adpilot": {
        "layout": "split",
        "primary_action": "read the imported campaign and request ad copy",
        "primary_action_source": "request ad copy",
        "empty_state": "No imported file; campaigns show UNKNOWN and the copy panel waits.",
        "why": "Ad work is evidence-in (the seller's own file) and proposal-out, so split keeps the imported metrics beside the copy they justify.",
    },
    "socialpulse": {
        "layout": "board",
        "primary_action": "move a draft to review, then to publish-ready",
        "primary_action_source": "local",
        "empty_state": "No drafts; the columns stay empty and the composer is the only way in.",
        "why": "The room is a content pipeline, so drafts, review, approval and publish-ready are columns and the value is where each post sits.",
    },
    "profitability": {
        "layout": "split",
        "primary_action": "compute contribution and readiness from the unit inputs",
        "primary_action_source": "compute economics",
        "empty_state": "No inputs; the result panel stays blank and readiness stays UNKNOWN.",
        "why": "Unit economics is inputs-in and verdict-out with a readiness gate, so the numbers stay on one side and the canonical result with its gate pill on the other.",
    },
}


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_actions(registry: Dict[str, Any]) -> List[str]:
    """Every action must resolve to a mounted route at the cited line."""
    errors: List[str] = []
    routes = backend_index.routes()
    for entry in registry["services"]:
        for action in entry["actions"]:
            route = backend_index.find(action["method"], action["endpoint"], routes)
            if route is None:
                errors.append(f"{entry['id']}: {action['method']} {action['endpoint']} is not mounted")
            elif route.ref != action["source"]:
                errors.append(
                    f"{entry['id']}: {action['endpoint']} cited at {action['source']} but defined at {route.ref}"
                )
    return errors


def check_evidence(registry: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    known = {route.ref for route in backend_index.routes()} | {"Northstar_backend/main.py:353"}
    for entry in registry["services"]:
        for ref in entry["evidence"]["backend"]:
            if ref not in known:
                errors.append(f"{entry['id']}: evidence.backend {ref} is not a route decorator or the /ui mount")
    return errors


def build_tool_list(registry: Dict[str, Any], tool_names: List[str], bojo_names: List[str]) -> Dict[str, Any]:
    owners: Dict[str, Dict[str, Any]] = {}
    for entry in registry["services"]:
        refs = [entry["bojo_tool"]] + list(entry.get("also_declares") or [])
        for position, ref in enumerate(refs):
            if ref["status"] == "none":
                continue
            record = owners.setdefault(
                ref["name"],
                {
                    "name": ref["name"],
                    "status": ref["status"],
                    "service": entry["id"],
                    "also_used_by": [],
                    "reason": ref["reason"],
                },
            )
            if ref["status"] == "wired":
                record["status"] = "wired"
                record["reason"] = ref["reason"]
            if position == 0 and entry["id"] != record["service"]:
                record["also_used_by"].append(entry["id"])
            elif position > 0 and entry["id"] != record["service"]:
                if entry["id"] not in record["also_used_by"]:
                    record["also_used_by"].append(entry["id"])

    tools = [owners[name] for name in sorted(owners)]
    claimed = set(owners)
    unclaimed = sorted(set(tool_names) - claimed)

    # chat_tools.SERVICES is a second, coarser mapping; record it so the two can be compared.
    areas = []
    for area in _chat_areas():
        areas.append(
            {
                "id": area["id"],
                "label": area["label"],
                "tools": area["tools"],
                "unclaimed_here": [name for name in area["tools"] if name not in claimed],
            }
        )

    wired = [tool for tool in tools if tool["status"] == "wired"]
    declared = [tool for tool in tools if tool["status"] == "declared"]
    unknown = [tool["name"] for tool in wired if tool["name"] not in tool_names]
    if unknown:
        raise SystemExit(f"wired tools missing from chat_tools.TOOLS: {unknown}")

    return {
        "schema": "northstar.bojo_tool_list.v1",
        "generated_from": "ty/service_registry.json",
        "count": len(tools),
        "totals": {"wired": len(wired), "declared": len(declared), "unclaimed": len(unclaimed)},
        "tools": tools,
        "unclaimed": unclaimed,
        "chat_service_areas": areas,
        "bojo_domain_registry": bojo_names,
    }


def _chat_areas() -> List[Dict[str, Any]]:
    import subprocess

    code = (
        "import json,sys;"
        f"sys.path.insert(0, r'{ROOT / 'Northstar_backend'}');"
        "import chat_tools;"
        "print(json.dumps(chat_tools.SERVICES))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit(f"chat_tools.SERVICES unavailable: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def build_workspaces(registry: Dict[str, Any]) -> Dict[str, Any]:
    workspaces = []
    for entry in registry["services"]:
        plan = WORKSPACE_PLAN[entry["id"]]
        workspaces.append(
            {
                "service": entry["id"],
                "label": entry["label"],
                "layout": plan["layout"],
                "primary_action": plan["primary_action"],
                "primary_action_source": plan["primary_action_source"],
                "empty_state": plan["empty_state"],
                "data_shown": [
                    {"name": item["name"], "kind": item["kind"], "where": item["where"]}
                    for item in entry["outputs"]
                ],
                "inputs_required": [item["name"] for item in entry["inputs"]],
                "why": plan["why"],
            }
        )
    counts: Dict[str, int] = {}
    for item in workspaces:
        counts[item["layout"]] = counts.get(item["layout"], 0) + 1
    return {
        "schema": "northstar.northstar_workspaces.v1",
        "generated_from": "ty/service_registry.json",
        "count": len(workspaces),
        "layout_distribution": counts,
        "workspaces": workspaces,
    }


def build_gaps(registry: Dict[str, Any]) -> Dict[str, Any]:
    gaps = []
    for entry in registry["services"]:
        if entry["has_controls"]:
            continue
        gaps.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "group": entry["group"],
                "advanced_route": entry["advanced_route"],
                "reason": entry["gap"],
                "evidence": entry["controls_evidence"],
            }
        )
    return {
        "schema": "northstar.registry_gaps.v1",
        "generated_from": "ty/service_registry.json",
        "count": len(gaps),
        "note": "A service listed here has no control of its own. The fix is a gap record, not a rewrite of the advanced view.",
        "gaps": gaps,
    }


def _dump(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


#: Top-level keys the generator does not own and must never drop.
#: Measured 2026-11-11: block3 added a hand-authored `scene_workspaces` block to
#: `ty/northstar_workspaces.json`, and a plain regeneration would have deleted it. A
#: generated file that silently loses hand-authored sections is worse than a stale one.
FOREIGN_KEYS_KEPT = True


def expected_doc(path: Path, doc: Dict[str, Any]) -> Dict[str, Any]:
    """The document as it should be on disk: generated keys, plus any foreign ones.

    Comparison and writing both go through this, so `--check` and the unit test agree
    with what a regeneration would actually produce.
    """
    if not FOREIGN_KEYS_KEPT or not path.is_file():
        return doc
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return doc
    if not isinstance(existing, dict):
        return doc
    merged = dict(doc)
    for key, value in existing.items():
        if key not in merged:
            merged[key] = value
    return merged



def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Northstar artefacts from the service registry")
    parser.add_argument("--check", action="store_true", help="verify the files on disk instead of writing")
    args = parser.parse_args(argv)

    services = load(SERVICES)["services"]
    registry = load(REGISTRY)

    errors = schema.validate_registry(registry, services)
    errors += check_actions(registry)
    errors += check_evidence(registry)
    if errors:
        for error in errors:
            print("ERROR", error, file=sys.stderr)
        return 1

    docs = {
        TOOLS_OUT: build_tool_list(registry, sorted(backend_index.tools()), backend_index.bojo_tools()),
        WORKSPACES_OUT: build_workspaces(registry),
        GAPS_OUT: build_gaps(registry),
    }
    errors = schema.validate_workspaces(docs[WORKSPACES_OUT], registry)
    errors += schema.validate_tool_list(docs[TOOLS_OUT])
    if errors:
        for error in errors:
            print("ERROR", error, file=sys.stderr)
        return 1

    if args.check:
        drifted = []
        for path, doc in docs.items():
            if not path.is_file() or path.read_text(encoding="utf-8") != _dump(expected_doc(path, doc)):
                drifted.append(str(path.relative_to(ROOT)))
        if drifted:
            print(f"generated files are stale: {drifted}", file=sys.stderr)
            return 1
        print("registry, tool list, workspaces and gaps agree")
        return 0

    for path, doc in docs.items():
        path.write_text(_dump(expected_doc(path, doc)), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    tools = docs[TOOLS_OUT]
    print(
        f"{registry['count']} services · {tools['count']} tools "
        f"({tools['totals']['wired']} wired, {tools['totals']['declared']} declared, "
        f"{tools['totals']['unclaimed']} unclaimed) · "
        f"gaps {docs[GAPS_OUT]['count']} · layouts {docs[WORKSPACES_OUT]['layout_distribution']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
