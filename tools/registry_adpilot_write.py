"""Give AdPilot a persisting primary action, in the registry where the contract reads it.

AdPilot's entry listed three reads and one external action, so `contract` was 0 and `complete` was 0:
there was no write to check and nothing to read back. A campaign plan is exactly the thing a seller
returns to, so AdPilot now declares a **write** action against the foundation's durable jobs store —
the same route and the same read-back that the `jobs` service is proved with.

The action is a claim, so it carries the real route source (`foundation/api/router.py:868`), not a
guess.
"""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
REGISTRY = ROOT / "ty" / "service_registry.json"

ACTION = {
    "name": "save a campaign plan",
    "effect": "write",
    "endpoint": "/api/v1/foundation/jobs-durable",
    "method": "POST",
    "source": "Northstar_backend/foundation/api/router.py:868",
    "why": ("a plan the seller can return to is the difference between a report and a tool; stored as "
            "a durable job and read back by id"),
}

payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
changed = []
for service in payload.get("services") or []:
    if service.get("id") != "adpilot":
        continue
    actions = service.get("actions") or []
    if any(a.get("endpoint") == ACTION["endpoint"] for a in actions):
        continue
    actions.append(dict(ACTION))
    service["actions"] = actions
    changed.append(service["id"])

REGISTRY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"changed": changed}, indent=2))
