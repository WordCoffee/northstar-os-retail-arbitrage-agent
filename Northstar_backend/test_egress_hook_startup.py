"""The service entrypoint installs the transport-level egress guard.

W9 / T0-egress-hook. Three things are proved here, in the order the control
matters:

  1. `tools/egress_guard.py` refuses Amazon at the transport, so a call site with
     no explicit check of its own still cannot reach Amazon.
  2. `main.install_egress_guard()` reports an active guard and points at the
     audit log.
  3. The real startup path (`lifespan`, exercised through TestClient) installs
     it, and a guard that cannot install refuses the boot instead of running
     unprotected.

No network is opened: the guard refuses before the transport, and every fake
transport here counts calls so "refused" cannot be confused with "attempted".
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent
_ROOT = _BACKEND.parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_ROOT / "tools"))

import egress_guard as eg  # noqa: E402


@pytest.fixture(autouse=True)
def _uninstall():
    """Leave no wrapper behind, even if a test died halfway through."""
    original = urllib.request.urlopen
    yield
    eg.uninstall()
    urllib.request.urlopen = original


def _counting_transport(monkeypatch):
    """Replace the real transport with a counter; returns the counter."""
    calls = {"n": 0}

    def fake_urlopen(*_a, **_k):
        calls["n"] += 1
        return io.BytesIO(b"ok")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def test_a_call_site_with_no_check_of_its_own_still_refuses_amazon(monkeypatch):
    import requests

    urllib_calls = _counting_transport(monkeypatch)
    api_calls = {"n": 0}

    def fake_request(*_a, **_k):
        api_calls["n"] += 1
        return "response"

    monkeypatch.setattr(requests.api, "request", fake_request)

    assert eg.install()["installed"] is True

    # Neither call site mentions Amazon or any policy: the transport does.
    with pytest.raises(eg.EgressRefused):
        urllib.request.urlopen("https://www.amazon.com/dp/B0EXAMPLE")
    with pytest.raises(eg.EgressRefused):
        requests.get("https://www.amazon.co.uk/dp/B0EXAMPLE")
    assert urllib_calls["n"] == 0, "a refused request must not reach the transport"
    assert api_calls["n"] == 0, "a refused request must not reach the transport"

    urllib.request.urlopen("https://example.com/ok")
    requests.get("https://example.com/ok")
    assert urllib_calls["n"] == 1 and api_calls["n"] == 1


def test_install_egress_guard_reports_an_active_guard():
    import main

    result = main.install_egress_guard()
    assert result.get("installed") or result.get("already")
    assert eg.installed() is True
    assert result["audit"].endswith("egress.jsonl")


def test_a_guard_that_cannot_install_refuses_the_boot(monkeypatch):
    import main

    def broken_install():
        raise RuntimeError("tooling missing")

    monkeypatch.setattr(eg, "install", broken_install)
    with pytest.raises(RuntimeError) as ei:
        main.install_egress_guard()
    assert "EGRESS GUARD VIOLATION" in str(ei.value)


def test_startup_path_installs_the_guard_before_any_request(monkeypatch):
    """The real lifespan is driven, so the hook cannot be lost in a refactor."""
    from fastapi.testclient import TestClient

    import amazon_linkage_gate
    import auth
    import httpx
    import live_gate
    import main
    import rate_limiter
    import studio_generation

    order = []
    calls = _counting_transport(monkeypatch)  # install() wraps this fake

    def no_op(*_a, **_k):
        return None

    monkeypatch.setattr(rate_limiter, "assert_prod_posture", no_op)
    monkeypatch.setattr(live_gate, "assert_live_posture", no_op)
    monkeypatch.setattr(auth, "assert_jwt_secret_posture", no_op)
    monkeypatch.setattr(amazon_linkage_gate, "assert_linkage_posture", no_op)
    monkeypatch.setattr(studio_generation, "restore_pending_session", lambda: None)

    real_install = main.install_egress_guard
    monkeypatch.setattr(main, "install_egress_guard",
                        lambda: (order.append("egress"), real_install())[1])

    # The first outbound request the startup path makes is the Ollama probe.
    class _NoOllama:
        status_code = 503

        def json(self):
            return {"models": []}

    monkeypatch.setattr(httpx, "get",
                        lambda *a, **k: (order.append("http"), _NoOllama())[1])

    with TestClient(main.app):
        assert eg.installed() is True
        assert order and order[0] == "egress", f"guard must run first, saw {order}"
        if "http" in order:
            assert order.index("egress") < order.index("http")

        # The guard installed at startup is the guard the call sites get.
        with pytest.raises(eg.EgressRefused):
            urllib.request.urlopen("https://www.amazon.com/dp/X")
        assert calls["n"] == 0
        urllib.request.urlopen("https://example.com/ok")
        assert calls["n"] == 1
