"""Record the service-sweep results into the capability matrix (batch 2)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "reports" / "northstar_acceptance_20261023" / "capability_matrix.json"

# route -> (status, note)
RESULTS = {
    "/home": ("passed", "renders signed-in Simple shell; composer, plan card, artefact chips verified"),
    "/design-studio/*": ("passed_with_gap", "Simple mode maps the room to the Create focus (chat only); "
                                            "the room itself needs advanced_view, which this account lacks"),
    "/listings": ("passed_with_gap", "resolves to the Grow focus; ListingGuardian room not reachable "
                                     "(advanced_view denied)"),
    "/adpilot": ("passed_with_gap", "resolves to the Grow focus; AdPilot room not reachable"),
    "/golden-goose": ("passed_with_gap", "resolves to the Research focus; GoldenGooseDesk not reachable"),
    "/memory-bank": ("passed_with_gap", "resolves to the Operate focus; MemoryBank not reachable"),
    "/beta-ops": ("failed", "redirects to /home; the operator's own account cannot open Beta Ops"),
    "/sign-in": ("passed", "renders and gates correctly (verified before sign-in)"),
}

TOOLS = {
    "creative_plan": ("passed", "plan card rendered; draft runs a real render"),
    "generate_image": ("passed", "832x1216 portrait render persisted as asset 180a9675"),
    "apply_label": ("passed", "composited the real logo + copy twice; asset 7367995f is the corrected fit"),
    "system_status": ("passed", "called by the model, engine reported"),
    "service_catalog": ("passed", "called by the model, catalogue returned"),
}


def main() -> int:
    m = json.loads(MATRIX.read_text(encoding="utf-8"))
    touched = 0
    for cap in m["capabilities"]:
        r = cap.get("route")
        if cap["kind"] == "ui_route" and r in RESULTS:
            status, note = RESULTS[r]
            cap["status"] = "tested"
            cap["result"] = status
            cap["note"] = note
            touched += 1
        elif cap["kind"] == "chat_tool" and cap["name"] in TOOLS:
            status, note = TOOLS[cap["name"]]
            cap["status"] = "tested"
            cap["result"] = status
            cap["note"] = note
            touched += 1
    m["coverage"] = {
        "tested": touched,
        "total": m["denominator"]["total"],
        "note": ("UI routes were rendered and read through Chrome Connect. In Simple mode a room "
                 "route selects a chat FOCUS instead of rendering the room, and ?shell=advanced is "
                 "demoted because this account has no advanced_view gate - so 'tested' here means "
                 "the route resolves and the chat surface is correct, NOT that the room workspace "
                 "was exercised."),
        "blocked_by_entitlement": ["all Advanced rooms: Design Studio workspace, ListingGuardian, "
                                   "AdPilot, GoldenGooseDesk, MemoryBank, Beta Ops, Admin"],
    }
    MATRIX.write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"updated {touched} capabilities; coverage {touched}/{m['denominator']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
