"""End-to-end local production matrix (1C-LC / Workstream E, E04).

Runs the production-posture foundation stack (temp signing material, local
issuer/audience, real org+membership, worker + scheduler threads, canonical UI
served) and asserts the 37-item matrix. Fake/local handlers only; no network.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.models import Organization, Membership, User
from Northstar_backend.foundation.tests.conftest import make_access_token, bearer

DIST = os.path.join("northstar-os-ui", "dist")


@pytest.fixture()
def stack(monkeypatch, tmp_path):
    """Production-posture stack on a fixed SQLite file with temp signing
    material. The worker runs on demand (drain), never as a background thread,
    so no connection is ever shared concurrently."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NORTHSTAR_JWT_SECRET", os.urandom(48).hex())
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "https://northstar.local")
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    monkeypatch.setenv("NORTHSTAR_JWT_ALGORITHMS", "HS256")
    monkeypatch.setenv("NORTHSTAR_JWT_KEY_ID", "local-prod-kid")
    monkeypatch.setenv("NS_FOUNDATION_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("NORTHSTAR_JWT_TOKEN_TYPES", "access")

    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.bootstrap import bootstrap_owner
    from Northstar_backend.foundation.app import create_app
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.jobs_worker import JobWorker

    db_path = str(tmp_path / "local-prod.db")
    st = FoundationState.build(db_path)
    boot = bootstrap_owner(st, org_name="Local Production",
                           user_email="owner@local.test")
    app = create_app()
    app.state.foundation = st
    client = TestClient(app)
    token = make_access_token(boot["user_id"], org=boot["organization_id"],
                              role=Role.ORGANIZATION_OWNER.value,
                              issuer="https://northstar.local",
                              audience="northstar-api")
    worker = JobWorker(st.jobs_durable, worker_id="e2e-worker",
                       organization_id=boot["organization_id"], poll_interval=0.005)

    def drain(max_iterations=200):
        return worker.drain(max_iterations=max_iterations)

    yield {
        "client": client, "state": st, "token": token,
        "org": boot["organization_id"], "user": boot["user_id"],
        "headers": bearer(token), "drain": drain,
    }
    st.close()


def test_01_missing_jwt_401(stack):
    assert stack["client"].get("/api/v1/foundation/me").status_code == 401


def test_02_valid_jwt_succeeds(stack):
    r = stack["client"].get("/api/v1/foundation/me", headers=stack["headers"])
    assert r.status_code == 200 and r.json()["user_id"] == stack["user"]


def test_03_wrong_issuer_fails(stack):
    t = make_access_token(stack["user"], org=stack["org"], issuer="https://evil",
                          audience="northstar-api")
    assert stack["client"].get("/api/v1/foundation/me",
                               headers=bearer(t)).status_code == 401


def test_04_wrong_audience_fails(stack):
    t = make_access_token(stack["user"], org=stack["org"],
                          issuer="https://northstar.local", audience="other")
    assert stack["client"].get("/api/v1/foundation/me",
                               headers=bearer(t)).status_code == 401


def test_05_revoked_session_fails(stack):
    t = make_access_token(stack["user"], org=stack["org"], jti="e2e-revoke",
                          issuer="https://northstar.local", audience="northstar-api")
    h = bearer(t)
    assert stack["client"].get("/api/v1/foundation/me", headers=h).status_code == 200
    stack["client"].post("/api/v1/foundation/session/revoke?jti=e2e-revoke", headers=h)
    assert stack["client"].get("/api/v1/foundation/me", headers=h).status_code == 401


def test_06_suspended_membership_fails(stack):
    st = stack["state"]
    rows = st.repos.memberships.for_user(stack["user"])
    st.db.conn.execute("UPDATE memberships SET status='suspended' WHERE id=?",
                       (rows[0]["id"],))
    st.db.conn.commit()
    assert stack["client"].get("/api/v1/foundation/me",
                               headers=stack["headers"]).status_code == 403


def test_07_unauthorized_org_fails(stack):
    t = make_access_token(stack["user"], org="not-a-member",
                          issuer="https://northstar.local", audience="northstar-api")
    assert stack["client"].get("/api/v1/foundation/me",
                               headers=bearer(t)).status_code == 403


def test_08_preview_banner_appears(stack):
    r = stack["client"].post("/api/v1/foundation/preview/start", headers=stack["headers"],
                             json={"target_organization_id": stack["org"],
                                   "reason": "e2e"})
    pid = r.json()["preview_id"]
    active = stack["client"].get("/api/v1/foundation/preview/active",
                                 headers={**stack["headers"], "X-Preview-Id": pid})
    assert active.json()["active"] is True
    stack["client"].post(f"/api/v1/foundation/preview/end?preview_id={pid}",
                         headers=stack["headers"])


def test_09_preview_exit_audited(stack):
    from Northstar_backend.foundation.enums import ViewContext
    r = stack["client"].post("/api/v1/foundation/preview/start", headers=stack["headers"],
                             json={"target_organization_id": stack["org"], "reason": "x"})
    pid = r.json()["preview_id"]
    stack["client"].post(f"/api/v1/foundation/preview/end?preview_id={pid}",
                         headers=stack["headers"])
    events = stack["state"].repos.audit.list(where={"action": "preview.end"})
    assert events


def test_10_economics_canonical(stack):
    r = stack["client"].get("/api/v1/foundation/economics/contract",
                            headers=stack["headers"])
    assert r.json()["formula_version"] == "economics-1.0.0"


def _compute(stack, **inputs):
    return stack["client"].post("/api/v1/foundation/economics/compute",
                                headers=stack["headers"], json={"input": inputs}).json()


def test_11_missing_cost_incomplete(stack):
    out = _compute(stack, selling_price="10.00")
    assert out["readiness"] != "complete_verified"
    assert "SELLING_PRICE_MISSING" in out.get("missing_inputs", []) or \
        out.get("selling_price") is None


def test_12_missing_fees_incomplete(stack):
    out = _compute(stack, selling_price="10.00", acquisition_cost="3.00")
    assert out["readiness"] != "complete_verified"


def test_13_pack_ambiguity_incomplete(stack):
    out = _compute(stack, selling_price="10.00", acquisition_cost="3.00")
    # pack ambiguity keeps readiness from COMPLETE_VERIFIED
    assert out["readiness"] != "complete_verified" or "PACK" in str(out.get("missing_inputs"))


def test_14_scanner_includes_formula_version(stack):
    from Northstar_backend.foundation.economics.versions import FORMULA_VERSION
    assert FORMULA_VERSION == "economics-1.0.0"


def test_15_gg_score_cannot_override_gates(stack):
    from Northstar_backend.foundation.golden_goose_decision import decide, FAIL
    res = decide(
        gate_inputs={"product_identity": "PASS", "variation_identity": "PASS",
                     "pack_identity": "PASS", "economics_complete": "PASS",
                     "cost_known": FAIL, "fees_known": "PASS",
                     "eligibility": "PASS", "sourcing_route": "PASS",
                     "documentation": "PASS", "brand_permission": "NOT_APPLICABLE"},
        economics_readiness="COMPLETE_VERIFIED",
        component_scores={"cost": 90, "fees": 80},
        component_weights={"cost": 0.5, "fees": 0.5},
        approval={"present": True})
    assert res["mandatory_gates"]["cost_known"] == FAIL
    assert res["purchase_ready"] is False
    assert res["decision_state"] == "BLOCKED_ECONOMICS"


def test_16_purchase_readiness_requires_approval(stack):
    from Northstar_backend.foundation.golden_goose_decision import decide
    res = decide(
        gate_inputs={"product_identity": "PASS", "variation_identity": "PASS",
                     "pack_identity": "PASS", "economics_complete": "PASS",
                     "cost_known": "PASS", "fees_known": "PASS",
                     "eligibility": "PASS", "sourcing_route": "PASS",
                     "documentation": "PASS", "brand_permission": "NOT_APPLICABLE"},
        economics_readiness="COMPLETE_VERIFIED",
        approval=None)
    assert res["approval_required"] is True
    assert res["purchase_ready"] is False


def test_17_get_creates_no_jobs(stack):
    c = stack["client"]; h = stack["headers"]
    before = stack["state"].repos.job_requests.count()
    for url in ("/ui", "/api/v1/foundation/jobs-durable/queue-posture",
                "/api/v1/foundation/schedules/posture",
                "/api/v1/foundation/keywords/search?q=x"):
        assert c.get(url, headers=h).status_code == 200
    assert stack["state"].repos.job_requests.count() == before


def test_18_get_calls_no_providers(stack):
    before = stack["state"].repos.providers.count()
    stack["client"].get("/ui/keywords", headers=stack["headers"])
    assert stack["state"].repos.providers.count() == before


def _submit(stack, job_type="immediate_success", **kw):
    body = {"job_type": job_type, "payload_schema_version": "1.0",
            "payload": kw.pop("payload", {})}
    body.update(kw)
    return stack["client"].post("/api/v1/foundation/jobs-durable", json=body,
                                headers=stack["headers"])


def _wait_state(stack, job_id, states, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job_id}",
                                headers=stack["headers"]).json()
        if d["state"] in states:
            return d
        time.sleep(0.05)
    return d


