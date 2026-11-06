"""Open API + webhooks + credit meter tests (RE build 2026-10-16, items 1 + 4).

Offline: key store uses tmp files, hooks use a local HTTP receiver, generation
submission is faked, dieline persistence is stubbed (no dev DB writes).
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import design_studio_api  # noqa: E402
import design_studio_openapi as dso  # noqa: E402
from credit_ledger import CreditLedger  # noqa: E402
from main import app  # noqa: E402


# ── key store ───────────────────────────────────────────────────────────────

def test_keystore_digest_only_and_lifecycle(tmp_path):
    store = dso._KeyStore(tmp_path / "keys.jsonl")
    made = store.create("org-a", label="ci")
    secret = made["key"]
    assert secret.startswith("nsk_") and len(secret) > 30

    # digest-only guarantee: the plaintext never lands on disk (the truncated
    # display prefix legitimately starts with nsk_ and IS expected there)
    raw = (tmp_path / "keys.jsonl").read_text(encoding="utf-8")
    assert secret not in raw
    import hashlib
    assert hashlib.sha256(secret.encode()).hexdigest() in raw

    assert store.verify(secret) == "org-a"
    assert store.verify(secret + "x") is None
    listed = store.list_for("org-a")
    assert listed and listed[0]["prefix"] == made["prefix"]

    assert store.revoke("org-a", made["id"]) is True
    assert store.verify(secret) is None  # revoked
    assert store.revoke("org-a", made["id"]) is False  # idempotent refusal

    # reload applies the revoke tombstone
    reopened = dso._KeyStore(tmp_path / "keys.jsonl")
    assert reopened.verify(secret) is None


# ── webhook delivery ────────────────────────────────────────────────────────

class _Recorder(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("content-length", 0) or 0)
        self.server.payloads.append(self.rfile.read(n))
        self.send_response(self.server.status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):  # silence test noise
        pass


def _serve(status: int):
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Recorder)
    srv.status = status
    srv.payloads = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_webhook_delivered_on_success(monkeypatch):
    # The test server is a loopback literal, which the SSRF policy refuses unless
    # the operator/dev opts in explicitly. That is the point of the guard: this
    # test is the one place that opts in, and it proves opt-in still delivers.
    monkeypatch.setenv("DESIGN_CALLBACK_ALLOW_LOOPBACK", "1")
    srv = _serve(200)
    try:
        url = f"http://127.0.0.1:{srv.server_port}/hook"
        rec = dso and __import__("design_studio_async").deliver_webhook(
            url, {"job_id": "j1", "status": "done"})
        assert rec["ok"] and rec["status"] == 200 and rec["attempts"] == 1
        assert json.loads(srv.payloads[0])["job_id"] == "j1"
    finally:
        srv.shutdown()


def test_webhook_retries_then_gives_up_bounded(monkeypatch):
    monkeypatch.setenv("DESIGN_CALLBACK_ALLOW_LOOPBACK", "1")
    srv = _serve(500)
    try:
        url = f"http://127.0.0.1:{srv.server_port}/hook"
        rec = __import__("design_studio_async").deliver_webhook(url, {"x": 1}, attempts=2)
        assert rec["ok"] is False and rec["attempts"] == 2 and rec["status"] == 500
        assert len(srv.payloads) == 2  # bounded: no thundering retries
    finally:
        srv.shutdown()


# ── open API endpoints ──────────────────────────────────────────────────────

def _patch_store(monkeypatch, tmp_path):
    store = dso._KeyStore(tmp_path / "keys.jsonl")
    monkeypatch.setattr(dso, "_STORE", store)
    return store.create("org-open", label="test")["key"]


def test_open_dielines_requires_key_and_returns_assets(tmp_path, monkeypatch):
    secret = _patch_store(monkeypatch, tmp_path)
    monkeypatch.setattr(dso._print_mod, "_persist",
                        lambda *a, **k: [{"format": "svg", "asset_id": "aid-1",
                                          "file_url": "/api/design-studio/assets/aid-1/file"}])
    c = TestClient(app)

    assert c.post("/api/open/2026-10/dielines",
                  json={"template_id": "label_circle"}).status_code == 401
    bogus = "nsk_" + "0" * 40  # assembled at runtime: no key-shaped literal in source
    assert c.post("/api/open/2026-10/dielines",
                  json={"template_id": "label_circle"},
                  headers={"X-Api-Key": bogus}).status_code == 401

    r = c.post("/api/open/2026-10/dielines",
               json={"template_id": "label_circle", "params": {"width_mm": 50, "height_mm": 50}},
               headers={"X-Api-Key": secret})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contract"] == "open/2026-10"
    assert body["size_mm"]["width"] == 56 and "trim" in body["layers"]
    assert body["assets"][0]["asset_id"] == "aid-1"

    r = c.post("/api/open/2026-10/dielines",
               json={"template_id": "rsc_box", "params": {"height_mm": 1}},
               headers={"X-Api-Key": secret})
    assert r.status_code == 422


def test_open_packaging_design_submits_and_validates(tmp_path, monkeypatch):
    secret = _patch_store(monkeypatch, tmp_path)
    captured = {}

    def fake_submit(acct, **kw):
        captured.update({"acct": acct, **kw})
        return {"job": {"id": "job-open-1", "cost_preview": {"credits": 1}}, "enforce": False}

    monkeypatch.setattr(dso, "submit_generation", fake_submit)
    c = TestClient(app)

    r = c.post("/api/open/2026-10/packaging-design",
               json={"prompt": "matte black coffee bag", "callback_url": "https://example.com/hook"},
               headers={"X-Api-Key": secret})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["contract"] == "open/2026-10" and body["job_id"] == "job-open-1"
    assert body["callback_registered"] is True
    assert captured["callback_url"] == "https://example.com/hook"

    r = c.post("/api/open/2026-10/packaging-design",
               json={"prompt": "x", "callback_url": "ftp://nope"},
               headers={"X-Api-Key": secret})
    assert r.status_code in (422,)  # invalid callback + too-short prompt


# ── credit meter (session) ──────────────────────────────────────────────────

def test_credit_meter_endpoints(monkeypatch, tmp_path):
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-cred"
    led = CreditLedger(path=str(tmp_path / "led.jsonl"))
    monkeypatch.setattr(dso, "get_ledger", lambda: led)
    try:
        c = TestClient(app)
        r = c.get("/api/design-studio/credits")
        assert r.status_code == 200 and r.json()["balance"] == 0

        r = c.post("/api/design-studio/credits/grant", json={"plan": "foundation"})
        assert r.status_code == 200, r.text
        first = r.json()
        assert first["granted"] is True and first["balance"] > 0

        r = c.post("/api/design-studio/credits/grant", json={"plan": "foundation"})
        assert r.json()["granted"] is False
        assert r.json()["balance"] == first["balance"]  # idempotent

        r = c.post("/api/design-studio/credits/grant", json={"plan": "nonsense"})
        assert r.status_code == 400
    finally:
        app.dependency_overrides = {}
