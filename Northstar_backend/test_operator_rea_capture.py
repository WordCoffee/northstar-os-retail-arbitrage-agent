"""Operator-window REA capture harness tests (V4.1 Step 3).

Offline: in-memory SQLite memory bank, fake controller. No browser, no Chrome
Connect, no network. Proves the operator gate, the allowlist gate, redaction, the
read-only task shape, and the honest BLOCKED paths.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import data_layer  # noqa: E402
import operator_rea_capture as rea  # noqa: E402

POLICY_ALLOW = {"allowed_hosts": ["www.packify.ai", "dyp.ai"]}
POLICY_DENY = {"allowed_hosts": ["example.com"]}


class _FakeLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE memory_entries (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, "
            "entry_type TEXT, content TEXT NOT NULL, source TEXT, confidence REAL DEFAULT 0.8, "
            "tags TEXT, provenance TEXT, retired_at TEXT, created_at TEXT, updated_at TEXT)")

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeDB:
    def __init__(self):
        self.layer = _FakeLayer()
        self.memory = data_layer.MemoryDB(self.layer)


@pytest.fixture()
def db():
    return _FakeDB()


def _now():
    return datetime.now(timezone.utc)


# ── Catalog + task shape ─────────────────────────────────────────────────────

def test_catalog_includes_packify_first():
    ids = [t["id"] for t in rea.REA_TARGETS]
    assert "packify_photoshoot" in ids and ids[0].startswith("packify")
    assert rea.target_by_id("packify_deep_agents")["host"] == "www.packify.ai"
    assert rea.target_by_id("nope") is None


def test_build_task_is_read_only_and_host_scoped():
    task = rea.build_task(rea.target_by_id("packify_photoshoot"))
    assert "www.packify.ai" in task
    assert "READ-ONLY" in task
    assert "Do NOT click" in task
    assert "json_body_shapes" in task


# ── Authorization ────────────────────────────────────────────────────────────

def test_authorize_unknown_target_raises():
    with pytest.raises(ValueError):
        rea.authorize("nope")


def test_authorize_is_ttl_capped():
    a = rea.authorize("packify_photoshoot", ttl_seconds=10 * 24 * 3600)
    issued = datetime.fromisoformat(a["issued_at"])
    expires = datetime.fromisoformat(a["expires_at"])
    assert (expires - issued).total_seconds() <= rea._MAX_AUTH_TTL_SECONDS


def test_auth_valid_expires():
    past = _now() - timedelta(hours=25)
    a = rea.authorize("packify_photoshoot", now=past, ttl_seconds=3600)
    assert rea.auth_valid(a, "packify_photoshoot", now=past + timedelta(minutes=10)) is True
    assert rea.auth_valid(a, "packify_photoshoot", now=_now()) is False


# ── Allowlist (operator-owned; read-only here) ───────────────────────────────

def test_host_allowed_matches_and_unknown():
    assert rea.host_allowed("www.packify.ai", POLICY_ALLOW) == "allowed"
    assert rea.host_allowed("evil.example.com", POLICY_ALLOW) == "refused"
    assert rea.host_allowed("www.packify.ai", None, _loaded=True) == "unknown"
    assert rea.host_allowed("sub.packify.ai", {"allowed_hosts": ["*.packify.ai"]}) == "allowed"


def test_load_operator_policy_missing_returns_none(tmp_path):
    assert rea.load_operator_policy(str(tmp_path / "nope.json")) is None


# ── The gate: plan_capture ───────────────────────────────────────────────────

def test_plan_blocked_without_authorization():
    out = rea.plan_capture("packify_photoshoot", policy=POLICY_ALLOW)
    assert out["status"] == "BLOCKED" and out["reason"] == "operator_authorization_required"


def test_plan_blocked_when_host_not_allowlisted():
    auth = rea.authorize("packify_photoshoot")
    out = rea.plan_capture("packify_photoshoot", authorization=auth, policy=POLICY_DENY)
    assert out["status"] == "BLOCKED" and out["reason"] == "host_not_allowlisted"
    assert out["policy"] == "refused"


def test_plan_blocked_when_policy_absent():
    auth = rea.authorize("packify_photoshoot")
    out = rea.plan_capture("packify_photoshoot", authorization=auth, policy=None)
    assert out["status"] == "BLOCKED" and out["policy"] == "unknown"


def test_plan_ready_when_authorized_and_allowlisted():
    auth = rea.authorize("packify_photoshoot")
    out = rea.plan_capture("packify_photoshoot", authorization=auth, policy=POLICY_ALLOW)
    assert out["status"] == "READY" and out["read_only"] is True
    assert out["host"] == "www.packify.ai" and "task" in out


def test_plan_unknown_target():
    out = rea.plan_capture("ghost", policy=POLICY_ALLOW)
    assert out["status"] == "BLOCKED" and out["reason"] == "unknown_target"


# ── run_capture: dry-run default, no accidental browser ──────────────────────

def test_run_capture_dry_run_calls_nothing():
    auth = rea.authorize("packify_photoshoot")
    calls = []

    def ctrl(task):
        calls.append(task)
        return {"ok": True}

    out = rea.run_capture("packify_photoshoot", authorization=auth, policy=POLICY_ALLOW,
                          controller=ctrl)  # dry_run defaults True
    assert out["mode"] == "dry_run" and calls == []


def test_run_capture_live_uses_controller_once():
    auth = rea.authorize("packify_photoshoot")
    calls = []

    def ctrl(task):
        calls.append(task)
        return {"ok": True, "requests": 0}

    out = rea.run_capture("packify_photoshoot", authorization=auth, policy=POLICY_ALLOW,
                          dry_run=False, controller=ctrl)
    assert out["status"] == "CAPTURED" and len(calls) == 1
    assert "www.packify.ai" in calls[0]


def test_run_capture_blocked_never_calls_controller():
    calls = []

    def ctrl(task):
        calls.append(task)
        return {"ok": True}

    out = rea.run_capture("packify_photoshoot", policy=POLICY_ALLOW, dry_run=False,
                          controller=ctrl)  # no authorization
    assert out["status"] == "BLOCKED" and calls == []


def test_run_capture_live_without_controller_is_blocked(monkeypatch):
    auth = rea.authorize("packify_photoshoot")
    monkeypatch.setattr(rea, "_default_controller", lambda: None)
    out = rea.run_capture("packify_photoshoot", authorization=auth, policy=POLICY_ALLOW,
                          dry_run=False)
    assert out["status"] == "BLOCKED" and out["reason"] == "controller_not_found"


# ── Redaction + memory ingestion ─────────────────────────────────────────────

def test_redact_url_strips_query_and_userinfo():
    out = rea.redact_url("https://user:pw@www.packify.ai/api/x?a=1&token=SECRET#frag")
    assert out == "https://www.packify.ai/api/x"
    assert "SECRET" not in out and "pw" not in out


def test_redact_text_scrubs_tokens():
    out = rea.redact_text("url?token=abc123&api_key=zzz Bearer deadbeef")
    assert "abc123" not in out and "zzz" not in out and "deadbeef" not in out
    assert "<redacted>" in out


def test_summarize_capture_is_value_free():
    payload = {"normalized_result": {"network": {"requests": [
        {"method": "POST", "url": "https://www.packify.ai/api/photoshoot/background?token=abc123&x=1"},
        {"method": "GET", "url": "https://www.packify.ai/api/photoshoot/template/list"},
    ], "websocket_frames": [{"dir": "in", "bytes": 12}]}}}
    s = rea.summarize_capture(payload)
    assert "2 request(s)" in s and "1 ws frame(s)" in s
    assert "photoshoot/background" in s
    assert "token=abc123" not in s and "?x=1" not in s


def test_ingest_capture_writes_memory_entry(db):
    auth = rea.authorize("packify_photoshoot", operator="tyrone")
    payload = {"normalized_result": {"network": {"requests": [
        {"method": "POST", "url": "https://www.packify.ai/api/photoshoot/background?token=abc123"}]}}}
    out = rea.ingest_capture(db, target_id="packify_photoshoot", payload=payload,
                             authorization=auth, account_id="acct-1")
    assert out["ok"] is True

    entries = rea.list_captures(db, account_id="acct-1")
    assert len(entries) == 1
    e = entries[0]
    assert e["entry_type"] == "rea_capture"
    assert "token=abc123" not in e["content"]
    prov = e["provenance"]
    if isinstance(prov, str):
        import json
        prov = json.loads(prov)
    assert prov["read_only"] is True and prov["host"] == "www.packify.ai"
    assert prov["operator"] == "tyrone"
    assert "token=" not in prov["url"]


def test_list_captures_filters_by_type(db):
    auth = rea.authorize("packify_photoshoot")
    rea.ingest_capture(db, target_id="packify_photoshoot",
                       payload={"normalized_result": {"network": {"requests": []}}},
                       authorization=auth, account_id="acct-1")
    db.memory.ingest({"account_id": "acct-1", "entry_type": "note", "content": "unrelated"})
    assert len(rea.list_captures(db, account_id="acct-1")) == 1
