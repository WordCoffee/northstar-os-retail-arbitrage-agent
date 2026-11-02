"""Simple-mode creative journey, end to end, against the LIVE backend.

The journey a user takes in simple mode: one prompt -> an asset on disk -> the
deliverable is fetchable. Every stage records a real status; nothing is inferred.

    python tools/simple_mode_journey.py --brief "..." [--tier draft]

Exit 0 only when every stage passes.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-User-Id": "demo-t2", "Content-Type": "application/json"}
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "evidence" / "simple_mode_journey.json"

DEFAULT_BRIEF = ("A 6 oz stand-up pouch of organic lion's mane mushroom powder on a warm "
                 "neutral background, soft studio light, premium packaging photography, "
                 "no text, no lettering")


def get(path: str, timeout: float = 20.0):
    req = urllib.request.Request(BASE + path, headers={"X-User-Id": "demo-t2"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:300]
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)[:200]


def post(path: str, payload: dict, timeout: float = 900.0):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"raw": body[:300]}
    except Exception as exc:  # noqa: BLE001
        return None, {"error": str(exc)[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--brief", default=DEFAULT_BRIEF)
    ap.add_argument("--tier", default="draft")
    args = ap.parse_args()
    stages = {}

    status, body = get("/health")
    stages["health"] = {"ok": status == 200, "status": status}

    status, body = get("/api/design-studio/engine")
    engine = {}
    try:
        engine = json.loads(body.decode()) if isinstance(body, (bytes, bytearray)) else {}
    except ValueError:
        engine = {}
    stages["engine_armed"] = {"ok": bool(engine.get("armed")), "status": status,
                              "armed": engine.get("armed"),
                              "reachable": engine.get("reachable")}

    started = time.time()
    status, res = post("/api/design-studio/generate",
                       {"kind": "image", "brief": args.brief, "tier": args.tier,
                        "text_safe": True})
    elapsed = round(time.time() - started, 1)
    asset = (res or {}).get("asset") or {}
    asset_id = asset.get("id") or (res or {}).get("asset_id")
    stages["generate"] = {"ok": status == 200 and bool(asset_id), "status": status,
                          "elapsed_s": elapsed, "asset_id": asset_id,
                          "error": (res or {}).get("detail")}

    if asset_id:
        status, data = get(f"/api/design-studio/assets/{asset_id}/file", timeout=60)
        ok = status == 200 and isinstance(data, (bytes, bytearray)) and len(data) > 10_000
        stages["deliverable"] = {"ok": bool(ok), "status": status,
                                 "bytes": len(data) if isinstance(data, (bytes, bytearray)) else 0}
    else:
        stages["deliverable"] = {"ok": False, "reason": "no asset id"}

    ok = all(s.get("ok") for s in stages.values())
    record = {"brief": args.brief, "tier": args.tier, "ok": ok,
              "stages": stages, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
