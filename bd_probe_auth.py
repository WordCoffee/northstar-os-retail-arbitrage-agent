#!/usr/bin/env python3
"""Probe: inspect 401 vs 404 bodies for each candidate Bright Data credential.
Prints status + body only (never credential values)."""
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
paths = [
    "/datasets/v3/list_dataset_ids",
    "/datasets/v3/filters",
]
cands = []
for envfile in (ROOT / ".env", ROOT / "Northstar_backend" / ".env"):
    if envfile.exists():
        for k, v in dotenv_values(envfile).items():
            if "BRIGHTDATA" in k and v and v.strip() and not k.endswith(("_ENABLED", "_ZONE")):
                cands.append((f"{k}@{envfile.name}", v.strip()))

for name, val in cands:
    for p in paths:
        try:
            r = requests.get(f"https://api.brightdata.com{p}",
                             headers={"Authorization": f"Bearer {val}"}, timeout=45)
            body = r.text[:180].replace("\n", " ")
            print(f"{name:55s} {p:38s} -> {r.status_code} {body}")
        except Exception as e:
            print(f"{name:55s} {p:38s} -> EXC {e}")
