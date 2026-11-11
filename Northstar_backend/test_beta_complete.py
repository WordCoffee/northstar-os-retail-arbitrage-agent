"""The four private-beta services can be driven by Bojo, and say so honestly.

`beta`, `beta-support`, `beta-signup` and `beta-ops` each declared no tool, so the
scorecard's `complete` dimension scored 0 — Bojo could not drive them at all.
They now declare one real tool each, backed by the Foundation service that already
answers the HTTP route:

    beta           onboarding_status       SupportService.onboarding_status + PlanUsageService.view
    beta-support   submit_support_ticket   SupportService.submit_ticket
    beta-signup    redeem_invite           InviteService.signup
    beta-ops       beta_cohort             TesterDashboard.list_orgs (platform admin only)

These tests drive every one of them through `chat_tools.run_tool` — the same path a
turn uses — against a real Foundation SQLite store built from the real schema, and
assert the refusals too: no identity, no membership, no platform-admin role, and an
argument that tries to smuggle an identity must not be served.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for entry in (str(HERE), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import bojo_tools_registry  # noqa: E402
import chat_schema  # noqa: E402
import chat_router  # noqa: E402
import chat_tools  # noqa: E402
import data_layer  # noqa: E402

SERVICE_TOOL = {
    "beta": "onboarding_status",
    "beta-support": "submit_support_ticket",
    "beta-signup": "redeem_invite",
    "beta-ops": "beta_cohort",
}


# ── a real Foundation store, on a temp path ─────────────────────────────────

@pytest.fixture()
def foundation(tmp_path):
    from foundation.api.state import FoundationState

    return FoundationState.build(str(tmp_path / "foundation.db"))


def _seed(foundation, *, role="operator", user_id="u-1", org_name="Beta Org",
          slug="beta-org", email="tester@example.com"):
    from foundation.models import Membership, Organization, User

    org_id = foundation.repos.organizations.add(
        Organization(name=org_name, slug=slug))["id"]
    foundation.repos.users.add(User(id=user_id, email=email, display_name=user_id))
    foundation.repos.memberships.add(Membership(
        id=f"m-{user_id}", organization_id=org_id, user_id=user_id, role=role))
    ctx = {"foundation": foundation, "account_id": org_id,
           "identity": {"id": user_id, "tenant_id": org_id, "role": role}}
    return org_id, ctx


# ── the declaration is a real handler, not a name ───────────────────────────

@pytest.mark.parametrize("service,tool", sorted(SERVICE_TOOL.items()))
def test_the_service_declares_a_tool_the_chat_surface_offers(service, tool):
    services = {row["id"]: row for row in
                json.loads((ROOT / "ty" / "services.json").read_text(encoding="utf-8"))["services"]}
    assert services[service]["tools"] == [tool], "services.json must name the tool"

    assert tool in chat_tools.TOOLS, f"{tool} has no chat spec"
    assert callable(chat_tools.TOOLS[tool]["handler"]), f"{tool} has no handler"
    assert tool in chat_tools.tool_names(), f"{tool} is not offered to the model"
    assert bojo_tools_registry.has_handler(tool), f"{tool} has no domain handler"


@pytest.mark.parametrize("service,tool", sorted(SERVICE_TOOL.items()))
def test_the_scorecard_counts_the_service_complete(service, tool):
    from tools import scorecards

    wired = scorecards._wired_tools([tool])
    assert wired == {tool: True}
    results = scorecards.measure_one(
        {"id": service, "label": service, "group": "Private Beta",
         "kind": "onboarding", "route": "/beta", "tools": [tool]},
        [], [])
    assert results["dimensions"]["complete"]["score"] == 100.0
    assert tool in results["dimensions"]["complete"]["evidence"]


# ── every handler answers through the chat surface ──────────────────────────

def test_onboarding_status_reads_the_stored_checklist(foundation):
    org_id, ctx = _seed(foundation)
    foundation.support.complete_onboarding(org_id, step="invite_issued")

    out = chat_tools.run_tool("onboarding_status", "{}", ctx)

    assert out["ok"] is True, out
    onboarding = out["data"]["onboarding"]
    assert onboarding["checklist"]["invite_issued"] is True
    assert onboarding["next_step"] == "legal_documents_accepted"
    assert onboarding["completed"] is False
    assert out["data"]["plan"], "the plan view must come back with the checklist"
    assert "Onboarding 1/9 steps complete" in out["summary"]


def test_submit_support_ticket_writes_the_real_queue_row(foundation):
    org_id, ctx = _seed(foundation)

    out = chat_tools.run_tool("submit_support_ticket", json.dumps({
        "category": "bug", "severity": "high",
        "subject": "Signup page reloads", "description": "The form reloads on submit.",
    }), ctx)

    assert out["ok"] is True, out
    assert out["data"]["reference_id"].startswith("NS-")
    assert out["data"]["category"] == "bug" and out["data"]["severity"] == "high"
    queued = foundation.support.list_tickets(org_id, tester_view=True)
    assert [row["id"] for row in queued] == [out["data"]["ticket_id"]]
    assert "do NOT submit passwords" in out["data"]["no_secrets_warning"]


def test_submit_support_ticket_refuses_an_unknown_category(foundation):
    org_id, ctx = _seed(foundation)

    out = chat_tools.run_tool("submit_support_ticket", json.dumps({
        "category": "made-up", "severity": "high",
        "subject": "Anything", "description": "Anything at all.",
    }), ctx)

    assert out["ok"] is False
    # The spec's enum is the first gate; the service's own category check is the
    # second. Whichever fires, the rule is the same: nothing reaches the queue.
    assert "category" in out["error"]
    assert foundation.support.list_tickets(org_id, tester_view=True) == []


def test_redeem_invite_creates_the_account_and_consumes_the_invite(foundation):
    from foundation.context import build_context
    from foundation.enums import Role

    org_id, ctx = _seed(foundation)
    invite = foundation.invites.issue(
        build_context(user_id="u-1", organization_id=org_id,
                      role=Role.ORGANIZATION_OWNER.value),
        email="newbie@example.com", role="operator")

    out = chat_tools.run_tool("redeem_invite", json.dumps({
        "email": "newbie@example.com", "invite_code": invite["invite_code"],
    }), ctx)

    assert out["ok"] is True, out
    assert out["data"]["organization_id"] == org_id
    assert out["data"]["role"] == "operator"
    memberships = foundation.repos.memberships.for_user(out["data"]["user_id"])
    assert [row["organization_id"] for row in memberships] == [org_id]
    assert foundation.repos.invites.get(invite["invite_id"])["status"] == "used"


def test_redeem_invite_denial_never_reveals_which_check_failed(foundation):
    from foundation.context import build_context
    from foundation.enums import Role

    _org_id, ctx = _seed(foundation)
    wrong_code = chat_tools.run_tool("redeem_invite", json.dumps({
        "email": "nobody@example.com", "invite_code": "0123456789abcdef",
    }), ctx)
    assert wrong_code["ok"] is False
    assert wrong_code["error"] == "signup_denied: signup is not available at this time"

    invite = foundation.invites.issue(
        build_context(user_id="u-1", organization_id=ctx["account_id"],
                      role=Role.ORGANIZATION_OWNER.value),
        email="invited@example.com", role="operator")
    wrong_email = chat_tools.run_tool("redeem_invite", json.dumps({
        "email": "someone-else@example.com", "invite_code": invite["invite_code"],
    }), ctx)
    assert wrong_email["ok"] is False
    assert wrong_email["error"] == wrong_code["error"], "the denial must not distinguish"


def test_beta_cohort_refuses_a_non_admin(foundation):
    _org_id, ctx = _seed(foundation)

    out = chat_tools.run_tool("beta_cohort", "{}", ctx)

    assert out["ok"] is False
    assert "permission_denied" in out["error"]
    assert "platform admin" in out["error"]


def test_beta_cohort_reads_the_dashboard_for_a_platform_admin(foundation):
    from foundation.enums import Role

    org_id, ctx = _seed(foundation)
    foundation.repos.memberships.add(_membership(entity="m-admin", org_id=org_id,
                                                 user_id="u-1",
                                                 role=Role.INTERNAL_PLATFORM_ADMIN.value))
    _seed_second_org(foundation)

    out = chat_tools.run_tool("beta_cohort", json.dumps({"limit": 10}), ctx)

    assert out["ok"] is True, out
    assert out["data"]["organizations"] == 2
    assert {"organization_id", "lifecycle_state", "open_tickets"} <= set(
        out["data"]["rows"][0])
    assert out["data"]["filters"]["limit"] == 10


def _membership(*, entity, org_id, user_id, role):
    from foundation.models import Membership

    return Membership(id=entity, organization_id=org_id, user_id=user_id, role=role)


def _seed_second_org(foundation):
    from foundation.models import Organization

    foundation.repos.organizations.add(Organization(name="Second Org", slug="second-org"))


# ── identity is verified, never accepted from the model ─────────────────────

@pytest.mark.parametrize("tool,args", [
    ("onboarding_status", {}),
    ("submit_support_ticket", {"category": "bug", "severity": "low",
                               "subject": "Something", "description": "Something broke."}),
    ("beta_cohort", {}),
])
def test_a_tool_without_a_verified_identity_is_refused(foundation, tool, args):
    _org_id, ctx = _seed(foundation)
    ctx.pop("identity")

    out = chat_tools.run_tool(tool, json.dumps(args), ctx)

    assert out["ok"] is False
    assert "no Foundation user" in out["error"]


def test_an_identity_supplied_as_an_argument_is_dropped_not_trusted(foundation):
    _org_id, ctx = _seed(foundation, role="operator")
    ctx.pop("identity")

    out = chat_tools.run_tool("beta_cohort", json.dumps({
        "user_id": "u-1", "organization_id": ctx["account_id"], "role": "internal_platform_admin",
    }), ctx)

    assert out["ok"] is False, "an argument must never grant a role"
    assert "no Foundation user" in out["error"]


def test_a_membership_in_another_org_grants_nothing(foundation):
    _org_id, ctx = _seed(foundation, role="operator")
    ctx["identity"]["tenant_id"] = "org-not-a-member"

    out = chat_tools.run_tool("onboarding_status", "{}", ctx)

    assert out["ok"] is False
    assert "no active membership" in out["error"]


# ── the turn actually hands the verified session to the tool ────────────────

class _FakeLayer:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)
        self.chat = data_layer.ChatContainer(_FakeLayer(self.conn))


def test_the_turn_passes_the_verified_session_into_the_tool_context(monkeypatch):
    db = _FakeDB()
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "New chat"})
    session = db.chat.sessions.get_by_id(sid, account_id="acct-1")
    seen = {}

    def fake_handler(args, ctx):
        seen["identity"] = (ctx or {}).get("identity")
        seen["account_id"] = (ctx or {}).get("account_id")
        return {"ok": True, "summary": "captured", "data": {}, "assets": []}

    monkeypatch.setitem(chat_tools.TOOLS["onboarding_status"], "handler", fake_handler)
    identity = {"id": "u-1", "tenant_id": "org-1", "role": "operator",
                "source": "foundation_session_cookie"}
    rounds = [
        [{"type": "tool_call",
          "call": {"index": 0, "function": {"name": "onboarding_status", "arguments": "{}"}}},
         {"type": "done", "cancelled": False, "usage": None}],
        [{"type": "content", "delta": "done"},
         {"type": "done", "cancelled": False, "usage": None}],
    ]

    def provider(round_idx, _messages):
        return iter(rounds[round_idx] if round_idx < len(rounds) else [])

    list(chat_router.turn_event_stream(
        db, "acct-1", session, "what is left in onboarding?",
        events=provider, tools_enabled=True, identity=identity))

    assert seen["identity"] == identity
    assert seen["account_id"] == "acct-1"
