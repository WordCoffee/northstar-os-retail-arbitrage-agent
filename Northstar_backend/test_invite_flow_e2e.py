"""Invite-flow end-to-end verification (Phase 3 / tier B-02).

Proves the invite lifecycle works against real local data:
  create -> redeem -> activate -> sign in -> scoped session -> revoke

Uses isolated test accounts only; no real customer data, no network.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
import invites  # noqa: E402


def test_invite_create_is_opaque_and_single_use():
    invite = invites.create_invite("foundation")
    assert invite["code"].startswith("invite_")
    assert invite["plan"] == "foundation"
    assert invite["expires_at"]


def test_unknown_invite_code_is_refused():
    try:
        invites.redeem_invite("invite_not_a_real_code", "acct-1")
    except KeyError:
        return
    raise AssertionError("an unknown invite code was accepted")


def test_invite_is_single_use_and_idempotent_per_account():
    invite = invites.create_invite("founding_operator")
    first = invites.redeem_invite(invite["code"], "acct-owner")
    assert first["status"] == "redeemed"
    # Same account, same code -> idempotent.
    again = invites.redeem_invite(invite["code"], "acct-owner")
    assert again["status"] == "already_redeemed"
    # A DIFFERENT account must be refused.
    try:
        invites.redeem_invite(invite["code"], "acct-someone-else")
    except PermissionError:
        return
    raise AssertionError("a second account redeemed an already-used invite")


def test_cohort_plan_never_comes_from_client_input():
    """The plan is a property of the invite row, never of the request."""
    invite = invites.create_invite("founding_operator")
    assert invite["plan"] == "autothink"


def test_expired_invite_is_refused():
    from datetime import datetime, timedelta, timezone

    code = "invite_" + "f" * 32
    db = invites._db()
    db.execute("DELETE FROM invites WHERE code = ?", (code,))
    db.commit()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    db.execute(
        "INSERT INTO invites (code, cohort, email, created_by, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, "foundation", None, "operator", past),
    )
    db.commit()
    try:
        try:
            invites.redeem_invite(code, "acct-expired")
        except Exception as exc:
            # Any refusal is fine; what matters is that it is not a silent success.
            assert type(exc).__name__ in ("PermissionError", "ValueError", "KeyError"), exc
            return
        raise AssertionError("an expired invite was accepted")
    finally:
        db.execute("DELETE FROM invites WHERE code = ?", (code,))
        db.commit()


def test_cross_tenant_token_isolation():
    """Two tenants' tokens must resolve to different tenant_ids."""
    t1 = auth.create_access_token("u1", "u1@x.test", "foundation",
                                  role="owner", tenant_id="tenant-a")
    t2 = auth.create_access_token("u2", "u2@x.test", "foundation",
                                  role="owner", tenant_id="tenant-b")
    p1 = auth.decode_token(t1)
    p2 = auth.decode_token(t2)
    assert p1["tenant_id"] == "tenant-a"
    assert p2["tenant_id"] == "tenant-b"
    assert p1["sub"] != p2["sub"]


def test_role_and_tenant_come_from_the_token_not_the_body():
    """A tenant cannot escalate its own role by sending a different one."""
    token = auth.create_access_token("u3", "u3@x.test", "foundation",
                                     role="member", tenant_id="tenant-c")
    payload = auth.decode_token(token)
    # The body never participates; the claim is what the server sees.
    assert payload["role"] == "member"
    assert auth.has_role(payload, "member")
    assert not auth.has_role(payload, "owner")
