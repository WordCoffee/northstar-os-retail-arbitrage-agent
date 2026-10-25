"""V3 shell tests (2026-10-18) — capability gate, focus catalogue, hardware.

Covers:
  • the v4 plan catalog: `ui_gates` (advanced_view on Keystone/AutothinK only)
    and the untouched live-gate arrays;
  • `resolve_capabilities` (pure): admin → advanced; plan ui gate → advanced;
    anonymous/foundation → no advanced; hosted org advanced_reports → advanced;
  • the focus catalogue: ids, server-owned tool subsets filtered to registered
    tools, chat_adapter focus injection;
  • turn_event_stream restricting offered tools by the session's focus;
  • PATCH /sessions/{sid} validation (direct call on a fake store);
  • hardware telemetry parsing (fake nvidia-smi output; honest ok=false).

Offline: no Ollama, no network, no server. Store = in-memory SQLite built from
the REAL chat DDL (chat_schema.CHAT_TABLES_SQL).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import auth  # noqa: E402
import chat_adapter  # noqa: E402
import chat_router  # noqa: E402
import chat_schema  # noqa: E402
import chat_tools  # noqa: E402
import data_layer  # noqa: E402
import shell_focus  # noqa: E402
import shell_router  # noqa: E402


# ── Fixtures: in-memory store speaking DataLayer's dialect ──────────────────

class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.chat = data_layer.ChatContainer(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def _parse_frames(chunks):
    out = []
    for frame in chunks:
        lines = [ln for ln in frame.split("\n") if ln]
        event = next((ln[7:] for ln in lines if ln.startswith("event: ")), None)
        data_line = next((ln[6:] for ln in lines if ln.startswith("data: ")), "{}")
        out.append((event, json.loads(data_line)))
    return out


# ── Plan catalog (v4): ui_gates vs live gates ───────────────────────────────

def test_ui_gates_are_advanced_view_on_top_tiers_only():
    plans = auth.PLAN_ENTITLEMENTS
    assert plans["foundation"]["ui_gates"] == []
    assert plans["scout"]["ui_gates"] == []
    assert plans["mover"]["ui_gates"] == ["advanced_view"]
    assert plans["autothink"]["ui_gates"] == ["advanced_view"]


def test_live_gate_arrays_unchanged_by_v4():
    plans = auth.PLAN_ENTITLEMENTS
    assert plans["foundation"]["gates"] == [
        "sourcescout_live_pull", "sourcescout_enrich",
        "listingforge_copy", "adpilot_ads_read",
    ]
    assert plans["autothink"]["gates"] == [
        "sourcescout_live_pull", "sourcescout_enrich",
        "listingforge_copy", "listingforge_media",
        "adpilot_ads_read", "adpilot_bulk_exec",
        "socialpulse_attrib", "socialpulse_publish",
        "autothink_workspace",
    ]
    # ui_gates never leak into the live gate arrays
    for pid, plan in plans.items():
        assert "advanced_view" not in plan["gates"], pid


def test_user_ui_gates_fail_closed_for_unknown_user():
    with mock.patch("auth.get_user", return_value=None):
        assert auth.user_ui_gates("nobody") == []


def test_user_ui_gates_read_plan():
    with mock.patch("auth.get_user", return_value={"plan": "mover"}):
        assert auth.user_ui_gates("u1") == ["advanced_view"]
    with mock.patch("auth.get_user", return_value={"plan": "scout"}):
        assert auth.user_ui_gates("u2") == []


# ── resolve_capabilities (pure) ─────────────────────────────────────────────

def _caps(identity, plan_row=None, org=None):
    with mock.patch("auth.get_user", return_value=plan_row), \
         mock.patch("shell_router._org_entitlements", return_value=org or {}):
        return shell_router.resolve_capabilities(identity)


def test_capabilities_anonymous_member_denied():
    caps = _caps({"user_id": "", "org_id": "", "role": "member", "source": "anonymous"})
    assert caps["capabilities"]["advanced_view"] is False
    assert caps["capabilities"]["autothink_workspace"] is False


def test_capabilities_admin_always_advanced():
    caps = _caps({"user_id": "", "org_id": "", "role": "admin", "source": "session"})
    assert caps["capabilities"]["advanced_view"] is True
    assert caps["capabilities"]["autothink_workspace"] is True


def test_capabilities_plan_ui_gate_grants_advanced():
    caps = _caps({"user_id": "u1", "org_id": "", "role": "member", "source": "session"},
                 plan_row={"plan": "autothink"})
    assert caps["capabilities"]["advanced_view"] is True
    assert caps["capabilities"]["autothink_workspace"] is True


def test_capabilities_foundation_plan_denied_even_with_user_row():
    caps = _caps({"user_id": "u2", "org_id": "", "role": "member", "source": "session"},
                 plan_row={"plan": "foundation"})
    assert caps["capabilities"]["advanced_view"] is False


def test_the_owner_role_gets_advanced_view_on_any_plan():
    """The owner's own account had advanced_view false: role 'owner' was not in
    ADMIN_ROLES, so every service room was unreachable in the browser."""
    caps = _caps({"user_id": "u1", "org_id": "", "role": "owner", "source": "session"},
                 plan_row={"plan": "foundation"})
    assert caps["capabilities"]["advanced_view"] is True
    assert caps["capabilities"]["autothink_workspace"] is True


def test_capabilities_hosted_org_advanced_reports_grants_advanced():
    caps = _caps({"user_id": "", "org_id": "org-1", "role": "member", "source": "session"},
                 org={"tier": "pro", "advanced_reports": True})
    assert caps["capabilities"]["advanced_view"] is True
    assert caps["capabilities"]["autothink_workspace"] is True


def test_capabilities_trial_org_denied():
    caps = _caps({"user_id": "", "org_id": "org-2", "role": "member", "source": "session"},
                 org={"tier": "trial", "advanced_reports": False})
    assert caps["capabilities"]["advanced_view"] is False
    assert caps["capabilities"]["autothink_workspace"] is False


# ── Focus catalogue ─────────────────────────────────────────────────────────

def test_focus_ids_and_uniqueness():
    ids = [f["id"] for f in shell_focus.FOCUS_MODES]
    assert ids == ["auto", "create", "grow", "research", "operate", "autothink"]
    assert len(ids) == len(set(ids))


def test_focus_tool_subsets_are_registered_or_filtered():
    for f in shell_focus.FOCUS_MODES:
        subset = shell_focus.tools_for_focus(f["id"])
        if subset is None:
            assert f["tools"] is None
            continue
        assert subset, f["id"]
        assert all(t in chat_tools.TOOLS for t in subset)


def test_unknown_focus_falls_back_to_auto():
    assert shell_focus.focus_by_id("nope")["id"] == "auto"
    assert shell_focus.tools_for_focus("nope") is None


def test_build_chat_messages_injects_focus_prompt_and_context():
    msgs = chat_adapter.build_chat_messages(
        [], focus={"mode": "create", "brand": "Mogul Organics"})
    system = msgs[0]["content"]
    assert "Active focus" in system
    assert "creative production" in system
    assert "brand: Mogul Organics" in system
    assert "mode: create" not in system  # the id renders as a prompt, not raw


def test_build_chat_messages_without_focus_matches_legacy_prompt():
    msgs = chat_adapter.build_chat_messages([{"role": "user", "content": "hi"}])
    # DELIVERABLE_ROUTING is part of every system prompt. Exact equality is too
    # brittle (breaks on any wording change); assert the invariants instead.
    assert chat_adapter.CHAT_SYSTEM_PROMPT in msgs[0]["content"]
    assert chat_adapter.DELIVERABLE_ROUTING in msgs[0]["content"]
    assert "[Skills" not in msgs[0]["content"]


# ── Turn stream: focus restricts offered tools ──────────────────────────────

def _script(*events):
    def it():
        for ev in events:
            yield ev
    return it()


def test_turn_offers_only_focus_tools(db):
    sid = db.chat.sessions.create({
        "account_id": "acct-1", "title": "New chat",
        "focus_json": {"mode": "create"},
    })
    session = db.chat.sessions.get_by_id(sid, account_id="acct-1")
    pairs = _parse_frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "hello",
        events=_script({"type": "content", "delta": "ok"}, {"type": "done", "cancelled": False}))))
    start = pairs[0][1]
    expected = set(shell_focus.tools_for_focus("create"))
    assert set(start["tools"]) == expected
    assert "generate_image" in start["tools"]
    # the finish-the-pack step must be reachable from the focus the operator uses
    assert "apply_label" in start["tools"]
    assert "system_status" not in start["tools"]


def test_turn_offers_all_tools_without_focus(db):
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "New chat"})
    session = db.chat.sessions.get_by_id(sid, account_id="acct-1")
    pairs = _parse_frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "hello",
        events=_script({"type": "done", "cancelled": False}))))
    assert set(pairs[0][1]["tools"]) == set(chat_tools.tool_names())


def test_turn_offers_all_tools_for_autothink_focus(db):
    sid = db.chat.sessions.create({
        "account_id": "acct-1", "title": "New chat",
        "focus_json": {"mode": "autothink"},
    })
    session = db.chat.sessions.get_by_id(sid, account_id="acct-1")
    pairs = _parse_frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "build me a playbook",
        events=_script({"type": "done", "cancelled": False}))))
    assert set(pairs[0][1]["tools"]) == set(chat_tools.tool_names())


# ── PATCH /sessions/{sid} (rename + focus) ──────────────────────────────────

def test_patch_session_sets_title_and_focus(db):
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "New chat"})
    with mock.patch("chat_router.get_northstar_db", return_value=db):
        out = chat_router.patch_session(
            sid, chat_router.SessionPatch(title="Mogra packaging", focus={"mode": "create"}),
            acct="acct-1")
    assert out["title"] == "Mogra packaging"
    assert out["focus_json"] == {"mode": "create"}


def test_patch_session_rejects_unknown_focus(db):
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "New chat"})
    from fastapi import HTTPException
    with mock.patch("chat_router.get_northstar_db", return_value=db):
        with pytest.raises(HTTPException) as err:
            chat_router.patch_session(
                sid, chat_router.SessionPatch(focus={"mode": "hax"}), acct="acct-1")
    assert err.value.status_code == 400
    assert "unknown focus" in err.value.detail


def test_patch_session_404_for_other_account(db):
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "New chat"})
    from fastapi import HTTPException
    with mock.patch("chat_router.get_northstar_db", return_value=db):
        with pytest.raises(HTTPException) as err:
            chat_router.patch_session(
                sid, chat_router.SessionPatch(title="stolen"), acct="acct-2")
    assert err.value.status_code == 404


def test_patch_session_rejects_empty_patch(db):
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "New chat"})
    from fastapi import HTTPException
    with mock.patch("chat_router.get_northstar_db", return_value=db):
        with pytest.raises(HTTPException) as err:
            chat_router.patch_session(sid, chat_router.SessionPatch(), acct="acct-1")
    assert err.value.status_code == 400


# ── HTTP surface (TestClient) ───────────────────────────────────────────────

def test_shell_context_endpoint_anonymous_and_dev_admin():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    r = client.get("/api/shell/context")
    assert r.status_code == 200
    body = r.json()
    assert body["contract"] == "shell/v1"
    assert body["default_mode"] == "simple"
    assert body["capabilities"]["advanced_view"] is False
    ids = [f["id"] for f in body["focuses"]]
    assert ids[0] == "auto" and "autothink" in ids
    autothink = next(f for f in body["focuses"] if f["id"] == "autothink")
    assert autothink["locked"] is True  # anonymous cannot use the premium focus

    r2 = client.get("/api/shell/context",
                    headers={"X-User-Id": "dev-op", "X-Role": "admin"})
    assert r2.status_code == 200
    assert r2.json()["capabilities"]["advanced_view"] is True
    assert next(f for f in r2.json()["focuses"]
                if f["id"] == "autothink")["locked"] is False


def test_shell_hardware_endpoint_shape():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    r = client.get("/api/shell/hardware")
    assert r.status_code == 200
    body = r.json()
    assert "sampled_at" in body
    assert "gpu" in body and "ram" in body
    # Either the real GPU answers or the reason is present — never invented.
    assert body["gpu"]["ok"] in (True, False)
    if not body["gpu"]["ok"]:
        assert body["gpu"]["reason"]


# ── Hardware telemetry ──────────────────────────────────────────────────────def test_parse_gpu_csv_real_shape():
    stdout = "NVIDIA GeForce RTX 5080 Laptop GPU, 16376, 1126, 7, 52\n"
    gpus = shell_router.parse_gpu_csv(stdout)
    assert len(gpus) == 1
    g = gpus[0]
    assert g["name"].startswith("NVIDIA")
    assert g["vram_total_mb"] == 16376
    assert g["vram_used_mb"] == 1126
    assert g["util_pct"] == 7.0
    assert g["temp_c"] == 52.0


def test_parse_gpu_csv_tolerates_na_and_junk():
    stdout = "GPU A, [N/A], [N/A], [N/A], [N/A]\nnot a gpu line\n"
    gpus = shell_router.parse_gpu_csv(stdout)
    assert len(gpus) == 1
    assert gpus[0]["vram_total_mb"] is None
    assert gpus[0]["util_pct"] is None


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_collect_hardware_reports_unavailable_honestly():
    payload = shell_router.collect_hardware(gpu_runner=lambda: _Proc(
        returncode=1, stderr="nvidia-smi: command not found"))
    assert payload["gpu"]["ok"] is False
    assert payload["gpu"]["gpus"] == []
    assert "nvidia-smi" in payload["gpu"]["reason"]
    assert "sampled_at" in payload


def test_collect_hardware_raises_are_caught():
    def _boom():
        raise FileNotFoundError("nvidia-smi")
    payload = shell_router.collect_hardware(gpu_runner=_boom)
    assert payload["gpu"]["ok"] is False
    assert payload["gpu"]["reason"] == "nvidia-smi not on PATH"


# ── Governor + daemon (V3 S6) ───────────────────────────────────────────────

def test_governor_full_dpr_when_reserve_ok():
    gpu = {"ok": True, "gpus": [{"name": "RTX 5080", "vram_total_mb": 16376,
                                  "vram_used_mb": 1126, "util_pct": 7, "temp_c": 52}]}
    gov = shell_router._governor(gpu)
    assert gov["reserve_ok"] is True
    assert gov["recommended_dpr"] == 1.5
    assert gov["free_mb"] == 16376 - 1126
    assert gov["reserve_target_mb"] == 1800


def test_governor_lowers_dpr_when_reserve_breached():
    gpu = {"ok": True, "gpus": [{"name": "RTX 5080", "vram_total_mb": 16376,
                                  "vram_used_mb": 15200, "util_pct": 95, "temp_c": 70}]}
    gov = shell_router._governor(gpu)
    assert gov["reserve_ok"] is False
    assert gov["recommended_dpr"] == 1.0


def test_governor_unknown_without_readings():
    gov = shell_router._governor({"ok": False, "gpus": []})
    assert gov["reserve_ok"] is None
    assert gov["recommended_dpr"] is None


def test_collect_hardware_includes_governor():
    payload = shell_router.collect_hardware(gpu_runner=lambda: _Proc(
        returncode=0, stdout="NVIDIA GeForce RTX 5080 Laptop GPU, 16376, 1126, 7, 52\n"))
    assert payload["governor"]["reserve_ok"] is True
    assert payload["governor"]["recommended_dpr"] == 1.5


def test_daemon_loop_updates_cache_and_breaks_cleanly():
    class _Stop(Exception):
        pass
    calls = {"n": 0}

    def fake_collect():
        return {"sampled_at": "x", "gpu": {"ok": True, "gpus": []},
                "ram": {"ok": True}, "governor": {}}

    def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise _Stop()

    with pytest.raises(_Stop):
        shell_router._hardware_daemon_loop(collect=fake_collect, sleep=fake_sleep)
    assert shell_router._HW_CACHE["payload"]["gpu"]["ok"] is True


def test_daemon_start_is_idempotent():
    shell_router.start_hardware_daemon()
    assert shell_router.start_hardware_daemon() is False
