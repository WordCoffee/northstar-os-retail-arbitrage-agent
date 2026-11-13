"""What may browse while the owner has paused browser work.

`state/vision/PAUSE` exists because a lane opened Chrome Profiles 1 and 4 and walked Northstar
pages back to back (2026-11-11, 03:14–03:38 local). The lane was the unlock watcher:
`tools/unlock_watch.py` → `tools/ty_unlock_checks.py` → `tools/registry/vision_walk.py` →
`tools/vision/chrome_uia.py`. Every step refused the *wrong page*; none of them checked the
*profile*, so the walk typed its route list into whatever Chrome window happened to hold focus.

The rule this module enforces is deliberately narrow:

* **PAUSE absent** — every kind is allowed, as before.
* **PAUSE present** — exactly one kind may browse: a **headless** Playwright run against a
  **loopback** URL (`127.0.0.1`, `localhost`, `::1`). That is the test lane, it composes no window,
  and it cannot type into the owner's browser.
* Everything else — UIA on a real Chrome window, CDP, a headed Playwright launch — is refused with
  the reason, not silently skipped.

    from tools.vision.browse_guard import may_browse
    ok, reason = may_browse("uia", "http://127.0.0.1:8101/ui/")   # refused while PAUSE exists
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PAUSE = ROOT / "state" / "vision" / "PAUSE"

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0"}

#: Browsing kinds, most invasive first. Only the headless-loopback one survives a pause.
UIA = "uia"                     # UI Automation on the owner's real Chrome window
CDP = "cdp"                     # DevTools protocol against a real profile
PLAYWRIGHT_HEADED = "playwright_headed"
PLAYWRIGHT_HEADLESS = "playwright_headless"


def _is_loopback(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return host in LOOPBACK_HOSTS


def may_browse(kind: str, url: Optional[str] = None, *, pause: Optional[Path] = None
               ) -> Tuple[bool, str]:
    """May this kind of browsing happen now? Returns (allowed, reason-when-refused)."""
    pause_path = Path(pause or PAUSE)
    if not pause_path.exists():
        return True, ""
    if kind == PLAYWRIGHT_HEADLESS and _is_loopback(url):
        return True, ""
    if kind == PLAYWRIGHT_HEADLESS:
        return False, ("PAUSE is present: headless Playwright may only reach loopback, "
                       f"not {urlset(url)}")
    return False, (f"PAUSE is present: {kind!r} browsing is refused. Only headless Playwright "
                   "against 127.0.0.1 may browse while the owner has paused browser work")


def urlset(url: Optional[str]) -> str:
    """The host of a URL, for a message that does not echo a query or a path."""
    try:
        return urlsplit(url or "").hostname or "(no host)"
    except ValueError:
        return "(unparseable)"


def refuse(kind: str, url: Optional[str] = None) -> None:
    """Raise where a caller must stop. `ToolRefused` is a typed refusal, not an error."""
    allowed, reason = may_browse(kind, url)
    if not allowed:
        raise ToolRefused(reason)


class ToolRefused(RuntimeError):
    """A tool declined to act. Expected, named, and never a partial action."""


def playwright_guard() -> None:
    """For a Playwright fixture: refuse a headed launch or a non-loopback base URL under PAUSE."""
    if not PAUSE.exists():
        return
    if os.environ.get("PWDEBUG"):  # headed debugging is not headless
        raise ToolRefused("PAUSE is present: PWDEBUG opens a headed browser")
    base = os.environ.get("PLAYWRIGHT_BASE_URL") or os.environ.get("BASE_URL") or ""
    if base and not _is_loopback(base):
        raise ToolRefused(f"PAUSE is present: Playwright base URL must be loopback, not {urlset(base)}")


__all__ = ["CDP", "PLAYWRIGHT_HEADED", "PLAYWRIGHT_HEADLESS", "ToolRefused", "UIA",
           "may_browse", "playwright_guard", "refuse", "urlset"]
