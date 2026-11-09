"""Does every service actually render? The audit U12 promised, run for real.

`reports/ty/ux_work_order.md` U12 passes only if *every service is reachable by click and
nothing renders blank*. That is a claim about pixels, so this checks pixels: open each route
in the leased Chrome window, screenshot it, compare it with the home page, and read it with
the local vision model. A route that renders the home shell is a failure even though its
`<Route>` exists — which is exactly the hole `measured` had.

    python -m tools.vision.ux_audit --run
"""
from __future__ import annotations

import argparse
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ty" / "ux_audit.json"
SHOTS = ROOT / "reports" / "ty" / "ux_audit_shots"
SERVICES = ROOT / "ty" / "services.json"
BASE = "http://127.0.0.1:8101/ui"

#: Below this share of changed cells a page is "the same page as home".
SAME_AS_HOME = 0.10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _changed_share(first: bytes, second: bytes) -> float:
    from PIL import Image, ImageChops

    with Image.open(io.BytesIO(first)) as a, Image.open(io.BytesIO(second)) as b:
        left = a.convert("L").resize((80, 50))
        right = b.convert("L").resize((80, 50))
    diff = ImageChops.difference(left, right)
    cells = list(diff.getdata())
    changed = sum(1 for value in cells if value > 24)
    return round(changed / max(1, len(cells)), 3)


def routes() -> List[Dict[str, str]]:
    data = json.loads(SERVICES.read_text(encoding="utf-8"))
    return [{"id": row["id"], "route": row.get("route") or ""}
            for row in data.get("services") or [] if row.get("route")]


def run(*, services: Optional[List[Dict[str, str]]] = None,
        open_url=None, screenshot=None, read_page=None,
        out: Optional[Path] = None) -> Dict[str, Any]:
    """Open every route, screenshot it, and decide whether it is its own page."""
    rows: List[Dict[str, Any]] = []
    if open_url is None:
        # no live session: report the refusal instead of inventing results
        return {"ok": False, "blocked": True, "at": _now(), "rows": rows,
                "reason": "no live Vision session (desktop must be unlocked)"}

    home = open_url(f"{BASE}/", new_tab=True)
    time.sleep(1.2)
    home_shot = (screenshot() or {}).get("png")
    for service in services or routes():
        url = f"{BASE}{service['route']}"
        entry: Dict[str, Any] = {"id": service["id"], "route": service["route"], "url": url}
        # One tab, reused: 29 fresh tabs eventually degrade the renderer ("Aw, Snap!") and
        # the audit starts measuring crashes instead of pages.
        opened = open_url(url, new_tab=False)
        entry["opened"] = bool(opened.get("ok"))
        if not opened.get("ok"):
            entry.update({"renders": False, "reason": opened.get("reason")})
            rows.append(entry)
            continue
        time.sleep(1.2)
        shot = screenshot() or {}
        png = shot.get("png")
        if not png or not home_shot:
            entry.update({"renders": False, "reason": "no screenshot"})
            rows.append(entry)
            continue
        share = _changed_share(home_shot, png)
        entry["changed_vs_home"] = share
        read = (read_page(png) if read_page else {}) or {}
        entry["title"] = read.get("title", "")
        entry["controls"] = [c.get("label") for c in (read.get("controls") or [])][:8]
        # The page is its own page when it differs from home beyond noise.
        entry["renders"] = share >= SAME_AS_HOME
        if not entry["renders"]:
            entry["reason"] = f"renders the home shell (changed {share:.1%} of cells)"
        SHOTS.mkdir(parents=True, exist_ok=True)
        (SHOTS / f"{service['id']}.png").write_bytes(png)
        rows.append(entry)

    passing = sum(1 for row in rows if row.get("renders"))
    payload = {"ok": True, "at": _now(), "base": BASE, "rows": rows,
               "renders": passing, "total": len(rows),
               "failures": [row["id"] for row in rows if not row.get("renders")]}
    target = Path(out or OUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def live() -> Dict[str, Any]:
    from . import chrome_uia, understand

    attached = chrome_uia.ChromeUIA.attach()
    if not attached.get("ok"):
        return {"ok": False, "reason": attached.get("reason")}
    page = attached["page"]
    focused = page.focus()
    if not focused.get("ok"):
        return {"ok": False, "reason": focused.get("reason")}
    return {"ok": True, "page": page, "understand": understand}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Service render audit")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--services", default="")
    ns = parser.parse_args(argv)

    session = live()
    if not session.get("ok"):
        payload = run()
        print(json.dumps({"ok": False, "reason": session.get("reason")}, indent=2))
        return 2
    page, understand = session["page"], session["understand"]
    wanted = [name.strip() for name in ns.services.split(",") if name.strip()]
    table = [row for row in routes() if not wanted or row["id"] in wanted]
    try:
        payload = run(services=table, open_url=page.open_url, screenshot=page.screenshot,
                      read_page=lambda png: understand.describe_page(png=png))
    finally:
        page.close_tab()
    print(json.dumps({"renders": payload["renders"], "total": payload["total"],
                      "failures": payload["failures"]}, indent=2))
    return 0 if payload["renders"] == payload["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
