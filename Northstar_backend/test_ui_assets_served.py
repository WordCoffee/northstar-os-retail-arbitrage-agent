"""UI regression — the canonical frontend's static assets must be SERVED.

The React/Vite production build (northstar-os-ui/dist) is served at /ui with
hash routing and an SPA index fallback. If the backend only serves the index
route without a static mount for /ui/assets, every hashed asset 404s and the
UI renders as a blank page.

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


def test_ui_index_served(client):
    r = client.get("/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert 'id="root"' in r.text
    assert "/assets/" in r.text  # vite-built asset references


def test_ui_deep_link_served(client):
    r = client.get("/ui/jobs")
    assert r.status_code == 200
    assert 'id="root"' in r.text


def test_ui_assets_are_served(client):
    dist = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "northstar-os-ui", "dist"))
    assets_dir = os.path.join(dist, "assets")
    assert os.path.isdir(assets_dir), "northstar-os-ui production build missing"
    js = next((a for a in os.listdir(assets_dir) if a.endswith(".js")), None)
    assert js is not None
    r = client.get("/ui/assets/%s" % js)
    assert r.status_code == 200, "/ui/assets/%s returned %s (asset 404 -> blank page)" % (js, r.status_code)
    assert len(r.content) > 0


def test_autothink_workspace_assets_served(client):
    r = client.get("/autothink/ui/index.html")
    assert r.status_code == 200
    assert "<html" in r.text.lower()