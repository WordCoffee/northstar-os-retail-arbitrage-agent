"""The Autothink offer must be deliverable — or refuse and say why.

The router has always priced an engineering handoff; these tests are about what
actually leaves the machine.
"""

import json

import chat_tools
import shell_focus
from specialists import autothink_transport as at

ENGINEERING = "refactor the listings service to async and add tests"


def _env(**kw):
    base = {"AUTOTHINK_ENDPOINT": "https://autothink.example/api/jobs", "AUTOTHINK_LIVE": "1"}
    base.update(kw)
    return base


def _packet(charge=2.5):
    p = at.build_packet(ENGINEERING, _env())
    assert p["ok"] is True
    p["estimated_charge_usd"] = charge
    return p


def _journal(tmp_path):
    return tmp_path / "handoffs.jsonl"


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── readiness ────────────────────────────────────────────────────────────────
def test_status_names_every_missing_piece():
    st = at.status({})
    assert st["configured"] is False
    assert any("AUTOTHINK_ENDPOINT" in b for b in st["blockers"])
    assert any("AUTOTHINK_LIVE" in b for b in st["blockers"])


def test_an_endpoint_without_an_armed_lane_is_still_not_configured():
    st = at.status({"AUTOTHINK_ENDPOINT": "https://x.example/a"})
    assert st["configured"] is False
    assert st["endpoint_host"] == "x.example"
    assert st["blockers"] == ["AUTOTHINK_LIVE is not 1 (the premium lane is not armed)"]


# ── what gets built ──────────────────────────────────────────────────────────
def test_a_seller_request_is_never_sent_to_a_paid_coding_service():
    p = at.build_packet("make me a quick tip calculator")
    assert p["ok"] is False
    assert p["reason"] == "not_engineering"


def test_the_packet_is_deterministic_and_carries_the_price():
    a = at.build_packet(ENGINEERING, _env())
    b = at.build_packet(ENGINEERING, _env())
    assert a["packet_id"] == b["packet_id"]
    assert a["packet_id"].startswith("ath_")
    assert a["estimated_charge_usd"] is not None
    assert a["acceptance"]
    assert a["status"]["configured"] is True


# ── every refusal happens before the network ─────────────────────────────────
def test_nothing_leaves_without_an_approval(tmp_path):
    calls = []
    res = at.send(_packet(), approved_by=None, max_charge_usd=5,
                  transport=lambda *a: calls.append(a) or (200, "{}"),
                  env=_env(), journal_path=_journal(tmp_path))
    assert res["status"] == "refused" and res["reason"] == "approval_required"
    assert calls == []


def test_nothing_leaves_an_unarmed_lane(tmp_path):
    calls = []
    res = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                  transport=lambda *a: calls.append(a) or (200, "{}"),
                  env={}, journal_path=_journal(tmp_path))
    assert res["reason"] == "not_configured"
    assert calls == []


def test_nothing_leaves_without_a_ceiling(tmp_path):
    calls = []
    res = at.send(_packet(), approved_by="acct-1", max_charge_usd=None,
                  transport=lambda *a: calls.append(a) or (200, "{}"),
                  env=_env(), journal_path=_journal(tmp_path))
    assert res["reason"] == "no_charge_ceiling"
    assert calls == []


def test_nothing_leaves_when_the_estimate_is_over_the_ceiling(tmp_path):
    calls = []
    res = at.send(_packet(charge=9.0), approved_by="acct-1", max_charge_usd=5,
                  transport=lambda *a: calls.append(a) or (200, "{}"),
                  env=_env(), journal_path=_journal(tmp_path))
    assert res["reason"] == "charge_exceeds_ceiling"
    assert calls == []


