"""Vet a package against OSV before installing it. Read-only.

The adoption gate (`Northstar_backend/provider_suite.py`) answers one question:
*may this lane use this package* — licence, lane, arming. It cannot answer a
different question: *is this package malicious*. Those are not the same, and an
agent free to install things from GitHub and Hugging Face needs the second one
before `pip install`, not after.

OSV.dev publishes supply-chain advisories; an id beginning `MAL-` is a known
malicious package, not a CVE. This tool refuses on `MAL-*` and reports ordinary
vulnerabilities as warnings, because a CVE is a risk decision and malware is a
stop.

    python tools/vet_package.py --name requests --ecosystem PyPI --version 2.31.0
    python tools/vet_package.py --name evil-pkg --ecosystem PyPI --json
    python tools/vet_package.py --name x --ecosystem PyPI --endpoint http://127.0.0.1:9/v1/query

Exit codes: 0 clear, 1 refused (malicious), 2 usage or transport failure.
A transport failure is never treated as "clear".
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_ENDPOINT = "https://api.osv.dev/v1/query"
#: Only these ecosystems are meaningful here; anything else is refused, not guessed.
ECOSYSTEMS = ("PyPI", "npm", "Go", "crates.io", "Maven", "NuGet", "RubyGems", "Packagist")


class VetError(RuntimeError):
    """The check could not be completed. Never a pass."""


def _post(endpoint: str, payload: Dict[str, Any], timeout: float = 20.0) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VetError(f"osv_unreachable: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VetError(f"osv_bad_json: {exc}") from exc
    if not isinstance(data, dict):
        raise VetError("osv_bad_payload: response is not an object")
    return data


def vet(name: str, ecosystem: str, version: Optional[str] = None, *,
        endpoint: str = DEFAULT_ENDPOINT, timeout: float = 20.0) -> Dict[str, Any]:
    """Return a verdict for one package.

    `{"ok": bool, "verdict": "clear"|"malicious", "malicious": [ids],
      "vulnerabilities": [ids], "name", "ecosystem", "version"}`

    Raises VetError when the check could not be completed.
    """
    clean_name = str(name or "").strip()
    if not clean_name:
        raise VetError("package_name_missing")
    if ecosystem not in ECOSYSTEMS:
        raise VetError(f"unknown_ecosystem: {ecosystem!r} is not one of {', '.join(ECOSYSTEMS)}")

    payload: Dict[str, Any] = {"package": {"name": clean_name, "ecosystem": ecosystem}}
    if version:
        payload["version"] = str(version)

    data = _post(endpoint, payload, timeout=timeout)
    vulns = data.get("vulns") or []
    if not isinstance(vulns, list):
        raise VetError("osv_bad_payload: vulns is not a list")

    ids: List[str] = []
    for entry in vulns:
        if isinstance(entry, dict) and entry.get("id"):
            ids.append(str(entry["id"]))
    malicious = sorted(i for i in ids if i.upper().startswith("MAL-"))
    return {
        "ok": not malicious,
        "verdict": "malicious" if malicious else "clear",
        "malicious": malicious,
        "vulnerabilities": sorted(i for i in ids if i not in malicious),
        "name": clean_name,
        "ecosystem": ecosystem,
        "version": str(version) if version else None,
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--ecosystem", required=True, help="one of: " + ", ".join(ECOSYSTEMS))
    ap.add_argument("--version", default="")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        result = vet(args.name, args.ecosystem, args.version or None,
                     endpoint=args.endpoint)
    except VetError as exc:
        print(f"REFUSED (check incomplete, never a pass): {exc}")
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['name']} ({result['ecosystem']}"
              f"{' ' + result['version'] if result['version'] else ''}): {result['verdict']}")
        if result["malicious"]:
            print("  MALICIOUS advisories: " + ", ".join(result["malicious"]))
        if result["vulnerabilities"]:
            print("  vulnerabilities (risk decision, not a stop): "
                  + ", ".join(result["vulnerabilities"]))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
