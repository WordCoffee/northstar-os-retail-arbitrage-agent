"""Walk every advanced-view route with Ty's Vision, or say honestly why it could not.

Order of preference, per route:

1. **live** — a Chrome window is attached through ``tools.vision.chrome_uia``,
   the route is opened in a session-owned tab, and ``tools.vision.understand``
   describes the rendered page. Recorded only when both steps return data.
2. **screenshot** — a committed capture of that route exists under ``reports/``.
   The capture is named, not described, so no claim is made beyond "this file
   shows this route".
3. **audit** — a prior live walk recorded the route's title and controls in
   ``ty/ux_audit.json`` (a committed artefact with rows that carry ``renders``).
4. **backend** — nothing visual is available; the entry says so and cites the
   backend only.

Nothing here starts or stops a server, launches Chrome, or writes into reports.
It prints JSON; ``build.py --vision`` merges the result into the registry.

    python -m tools.registry.vision_walk
    python -m tools.registry.vision_walk --routes /hub,/ledger
"""
from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8101/ui"

#: Committed caps that are not named after the route they show.
SCREENSHOT_ALIASES = {
    "listings": ("listing-guardian.png",),
    "product-finder": ("product-finder.png",),
}

SCREENSHOT_DIRS = (
    "reports/ui_audit_20261016",
    "reports/ty/ux_audit_shots",
    "reports/ty/dogfood_shots",
)


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def desktop_state() -> Dict[str, Any]:
    """Foreground process, Chrome windows and server reachability, measured now."""
    state: Dict[str, Any] = {"at_route_base": BASE}
    try:
        from tools.vision import capture  # noqa: PLC0415

        windows = capture.windows()
        state["windows"] = len(windows)
        state["foreground"] = (windows[0].get("process") if windows else None) or None
        state["chrome_windows"] = [w for w in windows if "chrome" in str(w.get("process", "")).lower()]
    except Exception as exc:  # noqa: BLE001 - a probe failure is data
        state["windows_error"] = f"{type(exc).__name__}: {exc}"
        state["chrome_windows"] = []
    state["locked"] = str(state.get("foreground") or "").lower().startswith("lockapp")
    state["server_8101"] = _port_open(8101)
    state["server_8000"] = _port_open(8000)
    return state


def _screenshot_for(service_id: str, route: str) -> Optional[Path]:
    slug = route.strip("/").replace("/", "-") or "root"
    names = SCREENSHOT_ALIASES.get(service_id, ()) + (f"{slug}.png", f"{service_id}.png")
    for directory in SCREENSHOT_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for name in names:
            candidate = base / name
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
    return None


def _audit_row(service_id: str) -> Optional[Dict[str, Any]]:
    path = ROOT / "ty" / "ux_audit.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    for row in data.get("rows", []):
        if row.get("id") == service_id and row.get("renders"):
            return row
    return None


def live_describe(route: str) -> Dict[str, Any]:
    """Open the route in a session-owned tab and describe the page.

    Returns ``{"ok": False, "reason": ...}`` whenever the desktop or the browser
    cannot supply a page. The caller records that reason verbatim.
    """
    try:
        from tools.vision import chrome_uia, understand  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"vision modules unavailable: {exc}"}

    attached = chrome_uia.ChromeUIA.attach()
    if not attached.get("ok"):
        return {"ok": False, "reason": attached.get("reason") or "no Chrome window"}
    page = attached["page"]
    try:
        opened = page.open_url(f"{BASE}{route}", new_tab=True)
        if not opened.get("ok"):
            return {"ok": False, "reason": opened.get("reason") or "route did not open"}
        frame = page.screenshot()
        if not frame.get("ok") or not frame.get("png"):
            return {"ok": False, "reason": frame.get("reason") or "no frame captured"}
        described = understand.describe_page(png=frame["png"])
        return {
            "ok": True,
            "title": described.get("title") or page.title_now(),
            "controls": described.get("controls") or [],
            "summary": described.get("summary") or "",
            "url": opened.get("url"),
        }
    finally:
        try:
            page.close_tab()
        except Exception:  # noqa: BLE001 - closing is best-effort
            pass


def walk(service_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    services = json.loads((ROOT / "ty" / "services.json").read_text(encoding="utf-8"))["services"]
    state = desktop_state()
    rows: List[Dict[str, Any]] = []

    for service in services:
        if service_ids and service["id"] not in service_ids:
            continue
        route = service["route"]
        row: Dict[str, Any] = {
            "id": service["id"],
            "route": route,
            "url": f"{BASE}{route}",
        }
        live = {"ok": False, "reason": "not attempted"}
        if not state["locked"] and state["server_8101"] and state["chrome_windows"]:
            live = live_describe(route)
        else:
            blockers = []
            if state["locked"]:
                blockers.append(f"desktop locked (foreground {state.get('foreground')})")
            if not state["server_8101"]:
                blockers.append("no dev server listening on 127.0.0.1:8101")
            if not state["chrome_windows"]:
                blockers.append("no Chrome window attached")
            live = {"ok": False, "reason": "; ".join(blockers)}

        if live.get("ok"):
            row.update(
                {
                    "vision": "live",
                    "title": live.get("title"),
                    "controls": live.get("controls") or [],
                    "summary": live.get("summary"),
                    "detail": "opened in a session-owned Chrome tab and described by understand.describe_page",
                }
            )
        else:
            shot = _screenshot_for(service["id"], route)
            audit = _audit_row(service["id"])
            if shot is not None:
                row.update(
                    {
                        "vision": "screenshot",
                        "shot": str(shot.relative_to(ROOT)).replace("\\", "/"),
                        "detail": "committed capture of this route; not described live",
                    }
                )
                if audit:
                    row["title"] = audit.get("title")
                    row["controls"] = audit.get("controls") or []
            elif audit:
                row.update(
                    {
                        "vision": "audit",
                        "title": audit.get("title"),
                        "controls": audit.get("controls") or [],
                        "detail": "title and controls recorded by the committed live walk in ty/ux_audit.json",
                    }
                )
            else:
                row.update(
                    {
                        "vision": "backend",
                        "detail": "no live page, no committed capture, no rendered audit row for this route",
                    }
                )
            row["blocked_by"] = live.get("reason")
        rows.append(row)

    totals: Dict[str, int] = {}
    for row in rows:
        totals[row["vision"]] = totals.get(row["vision"], 0) + 1
    return {"at": state, "totals": totals, "routes": rows}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Walk every advanced-view route with Ty's Vision")
    parser.add_argument("--routes", default="", help="comma-separated service ids")
    parser.add_argument("--out", default="", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    ids = [part.strip() for part in args.routes.split(",") if part.strip()]
    result = walk(ids or None)
    blob = json.dumps(result, indent=2, sort_keys=False)
    if args.out:
        Path(args.out).write_text(blob, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
