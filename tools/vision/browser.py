"""Browser control over the DevTools protocol: structure first, pixels second.

Work order §5.1 layer 5. Ty's Vision drives Chrome through CDP so it can read the DOM and
the accessibility tree of any page, then use pixels only for what the DOM cannot describe.
Playwright stays where it belongs: localhost test specs.

Three properties are enforced here rather than by the caller:

* **the lease comes first** — `attach()` refuses unless the Profile 6 lease is active;
* **every navigation is re-checked** — a redirect cannot land on a refused host because
  the *current* URL is re-evaluated after the page settles;
* **an edit on an external host is refused** — reading an external page is allowed,
  clicking or typing on one is not.

The transport is injectable so the protocol handling is testable without a browser:

    from vision.browser import Browser
    page = Browser.attach(transport=FakeTransport(...))
"""
from __future__ import annotations

import base64
import json
import time
import urllib.request
from typing import Any, Dict, List, Optional

from . import lease as lease_mod
from . import injection, privacy, risk

DEFAULT_ENDPOINT = "http://127.0.0.1:9222"
SETTLE_S = 0.15
LOAD_TIMEOUT_S = 15.0


class CDPError(RuntimeError):
    """The browser answered a command with an error."""


class SocketTransport:
    """One websocket, one command at a time. CDP is request/response by id."""

    def __init__(self, ws_url: str, *, timeout: float = 20.0) -> None:
        from websockets.sync.client import connect  # noqa: PLC0415

        self._ws = connect(ws_url, max_size=64 * 1024 * 1024, open_timeout=timeout)
        self._id = 0
        self._timeout = timeout

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._id += 1
        message = {"id": self._id, "method": method, "params": params or {}}
        self._ws.send(json.dumps(message))
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            raw = self._ws.recv(timeout=max(0.1, deadline - time.time()))
            reply = json.loads(raw)
            if reply.get("id") != self._id:
                continue  # an event, not our answer
            if "error" in reply:
                raise CDPError(f"{method}: {reply['error']}")
            return reply.get("result") or {}
        raise CDPError(f"{method}: timeout after {self._timeout}s")

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:  # noqa: BLE001 - closing twice is not an error worth raising
            pass


def list_targets(endpoint: str = DEFAULT_ENDPOINT, *, timeout: float = 5.0) -> List[Dict[str, Any]]:
    """The browser's open tabs. A missing endpoint is reported, not assumed away."""
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/json/list",
                                    timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace") or "[]")
        return [row for row in data if isinstance(row, dict)]
    except Exception:  # noqa: BLE001
        return []


def available(endpoint: str = DEFAULT_ENDPOINT) -> Dict[str, Any]:
    """Is a CDP endpoint reachable at all? Used by parity to refuse rather than fake."""
    targets = list_targets(endpoint)
    if not targets:
        return {"ok": False, "reason": f"no CDP endpoint at {endpoint}",
                "hint": ("Chrome must be started with --remote-debugging-port on the "
                         "leased profile; Ty never closes or relaunches the owner's "
                         "Chrome itself")}
    return {"ok": True, "targets": len(targets), "endpoint": endpoint}


