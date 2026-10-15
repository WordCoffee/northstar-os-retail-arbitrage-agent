"""google/robotstxt canonical cases through the gateway's RobotsGate (protego).

Phase-3 unit 4: the robots parser is protego (preferred) with the stdlib
urllib.robotparser as fallback. These tests pin the protego path against
canonical expectations derived from google/robotstxt's test suite.

Honesty notes:
- 11 of the 28 sampled cases come from upstream's "GoogleOnly_SystemTest"
  block (its own label: "Google-specific: system test"). Google's C++ matcher
  DENIES there while RFC 9309-style parsers (protego and urllib.robotparser
  alike) ALLOW. Kept in the fixture, tagged ``protego_matches_google_cpp:
  false``, and asserted only as a pinned divergence list.
- The empty-robots case is an INTENTIONAL difference: google/robotstxt treats
  an empty robots.txt as "everything allowed"; our gate fails CLOSED
  (``robots_unknown``) while ``require_robots=True`` - asserted explicitly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from northstar.policy import RobotsGate
from northstar.policy import robots as robots_mod
from northstar.policy.errors import PolicyDenied

FIXTURE = Path(__file__).parent / "fixtures" / "robotstxt_google" / "cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
AGREEING = [c for c in CASES if c["protego_matches_google_cpp"]]
DIVERGENT = [c for c in CASES if not c["protego_matches_google_cpp"]]
PARSE_CASES = [c for c in AGREEING if c["robots"].strip()]
EMPTY_ROBOTS = [c for c in AGREEING if not c["robots"].strip()]


def _gate(text: str, agent: str) -> RobotsGate:
    return RobotsGate({"foo.bar": text, "example.com": text}, user_agent=agent)


def test_protego_is_available():
    assert robots_mod._Protego is not None


@pytest.mark.parametrize("case", PARSE_CASES, ids=lambda c: f"{c['agent']}-{c['url']}")
def test_google_robotstxt_cases(case):
    gate = _gate(case["robots"], case["agent"])
    host = case["url"].split("/")[2]
    assert gate.parser_kind(host) == "protego"
    if case["expected_allowed"]:
        gate.check(case["url"])  # must not raise
    else:
        with pytest.raises(PolicyDenied) as exc:
            gate.check(case["url"])
        assert exc.value.reason == "robots_denied"


def test_google_cpp_divergences_are_documented():
    # All divergent cases sit in google/robotstxt's "GoogleOnly_SystemTest"
    # block: Google's C++ matcher DENIES, RFC-style parsers ALLOW. Pinned so a
    # parser change makes the divergence list visible.
    assert len(DIVERGENT) == 11
    for c in DIVERGENT:
        assert c["expected_allowed"] is False
        assert c["protego_allows"] is True


def test_empty_robots_fails_closed_by_design():
    # google/robotstxt allows everything when robots.txt is empty; our gate
    # deliberately fails CLOSED (robots_unknown) while require_robots=True.
    assert EMPTY_ROBOTS, "fixture should include the empty-robots case"
    for c in EMPTY_ROBOTS:
        gate = _gate(c["robots"], c["agent"])
        with pytest.raises(PolicyDenied) as exc:
            gate.check(c["url"])
        assert exc.value.reason == "robots_unknown"


def test_urllib_fallback_still_works(monkeypatch):
    monkeypatch.setattr(robots_mod, "_Protego", None)
    gate = RobotsGate({"foo.bar": "user-agent: FooBot\ndisallow: /\n"}, user_agent="FooBot")
    assert gate.parser_kind("foo.bar") == "urllib"
    with pytest.raises(PolicyDenied):
        gate.check("http://foo.bar/x")
    other = RobotsGate({"foo.bar": "user-agent: FooBot\ndisallow: /\n"}, user_agent="BarBot")
    other.check("http://foo.bar/x")  # a different agent is still allowed


def test_unknown_robots_still_fails_closed():
    gate = RobotsGate({}, user_agent="FooBot")
    with pytest.raises(PolicyDenied) as exc:
        gate.check("http://foo.bar/x")
    assert exc.value.reason == "robots_unknown"
