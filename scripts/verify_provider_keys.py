#!/usr/bin/env python3
"""Live credential verification for the Amazon-data provider keys.

Scope
-----
Confirms that the keys configured in the repo-root ``.env`` (the file the
project treats as authoritative) actually authenticate with their providers,
and reports what still blocks live use:

  * Bright Data  - ``BRIGHTDATA_UNLOCKER_API_KEY`` + the configured zone
                   (Web Unlocker), ``BRIGHTDATA_API_KEY`` (customer API)
  * ChocoData    - ``CHOCODATA_API_KEY`` + remaining credits
  * Rainforest   - ``RAINFOREST_API_KEY`` + remaining credits

Credential hygiene
------------------
Secret values are never printed, logged, written or committed. Each key is read
from the repo-root ``.env`` in-process and handed straight to the provider. This
script reports only: presence, the provider's *public* key-format prefix,
HTTP status and the provider's own account figures.

Gate discipline
---------------
No Amazon host is contacted and no credit is spent:

  * Bright Data  - customer zone metadata endpoints (free, no request credits)
  * ChocoData    - ``/api/v1/usage`` (free account read)
  * Rainforest   - ``/account`` (free account read)

Usage
-----
    python scripts/verify_provider_keys.py            # human report
    python scripts/verify_provider_keys.py --json     # machine report

Exit code 0 only when every provider authenticates AND has no blocker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_ENV = REPO_ROOT / ".env"
BACKEND_ENV = REPO_ROOT / "Northstar_backend" / ".env"

TIMEOUT = 45

# Public key prefixes documented by the providers. Printing these tells you a
# key is the right *kind* without revealing any secret material.
PUBLIC_PREFIXES = {
    "CHOCODATA_API_KEY": ("asa_live_", "cd_test_"),
}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return {k: (v or "").strip() for k, v in dotenv_values(path).items()}


def _prefix_label(name: str, value: str) -> str:
    for pref in PUBLIC_PREFIXES.get(name, ()):
        if value.startswith(pref):
            return pref
    return "unlabelled"


def _digest(value: str) -> str:
    """Non-reversible fingerprint, used only to compare two sources for equality."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] if value else ""


