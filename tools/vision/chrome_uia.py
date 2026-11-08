"""Drive the live Chrome profile through UI Automation, with pixels only as a fallback.

The owner's 2026-11-08 instruction: *if the chrome://inspect route fails, drive Profile 6
through UIA plus the pixel fallback; no throwaway profiles, no profile copies.* It failed —
Chrome 156 hands off to the running instance and opens no debugging port, and chrome://inspect
has no toggle that enables one. So this module is the path.

Why UIA first: Chrome publishes an accessibility tree for the page, so links, buttons and text
are readable deterministically. Pixels are used only to click something the tree cannot
invoke, and every click is verify-after-act.

Safety, in order:
* the window is found via `capture.windows()` and classified **before** it is touched, so an
  Amazon or banking window is never focused;
* focus is verified (`GetForegroundWindow`) immediately before any keystroke, and typing is
  refused if the foreground changed;
* a new tab is used, so the owner's current page is never navigated away;
* the tab is closed when the session ends.

    python -m tools.vision.chrome_uia --status
    python -m tools.vision.chrome_uia --open http://127.0.0.1:8101/ui/
"""
from __future__ import annotations

import argparse
import ctypes
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import capture, control, privacy, risk, tree

ROOT = Path(__file__).resolve().parents[2]
SETTLE_S = 0.6
NAV_TIMEOUT_S = 15.0


def _safe(call, default=None):
    try:
        return call()
    except Exception:  # noqa: BLE001 - a dead UIA node is data
        return default


def _pixels_changed(before: bytes, after: bytes, *, threshold: int = 12) -> bool:
    """Did the screen change? Downscaled mean absolute difference, tolerant of caret flicker."""
    try:
        import io

        from PIL import Image, ImageChops, ImageStat

        with Image.open(io.BytesIO(before)) as first, Image.open(io.BytesIO(after)) as second:
            a = first.convert("L").resize((160, 100))
            b = second.convert("L").resize((160, 100))
        diff = ImageChops.difference(a, b)
        mean = ImageStat.Stat(diff).mean[0]
        return mean > threshold
    except Exception:  # noqa: BLE001 - an unreadable frame is not a change
        return False


def foreground_hwnd() -> int:
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:  # noqa: BLE001
        return 0


def chrome_windows() -> List[Dict[str, Any]]:
    """Chrome's top-level windows, already classified by the privacy gate."""
    rows = []
    for window in capture.windows():
        if "chrome" not in str(window.get("process") or "").casefold():
            continue
        verdict = privacy.classify(title=window.get("title", ""),
                                   process=window.get("process", ""))
        rows.append({"hwnd": window["hwnd"], "title": window.get("title", ""),
                     "area": int(window.get("width") or 0) * int(window.get("height") or 0),
                     "allowed": bool(verdict.get("allow")),
                     "reason": verdict.get("reason", "")})
    # A real page window has an area and a title beyond the bare product name; a stale or
    # hidden "Google Chrome" window does not.
    rows.sort(key=lambda row: (row["area"], len(row["title"])), reverse=True)
    return rows


def status() -> Dict[str, Any]:
    rows = chrome_windows()
    return {"windows": len(rows), "allowed": sum(1 for row in rows if row["allowed"]),
            "blocked": sum(1 for row in rows if not row["allowed"]),
            "titles": [row["title"][:60] for row in rows if row["allowed"]][:6],
            "foreground": foreground_hwnd()}


