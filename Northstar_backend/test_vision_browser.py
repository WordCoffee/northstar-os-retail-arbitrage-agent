"""D8: the CDP browser layer, with a scripted transport instead of a browser.

The transport is where the protocol lives, so a fake transport exercises the real control
flow: the lease gate, the refusal before input, the redirect re-check, the screenshot that
yields no pixels on a refused page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import browser, lease, risk  # noqa: E402

BASE = "http://127.0.0.1:8101/ui/"


class FakeTransport:
    """Answers CDP commands from a dict; records what was asked."""

    url = BASE

    def __init__(self, *, url: str = BASE, evaluate=None, tree=None, box=None,
                 navigate_url: str = "") -> None:
        self.url = url
        self.calls = []
        self.closed = False
        self._evaluate = evaluate or {}
        self._tree = tree
        self._box = box
        self._navigate_url = navigate_url

    def request(self, method, params=None):
        self.calls.append((method, params or {}))
        if method == "Runtime.evaluate":
            expression = params.get("expression", "")
            if expression in self._evaluate:
                value = self._evaluate[expression]
                return {"result": {"value": value() if callable(value) else value}}
            if expression == "location.href":
                return {"result": {"value": self.url}}
            if expression == "document.title":
                return {"result": {"value": ""}}
            return {"result": {"value": None}}
        if method == "Accessibility.getFullAXTree" and self._tree is not None:
            return self._tree
        if method == "DOM.getBoxModel" and self._box is not None:
            return self._box
        if method == "Page.captureScreenshot":
            return {"data": "cG5n"}
        return {}

    def close(self):
        self.closed = True


def active_lease():
    return {"state": lease.ACTIVE, "directory": "Profile 6", "idle_minutes": 30}


def make_browser(transport, lease_state=None):
    attached = browser.Browser.attach(transport=transport,
                                      lease_state=lease_state or active_lease())
    assert attached["ok"] is True, attached
    return attached["browser"]


# ------------------------------------------------------------------ lease gate
def test_attach_refuses_without_a_lease():
    attached = browser.Browser.attach(transport=FakeTransport(),
                                      lease_state={"state": lease.UNLEASED,
                                                   "directory": ""})
    assert attached["ok"] is False and attached["refused"] is True


def test_attach_refuses_a_lease_on_another_profile():
    attached = browser.Browser.attach(
        transport=FakeTransport(),
        lease_state={"state": lease.ACTIVE, "directory": "Profile 7"})
    assert attached["ok"] is False
    assert "Profile 6" in attached["reason"]


def test_attach_enables_the_domains_it_needs():
    transport = FakeTransport()
    make_browser(transport)
    methods = [call[0] for call in transport.calls]
    for domain in ("Page.enable", "DOM.enable", "Runtime.enable", "Accessibility.enable"):
        assert domain in methods


# ------------------------------------------------------------- refusal before input
def test_navigating_to_amazon_is_refused_before_a_command_is_sent():
    transport = FakeTransport()
    page = make_browser(transport)
    result = page.navigate("https://www.amazon.com/dp/B0TEST")
    assert result["ok"] is False and result["risk"] == risk.BLOCKED
    assert not any(call[0] == "Page.navigate" for call in transport.calls)


def test_a_click_on_an_external_host_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(risk, "NEEDS", tmp_path / "needs_you.md")
    transport = FakeTransport(url="https://shop.example.com/item")
    page = make_browser(transport)
    element = {"name": "Add to cart", "backend_node_id": 7}
    result = page.click(element)
    assert result["ok"] is False and result["needs_you"] is True
    assert not any(call[0] == "Input.dispatchMouseEvent" for call in transport.calls)
    assert "Add to cart" in (tmp_path / "needs_you.md").read_text(encoding="utf-8")


def test_a_click_on_our_own_page_is_sent_at_the_box_centre():
    transport = FakeTransport(
        box={"model": {"content": [10, 20, 30, 20, 30, 40, 10, 40]}})
    page = make_browser(transport)
    result = page.click({"name": "Open", "backend_node_id": 3})
    assert result["ok"] is True
    assert result["at"] == [20.0, 30.0]
    sent = [call for call in transport.calls
            if call[0] == "Input.dispatchMouseEvent"]
    assert len(sent) == 3


# ------------------------------------------------------------------ redirect recheck
def test_a_redirect_onto_a_refused_host_is_caught_and_stopped():
    current = {"value": BASE}

    def evaluate(params):
        expression = params.get("expression", "")
        if expression == "location.href":
            return {"result": {"value": current["value"]}}
        if expression == "document.readyState":
            return {"result": {"value": "complete"}}
        if expression == "document.title":
            return {"result": {"value": "Northstar"}}
        return {"result": {"value": None}}

    transport = FakeTransport()

    def request(method, params=None):
        transport.calls.append((method, params or {}))
        if method == "Page.navigate":
            # the page redirected somewhere it was never approved to go
            current["value"] = "https://www.amazon.com/gp/cart"
            return {}
        if method == "Runtime.evaluate":
            return evaluate(params or {})
        return {}

    transport.request = request  # type: ignore[method-assign]
    page = make_browser(transport)
    result = page.navigate("http://127.0.0.1:8101/ui/go")
    assert result["ok"] is False and result["refused"] is True
    assert result["redirected_to"].startswith("https://www.amazon.com")
    assert any(call[0] == "Page.stopLoading" for call in transport.calls)


def test_an_allowed_navigation_reports_the_final_url():
    transport = FakeTransport(evaluate={
        "location.href": BASE,
        "document.readyState": "complete",
        "document.title": "Northstar",
    })
    page = make_browser(transport)
    result = page.navigate(BASE)
    assert result["ok"] is True and result["url"] == BASE


# --------------------------------------------------------------------- observation
def test_the_accessibility_tree_is_flattened_and_masked():
    tree = {"nodes": [
        {"ignored": False, "role": {"value": "button"}, "name": {"value": "Open"},
         "backendDOMNodeId": 1, "nodeId": "n1"},
        {"ignored": True, "role": {"value": "generic"}, "name": {"value": "ignored"}},
        {"ignored": False, "role": {"value": "textbox"}, "name": {"value": "Password"},
         "value": {"value": "hunter2"}, "backendDOMNodeId": 2, "nodeId": "n2"},
    ]}
    transport = FakeTransport(tree=tree, evaluate={"document.title": "Northstar"})
    page = make_browser(transport)
    result = page.ax_tree()
    assert result["count"] == 2
    password = [el for el in result["elements"] if el["name"] == "Password"][0]
    assert password["mask"] is True and password["value"] == ""


def test_read_text_redacts_credentials():
    transport = FakeTransport(evaluate={
        "document.title": "Northstar",
        "(document.querySelector(\"body\")||{}).innerText || ''":
            "api_key=super-secret-value and a heading",
    })
    page = make_browser(transport)
    result = page.read_text("body")
    assert result["ok"] is True
    assert "super-secret-value" not in result["text"]
    assert "[redacted]" in result["text"]


def test_a_screenshot_of_a_refused_page_yields_no_pixels():
    transport = FakeTransport(url="https://www.amazon.com/dp/B0X",
                              evaluate={"document.title": "Amazon.com"})
    page = make_browser(transport)
    result = page.screenshot()
    assert result["ok"] is False and result["blocked"] is True
    assert result["png"] is None
    assert not any(call[0] == "Page.captureScreenshot" for call in transport.calls)


def test_a_screenshot_of_our_own_page_returns_png_bytes():
    transport = FakeTransport(evaluate={"document.title": "Northstar"})
    page = make_browser(transport)
    result = page.screenshot()
    assert result["ok"] is True and result["png"] == b"png"


# ------------------------------------------------------------------------ typing
def test_typing_into_a_password_field_is_refused_at_the_protocol_boundary(tmp_path,
                                                                        monkeypatch):
    monkeypatch.setattr(risk, "NEEDS", tmp_path / "needs.md")
    transport = FakeTransport(evaluate={"document.title": "Northstar"})
    page = make_browser(transport)
    result = page.type_text("hunter2", field={"name": "Password"})
    assert result["ok"] is False and result["risk"] == risk.BLOCKED
    assert not any(call[0] == "Input.insertText" for call in transport.calls)


def test_typing_into_a_normal_field_is_sent():
    transport = FakeTransport(evaluate={"document.title": "Northstar"})
    page = make_browser(transport)
    result = page.type_text("northstar", field={"name": "Search"})
    assert result["ok"] is True
    assert any(call[0] == "Input.insertText" for call in transport.calls)


# ----------------------------------------------------------------- availability
def test_availability_reports_no_endpoint_rather_than_assuming_one():
    found = browser.available("http://127.0.0.1:9")
    assert found["ok"] is False
    assert "no CDP endpoint" in found["reason"]
