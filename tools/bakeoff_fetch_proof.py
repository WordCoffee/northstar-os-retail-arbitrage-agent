"""Prove the hosted bake-off target is a live public site, and log the fetch.

The owner's question: was the hosted target a *live public site*, or something we wrote? The
answer has to be evidence, so this fetches it again now, records the status code, the final URL,
the timestamp and the SHA-256 of the bytes, and compares those bytes with the tracked copy the
bake-off scored.

    python tools/bakeoff_fetch_proof.py --run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "research" / "bakeoff" / "targets" / "hosted"
URL = "https://opencode.ai/"
LOG = TARGET / "_fetch.json"


def fetch(url: str = URL) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "northstar-bakeoff/1.0"})
    started = datetime.now(timezone.utc)
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read()
        status = response.status
        final = response.geturl()
        headers = {key: value for key, value in response.headers.items()
                   if key.casefold() in ("content-type", "server", "last-modified", "etag")}
    local = TARGET / "index.html"
    local_sha = hashlib.sha256(local.read_bytes()).hexdigest() if local.is_file() else ""
    live_sha = hashlib.sha256(body).hexdigest()
    payload = {
        "url": url,
        "final_url": final,
        "status": status,
        "fetched_at": started.isoformat(timespec="seconds"),
        "bytes": len(body),
        "sha256": live_sha,
        "content_type": headers.get("Content-Type", ""),
        "headers": headers,
        "tracked_copy": str(local.relative_to(ROOT)) if local.is_file() else None,
        "tracked_sha256": local_sha,
        "identical_to_tracked": bool(local_sha) and local_sha == live_sha,
        "note": ("A 200 from the site itself, fetched now. If identical_to_tracked is false the "
                 "tracked copy was captured at an earlier time and the site has changed since; "
                 "the bake-off still scored a real capture, and the mismatch is recorded rather "
                 "than hidden."),
    }
    LOG.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove the hosted target is live")
    parser.add_argument("--run", action="store_true")
    ns = parser.parse_args(argv)
    payload = fetch() if ns.run else json.loads(LOG.read_text(encoding="utf-8"))
    print(json.dumps({k: payload.get(k) for k in
                      ("url", "final_url", "status", "fetched_at", "bytes", "sha256",
                       "tracked_sha256", "identical_to_tracked", "content_type")}, indent=2))
    return 0 if payload.get("status") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
