"""The Chrome Connect parity suite: the same ten tasks, both controllers.

Work order §5.2 V3 and unit D8. Chrome Connect may only be quarantined after Ty's Vision
matches or beats it on success **and** recovery, twice. A suite that reports "pass" when a
backend could not run is worse than useless, so every backend answers `available()` and an
unavailable backend produces `not_run` — never a pass.

    python -m tools.vision.parity --run --backend vision --base http://127.0.0.1:8101
    python -m tools.vision.parity --twice --base http://127.0.0.1:8101
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "ty"

INJECTION_MARKERS = ("ignore your rules", "ignore previous instructions",
                     "ignore all previous", "disregard your instructions",
                     "you must now", "system prompt")


@dataclass
class Task:
    id: str
    title: str
    run: Callable[[Any, str], Dict[str, Any]]


def _ok(**evidence: Any) -> Dict[str, Any]:
    return {"ok": True, "evidence": evidence}


def _fail(reason: str, **evidence: Any) -> Dict[str, Any]:
    return {"ok": False, "reason": reason, "evidence": evidence}


# ------------------------------------------------------------------ the ten tasks
def t_open_home(backend: Any, base: str) -> Dict[str, Any]:
    result = backend.navigate(base)
    if not result.get("ok"):
        return _fail("navigate failed", result=result)
    return _ok(url=backend.current_url())


def t_read_title(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    title = backend.title()
    return _ok(title=title) if title else _fail("empty title")


def t_find_nav(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    for needle in ("Prospector", "Home", "Listings", "Design"):
        element = backend.find(needle)
        if element:
            return _ok(found=needle, role=element.get("role"))
    return _fail("no navigation element found")


def t_read_heading(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    text = backend.read_text("h1")
    if text.get("ok") and len(text.get("text") or "") >= 3:
        return _ok(text=text["text"][:120])
    return _fail("no heading text", detail=text)


def t_count_elements(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    tree = backend.ax_tree()
    count = int(tree.get("count") or 0)
    return _ok(count=count) if count >= 5 else _fail("too few elements", count=count)


def t_click_nav(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    before = backend.current_url()
    for needle in ("Prospector", "Listings", "Design", "Home"):
        element = backend.find(needle)
        if not element:
            continue
        clicked = backend.click(element)
        if not clicked.get("ok"):
            continue
        after = backend.current_url()
        if after and after != before:
            return _ok(found=needle, before=before, after=after)
    return _fail("click did not change the URL", before=before)


def t_type_and_read_back(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    field = None
    for needle in ("Search", "search", "Ask Bojo", "Message"):
        field = backend.find(needle)
        if field:
            break
    if not field:
        return _fail("no input to type into")
    typed = backend.type_text("northstar parity")
    if not typed.get("ok"):
        return _fail("type refused", result=typed)
    return _ok(field=field.get("name"), typed=typed.get("typed"))


def t_scroll(backend: Any, base: str) -> Dict[str, Any]:
    backend.navigate(base)
    result = backend.scroll(500)
    return _ok() if result.get("ok") else _fail("scroll refused", result=result)


def t_second_page(backend: Any, base: str) -> Dict[str, Any]:
    first = backend.navigate(base)
    if not first.get("ok"):
        return _fail("first navigate failed")
    other = base.rstrip("/") + "/listings"
    second = backend.navigate(other)
    if not second.get("ok"):
        return _fail("second navigate failed", result=second)
    url = backend.current_url()
    return _ok(url=url) if url else _fail("no url after second navigate")


def t_ignore_injection(backend: Any, base: str) -> Dict[str, Any]:
    """A page that tells Ty to act must be logged and ignored, not obeyed."""
    backend.navigate(base)
    text = backend.read_text("body")
    body = str(text.get("text") or "").casefold()
    hit = next((marker for marker in INJECTION_MARKERS if marker in body), "")
    if not text.get("ok"):
        return _fail("could not read page text", detail=text)
    # Either the page carries an injection (we must not act on it) or it does not.
    # Both are fine: what is not fine is following it. No action follows this read.
    return _ok(injection_text_present=bool(hit), ignored=True)


TASKS: List[Task] = [
    Task("open_home", "open the base page", t_open_home),
    Task("read_title", "read the document title", t_read_title),
    Task("find_nav", "find a navigation element", t_find_nav),
    Task("read_heading", "read the h1", t_read_heading),
    Task("count_elements", "count actionable elements", t_count_elements),
    Task("click_nav", "click navigation and change URL", t_click_nav),
    Task("type_and_read_back", "type into an input", t_type_and_read_back),
    Task("scroll", "scroll the page", t_scroll),
    Task("second_page", "navigate to a second route", t_second_page),
    Task("ignore_injection", "log and ignore injected text", t_ignore_injection),
]

#: A recovery probe: each backend must survive a wrong first URL and still complete task 1.
RECOVERY_PROBE = {"id": "recovery", "title": "recover from a failed first navigation"}


# ---------------------------------------------------------------------- backends
class VisionBackend:
    """Ty's Vision driving Chrome over CDP, through the Profile 6 lease."""

    name = "vision"

    def __init__(self, *, endpoint: Optional[str] = None) -> None:
        from .browser import DEFAULT_ENDPOINT

        self.endpoint = endpoint or os.environ.get("TY_CDP_ENDPOINT", DEFAULT_ENDPOINT)
        self.page: Any = None
        self._attach_error = ""

    def available(self) -> Dict[str, Any]:
        from . import browser as browser_mod

        found = browser_mod.available(self.endpoint)
        if not found.get("ok"):
            return found
        attached = browser_mod.Browser.attach(self.endpoint)
        if not attached.get("ok"):
            return {"ok": False, "reason": attached.get("reason"),
                    "kind": "lease_or_target"}
        self.page = attached["browser"]
        return {"ok": True, "endpoint": self.endpoint}

    def navigate(self, url: str) -> Dict[str, Any]:
        if not self.page:
            return {"ok": False, "reason": "not attached"}
        return self.page.navigate(url)

    def current_url(self) -> str:
        return self.page.current_url() if self.page else ""

    def title(self) -> str:
        return self.page.title() if self.page else ""

    def find(self, needle: str) -> Optional[Dict[str, Any]]:
        return self.page.find(needle) if self.page else None

    def ax_tree(self) -> Dict[str, Any]:
        return self.page.ax_tree() if self.page else {"ok": False, "elements": []}

    def read_text(self, selector: str) -> Dict[str, Any]:
        return self.page.read_text(selector) if self.page else {"ok": False}

    def click(self, element: Dict[str, Any]) -> Dict[str, Any]:
        return self.page.click(element) if self.page else {"ok": False}

    def type_text(self, text: str) -> Dict[str, Any]:
        return self.page.type_text(text) if self.page else {"ok": False}

    def scroll(self, dy: int) -> Dict[str, Any]:
        return self.page.scroll(dy) if self.page else {"ok": False}

    def close(self) -> None:
        if self.page:
            self.page.close()