# ── one attempt, one receipt ─────────────────────────────────────────────────
def test_a_failed_send_is_attempted_once_and_recorded(tmp_path):
    calls = []

    def boom(*_a):
        calls.append(1)
        raise RuntimeError("connection reset by peer")

    path = _journal(tmp_path)
    res = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                  transport=boom, env=_env(), journal_path=path)

    assert res["ok"] is False and res["status"] == "failed"
    assert len(calls) == 1, "a failed send must never be retried automatically"
    rows = _rows(path)
    assert len(rows) == 1 and rows[0]["ok"] is False


def test_a_successful_send_records_the_response_id(tmp_path):
    res = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                  transport=lambda *a: (202, '{"job_id": "job-9"}'),
                  env=_env(), journal_path=_journal(tmp_path))
    assert res["ok"] is True and res["status"] == "sent"
    assert res["receipt"]["response_id"] == "job-9"
    assert res["receipt"]["attempt"] == 1


def test_an_http_error_is_reported_as_failed_not_sent(tmp_path):
    res = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                  transport=lambda *a: (500, "nope"),
                  env=_env(), journal_path=_journal(tmp_path))
    assert res["ok"] is False and res["status"] == "failed"
    assert res["receipt"]["http_status"] == 500


def test_the_same_brief_cannot_be_charged_twice(tmp_path):
    calls = []

    def ok(*a):
        calls.append(1)
        return 200, '{"id": "first"}'

    path = _journal(tmp_path)
    first = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                    transport=ok, env=_env(), journal_path=path)
    second = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                     transport=ok, env=_env(), journal_path=path)

    assert first["ok"] is True
    assert second["reason"] == "already_sent"
    assert len(calls) == 1


def test_the_token_never_reaches_a_receipt_or_an_error(tmp_path):
    token = "sk-live-supersecret-token"

    def boom(*_a):
        raise RuntimeError(f"refused for {token}")

    path = _journal(tmp_path)
    res = at.send(_packet(), approved_by="acct-1", max_charge_usd=5,
                  transport=boom, env=_env(AUTOTHINK_TOKEN=token), journal_path=path)

    assert token not in path.read_text(encoding="utf-8")
    assert token not in json.dumps(res)
    assert "***" in path.read_text(encoding="utf-8")


# ── the chat surface ─────────────────────────────────────────────────────────
def test_the_tool_prepares_the_brief_without_sending(monkeypatch):
    monkeypatch.setenv("AUTOTHINK_ENDPOINT", "https://autothink.example/api/jobs")
    monkeypatch.setenv("AUTOTHINK_LIVE", "1")
    res = chat_tools.run_tool("handoff_to_autothink", {"request": ENGINEERING},
                              {"account_id": "acct-1"})
    assert res["ok"] is True
    assert res["data"]["sent"] is False
    assert "Nothing has been sent" in res["summary"]


def test_the_tool_refuses_when_the_lane_is_not_armed(monkeypatch):
    monkeypatch.delenv("AUTOTHINK_ENDPOINT", raising=False)
    monkeypatch.delenv("AUTOTHINK_LIVE", raising=False)
    res = chat_tools.run_tool("handoff_to_autothink",
                              {"request": ENGINEERING, "confirm": True},
                              {"account_id": "acct-1"})
    assert res["ok"] is False
    assert "AUTOTHINK_ENDPOINT" in (res["error"] or "")


def test_the_tool_will_not_approve_itself_without_an_account(monkeypatch):
    monkeypatch.setenv("AUTOTHINK_ENDPOINT", "https://autothink.example/api/jobs")
    monkeypatch.setenv("AUTOTHINK_LIVE", "1")
    monkeypatch.setenv("AUTOTHINK_MAX_CHARGE_USD", "5")
    res = chat_tools.run_tool("handoff_to_autothink",
                              {"request": ENGINEERING, "confirm": True}, {})
    assert res["ok"] is False
    assert "approval" in (res["error"] or "").lower()


def test_the_handoff_tool_is_reachable_from_every_focus():
    for focus in ("create", "grow", "research", "operate"):
        assert "handoff_to_autothink" in shell_focus.tools_for_focus(focus), focus
