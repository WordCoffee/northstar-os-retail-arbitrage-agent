"""One-off E2E smoke for the RE design-studio build (run from Northstar_backend).

Project -> persisted dielines (SVG+PDF assets) -> file serving -> project ZIP
export -> design-agent brief. Uses dependency-override identity and the real
dev database + file store. Cleans its project up afterwards.

Run:  python _re_ext_e2e_smoke.py
"""

from __future__ import annotations

import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import design_studio_api  # noqa: E402
from main import app  # noqa: E402

app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-re-e2e"
c = TestClient(app)
fails = []


def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(label)


# 1) project
r = c.post("/api/design-studio/projects",
           json={"name": "RE E2E project (scratch)", "section": "re-e2e"})
pj = r.json() if r.status_code == 200 else {}
pid = pj.get("id") or (pj.get("project") or {}).get("id")
check("create project", r.status_code == 200 and bool(pid), f"{r.status_code} pid={pid}")

# 2) persisted dielines
assets = []
for template, params in (("rsc_box", {"length_mm": 160, "width_mm": 120, "height_mm": 80}),
                         ("label_rounded_rectangle", {"width_mm": 90, "height_mm": 60})):
    r = c.post("/api/design-studio/print/dielines",
               json={"template_id": template, "params": params, "persist": True,
                     "project_id": pid})
    body = r.json() if r.status_code == 200 else {}
    got = body.get("assets") or []
    check(f"persist dieline {template}", r.status_code == 200 and len(got) == 2,
          f"{r.status_code} assets={[a['format'] for a in got]}")
    assets += got

# 3) served files
for a in assets:
    r = c.get(a["file_url"])
    check(f"serve {a['format']} {a['asset_id']}", r.status_code == 200 and len(r.content) > 400,
          f"{r.status_code} {len(r.content)}B")

# 4) project ZIP export
r = c.get(f"/api/design-studio/print/projects/{pid}/export.zip")
ok_zip = r.status_code == 200 and r.headers.get("content-type", "").startswith("application/zip")
names = []
if ok_zip:
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        manifest_ok = "manifest.json" in names
        asset_files = [n for n in names if n.startswith("assets/")]
    check("zip export", manifest_ok and len(asset_files) == len(assets),
          f"entries={names}")
else:
    check("zip export", False, f"{r.status_code}")

# 5) design agent brief
r = c.post("/api/design-studio/agent/brief",
           json={"message": "eco kraft stand-up pouch for loose leaf tea",
                 "product": {"title": "Highland Tea", "category": "tea"}})
body = r.json() if r.status_code == 200 else {}
check("agent brief", r.status_code == 200
      and body.get("brief", {}).get("prompt_text", "").startswith("[PRODUCT]"),
      f"{r.status_code} templates={body.get('brief', {}).get('format', {}).get('suggested_templates')}")

# 6) cleanup
r = c.delete(f"/api/design-studio/projects/{pid}")
check("cleanup project", r.status_code in (200, 204), str(r.status_code))

# 7) open API: key lifecycle + key-authenticated endpoints
r = c.post("/api/design-studio/api-keys", json={"label": "e2e"})
kb = r.json() if r.status_code == 201 else {}
secret = (kb.get("key") or {}).get("key")
key_id = (kb.get("key") or {}).get("id")
check("create api key", r.status_code == 201 and bool(secret), f"{r.status_code}")

r2 = c.post("/api/open/2026-10/dielines", json={"template_id": "label_circle"})
check("open api rejects missing key", r2.status_code == 401)

r2 = c.post("/api/open/2026-10/dielines",
            json={"template_id": "label_oval", "params": {"width_mm": 80, "height_mm": 50}},
            headers={"X-Api-Key": secret})
ob = r2.json() if r2.status_code == 200 else {}
check("open dielines with key", r2.status_code == 200 and len(ob.get("assets", [])) == 2,
      f"{r2.status_code} assets={[a['format'] for a in ob.get('assets', [])]}")

r2 = c.post("/api/open/2026-10/packaging-design",
            json={"prompt": "e2e open api design", "callback_url": "https://example.com/hook"},
            headers={"X-Api-Key": secret})
check("open design accepted-or-gated", r2.status_code in (202, 409), f"{r2.status_code}")
if r2.status_code == 202:
    jid = r2.json().get("job_id")
    r3 = c.get(f"/api/open/2026-10/jobs/{jid}", headers={"X-Api-Key": secret})
    check("open job poll", r3.status_code == 200)

r2 = c.delete(f"/api/design-studio/api-keys/{key_id}")
check("revoke api key", r2.status_code == 200)

r2 = c.post("/api/open/2026-10/dielines", json={"template_id": "label_circle"},
            headers={"X-Api-Key": secret})
check("revoked key rejected", r2.status_code == 401)

print("----")
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL -> {fails}")