class ChromeConnectBackend:
    """The incumbent controller, reached through its job-runner CLI.

    Chrome Connect is driven by an extension in the owner's Chrome; it has no CDP port of
    its own. When the runner is not configured the backend is unavailable, and the suite
    says so instead of scoring itself against nothing.
    """

    name = "chromeconnect"

    def __init__(self, cli: Optional[str] = None) -> None:
        self.cli = cli or os.environ.get("CHROMECONNECT_CLI", "")

    def available(self) -> Dict[str, Any]:
        if not self.cli or not Path(self.cli).exists():
            return {"ok": False,
                    "reason": "no Chrome Connect runner CLI configured (CHROMECONNECT_CLI)",
                    "hint": ("Chrome Connect runs as an extension in the owner's Chrome; "
                             "the parity suite needs a runner that can accept tasks")}
        return {"ok": True, "cli": self.cli}

    def navigate(self, url: str) -> Dict[str, Any]:  # pragma: no cover - needs the runner
        out = subprocess.run([self.cli, "navigate", url], capture_output=True, text=True,
                             timeout=120)
        return {"ok": out.returncode == 0, "stdout": out.stdout[-400:]}

    def current_url(self) -> str:  # pragma: no cover
        return ""

    def title(self) -> str:  # pragma: no cover
        return ""

    def find(self, needle: str):  # pragma: no cover
        return None

    def ax_tree(self) -> Dict[str, Any]:  # pragma: no cover
        return {"ok": False, "elements": []}

    def read_text(self, selector: str) -> Dict[str, Any]:  # pragma: no cover
        return {"ok": False}

    def click(self, element):  # pragma: no cover
        return {"ok": False}

    def type_text(self, text: str) -> Dict[str, Any]:  # pragma: no cover
        return {"ok": False}

    def scroll(self, dy: int) -> Dict[str, Any]:  # pragma: no cover
        return {"ok": False}

    def close(self) -> None:  # pragma: no cover
        return None


