#!/usr/bin/env python3
"""Step 0 probe: enumerate Bright Data datasets and identify the Amazon
discover-by-keyword and product-by-URL dataset IDs. Prints no secrets."""
import json
import os
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
candidates = []  # (var_name, source_file) - names only, never values
for envfile in (ROOT / ".env", ROOT / "Northstar_backend" / ".env"):
    if envfile.exists():
        for k, v in dotenv_values(envfile).items():
            if "BRIGHTDATA" in k and v and v.strip():
                candidates.append((k, envfile.name, v.strip()))
if os.environ.get("BRIGHTDATA_API_KEY"):
    candidates.append(("process_env:BRIGHTDATA_API_KEY", "env", os.environ["BRIGHTDATA_API_KEY"].strip()))

KEY, KEY_NAME = "", ""
for name, src, val in candidates:
    r = requests.get("https://api.brightdata.com/datasets/v3/list_dataset_ids",
                     headers={"Authorization": f"Bearer {val}"}, timeout=60)
    print(f"tried {name} (from {src}): HTTP {r.status_code}")
    if r.status_code == 200:
        KEY, KEY_NAME = val, f"{name} ({src})"
        break
if not KEY:
    print("FATAL: no working Bright Data credential among:", ", ".join(f"{n}@{s}" for n, s, _ in candidates))
    raise SystemExit(1)
print("Using credential:", KEY_NAME)

HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
BASE = "https://api.brightdata.com/datasets/v3"

def main():
    # 1) list dataset ids available to this account
    r = requests.get(f"{BASE}/list_dataset_ids", headers=HDR, timeout=60)
    print("list_dataset_ids HTTP", r.status_code)
    ids = []
    if r.status_code == 200:
        try:
            data = r.json()
        except Exception:
            data = r.text
        if isinstance(data, list):
            ids = [str(x) for x in data]
        elif isinstance(data, dict):
            ids = [str(x) for x in (data.get("dataset_ids") or data.get("datasets") or [])]
        print(f"count={len(ids)}")
        print(json.dumps(ids, indent=2))
    else:
        print(r.text[:500])

    # 2) metadata for each id -> name/description so we can tell amazon_search from amazon_product
    meta = {}
    for did in ids:
        try:
            m = requests.get(f"{BASE}/{did}", headers=HDR, timeout=60)
            if m.status_code == 200:
                j = m.json()
                meta[did] = {
                    "name": j.get("name"),
                    "description": (j.get("description") or "")[:300],
                    "fields": sorted(j.get("fields", {}).keys()) if isinstance(j.get("fields"), dict) else j.get("fields"),
                }
            else:
                meta[did] = {"http": m.status_code}
        except Exception as e:
            meta[did] = {"error": str(e)[:200]}
    Path("bd_dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    for did, m in meta.items():
        print(did, "->", json.dumps(m)[:240])

if __name__ == "__main__":
    main()
