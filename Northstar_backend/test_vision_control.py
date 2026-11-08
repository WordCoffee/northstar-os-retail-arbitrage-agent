"""D8: risk classes, verify-after-act, and the refusal that happens before input.

V4 needs a deliberately broken action to be *detected*, so the tests break one on purpose
and assert the failure is reported rather than smoothed over. V6 (a page that talks) is
covered by the action/policy split: text is data and never becomes an action.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import act, lease, risk  # noqa: E402


class FakeControl:
    """The real Control's contract: can_act first, then act, then a visible indicator."""

    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.acted = 0
        self.indicators = []

    def act(self, action):
        if not self.allow:
            return {"ok": False, "blocked": True, "reason": "pause_file"}
        self.acted += 1
        try:
            return {"ok": True, "result": action()}
        finally:
            self.indicators.append(False)


# ------------------------------------------------------------------------ risk
def test_action_table_classes():
    assert risk.infer({"kind": "screenshot"}) == risk.OBSERVE
    assert risk.infer({"kind": "navigate"}) == risk.NAVIGATE
    assert risk.infer({"kind": "click"}) == risk.EDIT_OWN
    assert risk.infer({"kind": "submit"}) == risk.EXTERNAL_IRREVERSIBLE
    # an unknown kind is never treated as harmless
    assert risk.infer({"kind": "frobnicate"}) == risk.EXTERNAL_IRREVERSIBLE
    assert risk.infer({}) == risk.EXTERNAL_IRREVERSIBLE


def test_amazon_is_blocked_by_url_before_the_action_is_considered():
    verdict = risk.evaluate({"kind": "screenshot"}, url="https://www.amazon.com/dp/B0X")
    assert verdict["allow"] is False
    assert verdict["risk"] == risk.BLOCKED
    # an observe on Amazon is still an Amazon interaction: no needs_you, there is no
    # owner action that would make it acceptable
    assert verdict["needs_you"] is False


def test_amazon_is_blocked_by_title_even_without_a_url():
    verdict = risk.evaluate({"kind": "click", "target": "Buy now"},
                            title="Amazon.com - Cart")
    assert verdict["allow"] is False and verdict["risk"] == risk.BLOCKED


def test_external_irreversible_needs_the_owner():
    verdict = risk.evaluate({"kind": "checkout"}, url="https://shop.example.com/cart")
    assert verdict["allow"] is False
    assert verdict["risk"] == risk.EXTERNAL_IRREVERSIBLE
    assert verdict["needs_you"] is True


def test_typing_into_a_credential_field_is_blocked():
    verdict = risk.evaluate({"kind": "type", "field": "Password"},
                            url="http://127.0.0.1:8101/sign-in")
    assert verdict["allow"] is False
    assert verdict["risk"] == risk.BLOCKED
    assert "credential" in verdict["reason"]


def test_edit_on_an_external_host_is_refused_but_navigation_is_not():
    click = risk.evaluate({"kind": "click", "target": "Add to cart"},
                          url="https://shop.example.com/item")
    assert click["allow"] is False and click["needs_you"] is True
    nav = risk.evaluate({"kind": "navigate"}, url="https://shop.example.com/item")
    assert nav["allow"] is True


def test_edit_inside_scope_is_allowed_and_outside_is_not(tmp_path):
    inside = risk.evaluate({"kind": "edit_file", "path": "tools/vision/risk.py"},
                           scope=["tools/vision"])
    assert inside["allow"] is True
    outside = risk.evaluate({"kind": "edit_file", "path": "C:/Windows/system.ini"},
                            scope=["tools/vision"])
    assert outside["allow"] is False and outside["needs_you"] is True


def test_refusal_can_be_queued_for_the_owner(tmp_path):
    needs = tmp_path / "needs_you.md"
    verdict = risk.evaluate({"kind": "purchase"}, url="https://shop.example.com")
    line = risk.record_needs_you({"kind": "purchase"}, verdict, needs=needs)
    assert "external_irreversible" in line
    assert "purchase" in needs.read_text(encoding="utf-8")


def test_own_url_detection():
    assert risk.is_own_url("http://127.0.0.1:8101/ui/") is True
    assert risk.is_own_url("http://localhost:3000/") is True
    assert risk.is_own_url("https://example.com/") is False
    assert risk.is_own_url("file:///C:/tmp/page.html") is True


