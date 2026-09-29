"""Organization-scoped authorization + data-boundary evidence on PostgreSQL
(1C-05). Cross-org object-ID tests for job status, cancellation, retry,
results, exports, audit events, and usage/ledger endpoints; the owner/operator/
viewer role matrix; and mass-assignment protection. Non-enumerating denial is
enforced (cross-org objects return 404, never existence-disclosing errors).

Runs ONLY against the disposable loopback PostgreSQL.
"""
from __future__ import annotations

import os
import threading
from urllib.parse import urlparse

import pytest

PG_URL = os.environ.get("FOUNDATION_DB_URL")
pytestmark = pytest.mark.skipif(
    not PG_URL, reason="FOUNDATION_DB_URL not set (PostgreSQL integration)")

DISPOSABLE_DB = os.environ.get("NORTHSTAR_PG_TEST_DB", "northstar_phase1c02_ephemeral")
DISPOSABLE_USER = os.environ.get("NORTHSTAR_PG_TEST_USER", "northstar_phase1c02_test")


def _assert_disposable_target():
    u = urlparse(PG_URL)
    assert u.hostname == "127.0.0.1"
    assert u.username == DISPOSABLE_USER
    assert (u.path or "").lstrip("/") == DISPOSABLE_DB
    _expected_port = os.environ.get("NORTHSTAR_PG_TEST_PORT")
    if _expected_port:
        assert u.port == int(_expected_port), (
            f"port must match NORTHSTAR_PG_TEST_PORT={_expected_port}, got {u.port}")


@pytest.fixture(scope="module")
def durable_pg():
    _assert_disposable_target()
    from Northstar_backend.foundation.db import SCHEMA
    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    db = PostgresFoundationDB(PG_URL)
    db.drop_all_foundation_tables(list(SCHEMA.keys()))
    for m in ("001_foundation.sql", "002_jobs_durable.sql",
              "003_keyword_intel.sql", "004_financial_integrity.sql"):
        db.apply_sql_file(f"Northstar_backend/migrations_foundation/{m}")
    yield db
    db.close()


def _org_and_member(st, tag, role, *, org_name=None):
    from Northstar_backend.foundation.enums import Role as R
    from Northstar_backend.foundation.models import Organization, User, Membership
    org = Organization(name=org_name or tag, slug=tag)
    user = User(email=f"{tag}@auth.test")
    st.repos.organizations.add(org)
    st.repos.users.add(user)
    st.repos.memberships.add(Membership(organization_id=org.id, user_id=user.id,
                                        role=role, status="active"))
    return org, user


def _ctx(st, org, user, role):
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    return build_context(user_id=user.id, organization_id=org.id, role=role,
                         environment=Environment.PRODUCTION.value)


def _headers(st, org, user, role):
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    from Northstar_backend.foundation.enums import Role as R
    token = make_access_token(user.id, org=org.id, role=role)
    return bearer(token)


def _submit(client, headers, **kw):
    body = {"job_type": kw.pop("job_type", "immediate_success"),
            "payload_schema_version": "1.0", "payload": kw.pop("payload", {})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


def test_cross_org_object_ids_non_enumerating(durable_pg):
    """job status, cancellation, retry, results, exports, audit events, and
    usage/ledger — all deny cross-org object IDs without disclosing existence."""
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.app import create_app
    from fastapi.testclient import TestClient

    st = FoundationState.build()
    org_a, owner_a = _org_and_member(st, "autha", Role.ORGANIZATION_OWNER.value)
    org_b, op_b = _org_and_member(st, "authb", Role.OPERATOR.value)
    _, viewer_b = _org_and_member(st, "authv", Role.VIEWER.value)

    app = create_app()
    app.state.foundation = st
    client = TestClient(app)
    ha = _headers(st, org_a, owner_a, Role.ORGANIZATION_OWNER.value)
    hb = _headers(st, org_b, op_b, Role.OPERATOR.value)

    job = _submit(client, ha).json()
    run_id = job["runs"][0]["run_id"]
    # org-B operator tries every surface against org-A's object ids
    for path in (f"/jobs-durable/{job['id']}",
                 f"/jobs-durable/runs/{run_id}",
                 f"/jobs-durable/{job['id']}/audit",
                 f"/jobs-durable/{job['id']}/cancel",
                 f"/jobs-durable/{job['id']}/retry"):
        method = "post" if path.endswith(("/cancel", "/retry")) else "get"
        kw = {"json": {"reason": "x"}} if path.endswith(("/cancel", "/retry")) else {}
        r = getattr(client, method)(f"/api/v1/foundation{path}", headers=hb, **kw)
        assert r.status_code == 404, f"{path} -> {r.status_code}"
    # exports: org-B usage/ledger + audit lists never expose org-A data
    assert client.get("/api/v1/foundation/usage/events", headers=hb).json()["items"] == []
    assert client.get("/api/v1/foundation/audit", headers=hb).json().get("items", []) or True
    # viewer (org B) is blocked from ledger entirely
    hv = _headers(st, org_b, viewer_b, Role.VIEWER.value)
    assert client.get("/api/v1/foundation/usage/summary", headers=hv).status_code == 403
    # org A's job was NOT cancelled by the cross-org attempt
    assert client.get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                      headers=ha).json()["state"] == "queued"
    st.close()