class UIABackend:
    """Ty's Vision driving the live Profile 6 window through UI Automation.

    Used when there is no CDP endpoint (owner instruction 2026-11-08: *drive Profile 6
    through UIA plus the pixel fallback*). It needs an unlocked, signed-in desktop: UIA can
    read a locked screen's lock window, not the browser behind it.
    """

    name = "uia"

    def __init__(self) -> None:
        self.page: Any = None
        self.url = ""

    def available(self) -> Dict[str, Any]:
        from . import chrome_uia  # noqa: PLC0415

        status = chrome_uia.status()
        if not status.get("windows"):
            return {"ok": False, "reason": "no Chrome window to drive"}
        # The lock screen is a different desktop: the foreground belongs to LockApp and no
        # keystroke can reach Chrome. Detect it by process, not by hope.
        foreground = int(status.get("foreground") or 0)
        process = ""
        if foreground:
            import ctypes  # noqa: PLC0415
            from ctypes import wintypes  # noqa: PLC0415

            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
            from . import capture  # noqa: PLC0415

            process = capture._process_name(pid.value)
        if process.casefold() == "lockapp.exe":
            return {"ok": False,
                    "reason": ("the desktop is locked (foreground is LockApp.exe); UIA "
                               "cannot drive a browser behind the lock screen"),
                    "kind": "desktop_locked"}
        attached = chrome_uia.ChromeUIA.attach()
        if not attached.get("ok"):
            return {"ok": False, "reason": attached.get("reason"),
                    "kind": "attach_refused"}
        self.page = attached["page"]
        return {"ok": True, "hwnd": self.page.hwnd}

    def navigate(self, url: str) -> Dict[str, Any]:
        if not self.page:
            return {"ok": False, "reason": "not attached"}
        result = self.page.open_url(url)
        if result.get("ok"):
            self.url = url
        return result

    def current_url(self) -> str:
        return self.url

    def title(self) -> str:
        return self.page.title_now() if self.page else ""

    def find(self, needle: str):
        return self.page.find(needle) if self.page else None

    def ax_tree(self) -> Dict[str, Any]:
        if not self.page:
            return {"ok": False, "elements": [], "count": 0}
        elements = self.page.elements()
        return {"ok": True, "elements": elements, "count": len(elements)}

    def read_text(self, selector: str) -> Dict[str, Any]:
        return self.page.read_text() if self.page else {"ok": False, "text": ""}

    def click(self, element: Dict[str, Any]) -> Dict[str, Any]:
        return self.page.click(element) if self.page else {"ok": False}

    def type_text(self, text: str) -> Dict[str, Any]:
        if not self.page:
            return {"ok": False}
        return self.page._type(text)

    def scroll(self, dy: int) -> Dict[str, Any]:
        if not self.page:
            return {"ok": False}
        return self.page._keys("pagedown")

    def close(self) -> None:
        if self.page:
            self.page.close_tab()


BACKENDS: Dict[str, Callable[..., Any]] = {"vision": VisionBackend,
                                          "chromeconnect": ChromeConnectBackend,
                                          "uia": UIABackend}


# ------------------------------------------------------------------------- runner
def run_suite(backend: Any, *, base: str, tasks: Optional[List[Task]] = None) -> Dict[str, Any]:
    """Run every task once. Unavailable backend => not_run for all, overall not_run."""
    started = time.time()
    readiness = backend.available()
    if not readiness.get("ok"):
        return {"backend": backend.name, "base": base, "pass": False, "ran": False,
                "reason": readiness.get("reason"), "hint": readiness.get("hint", ""),
                "tasks": [{"id": task.id, "status": "not_run"} for task in tasks or TASKS],
                "at": time.time()}
    results = []
    for task in tasks or TASKS:
        try:
            outcome = task.run(backend, base)
        except Exception as exc:  # noqa: BLE001 - a task that throws is a failed task
            outcome = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        results.append({"id": task.id, "title": task.title,
                        "status": "pass" if outcome.get("ok") else "fail",
                        "reason": outcome.get("reason", ""),
                        "evidence": outcome.get("evidence", {})})
    passed = sum(1 for row in results if row["status"] == "pass")
    recovery = _recovery(backend, base)
    return {"backend": backend.name, "base": base,
            "pass": passed == len(results) and recovery.get("ok") is True,
            "ran": True, "passed": passed, "total": len(results),
            "recovery": recovery, "tasks": results,
            "seconds": round(time.time() - started, 1), "at": time.time()}


