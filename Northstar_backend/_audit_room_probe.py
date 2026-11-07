"""Session A: augmented offline room/scheduler/beta probe (read-only, no external calls).

Reports HTTP status for read-only endpoints to classify local readiness:
 200 = public/working  |  401/403 = present + auth-gated (expected, ready)  |  404 = missing
Requires the local app importable (run from Northstar_backend with the venv).
"""
import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)

# (label, path, method)
PROBES = [
    ("golden-goose/health", "/api/golden-goose/health", "GET"),
    ("golden-goose/entitlements", "/api/golden-goose/entitlements", "GET"),
    ("foundation/health", "/api/v1/foundation/health", "GET"),
    ("foundation/auth-posture", "/api/v1/foundation/auth-posture", "GET"),
    ("foundation/environment", "/api/v1/foundation/environment", "GET"),
    ("foundation/ui-mode", "/api/v1/foundation/ui-mode", "GET"),
    ("foundation/beta-status", "/api/v1/foundation/beta-status", "GET"),
    ("foundation/demo/status", "/api/v1/foundation/demo/status", "GET"),
    ("foundation/providers", "/api/v1/foundation/providers", "GET"),
    ("foundation/schedules/posture", "/api/v1/foundation/schedules/posture", "GET"),
    ("foundation/schedules", "/api/v1/foundation/schedules", "GET"),
    ("foundation/preview/active", "/api/v1/foundation/preview/active", "GET"),
    ("foundation/jobs-durable/queue-posture", "/api/v1/foundation/jobs-durable/queue-posture", "GET"),
    ("foundation/entitlements", "/api/v1/foundation/entitlements", "GET"),
    ("monitoring/error-alerts", "/api/monitoring/error-alerts", "GET"),
]

results = {}
for label, path, method in PROBES:
    try:
        r = client.request(method, path)
        code = r.status_code
        note = ""
        if code == 404:
            note = "  <- MISSING (review)"
        elif code in (401, 403):
            note = "  <- auth-gated (present; needs session/dev-shim)"
        results[label] = f"{code}{note}"
    except Exception as e:  # noqa: BLE001
        results[label] = f"EXC:{type(e).__name__}"

# Product Finder: enumerate search/api paths present in the schema
r = client.get("/openapi.json")
paths = set(r.json().get("paths", {}).keys()) if r.status_code == 200 else set()
prod = sorted(p for p in paths if "/api/search" in p or "/api/scanner" in p
              or "/api/sourcescout" in p or "/api/product" in p)
mon = sorted(p for p in paths if "/api/monitoring" in p)

print("==== AUGMENTED ROOM/SCHEDULER/BETA PROBE (offline) ====")
for k, v in results.items():
    print(f"  {k:38s} {v}")
print("==== product-finder /api paths (schema) ====")
for p in prod:
    print("  ", p)
print("==== monitoring /api paths (schema) ====")
for p in mon:
    print("  ", p)
print("==== json ====")
print(json.dumps(results, indent=2))