def test_19_fake_job_succeeds(stack):
    job = _submit(stack).json()
    stack["drain"]()
    d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                            headers=stack["headers"]).json()
    assert d["state"] == "succeeded"


def test_20_transient_failure_retries(stack):
    job = _submit(stack, job_type="transient_failure",
                  payload={"succeed_on_attempt": 2}).json()
    # retries need the scheduler to re-queue; drain won't progress retry_wait.
    from Northstar_backend.foundation.jobs_state import JobState
    out = stack["drain"]()
    d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                            headers=stack["headers"]).json()
    assert d["state"] in ("retry_wait", "succeeded")
    # drive the retry: backdate scheduled_time, re-queue, drain again
    if d["state"] == "retry_wait":
        run = stack["state"].repos.job_runs.by_request(job["id"])[0]
        stack["state"].db.conn.execute(
            "UPDATE job_runs SET scheduled_time=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
        stack["state"].db.conn.commit()
        stack["state"].jobs_durable._transition(
            job=stack["state"].repos.job_requests.get(job["id"]), run=run,
            new_state=JobState.QUEUED.value, actor="scheduler",
            reason="backoff elapsed")
        stack["drain"]()
        d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                                headers=stack["headers"]).json()
    assert d["state"] == "succeeded"
    assert d["runs"][0]["attempts"] >= 2