# --------------------------------------------------------------- verify-after-act
class Observed:
    """A mutable observation the executor changes, like a real UI would."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def __call__(self):
        return [{"role": "EditControl", "name": "Search", "value": self.value}]


def test_a_landed_action_is_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(risk, "NEEDS", tmp_path / "needs_you.md")
    observed = Observed("")
    result = act.perform(
        action=act.Action("type", target="Search", context={"url": "http://127.0.0.1:8101"}),
        control=FakeControl(),
        execute=lambda: setattr(observed, "value", "northstar"),
        observe=observed,
        expect=act.element_value_is([], "Search", "northstar"))
    assert result["ok"] is True and result["verified"] is True
    assert result["risk"] == risk.EDIT_OWN
    assert len(result["attempts"]) == 1


def test_a_broken_action_is_detected_and_reported():
    """V4: the action is sent, nothing lands, and the caller is told so."""
    observed = Observed("")
    calls = {"n": 0}

    def execute():
        calls["n"] += 1  # deliberately does not change the observation

    result = act.perform(
        action=act.Action("type", target="Search", context={"url": "http://127.0.0.1:8101"}),
        control=FakeControl(), execute=execute, observe=observed,
        expect=act.element_value_is([], "Search", "northstar"), attempts=2)
    assert result["ok"] is False and result["verified"] is False
    assert result["reason"] == "intended change not observed"
    assert calls["n"] == 2  # retried once, then reported
    assert len(result["attempts"]) == 2


def test_a_flaky_action_is_retried_and_then_verified():
    observed = Observed("")
    state = {"n": 0}

    def execute():
        state["n"] += 1
        if state["n"] >= 2:
            observed.value = "northstar"

    result = act.perform(
        action=act.Action("type", target="Search", context={"url": "http://127.0.0.1:8101"}),
        control=FakeControl(), execute=execute, observe=observed,
        expect=act.element_value_is([], "Search", "northstar"), attempts=2)
    assert result["ok"] is True and state["n"] == 2


def test_the_kill_switch_stops_input_without_retrying():
    control = FakeControl(allow=False)
    result = act.perform(
        action=act.Action("click", target="Save", context={"url": "http://127.0.0.1:8101"}),
        control=control, execute=lambda: None, observe=Observed(),
        expect=lambda after, before: True, attempts=3)
    assert result["ok"] is False and result["blocked"] is True
    assert control.acted == 0
    assert len(result["attempts"]) == 1


def test_a_refused_action_never_reaches_the_control_layer(tmp_path, monkeypatch):
    needs = tmp_path / "needs_you.md"
    monkeypatch.setattr(risk, "NEEDS", needs)
    control = FakeControl()
    result = act.perform(
        action=act.Action("purchase", context={"url": "https://shop.example.com"}),
        control=control, execute=lambda: pytest.fail("must not run"),
        observe=Observed(), expect=lambda a, b: True)
    assert result["ok"] is False and result["refused"] is True
    assert control.acted == 0
    assert "purchase" in needs.read_text(encoding="utf-8")


def test_predicates():
    elements = [{"name": "Search", "value": "abc"}, {"name": "Title", "value": "x"}]
    assert act.element_present(elements, "Search")(elements, None) is True
    assert act.element_value_is(elements, "Search", "abc")(elements, None) is True
    assert act.element_value_is(elements, "Search", "zzz")(elements, None) is False
    assert act.url_is("8101")({"url": "http://127.0.0.1:8101/ui/"}, None) is True
    assert act.text_is("hello")({"text": "Hello world"}, None) is True
    assert act.tree_changed()(elements, []) is True
    assert act.tree_changed()(elements, elements) is False
    both = act.all_of(act.url_is("8101"), act.text_is("hello"))
    assert both({"url": "http://127.0.0.1:8101", "text": "hello"}, None) is True
    assert both({"url": "http://127.0.0.1:8101", "text": "bye"}, None) is False


# ------------------------------------------------------------------------- lease
def test_lease_refuses_anything_but_profile_6(tmp_path):
    result = lease.acquire("Profile 7", path=tmp_path / "lease.json")
    assert result["ok"] is False
    assert lease.load(tmp_path / "lease.json") == {}


def test_lease_gate_needs_an_active_profile_6(tmp_path):
    path = tmp_path / "lease.json"
    assert lease.gate(lease.status(path=path))["allow"] is False
    lease.acquire("Profile 6", profile_name="Work", path=path)
    state = lease.status(path=path)
    assert state["directory"] == "Profile 6"
    assert lease.gate(state)["allow"] is True


def test_a_display_name_never_satisfies_the_lease(tmp_path):
    state = {"state": lease.ACTIVE, "directory": "Work"}
    verdict = lease.gate(state)
    assert verdict["allow"] is False
    assert "Profile 6" in verdict["reason"]


def test_an_idle_lease_expires():
    now = 1_000_000.0
    state = {"state": lease.ACTIVE, "directory": "Profile 6", "idle_minutes": 30,
             "last_activity": "2026-11-08T00:00:00+00:00"}
    fresh = lease.status(path=Path("does-not-exist"), now=now)
    assert fresh["state"] == lease.UNLEASED
    expired = lease.gate({"state": lease.EXPIRED, "directory": "Profile 6"})
    assert expired["allow"] is False


def test_revoke_ends_the_lease(tmp_path):
    path = tmp_path / "lease.json"
    lease.acquire("Profile 6", path=path)
    lease.revoke(path=path)
    assert lease.gate(lease.status(path=path))["allow"] is False