class Browser:
    """A page target, with the policy gate in front of every input."""

    def __init__(self, transport: Any, *, endpoint: str = DEFAULT_ENDPOINT,
                 target: Optional[Dict[str, Any]] = None,
                 lease_state: Optional[Dict[str, Any]] = None) -> None:
        self.transport = transport
        self.endpoint = endpoint
        self.target = target or {}
        self.lease_state = lease_state or {}
        self.events: List[Dict[str, Any]] = []

    # -- construction ------------------------------------------------------
    @classmethod
    def attach(cls, endpoint: str = DEFAULT_ENDPOINT, *,
               lease_state: Optional[Dict[str, Any]] = None,
               target_hint: str = "", transport: Any = None) -> Dict[str, Any]:
        """Attach to a page, but only through an active Profile 6 lease."""
        state = lease_state if lease_state is not None else lease_mod.status()
        verdict = lease_mod.gate(state)
        if not verdict.get("allow"):
            return {"ok": False, "refused": True, "reason": verdict.get("reason"),
                    "lease": state}

        target: Dict[str, Any] = {}
        if transport is None:
            targets = [row for row in list_targets(endpoint)
                       if str(row.get("type") or "page") == "page"]
            if not targets:
                return {"ok": False, "reason": f"no page target at {endpoint}",
                        "lease": state}
            target = next((row for row in targets
                           if target_hint and target_hint.casefold()
                           in str(row.get("url", "")).casefold()), targets[0])
            transport = SocketTransport(str(target.get("webSocketDebuggerUrl") or ""))
        else:
            target = {"url": str(getattr(transport, "url", "") or "")}

        browser = cls(transport, endpoint=endpoint, target=target, lease_state=state)
        for domain in ("Page", "DOM", "Runtime", "Accessibility"):
            try:
                browser.transport.request(f"{domain}.enable")
            except Exception:  # noqa: BLE001 - a domain that will not enable is not fatal
                pass
        return {"ok": True, "browser": browser, "lease": state, "target": target}

    # -- observation -------------------------------------------------------
    def current_url(self) -> str:
        try:
            value = self.evaluate("location.href")
            return str(value or "")
        except Exception:  # noqa: BLE001
            return ""

    def evaluate(self, expression: str) -> Any:
        result = self.transport.request("Runtime.evaluate",
                                        {"expression": expression, "returnByValue": True})
        return (result.get("result") or {}).get("value")

    def title(self) -> str:
        try:
            return str(self.evaluate("document.title") or "")
        except Exception:  # noqa: BLE001
            return ""

    def policy(self, url: str = "") -> Dict[str, Any]:
        """Classify the current page. Refusal is by URL then by title."""
        current = url or self.current_url()
        return privacy.classify(title=self.title(), url=current)

    def ax_tree(self) -> Dict[str, Any]:
        """The accessibility tree, flattened to the nodes a person can act on."""
        try:
            result = self.transport.request("Accessibility.getFullAXTree")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "elements": []}
        elements: List[Dict[str, Any]] = []
        for node in result.get("nodes") or []:
            if node.get("ignored"):
                continue
            role = str((node.get("role") or {}).get("value") or "")
            name = str((node.get("name") or {}).get("value") or "")
            value = str((node.get("value") or {}).get("value") or "")
            backend = node.get("backendDOMNodeId")
            if not (role or name):
                continue
            elements.append({"role": role, "name": name, "value": value,
                             "node_id": node.get("nodeId"), "backend_node_id": backend})
        return {"ok": True, "elements": privacy.mask_regions(elements),
                "count": len(elements)}

    def find(self, needle: str, *, role: str = "") -> Optional[Dict[str, Any]]:
        tree = self.ax_tree()
        low = str(needle).casefold()
        candidates = [el for el in tree.get("elements") or []
                      if not role or str(el.get("role", "")).casefold() == role.casefold()]
        for element in candidates:
            if str(element.get("name", "")).casefold() == low:
                return element
        for element in candidates:
            if low in str(element.get("name", "")).casefold():
                return element
        return None

    def read_text(self, selector: str = "body") -> Dict[str, Any]:
        tree = self.ax_tree()
        if not tree.get("ok"):
            return {"ok": False, "text": "", "reason": tree.get("error")}
        expression = (f"(document.querySelector({json.dumps(selector)})||{{}})"
                      ".innerText || ''")
        text = self.evaluate(expression)
        if text in (None, ""):
            return {"ok": False, "text": "", "reason": f"no text for {selector!r}"}
        clean = privacy.redact(str(text))[:4000]
        # The page's text is data. Scanning it records an attempt; it never changes the
        # plan, so the returned verdict is informational.
        verdict = injection.guard(clean, source=self.current_url() or selector)
        return {"ok": True, "text": clean, "selector": selector, "injection": verdict}

    def screenshot(self) -> Dict[str, Any]:
        """Pixels, but only from a page the policy allows. A refused page yields none."""
        verdict = self.policy()
        if not verdict.get("allow"):
            self._event("blocked-window", reason=verdict.get("reason"),
                        url=self.current_url())
            return {"ok": False, "blocked": True, "reason": verdict.get("reason"),
                    "png": None}
        try:
            result = self.transport.request("Page.captureScreenshot", {"format": "png"})
            return {"ok": True, "png": base64.b64decode(result.get("data") or ""),
                    "size": len(result.get("data") or "")}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "png": None, "reason": f"{type(exc).__name__}: {exc}"}

    # -- actions -----------------------------------------------------------
    def navigate(self, url: str, *, timeout: float = LOAD_TIMEOUT_S) -> Dict[str, Any]:
        """Navigate, then re-check the URL that is actually current (redirect recheck)."""
        verdict = risk.evaluate({"kind": "navigate", "url": url}, url=url)
        if not verdict["allow"]:
            self._event("refused-navigation", url=url, reason=verdict["reason"])
            return {"ok": False, "refused": True, **verdict}
        try:
            self.transport.request("Page.navigate", {"url": url})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "url": url}
        self._wait_ready(timeout=timeout)
        final = self.current_url()
        if final and final != url:
            after = risk.evaluate({"kind": "navigate", "url": final}, url=final)
            if not after["allow"]:
                # Redirected onto a refused host: stop here, record it, touch nothing.
                self._event("redirect-refused", requested=url, final=final,
                            reason=after["reason"])
                try:
                    self.transport.request("Page.stopLoading")
                except Exception:  # noqa: BLE001
                    pass
                return {"ok": False, "refused": True, "redirected_to": final, **after}
        return {"ok": True, "url": final or url, "requested": url}

    def click(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Click an element's box centre, after asking the policy about this page."""
        verdict = risk.evaluate({"kind": "click", "target": element.get("name", "")},
                                url=self.current_url(), title=self.title())
        if not verdict["allow"]:
            if verdict.get("needs_you"):
                risk.record_needs_you({"kind": "click", "target": element.get("name")},
                                      verdict)
            return {"ok": False, "refused": True, **verdict}
        box = self._box(element)
        if not box.get("ok"):
            return {"ok": False, "reason": box.get("reason", "no box model")}
        x, y = box["x"], box["y"]
        self.transport.request("Input.dispatchMouseEvent",
                               {"type": "mouseMoved", "x": x, "y": y})
        self.transport.request("Input.dispatchMouseEvent",
                               {"type": "mousePressed", "x": x, "y": y,
                                "button": "left", "clickCount": 1})
        self.transport.request("Input.dispatchMouseEvent",
                               {"type": "mouseReleased", "x": x, "y": y,
                                "button": "left", "clickCount": 1})
        time.sleep(SETTLE_S)
        return {"ok": True, "at": [x, y], "target": element.get("name", "")}

    def type_text(self, text: str, *, field: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        action = {"kind": "type", "target": (field or {}).get("name", ""),
                  "field": (field or {}).get("name", "")}
        verdict = risk.evaluate(action, url=self.current_url(), title=self.title())
        if not verdict["allow"]:
            if verdict.get("needs_you"):
                risk.record_needs_you(action, verdict)
            return {"ok": False, "refused": True, **verdict}
        self.transport.request("Input.insertText", {"text": str(text)})
        time.sleep(SETTLE_S)
        return {"ok": True, "typed": len(str(text))}

    def press(self, key: str) -> Dict[str, Any]:
        verdict = risk.evaluate({"kind": "press"}, url=self.current_url(),
                                title=self.title())
        if not verdict["allow"]:
            return {"ok": False, "refused": True, **verdict}
        self.transport.request("Input.dispatchKeyEvent",
                               {"type": "keyDown", "key": key})
        self.transport.request("Input.dispatchKeyEvent",
                               {"type": "keyUp", "key": key})
        time.sleep(SETTLE_S)
        return {"ok": True, "key": key}

    def scroll(self, dy: int = 400) -> Dict[str, Any]:
        verdict = risk.evaluate({"kind": "scroll"}, url=self.current_url(),
                                title=self.title())
        if not verdict["allow"]:
            return {"ok": False, "refused": True, **verdict}
        self.transport.request("Input.dispatchMouseEvent",
                               {"type": "mouseWheel", "x": 1, "y": 1,
                                "deltaX": 0, "deltaY": int(dy)})
        time.sleep(SETTLE_S)
        return {"ok": True, "dy": int(dy)}

    # -- internals ---------------------------------------------------------
    def _box(self, element: Dict[str, Any]) -> Dict[str, Any]:
        node = element.get("backend_node_id") or element.get("backendDOMNodeId")
        if node is None:
            return {"ok": False, "reason": "element has no backend node id"}
        try:
            model = self.transport.request("DOM.getBoxModel", {"backendNodeId": int(node)})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        content = (model.get("model") or {}).get("content") or []
        if len(content) < 8:
            return {"ok": False, "reason": "empty box model"}
        xs = content[0::2]
        ys = content[1::2]
        return {"ok": True, "x": (min(xs) + max(xs)) / 2.0,
                "y": (min(ys) + max(ys)) / 2.0,
                "width": max(xs) - min(xs), "height": max(ys) - min(ys)}

    def _wait_ready(self, *, timeout: float = LOAD_TIMEOUT_S) -> str:
        deadline = time.time() + timeout
        state = ""
        while time.time() < deadline:
            try:
                state = str(self.evaluate("document.readyState") or "")
            except Exception:  # noqa: BLE001 - a page mid-navigation throws; poll again
                state = ""
            if state == "complete":
                return state
            time.sleep(0.1)
        return state

    def _event(self, name: str, **fields: Any) -> None:
        row = {"event": name, **fields}
        self.events.append(row)
        risk.record_event(row)

    def close(self) -> None:
        try:
            self.transport.close()
        except Exception:  # noqa: BLE001
            pass


__all__ = ["Browser", "SocketTransport", "CDPError", "list_targets", "available",
           "DEFAULT_ENDPOINT"]