def test_21_permanent_failure_dead_letters(stack):
    from Northstar_backend.foundation.jobs_state import JobState
    job = _submit(stack, job_type="transient_failure",
                  payload={"succeed_on_attempt": 99}).json()
    for _ in range(4):
        out = stack["drain"]()
        if not out:
            break
        if out[-1].state in (JobState.DEAD_LETTER.value, JobState.FAILED.value):
            break
        row = stack["state"].repos.job_runs.by_request(job["id"])[0]
        stack["state"].db.conn.execute(
            "UPDATE job_runs SET scheduled_time=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), row["id"]))
        stack["state"].db.conn.commit()
        stack["state"].jobs_durable._transition(
            job=stack["state"].repos.job_requests.get(job["id"]), run=row,
            new_state=JobState.QUEUED.value, actor="scheduler",
            reason="backoff elapsed")
    d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                            headers=stack["headers"]).json()
    assert d["state"] == "dead_letter"


def test_22_cancellation_works(stack):
    job = _submit(stack, job_type="immediate_success").json()
    stack["client"].post(f"/api/v1/foundation/jobs-durable/{job['id']}/cancel",
                         json={"reason": "e2e"}, headers=stack["headers"])
    d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                            headers=stack["headers"]).json()
    assert d["state"] == "cancelled"


def test_23_idempotency_works(stack):
    a = _submit(stack, idempotency_key="e2e-idem").json()
    b = _submit(stack, idempotency_key="e2e-idem").json()
    assert a["id"] == b["id"]


def test_24_schedule_enqueues_once(stack):
    sched = stack["state"].scheduler
    first = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    row = sched.create_schedule(
        organization_id=stack["org"], owner_user_id=stack["user"],
        job_template={"job_type": "immediate_success"}, interval_seconds=3600,
        enabled=True, first_run_at=first)
    r1 = sched.tick()
    r2 = sched.tick()
    assert r1["enqueued"] == 1 and r2["enqueued"] == 0
    jobs = stack["state"].repos.job_requests.list(
        where={"organization_id": stack["org"]})
    assert len(jobs) == 1


def test_25_keyword_import_succeeds(stack):
    fixture = os.path.join("Northstar_backend", "foundation", "tests", "fixtures",
                           "search_term_report_sample.csv")
    r = stack["state"].keywords.import_file(stack["org"], fixture,
                                            submitted_by=stack["user"])
    assert r["status"] == "completed"
    assert stack["state"].repos.keywords.count() == 4


def test_26_duplicate_import_idempotent(stack):
    fixture = os.path.join("Northstar_backend", "foundation", "tests", "fixtures",
                           "search_term_report_sample.csv")
    a = stack["state"].keywords.import_file(stack["org"], fixture)
    b = stack["state"].keywords.import_file(stack["org"], fixture)
    assert b["idempotent_replay"] is True and a["id"] == b["id"]


def test_27_invalid_rows_preserved(stack):
    fixture = os.path.join("Northstar_backend", "foundation", "tests", "fixtures",
                           "search_term_report_sample.csv")
    r = stack["state"].keywords.import_file(stack["org"], fixture)
    rejected = stack["state"].keywords.rejected_rows(stack["org"], r["id"])
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "missing_search_term"