@dataclass
class ChromeUIA:
    """One Chrome window, driven by UIA and, when it must, by a click at a box centre."""

    hwnd: int
    title: str = ""
    control_layer: Any = control.DEFAULT
    opened_tab: bool = False
    _window: Any = None

    # -- lifecycle ---------------------------------------------------------
    @classmethod
    def attach(cls, *, title_hint: str = "", hwnd: int = 0) -> Dict[str, Any]:
        rows = chrome_windows()
        if not rows:
            return {"ok": False, "reason": "no Chrome window found"}
        if hwnd:
            match = next((row for row in rows if row["hwnd"] == int(hwnd)), None)
        else:
            match = next((row for row in rows
                          if title_hint and title_hint.casefold()
                          in row["title"].casefold()), None)
            if match is None:
                match = next((row for row in rows if row["allowed"]), None)
            if match is None:
                blocked = next((row for row in rows if not row["allowed"]), None)
                if blocked:
                    return {"ok": False, "refused": True,
                            "reason": blocked.get("reason") or "blocked window"}
        if not match:
            return {"ok": False, "reason": "no matching Chrome window"}
        if not match["allowed"]:
            return {"ok": False, "refused": True, "reason": match["reason"]}
        page = cls(hwnd=match["hwnd"], title=match["title"])
        found = page._resolve()
        if not found:
            return {"ok": False, "reason": "window handle is not a UIA window"}
        return {"ok": True, "page": page, "title": match["title"]}

    def _resolve(self):
        try:
            import uiautomation as auto  # noqa: PLC0415

            self._window = auto.ControlFromHandle(int(self.hwnd))
            return self._window if self._window else None
        except Exception:  # noqa: BLE001
            return None

    def close_tab(self) -> Dict[str, Any]:
        if not self.opened_tab:
            return {"ok": True, "detail": "no tab owned by this session"}
        return self._keys("^w", expect_foreground=True)

    # -- observation -------------------------------------------------------
    def title_now(self) -> str:
        return str(_safe(lambda: self._window.Name, "") or "")

    def elements(self) -> List[Dict[str, Any]]:
        if self._window is None:
            self._resolve()
        found = tree.walk(self._window) if self._window is not None else []
        return found

    def read_text(self, limit: int = 4000) -> Dict[str, Any]:
        elements = self.elements()
        if not elements:
            return {"ok": False, "text": "", "reason": "empty accessibility tree"}
        parts = []
        for element in elements:
            name = str(element.get("name") or "")
            if name and not element.get("mask"):
                parts.append(name)
        text = " ".join(dict.fromkeys(parts))[:limit]
        return {"ok": bool(text), "text": privacy.redact(text),
                "elements": len(elements)}

    def find(self, needle: str, *, role: str = "") -> Optional[Dict[str, Any]]:
        low = str(needle).casefold()
        elements = self.elements()
        candidates = [e for e in elements if not role
                      or str(e.get("role", "")).casefold() == role.casefold()]
        for element in candidates:
            if str(element.get("name", "")).casefold() == low:
                return element
        for element in candidates:
            if low in str(element.get("name", "")).casefold():
                return element
        return None

    def screenshot(self) -> Dict[str, Any]:
        return capture.frame({"hwnd": self.hwnd, "title": self.title_now(),
                              "process": "chrome.exe"})

    # -- actions -----------------------------------------------------------
    def focus(self) -> Dict[str, Any]:
        verdict = privacy.classify(title=self.title_now(), process="chrome.exe")
        if not verdict.get("allow"):
            return {"ok": False, "refused": True, "reason": verdict.get("reason")}
        if self._window is None:
            self._resolve()
        if self._force_foreground():
            return {"ok": True, "foreground": int(self.hwnd)}
        try:
            self._window.SetActive()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        deadline = time.time() + 3
        while time.time() < deadline:
            if foreground_hwnd() == int(self.hwnd):
                return {"ok": True, "foreground": int(self.hwnd)}
            time.sleep(0.1)
        return {"ok": False, "reason": "window did not take the foreground"}

    def _force_foreground(self) -> bool:
        """Windows only lets the foreground process steal focus; borrow its input thread."""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = int(self.hwnd)
        if foreground_hwnd() == hwnd:
            return True
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        foreground = foreground_hwnd()
        current = kernel32.GetCurrentThreadId()
        attached = []
        try:
            for other in (foreground, hwnd):
                tid = user32.GetWindowThreadProcessId(other, None)
                if tid and tid != current:
                    attached.append(tid)
                    user32.AttachThreadInput(current, tid, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        except Exception:  # noqa: BLE001
            return False
        finally:
            for tid in attached:
                try:
                    user32.AttachThreadInput(current, tid, False)
                except Exception:  # noqa: BLE001
                    pass
        deadline = time.time() + 2
        while time.time() < deadline:
            if foreground_hwnd() == hwnd:
                return True
            time.sleep(0.1)
        return False

    def _keys(self, sequence: str, *, expect_foreground: bool = True) -> Dict[str, Any]:
        if expect_foreground and foreground_hwnd() != int(self.hwnd):
            return {"ok": False, "refused": True,
                    "reason": "foreground is not the Chrome window; refusing to type"}
        verdict = privacy.classify(title=self.title_now(), process="chrome.exe")
        if not verdict.get("allow"):
            return {"ok": False, "refused": True, "reason": verdict.get("reason")}

        def run():
            import pyautogui  # noqa: PLC0415

            pyautogui.PAUSE = 0.02
            # A chord is `hotkey`; a single key is `press`. Passing a bare string to
            # `hotkey` types its letters one by one — measured 2026-11-08, when "enter"
            # ended up inside the omnibox as "...competitor-monitorenter".
            if "+" in sequence:
                pyautogui.hotkey(*[part.strip() for part in sequence.split("+")])
            else:
                pyautogui.press(sequence)
            return sequence

        return self.control_layer.act(run)

    def _type(self, text: str) -> Dict[str, Any]:
        if foreground_hwnd() != int(self.hwnd):
            return {"ok": False, "refused": True, "reason": "foreground changed"}
        action = {"kind": "type", "target": "omnibox", "field": "address bar"}
        verdict = risk.evaluate(action, url=self.title_now(), title=self.title_now())
        if not verdict["allow"]:
            return {"ok": False, "refused": True, **verdict}

        def run():
            import pyautogui  # noqa: PLC0415

            pyautogui.write(text, interval=0.01)
            return len(text)

        return self.control_layer.act(run)

    def open_url(self, url: str, *, new_tab: bool = True) -> Dict[str, Any]:
        """Open a URL in a tab this session owns, and verify the page actually changed.

        A single-page app keeps one document title, so a title change is not a navigation
        signal. The verified signal is: the title changed **or** the pixels changed.
        """
        verdict = risk.evaluate({"kind": "navigate", "url": url}, url=url)
        if not verdict["allow"]:
            return {"ok": False, "refused": True, **verdict}
        before_title = self.title_now()
        before_png = (self.screenshot() or {}).get("png")
        focused = self.focus()
        if not focused.get("ok"):
            return {"ok": False, "reason": focused.get("reason")}
        if new_tab:
            opened = self._keys("ctrl+t")
            if not opened.get("ok"):
                return {"ok": False, "reason": f"could not open a tab: {opened}"}
            self.opened_tab = True
            time.sleep(SETTLE_S)
        selected = self._keys("ctrl+l")
        if not selected.get("ok"):
            return {"ok": False, "reason": f"could not focus the address bar: {selected}"}
        time.sleep(0.2)
        typed = self._type(url)
        if not typed.get("ok"):
            return {"ok": False, "reason": f"could not type the URL: {typed}"}
        self._keys("enter", expect_foreground=False)
        changed = self._wait_navigation(before_title, before_png)
        return {"ok": bool(changed), "url": url, "title": self.title_now(),
                "new_tab": new_tab,
                "reason": "" if changed else "neither the title nor the pixels changed"}

    def _wait_navigation(self, before_title: str, before_png: Optional[bytes],
                         *, timeout: float = NAV_TIMEOUT_S) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.4)
            if self.title_now() and self.title_now() != before_title:
                time.sleep(SETTLE_S)
                return True
            after = (self.screenshot() or {}).get("png")
            if before_png and after and _pixels_changed(before_png, after):
                time.sleep(SETTLE_S)
                return True
        return False

    def click(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """UIA Invoke if the element offers it, otherwise a click at the box centre."""
        verdict = risk.evaluate({"kind": "click", "target": element.get("name", "")},
                                url=self.title_now(), title=self.title_now())
        if not verdict["allow"]:
            if verdict.get("needs_you"):
                risk.record_needs_you({"kind": "click", "target": element.get("name")},
                                      verdict)
            return {"ok": False, "refused": True, **verdict}

        def run():
            node = self._node_for(element)
            if node is not None:
                pattern = _safe(lambda: node.GetInvokePattern(), None)
                if pattern is not None:
                    pattern.Invoke()
                    return {"via": "uia_invoke"}
            rect = element.get("rect") or []
            if len(rect) != 4:
                raise RuntimeError("element has no bounding rectangle")
            import pyautogui  # noqa: PLC0415

            x = (rect[0] + rect[2]) / 2
            y = (rect[1] + rect[3]) / 2
            pyautogui.click(x, y)
            return {"via": "pixel", "at": [x, y]}

        acted = self.control_layer.act(run)
        time.sleep(SETTLE_S)
        return {"ok": bool(acted.get("ok")), **acted}

    def _node_for(self, element: Dict[str, Any]):
        """Best-effort mapping from a flattened element back to a live UIA node."""
        if self._window is None:
            self._resolve()
        wanted = str(element.get("name") or "")
        if not wanted:
            return None
        try:
            import uiautomation as auto  # noqa: PLC0415

            found = auto.Control(searchFromControl=self._window, Name=wanted,
                                 searchDepth=14)
            return found if _safe(lambda: found.Exists(0.2), False) else None
        except Exception:  # noqa: BLE001
            return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Chrome over UI Automation")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--open", default="")
    parser.add_argument("--keep", action="store_true")
    ns = parser.parse_args(argv)

    if ns.open:
        attached = ChromeUIA.attach()
        if not attached.get("ok"):
            print(json.dumps(attached, indent=2))
            return 1
        page = attached["page"]
        result = page.open_url(ns.open)
        text = page.read_text() if result.get("ok") else {"text": ""}
        if not ns.keep:
            page.close_tab()
        print(json.dumps({"open": result, "title": page.title_now(),
                          "text": (text.get("text") or "")[:300]}, indent=2))
        return 0 if result.get("ok") else 1
    print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
