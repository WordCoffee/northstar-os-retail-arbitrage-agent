"""Regression tests: rate-limiter plan resolution from bearer tokens.

Context: a scanner false positive once flagged `_get_plan`'s
``token = auth_header[7:]`` slice as a credential (fixed in the scanner by
treating unquoted index/slice syntax as code). The extraction was correct all
along; these tests pin the behavior and the fail-closed fallbacks.
"""
from __future__ import annotations

import auth as auth_mod
import rate_limiter as rl


class _StubRequest:
    def __init__(self, authorization=None):
        self.headers = {}
        if authorization is not None:
            self.headers["Authorization"] = authorization
        self.client = None


def _middleware():
    return rl.RateLimitMiddleware(app=None)


def test_no_header_is_foundation():
    assert _middleware()._get_plan(_StubRequest(None)) == "foundation"


def test_non_bearer_header_is_foundation():
    assert _middleware()._get_plan(_StubRequest("Basic abc")) == "foundation"


def test_bearer_token_plan_is_resolved(monkeypatch):
    monkeypatch.setattr(auth_mod, "decode_token", lambda token: {"plan": "scout"})
    assert _middleware()._get_plan(_StubRequest("Bearer faketoken123")) == "scout"


def test_decode_failure_fails_closed_to_foundation(monkeypatch):
    def boom(token):
        raise ValueError("bad token")

    monkeypatch.setattr(auth_mod, "decode_token", boom)
    assert _middleware()._get_plan(_StubRequest("Bearer faketoken123")) == "foundation"


def test_decode_without_plan_defaults_to_foundation(monkeypatch):
    monkeypatch.setattr(auth_mod, "decode_token", lambda token: {})
    assert _middleware()._get_plan(_StubRequest("Bearer faketoken123")) == "foundation"


def test_extracted_token_is_forwarded_exactly(monkeypatch):
    seen = {}

    def fake(token):
        seen["token"] = token
        return {"plan": "mover"}

    monkeypatch.setattr(auth_mod, "decode_token", fake)
    plan = _middleware()._get_plan(_StubRequest("Bearer fakebearer321"))
    assert plan == "mover"
    assert seen["token"] == "fakebearer321"
