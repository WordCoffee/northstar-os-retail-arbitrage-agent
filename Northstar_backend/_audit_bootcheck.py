"""Offline local-boot verification for the local-readiness audit (Parallel Session A).

Boots the local FastAPI app with TestClient (no external calls, no server bind)
and verifies: app imports/boots, canonical routes mount, foundation + golden
goose routers are present, and safe read-only endpoints respond.
"""
import json
import sys

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

results = {}

# 1. Health
r = client.get("/health")
results["/health"] = r.status_code

# 2. Root redirect to /ui
r = client.get("/", follow_redirects=False)
results["/ (redirect -> /ui)"] = r.status_code

# 3. OpenAPI schema present (enumerate route namespaces)
r = client.get("/openapi.json")
results["/openapi.json"] = r.status_code
schema_paths = set()
if r.status_code == 200:
    schema_paths = set(r.json().get("paths", {}).keys())

# 4. Namespace presence
def has(prefix):
    return any(p.startswith(prefix) for p in schema_paths)

results["namespace /api/v1/foundation"] = has("/api/v1/foundation")
results["namespace /api/golden-goose"] = has("/api/golden-goose")
results["namespace /api/search|product"] = has("/api/search") or has("/api/product")
results["namespace /api/monitoring"] = has("/api/monitoring")
results["namespace /api/admin"] = has("/api/admin")

# 5. Foundation readiness-ish read (orgs list) - offline shim; may 401/404 safely
r = client.get("/api/v1/foundation/organizations")
results["foundation /organizations"] = r.status_code

print("==== BOOT VERIFICATION ====")
print(json.dumps(results, indent=2))
print("total schema paths:", len(schema_paths))
for p in sorted(schema_paths):
    if any(p.startswith(x) for x in ("/api/v1/foundation", "/api/golden-goose", "/api/monitoring", "/api/admin", "/api/search")):
        print("  ", p)