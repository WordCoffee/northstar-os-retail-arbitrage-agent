"""Produce a designed product picture through the product's own API.

    python tools/render_product_picture.py --out renders/mogra_lions_mane

This is a thin client: it POSTs to `POST /api/design-studio/product-picture`
on the local backend. It does not composite, render or OCR anything itself, so a
file on disk is evidence that the SERVICE produced it. If the API is not up the
command fails with the exact start instruction instead of quietly rendering in a
different code path.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = "http://127.0.0.1:8000"


def _post(url: str, payload: dict, token: str | None) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    # The dev shim accepts an explicit loopback identity; a hosted deployment
    # needs the bearer token instead.
    req.add_header("X-User-Id", "demo-t2")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=2400) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw[:1200]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path("renders") / "mogra_lions_mane"),
                    help="output directory (must be inside renders/)")
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--faces", default="front,back")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1536)
    ap.add_argument("--tier", default="final", choices=("draft", "final"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--product", default="mogra-lions-mane")
    ap.add_argument("--token", default=None,
                    help="bearer token for a hosted deployment (dev uses the loopback shim)")
    args = ap.parse_args(argv)

    faces = [f.strip() for f in str(args.faces).split(",") if f.strip()]
    payload = {"product": args.product, "out_dir": str(args.out), "faces": faces,
               "width": args.width, "height": args.height, "tier": args.tier}
    if args.seed is not None:
        payload["seed"] = args.seed

    url = args.api.rstrip("/") + "/api/design-studio/product-picture"
    try:
        status, data = _post(url, payload, args.token)
    except urllib.error.URLError as exc:
        print(json.dumps({
            "ok": False,
            "error": "api_unreachable",
            "detail": str(exc.reason),
            "remedy": "start the dev stack with scripts/dev-start.ps1, then re-run",
        }, indent=2))
        return 2

    print(json.dumps({"status": status, "response": data}, indent=2))
    if status != 200 or not data.get("ok"):
        return 1

    produced = [r.get("file") for r in data.get("faces") or [] if r.get("file")]
    missing = [p for p in produced if not Path(p).is_file()]
    if missing:
        print(json.dumps({"ok": False, "error": "reported_files_missing",
                          "files": missing}, indent=2))
        return 1
    print(json.dumps({"ok": True, "files": produced}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
