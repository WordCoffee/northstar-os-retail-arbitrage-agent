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

print("----")
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL -> {fails}")
