"""V9 dogfood: visit improved services through Ty's Vision and run a seller task on each.

Owner instruction 2026-11-08: *have the verifier open 3 improved services
(competitor-monitor, listings, socialpulse) via Vision and run a real seller task on each.*

The mechanics are here and tested without a browser: attach through the leased Chrome window
(UIA, pixel fallback), open the service, read what rendered, run a task, and record the
evidence — plus the screenshot, so a reviewer can see what Ty saw.

Being honest about the precondition: this needs an **unlocked, signed-in desktop**. On a
locked session the backend refuses by name and nothing is driven.

    python -m tools.vision.dogfood --services competitor-monitor,listings,socialpulse
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "ty" / "d15_dogfood.json"
SHOTS = ROOT / "reports" / "ty" / "dogfood_shots"
BASE = "http://127.0.0.1:8101/ui"

DEFAULT_SERVICES = ("competitor-monitor", "listings", "socialpulse")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seller_task(service: str, page_text: str) -> Dict[str, Any]:
    """The seller's question, answered from what the page actually shows.

    The task is deliberately checkable: does the service's own vocabulary appear, is there a
    number on the page, and is there something a seller can act on. A page that renders a
    shell with no data fails, which is the point of dogfooding.
    """
    text = str(page_text or "")
    folded = text.casefold()
    vocabulary = {
        "competitor-monitor": ("competitor", "price", "change"),
        "listings": ("listing", "title", "price"),
        "socialpulse": ("social", "post", "reach"),
    }.get(service, (service,))
    hits = [word for word in vocabulary if word in folded]
    has_number = any(char.isdigit() for char in text)
    actionable = any(word in folded for word in ("save", "apply", "generate", "refresh",
                                                 "run", "review", "create", "export"))
    passed = bool(hits) and has_number
    return {"ok": passed, "service": service, "vocabulary": hits,
            "has_number": has_number, "actionable": actionable,
            "chars": len(text),
            "why": ("" if passed else
                    "the page did not show the service's own vocabulary and a number")}


def run(*, services: List[str] = None, open_url: Optional[Callable[[str], Dict[str, Any]]] = None,
        read_text: Optional[Callable[[], Dict[str, Any]]] = None,
        shot: Optional[Callable[[], Dict[str, Any]]] = None,
        base: str = BASE, out: Optional[Path] = None) -> Dict[str, Any]:
    """Open each service via Vision, read it, run the seller task, keep the evidence."""
    names = list(services or DEFAULT_SERVICES)
    rows: List[Dict[str, Any]] = []
    for name in names:
        url = f"{base.rstrip('/')}/{name}"
        step: Dict[str, Any] = {"service": name, "url": url, "at": _now()}
        if open_url is None or read_text is None:
            step.update({"ok": False, "blocked": True,
                         "reason": ("no live Vision session: the desktop must be unlocked "
                                    "and Chrome attached before this can drive anything")})
            rows.append(step)
            continue
        opened = open_url(url)
        step["opened"] = bool(opened.get("ok"))
        step["title"] = opened.get("title") or opened.get("reason")
        if not opened.get("ok"):
            step.update({"ok": False, "reason": opened.get("reason")})
            rows.append(step)
            continue
        time.sleep(0.5)
        text = read_text()
        step["text_chars"] = len(str(text.get("text") or ""))
        step["task"] = seller_task(name, text.get("text") or "")
        step["ok"] = bool(step["task"].get("ok"))
        if shot is not None:
            captured = shot()
            step["screenshot"] = _save_shot(name, captured)
        rows.append(step)

    passed = sum(1 for row in rows if row.get("ok"))
    payload = {"at": _now(), "services": rows, "passed": passed, "total": len(rows),
               "pass": passed == len(rows) and bool(rows),
               "base": base}
    target = Path(out or OUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return payload


def _save_shot(service: str, captured: Dict[str, Any]) -> Optional[str]:
    png = (captured or {}).get("png")
    if not png:
        return None
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{service.replace('/', '_')}.png"
    path.write_bytes(png)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def live() -> Dict[str, Any]:
    """Wire the real Chrome UIA session, and refuse loudly if it cannot drive."""
    from . import chrome_uia

    attached = chrome_uia.ChromeUIA.attach()
    if not attached.get("ok"):
        return {"ok": False, "reason": attached.get("reason"),
                "refused": attached.get("refused", False)}
    page = attached["page"]
    focused = page.focus()
    if not focused.get("ok"):
        return {"ok": False, "reason": f"cannot take the foreground: {focused.get('reason')}"}
    return {"ok": True, "page": page}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V9 dogfood through Ty's Vision")
    parser.add_argument("--services", default=",".join(DEFAULT_SERVICES))
    parser.add_argument("--base", default=BASE)
    ns = parser.parse_args(argv)
    names = [name.strip() for name in ns.services.split(",") if name.strip()]

    session = live()
    if not session.get("ok"):
        payload = run(services=names, base=ns.base)
        print(json.dumps({"pass": payload["pass"],
                          "reason": session.get("reason"),
                          "rows": [{k: row.get(k) for k in ("service", "ok", "reason")}
                                   for row in payload["services"]]}, indent=2))
        return 2
    page = session["page"]
    try:
        payload = run(services=names, base=ns.base, open_url=page.open_url,
                      read_text=page.read_text, shot=page.screenshot)
    finally:
        page.close_tab()
    print(json.dumps({"pass": payload["pass"], "passed": payload["passed"],
                      "total": payload["total"],
                      "rows": [{k: row.get(k) for k in ("service", "ok", "text_chars",
                                                        "task", "screenshot")}
                               for row in payload["services"]]}, indent=2, default=str))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
