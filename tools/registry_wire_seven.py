import json
from pathlib import Path

ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
REGISTRY = ROOT / "ty" / "service_registry.json"
NAMES = {"scan_products", "compose_listing", "build_dieline", "track_keywords",
         "watch_competitor", "margin_report", "plan_campaign"}

payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
flipped = []
for service in payload.get("services") or []:
    refs = [("bojo_tool", service.get("bojo_tool") or {})]
    refs += [("also_declares", ref) for ref in (service.get("also_declares") or [])]
    for field, ref in refs:
        if ref.get("name") in NAMES and ref.get("status") == "declared":
            ref["status"] = "wired"
            ref["reason"] = ("reg-03 handler exists in bojo_tools and chat_tools.TOOLS carries a spec "
                             "(2026-11-10)")
            flipped.append(f"{service['id']}:{ref['name']}")

REGISTRY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"flipped": flipped, "count": len(flipped)}, indent=2))
