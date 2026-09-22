"""Phase H / UI regression — the suite shell's static assets must be SERVED.

The shell (static/northstar-os/index.html) loads its css/js with RELATIVE
paths (css/tokens.css, js/engine.js). If the backend only serves the index
route without a static mount for /northstar-os, every asset 404s and the UI
renders as an unstyled, non-interactive page (the "bare shell" bug).

This test fetches over HTTP, which the file-reading shell contract test cannot
catch.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_shell_index_served_with_stylesheet_links(client):
    r = client.get("/northstar-os/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "css/tokens.css" in r.text
    assert "js/engine.js" in r.text


def test_shell_no_trailing_slash_redirects(client):
    r = client.get("/northstar-os", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"].endswith("/northstar-os/")


@pytest.mark.parametrize("asset", [
    "/northstar-os/css/tokens.css",
    "/northstar-os/css/components.css",
    "/northstar-os/css/layout.css",
    "/northstar-os/css/hub.css",
    "/northstar-os/css/shell.css",
    "/northstar-os/css/onboarding.css",
    "/northstar-os/js/engine.js",
    "/northstar-os/js/demo-data.js",
    "/northstar-os/js/brain.js",
    "/northstar-os/js/hub.js",
    "/northstar-os/js/deck.js",
    "/northstar-os/js/account.js",
])
def test_shell_assets_are_served(client, asset):
    r = client.get(asset)
    assert r.status_code == 200, "%s returned %s (asset 404 -> bare shell)" % (asset, r.status_code)
    assert len(r.content) > 0


def test_autothink_workspace_assets_served(client):
    r = client.get("/autothink/ui/index.html")
    assert r.status_code == 200
    assert "<html" in r.text.lower()