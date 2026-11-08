"""The egress guard must refuse Amazon at the transport, not at each call site."""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import egress_guard as eg  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    """Leave the *real* transport behind, not the one `eg.install()` captured.

    Measured defect: teardown is LIFO, so `monkeypatch` restored the true urlopen
    first and this fixture's `eg.uninstall()` then re-applied the fake that install
    had captured - a `BytesIO` fake leaked into every later test in the suite and
    12-17 of them failed with `JSONDecodeError` or `no attribute 'status'`. All of
    them passed in isolation.
    """
    original = urllib.request.urlopen
    yield
    eg.uninstall()
    urllib.request.urlopen = original


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/X",
    "https://amazon.co.uk/x",
    "https://smile.amazon.com/",
    "https://amzn.eu/d/x",
    "https://media-amazon.com/images/I/x.jpg",
    "https://www.amazon.com.evil.test/x",
])
def test_amazon_is_refused(url):
    with pytest.raises(eg.EgressRefused):
        eg.check(url, caller="test")


@pytest.mark.parametrize("url", [
    "https://github.com/block/goose",
    "https://huggingface.co/x",
    "https://notamazon.com.evil.test/",
])
def test_everything_else_passes(url):
    assert eg.check(url, caller="test") == url


def test_install_wraps_urlopen_and_refuses_before_the_network(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(*_a, **_k):
        calls["n"] += 1
        return io.BytesIO(b"ok")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    eg.install()
    with pytest.raises(eg.EgressRefused):
        urllib.request.urlopen("https://www.amazon.com/dp/X")
    assert calls["n"] == 0, "the guard must refuse before the real transport runs"


def test_an_allowed_url_still_reaches_the_transport(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(*_a, **_k):
        calls["n"] += 1
        return io.BytesIO(b"ok")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    eg.install()
    urllib.request.urlopen("https://example.com/x")
    assert calls["n"] == 1


def test_install_is_idempotent_and_uninstall_restores(monkeypatch):
    original = urllib.request.urlopen
    first = eg.install()
    second = eg.install()
    assert first["installed"] is True
    assert second["already"] is True
    eg.uninstall()
    assert urllib.request.urlopen is original


def test_requests_api_is_guarded_too(monkeypatch):
    import requests

    calls = {"n": 0}

    def fake_request(*_a, **_k):
        calls["n"] += 1
        return "response"

    monkeypatch.setattr(requests.api, "request", fake_request)
    eg.install()
    with pytest.raises(eg.EgressRefused):
        requests.get("https://www.amazon.com/dp/X")
    requests.get("https://example.com/x")
    assert calls["n"] == 1


def test_refusals_are_journaled_with_a_caller(tmp_path, monkeypatch):
    audit = tmp_path / "egress.jsonl"
    monkeypatch.setattr(eg, "AUDIT", audit)
    with pytest.raises(eg.EgressRefused):
        eg.check("https://www.amazon.com/dp/X", caller="test_file.py:12")
    line = audit.read_text(encoding="utf-8").strip()
    assert '"decision": "amazon_refused"' in line
    assert "test_file.py:12" in line