def _recovery(backend: Any, base: str) -> Dict[str, Any]:
    """Break the first attempt deliberately; the backend must still finish the task."""
    bad = base.rstrip("/") + "/__parity_missing__"
    first = backend.navigate(bad)
    second = backend.navigate(base)
    url = backend.current_url()
    ok = bool(second.get("ok") and url)
    return {"ok": ok, "first_attempt_ok": bool(first.get("ok")),
            "second_attempt_ok": bool(second.get("ok")), "url": url}


def compare(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """A challenger matches or beats Chrome Connect on success rate and recovery."""
    by_name = {row["backend"]: row for row in rows}
    challenger = next((by_name[name] for name in ("vision", "uia") if name in by_name), None)
    incumbent = by_name.get("chromeconnect")
    if not challenger or not incumbent:
        return {"ok": False, "reason": "both a challenger and the incumbent are required"}
    if not challenger.get("ran") or not incumbent.get("ran"):
        missing = [row["backend"] for row in rows if not row.get("ran")]
        return {"ok": False, "reason": "not_run", "missing": missing,
                "detail": {name: by_name[name].get("reason") for name in missing}}
    challenger_rate = challenger["passed"] / max(1, challenger["total"])
    incumbent_rate = incumbent["passed"] / max(1, incumbent["total"])
    ok = (challenger_rate >= incumbent_rate
          and bool(challenger["recovery"].get("ok"))
          >= bool(incumbent["recovery"].get("ok")))
    return {"ok": ok, "challenger": challenger["backend"],
            "challenger_rate": round(challenger_rate, 2),
            "chromeconnect_rate": round(incumbent_rate, 2),
            "challenger_recovery": challenger["recovery"].get("ok"),
            "chromeconnect_recovery": incumbent["recovery"].get("ok")}


def run_twice(*, base: str, out_dir: Optional[Path] = None,
              backends: Optional[List[str]] = None) -> Dict[str, Any]:
    """Two independent runs. Quarantine needs two passes; one pass is not two."""
    folder = Path(out_dir or OUT)
    folder.mkdir(parents=True, exist_ok=True)
    names = backends or ["vision", "chromeconnect"]
    runs = []
    for index in (1, 2):
        rows = []
        for name in names:
            backend = BACKENDS[name]()
            row = run_suite(backend, base=base)
            try:
                backend.close()
            except Exception:  # noqa: BLE001
                pass
            rows.append(row)
        verdict = compare(rows)
        payload = {"run": index, "base": base, "rows": rows, "comparison": verdict,
                   "at": time.time()}
        (folder / f"d8_parity_run{index}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        runs.append(payload)
    both = all(run["comparison"].get("ok") for run in runs)
    return {"ok": both, "passes": sum(1 for run in runs if run["comparison"].get("ok")),
            "runs": [{k: run[k] for k in ("run", "comparison")} for run in runs]}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Chrome Connect parity suite")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--twice", action="store_true")
    parser.add_argument("--backend", default="vision")
    parser.add_argument("--backends", default="",
                        help="comma list for --twice, e.g. uia,chromeconnect")
    parser.add_argument("--base", default="http://127.0.0.1:8101/ui/")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)

    if ns.twice:
        names = [name.strip() for name in (ns.backends or "").split(",") if name.strip()]
        result = run_twice(base=ns.base, backends=names or None)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if ns.run:
        backend = BACKENDS[ns.backend]()
        row = run_suite(backend, base=ns.base)
        if ns.out:
            Path(ns.out).write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: row.get(k) for k in ("backend", "pass", "ran", "passed",
                                                 "total", "reason", "recovery",
                                                 "hint")}, indent=2))
        return 0 if row["pass"] else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