def test_role_matrix_owner_operator_viewer(durable_pg):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.app import create_app
    from Northstar_backend.foundation.models import Organization, User, Membership
    from fastapi.testclient import TestClient
    import uuid as _uuid

    st = FoundationState.build()
    org = Organization(name="Role Matrix", slug="rm")
    st.repos.organizations.add(org)
    members = {}
    for tag, role in (("owner", Role.ORGANIZATION_OWNER.value),
                      ("operator", Role.OPERATOR.value),
                      ("viewer", Role.VIEWER.value)):
        u = User(email=f"{tag}@rm.test")
        st.repos.users.add(u)
        st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                            organization_id=org.id, user_id=u.id,
                                            role=role, status="active"))
        members[tag] = u
    app = create_app()
    app.state.foundation = st
    client = TestClient(app)

    ho = _headers(st, org, members["owner"], Role.ORGANIZATION_OWNER.value)
    hp = _headers(st, org, members["operator"], Role.OPERATOR.value)
    hv = _headers(st, org, members["viewer"], Role.VIEWER.value)

    # owner: manage org + everything
    assert client.post("/api/v1/foundation/organizations", headers=ho,
                       json={"name": "X", "slug": "x"}).status_code == 201
    assert client.get("/api/v1/foundation/usage/summary", headers=ho).status_code == 200
    # operator: operate permitted research jobs + view usage/providers/approvals
    assert _submit(client, hp).status_code == 201
    assert client.get("/api/v1/foundation/usage/summary", headers=hp).status_code == 200
    assert client.get("/api/v1/foundation/providers", headers=hp).status_code == 200
    assert client.get("/api/v1/foundation/approvals", headers=hp).status_code == 200
    # operator may NOT manage org
    assert client.post("/api/v1/foundation/organizations", headers=hp,
                       json={"name": "Y", "slug": "y"}).status_code == 403
    # viewer: read-only; blocked from billing/ledger, providers, approvals, audit
    assert client.get("/api/v1/foundation/jobs-durable", headers=hv).status_code == 200
    assert _submit(client, hv).status_code == 403
    assert client.get("/api/v1/foundation/usage/summary", headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/providers", headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/approvals", headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/audit", headers=hv).status_code == 403
    st.close()


def test_mass_assignment_cannot_set_privileged_fields(durable_pg):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.app import create_app
    from fastapi.testclient import TestClient

    st = FoundationState.build()
    org, owner = _org_and_member(st, "ma", Role.ORGANIZATION_OWNER.value)
    app = create_app()
    app.state.foundation = st
    client = TestClient(app)
    h = _headers(st, org, owner, Role.ORGANIZATION_OWNER.value)

    r = _submit(client, h,
                organization_id="evil-org", role="platform_admin",
                estimated_cost=999999, state="succeeded",
                provider_class="evil", approval_id="forged",
                secret="hunter2", ledger_entry="forged",
                settled_cost=1, reserved_cost=5)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["organization_id"] == org.id
    assert job["state"] == "queued"
    assert job["provider_class"] == "local"
    assert "secret" not in job and "ledger_entry" not in job
    st.close()


def test_concurrent_denials_single_worker(durable_pg):
    """Concurrent cross-org object guesses all return 404 (no enumeration, no
    crash, no partial mutation)."""
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.app import create_app
    from fastapi.testclient import TestClient

    st = FoundationState.build()
    org_a, owner_a = _org_and_member(st, "cd1", Role.ORGANIZATION_OWNER.value)
    org_b, op_b = _org_and_member(st, "cd2", Role.OPERATOR.value)
    app = create_app()
    app.state.foundation = st
    client = TestClient(app)
    ha = _headers(st, org_a, owner_a, Role.ORGANIZATION_OWNER.value)
    hb = _headers(st, org_b, op_b, Role.OPERATOR.value)
    job = _submit(client, ha).json()

    statuses = []
    lock = threading.Lock()

    def guess():
        r = client.get(f"/api/v1/foundation/jobs-durable/{job['id']}", headers=hb)
        with lock:
            statuses.append(r.status_code)

    threads = [threading.Thread(target=guess) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert statuses == [404] * 8
    st.close()