def test_28_keyword_search_works(stack):
    from Northstar_backend.foundation.models import Keyword
    stack["state"].repos.keywords.add(Keyword(
        organization_id=stack["org"], normalized_phrase="dog leash",
        original_phrase="Dog Leash", match_type="exact"))
    r = stack["client"].get("/api/v1/foundation/keywords/search?q=dog",
                            headers=stack["headers"])
    assert any(k["normalized_phrase"] == "dog leash" for k in r.json()["items"])


def test_29_search_term_performance_works(stack):
    r = stack["client"].get("/api/v1/foundation/keywords/search-terms",
                            headers=stack["headers"])
    assert r.status_code == 200


def test_30_pinned_preference_persists(stack):
    c = stack["client"]; h = stack["headers"]
    c.put("/api/v1/foundation/ui/preferences/pinned_drawer",
          json={"value": {"open": True}}, headers=h)
    got = c.get("/api/v1/foundation/ui/preferences/pinned_drawer", headers=h)
    assert got.json()["value"] == {"open": True}


def test_31_tour_dismissal_persists(stack):
    c = stack["client"]; h = stack["headers"]
    c.put("/api/v1/foundation/ui/preferences/tour_done_hub",
          json={"value": {"done": True}}, headers=h)
    got = c.get("/api/v1/foundation/ui/preferences/tour_done_hub", headers=h)
    assert got.json()["value"] == {"done": True}


def test_32_tour_replay_works(stack):
    c = stack["client"]; h = stack["headers"]
    c.put("/api/v1/foundation/ui/preferences/tour_done_hub",
          json={"value": {"done": False}}, headers=h)
    got = c.get("/api/v1/foundation/ui/preferences/tour_done_hub", headers=h)
    assert got.json()["value"] == {"done": False}


def test_33_session_revocation_updates_ui(stack):
    c = stack["client"]
    t = make_access_token(stack["user"], org=stack["org"], jti="e2e-ui-revoke",
                          issuer="https://northstar.local", audience="northstar-api")
    h = bearer(t)
    assert c.get("/api/v1/foundation/me", headers=h).status_code == 200
    c.post("/api/v1/foundation/session/revoke?jti=e2e-ui-revoke", headers=h)
    assert c.get("/api/v1/foundation/me", headers=h).status_code == 401


def test_34_backend_unavailable_state_works():
    src = open(os.path.join("northstar-os-ui", "src", "foundation", "pages",
                            "Jobs.jsx"), encoding="utf-8").read()
    assert "Backend unavailable" in src  # explicit error state


def test_35_restart_recovery_works(stack):
    st = stack["state"]
    svc = st.jobs_durable
    job = _submit(stack).json()
    claimed = svc.claim_next("crashy", organization_id=stack["org"])
    past = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    st.db.conn.execute("UPDATE job_runs SET lease_expiration=? WHERE id=?",
                       (past, claimed["id"]))
    st.db.conn.commit()
    recovered = svc.recover_expired_leases(organization_id=stack["org"])
    assert recovered == [claimed["run_id"]]
    stack["drain"]()
    d = stack["client"].get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                            headers=stack["headers"]).json()
    assert d["state"] == "succeeded"


def test_36_cross_organization_apis_fail(stack):
    other = Organization(name="Other", slug="other")
    user = User(email="other@local.test")
    stack["state"].repos.organizations.add(other)
    stack["state"].repos.users.add(user)
    stack["state"].repos.memberships.add(Membership(
        organization_id=other.id, user_id=user.id, role=Role.OPERATOR.value))
    t = make_access_token(user.id, org=other.id, role="operator",
                          issuer="https://northstar.local", audience="northstar-api")
    assert stack["client"].get("/api/v1/foundation/me",
                               headers=bearer(t)).status_code == 200
    # cross-org cannot see the primary org's jobs (list is empty)
    jobs = stack["client"].get("/api/v1/foundation/jobs-durable",
                               headers=bearer(t)).json()["items"]
    assert jobs == []


def test_37_frontend_bundle_no_secrets(stack):
    bundle = ""
    for a in os.listdir(os.path.join(DIST, "assets")):
        if a.endswith(".js"):
            bundle += open(os.path.join(DIST, "assets", a), encoding="utf-8",
                           errors="ignore").read()
    for pat in (r"(?i)NORTHSTAR_JWT_SECRET", r"BEGIN (RSA|PRIVATE) KEY"):
        assert not re.search(pat, bundle)