def _get(url: str, **kwargs) -> tuple[int | None, str, dict | list | None]:
    try:
        r = requests.get(url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.RequestException as exc:
        return None, f"{type(exc).__name__}: {exc}", None
    try:
        body = r.json()
    except ValueError:
        body = None
    return r.status_code, r.text[:300].replace("\n", " "), body


def check_brightdata_unlocker(key: str, configured_zone: str) -> dict:
    status, snippet, body = _get(
        "https://api.brightdata.com/zone/get_all_zones",
        headers={"Authorization": f"Bearer {key}"},
    )
    zones: dict[str, str] = {}
    if isinstance(body, list):
        for z in body:
            if isinstance(z, dict) and z.get("name"):
                zones[z["name"]] = z.get("status", "unknown")
    active = sorted(n for n, s in zones.items() if s == "active")
    zone_status = zones.get(configured_zone, "missing")
    blockers = []
    if status != 200:
        blockers.append(f"auth/API error (HTTP {status})")
    if status == 200 and zone_status != "active":
        blockers.append(
            f"configured zone {configured_zone!r} is {zone_status}; "
            f"active zones on this account: {active or 'none'}"
        )
    return {
        "provider": "brightdata/unlocker",
        "env_var": "BRIGHTDATA_UNLOCKER_API_KEY",
        "http_status": status,
        "auth_ok": status == 200,
        "ready": not blockers,
        "zones": zones,
        "configured_zone": configured_zone,
        "configured_zone_status": zone_status,
        "active_zones": active,
        "blockers": blockers,
        "detail": snippet if status != 200 else f"{len(zones)} zone(s) visible",
    }


def check_brightdata_datasets(key: str) -> dict:
    status, snippet, body = _get(
        "https://api.brightdata.com/datasets/v3/list_dataset_ids",
        headers={"Authorization": f"Bearer {key}"},
    )
    return {
        "provider": "brightdata/datasets",
        "env_var": "BRIGHTDATA_API_KEY",
        "http_status": status,
        "auth_ok": status == 200,
        "ready": status == 200,
        "blockers": [] if status == 200 else
        ["datasets endpoints not provisioned for this account/token"],
        "detail": snippet if status != 200 else f"datasets visible: {body}",
    }


def check_chocodata(key: str) -> dict:
    """Read the workspace usage record; costs nothing and touches no target site."""
    status, snippet, body = _get(
        "https://api.chocodata.com/api/v1/usage", params={"api_key": key}
    )
    remaining = body.get("credits_remaining") if isinstance(body, dict) else None
    plan = body.get("plan") if isinstance(body, dict) else None
    blockers = []
    if status != 200:
        blockers.append(f"usage endpoint HTTP {status} (key rejected?)")
    elif remaining == 0:
        blockers.append("credit balance is 0 - every scrape returns 402 INSUFFICIENT_CREDITS")
    return {
        "provider": "chocodata",
        "env_var": "CHOCODATA_API_KEY",
        "http_status": status,
        "auth_ok": status == 200,
        "ready": status == 200 and (remaining or 0) > 0,
        "plan": plan,
        "credits_remaining": remaining,
        "blockers": blockers,
        "detail": snippet if status != 200 else f"credits_remaining={remaining}",
    }


def check_rainforest(key: str) -> dict:
    status, snippet, body = _get(
        "https://api.rainforestapi.com/account", params={"api_key": key}
    )
    info = {}
    if isinstance(body, dict):
        acct = body.get("account_info") if isinstance(body.get("account_info"), dict) else body
        for field in ("plan", "credits_used", "credits_limit", "credits_remaining",
                      "credits_reset_at", "overage_allowed"):
            if field in acct:
                info[field] = acct[field]
    remaining = info.get("credits_remaining", 0) or 0
    return {
        "provider": "rainforest",
        "env_var": "RAINFOREST_API_KEY",
        "http_status": status,
        "auth_ok": status == 200,
        "ready": status == 200 and remaining > 0,
        "account": info,
        "blockers": [] if (status == 200 and remaining > 0) else
        [snippet[:160] if status != 200 else "no credits remaining"],
        "detail": snippet if status != 200 else "account endpoint OK",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    root = _load(ROOT_ENV)
    backend = _load(BACKEND_ENV)

    wanted = [
        "BRIGHTDATA_UNLOCKER_API_KEY",
        "BRIGHTDATA_UNLOCKER_ZONE",
        "BRIGHTDATA_API_KEY",
        "CHOCODATA_API_KEY",
        "RAINFOREST_API_KEY",
    ]

    visibility = {}
    for name in wanted:
        r_val, b_val = root.get(name, ""), backend.get(name, "")
        visibility[name] = {
            "root_env": bool(r_val),
            "backend_env": bool(b_val),
            "same_value_in_both": bool(r_val and b_val and _digest(r_val) == _digest(b_val)),
            "backend_shadows_root": bool(r_val and b_val and _digest(r_val) != _digest(b_val)),
        }

    results = []

    key = root.get("BRIGHTDATA_UNLOCKER_API_KEY", "")
    if key:
        results.append(check_brightdata_unlocker(key, root.get("BRIGHTDATA_UNLOCKER_ZONE", "")))
    else:
        results.append({"provider": "brightdata/unlocker", "env_var": "BRIGHTDATA_UNLOCKER_API_KEY",
                        "http_status": None, "auth_ok": False, "ready": False,
                        "blockers": ["key absent from repo-root .env"], "detail": "key absent"})

    key = root.get("BRIGHTDATA_API_KEY", "")
    if key:
        results.append(check_brightdata_datasets(key))
    else:
        results.append({"provider": "brightdata/datasets", "env_var": "BRIGHTDATA_API_KEY",
                        "http_status": None, "auth_ok": False, "ready": False,
                        "blockers": ["key absent"], "detail": "key absent"})

    key = root.get("CHOCODATA_API_KEY", "")
    if key:
        res = check_chocodata(key)
        res["key_prefix"] = _prefix_label("CHOCODATA_API_KEY", key)
        results.append(res)
    else:
        results.append({"provider": "chocodata", "env_var": "CHOCODATA_API_KEY",
                        "http_status": None, "auth_ok": False, "ready": False,
                        "blockers": ["key absent"], "detail": "key absent"})

    key = root.get("RAINFOREST_API_KEY", "")
    if key:
        results.append(check_rainforest(key))
    else:
        results.append({"provider": "rainforest", "env_var": "RAINFOREST_API_KEY",
                        "http_status": None, "auth_ok": False, "ready": False,
                        "blockers": ["key absent"], "detail": "key absent"})

    report = {
        "env_file_checked": str(ROOT_ENV),
        "visibility": visibility,
        "checks": results,
        "all_auth_ok": all(r.get("auth_ok") for r in results),
        "all_ready": all(r.get("ready") for r in results),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"env file: {ROOT_ENV}")
        print("\nvisibility (presence only, no values):")
        for name, v in visibility.items():
            print(f"  {name:28s} root={'yes' if v['root_env'] else 'NO ':3s} "
                  f"backend={'yes' if v['backend_env'] else 'NO ':3s} "
                  f"identical={'yes' if v['same_value_in_both'] else 'no'}"
                  f"{'  <- backend copy DIFFERS (stale)' if v['backend_shadows_root'] else ''}")
        print("\nlive checks:")
        for r in results:
            auth = "AUTH OK" if r.get("auth_ok") else "AUTH FAIL"
            ready = "ready" if r.get("ready") else "BLOCKED"
            print(f"  [{auth:9s}|{ready:7s}] {r['provider']:22s} {r['env_var']:28s} http={r['http_status']}")
            if r.get("key_prefix"):
                print(f"         key format prefix: {r['key_prefix']}")
            if r.get("account"):
                print(f"         account: {r['account']}")
            if r.get("active_zones") is not None:
                print(f"         configured zone {r['configured_zone']!r} -> "
                      f"{r['configured_zone_status']}; active: {r['active_zones']}")
            if r.get("plan") is not None:
                print(f"         plan: {r['plan']}")
            for b in r.get("blockers") or []:
                print(f"         blocker: {b}")
            if not r.get("auth_ok"):
                print(f"         detail: {str(r.get('detail'))[:200]}")
        print(f"\nALL AUTH OK: {report['all_auth_ok']} | ALL READY: {report['all_ready']}")

    return 0 if report["all_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
