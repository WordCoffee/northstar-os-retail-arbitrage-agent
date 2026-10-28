"""Rate-limit bucket resolution for the local-development identity shim.

Found live on 2026-10-28 during the Chrome Connect acceptance run: a Design
Studio chat turn answered

    Error: Max 30 requests per minute on foundation plan — nothing was fabricated. Retry

because the dev shim identity never resolved to a bucket. The cookie path had
already been fixed for this exact class of bug (a signed-in human fires 6-10
calls per room, so 30/min makes the product look broken); the dev shim, which is
the ONLY identity a local session uses, still fell through to the anonymous
`foundation` bucket.

These tests pin the resolution AND, just as importantly, that it fails closed:
a dev-shim header from a non-loopback peer, or in a production process, must
still land in the tight anonymous bucket.
"""

from __future__ import annotations

import os
import sys

import pytest

_BACKEND = os.path.dirname(os.path.abspath(__file__))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from rate_limiter import RateLimitMiddleware  # noqa: E402


class _Client:
    def __init__(self, host: str):
        self.host = host


class _CIHeaders(dict):
    """Case-insensitive header map.

    Starlette passes a `Headers` object to real requests; `_dev_shim_identity`
    reads ``X-User-Id`` while ``effective_client_host`` reads
    ``x-forwarded-for``. A plain dict would answer only one spelling, so this
    fake must mirror Starlette or the test would pass for the wrong reason.
    """

    def __init__(self, data=None):
        super().__init__()
        for k, v in (data or {}).items():
            self[str(k).lower()] = v

    def get(self, key, default=None):
        return super().get(str(key).lower(), default)

    def __contains__(self, key):
        return super().__contains__(str(key).lower())

    def __getitem__(self, key):
        return super().__getitem__(str(key).lower())


class _Request:
    """The minimal Starlette-Request shape the limiter reads."""

    def __init__(self, headers=None, client_host="127.0.0.1", cookies=None):
        self.headers = _CIHeaders(headers)
        self.client = _Client(client_host)
        self.cookies = dict(cookies or {})


def _plan(headers=None, client_host="127.0.0.1"):
    mw = RateLimitMiddleware(app=None)
    return mw._get_plan(_Request(headers=headers, client_host=client_host))


def _dev_headers(**extra):
    base = {"X-User-Id": "demo-t2", "X-Org-Id": "org-t2", "X-Role": "operator",
            "X-Env": "development"}
    base.update(extra)
    return base


# --- the fix -----------------------------------------------------------------

def test_dev_shim_resolves_to_an_authenticated_bucket(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    plan = _plan(_dev_headers())
    assert plan != "foundation", (
        "the dev shim must not be billed to the anonymous 30/min bucket; that is "
        "what made a single Design Studio chat turn 429")
    assert RateLimitMiddleware.PLAN_LIMITS[plan] >= 300


def test_dev_shim_with_owner_role_gets_the_widest_bucket(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    # `owner` is the role vocabulary auth.py knows. The cookie branch speaks the
    # Foundation vocabulary (organization_owner / platform_admin); _dev_shim_identity
    # normalises through auth.is_valid_role, so a dev shim can only ever reach the
    # `mover` tier here — which is the honest, bounded outcome.
    assert _plan(_dev_headers(**{"X-Role": "owner"})) == "mover"


# --- still fail-closed -------------------------------------------------------

def test_dev_shim_ignored_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert _plan(_dev_headers()) == "foundation"


def test_dev_shim_ignored_from_a_remote_peer(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert _plan(_dev_headers(), client_host="203.0.113.9") == "foundation"


def test_dev_shim_ignored_behind_an_untrusted_proxy(monkeypatch):
    """X-Forwarded-For from a peer that is not a trusted proxy is not loopback."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    headers = _dev_headers(**{"X-Forwarded-For": "203.0.113.9"})
    assert _plan(headers) == "foundation"


def test_anonymous_caller_stays_in_the_tight_bucket(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert _plan({}) == "foundation"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_every_loopback_spelling_resolves(monkeypatch, host):
    monkeypatch.setenv("ENVIRONMENT", "development")
    plan = _plan(_dev_headers(), client_host=host)
    if host == "::1":
        # Starlette reports the IPv6 loopback as "::1"; is_loopback_host covers it.
        assert plan in ("mover", "autothink")
    else:
        assert plan == "mover"
