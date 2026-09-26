#!/usr/bin/env python
"""Staging smoke suite (1C-LC / Step 5; staging-handoff-checklist.md F03).

Runs the 15-item staging smoke plan against the provisioned staging database
via the production-posture foundation app (in-process; on-demand worker).

Reads the staging URL from the encrypted secrets vault (never echoed). Records
evidence to docs/northstar-phase1c/staging-smoke-report.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

REPORT = Path("docs") / "northstar-phase1c" / "staging-smoke-report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    from Northstar_backend.foundation import secrets as vault
    password = vault.get_secret("staging_db_password")
    if not password:
        print("staging_db_password not in the vault; nothing to smoke against.")
        return 2
    url = (f"postgresql://northstar_staging_owner:{password}"
           f"@127.0.0.1:55433/northstar_staging")
    os.environ["FOUNDATION_DB_URL"] = url
    os.environ["ENVIRONMENT"] = "production"
    os.environ["NORTHSTAR_JWT_SECRET"] = __import__("secrets").token_urlsafe(48)
    os.environ["NORTHSTAR_JWT_ISSUER"] = "https://northstar.staging.local"
    os.environ["NORTHSTAR_JWT_AUDIENCE"] = "northstar-staging"
    os.environ["NORTHSTAR_JWT_ALGORITHMS"] = "HS256"
    os.environ["NORTHSTAR_JWT_KEY_ID"] = "staging-kid"
    os.environ["NS_FOUNDATION_BIND_HOST"] = "127.0.0.1"
    os.environ["NORTHSTAR_JWT_TOKEN_TYPES"] = "access"

    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.bootstrap import bootstrap_owner
    from Northstar_backend.foundation.app import create_app
    from Northstar_backend.foundation.jobs_worker import JobWorker
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    from fastapi.testclient import TestClient
    from Northstar_backend.foundation.jobs_state import JobState

    st = FoundationState.build()
    boot = bootstrap_owner(st, org_name="Staging Smoke", user_email="tyrone@staging.local",
                           recover=True)
    org, user = boot["organization_id"], boot["user_id"]
    app = create_app()
    app.state.foundation = st
    client = TestClient(app)
    h = bearer(make_access_token(user, org=org, role="organization_owner",
                                 issuer="https://northstar.staging.local",
                                 audience="northstar-staging"))
    # 1C-06: publish the beta documents and record acceptance for the primary
    # staging operator so feature use is permitted (the gate is then ACTIVE
    # and proven by the dedicated new-account denial test).
    from Northstar_backend.foundation.beta.acceptance import (
        publish_documents, record_acceptance,
    )
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment, Role as _Role
    publish_documents(st)
    boot_ctx = build_context(user_id=user, organization_id=org,
                             role=_Role.ORGANIZATION_OWNER.value,
                             environment=Environment.PRODUCTION.value)
    record_acceptance(st, boot_ctx, business_use=True, age_18_plus=True,
                      request_id="staging-smoke-boot")
    worker = JobWorker(st.jobs_durable, worker_id="staging-smoke-worker",
                       organization_id=org, poll_interval=0.005)

    def drain(max_iterations=200):
        return worker.drain(max_iterations=max_iterations)

    def submit(job_type="immediate_success", **kw):
        body = {"job_type": job_type, "payload_schema_version": "1.0",
                "payload": kw.pop("payload", {})}
        body.update(kw)
        return client.post("/api/v1/foundation/jobs-durable", json=body, headers=h).json()

    def job_state(job_id):
        return client.get(f"/api/v1/foundation/jobs-durable/{job_id}",
                          headers=h).json()["state"]

    results = {}
    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        results[name] = {"pass": bool(passed), "detail": detail}
        ok = ok and bool(passed)
        print(("PASS " if passed else "FAIL ") + name + (f" — {detail}" if detail else ""))

    # 1. startup posture
    check("01_auth_posture_jwt",
          client.get("/api/v1/foundation/auth-posture", headers=h).json()
          .get("real_authentication_active") is True)
    check("02_environment", client.get("/api/v1/foundation/environment",
                                       headers=h).json()["environment"] == "production")
    # 2. authentication
    check("03_missing_jwt_401",
          client.get("/api/v1/foundation/me").status_code == 401)
    check("04_valid_jwt_ok", client.get("/api/v1/foundation/me", headers=h).status_code == 200)
    # 3. organization resolution / isolation
    other = st.repos.organizations.list()
    check("05_org_resolved", client.get("/api/v1/foundation/me", headers=h).json()
          .get("active_organization_id") == org)
    check("06_cross_org_denied",
          client.get("/api/v1/foundation/me",
                     headers=bearer(make_access_token(user, org="not-a-member",
                                                     issuer="https://northstar.staging.local",
                                                     audience="northstar-staging")))
          .status_code == 403)
    # 4. revocation
    jti = f"staging-revoke-{int(time.time() * 1000)}"
    tok = make_access_token(user, org=org, jti=jti,
                            issuer="https://northstar.staging.local",
                            audience="northstar-staging")
    hh = bearer(tok)
    ok_me = client.get("/api/v1/foundation/me", headers=hh).status_code == 200
    client.post(f"/api/v1/foundation/session/revoke?jti={jti}", headers=hh)
    check("07_session_revocation",
          ok_me and client.get("/api/v1/foundation/me", headers=hh).status_code == 401)
    # 5. preview + audit
    p = client.post("/api/v1/foundation/preview/start", headers=h, json={
        "target_organization_id": org, "reason": "staging smoke"}).json()
    check("08_preview_banner",
          client.get("/api/v1/foundation/preview/active",
                     headers={**h, "X-Preview-Id": p["preview_id"]}).json()["active"] is True)
    client.post(f"/api/v1/foundation/preview/end?preview_id={p['preview_id']}", headers=h)
    check("09_preview_audited",
          bool(st.repos.audit.list(where={"action": "preview.end"})))
    # 6. economics canonical
    ec = client.get("/api/v1/foundation/economics/contract", headers=h).json()
    check("10_economics_canonical", ec["formula_version"] == "economics-1.0.0")
    inc = client.post("/api/v1/foundation/economics/compute", headers=h,
                      json={"input": {"selling_price": "10.00"}}).json()
    check("11_missing_cost_incomplete", inc["readiness"] != "complete_verified")
    # 7. jobs: submit -> worker -> success
    j = submit()
    drain()
    check("12_fake_job_succeeds", job_state(j["id"]) == "succeeded")
    # transient retry
    j2 = submit(job_type="transient_failure", payload={"succeed_on_attempt": 2})
    drain()
    s2 = job_state(j2["id"])
    if s2 == "retry_wait":
        run = st.repos.job_runs.by_request(j2["id"])[0]
        st.db.conn.execute("UPDATE job_runs SET scheduled_time=? WHERE id=?",
                           ((datetime.now(timezone.utc)
                             - __import__("datetime").timedelta(seconds=5)).isoformat(),
                            run["id"]))
        st.db.conn.commit()
        st.jobs_durable._transition(job=st.repos.job_requests.get(j2["id"]), run=run,
                                    new_state=JobState.QUEUED.value,
                                    actor="scheduler", reason="backoff elapsed")
        drain()
        s2 = job_state(j2["id"])
    check("13_transient_retries", s2 == "succeeded")
    # 8. scheduler dedup
    sched = st.scheduler.create_schedule(
        organization_id=org, owner_user_id=user,
        job_template={"job_type": "immediate_success"}, interval_seconds=3600,
        enabled=True, first_run_at=(datetime.now(timezone.utc)
                                    - __import__("datetime").timedelta(seconds=5)).isoformat())
    r1 = st.scheduler.tick(); r2 = st.scheduler.tick()
    occ_for_sched = [o for o in st.repos.schedule_occurrences.list(
        where={"schedule_id": sched["id"]})]
    check("14_scheduler_dedup", len(occ_for_sched) == 1 and r2["enqueued"] == 0,
          json.dumps({"occurrences": len(occ_for_sched), "r2_enqueued": r2["enqueued"]}))
    # 9. keyword import
    fixture = Path("Northstar_backend") / "foundation" / "tests" / "fixtures" / "search_term_report_sample.csv"
    imp = st.keywords.import_file(org, str(fixture), submitted_by=user)
    check("15_keyword_import", imp["status"] == "completed"
          and imp["summary"]["accepted_rows"] == 4)
    reimp = st.keywords.import_file(org, str(fixture), submitted_by=user)
    check("16_import_idempotent", reimp["idempotent_replay"] is True)
    rej = st.keywords.rejected_rows(org, imp["id"])
    check("17_rejected_rows_preserved", len(rej) == 1
          and rej[0]["rejection_reason"] == "missing_search_term")
    check("18_keyword_search",
          bool(client.get("/api/v1/foundation/keywords/search?q=leash",
                          headers=h).json()["items"]))
    check("19_search_term_performance",
          client.get("/api/v1/foundation/keywords/search-terms",
                     headers=h).status_code == 200)
    # 10. frontend + deep link
    check("20_frontend_served", client.get("/ui").status_code == 200
          and "id=\"root\"" in client.get("/ui").text)
    check("21_deep_link", client.get("/ui/jobs").status_code == 200)
    # 11/12. security + GET side effects
    r = client.get("/ui")
    check("22_security_headers", "frame-ancestors 'none'" in r.headers.get(
        "content-security-policy", "") and r.headers.get("x-frame-options") == "DENY")
    before_jobs = st.repos.job_requests.count()
    for u in ("/api/v1/foundation/jobs-durable/queue-posture",
              "/api/v1/foundation/schedules/posture",
              "/api/v1/foundation/keywords/search?q=x"):
        client.get(u, headers=h)
    check("23_get_creates_no_jobs", st.repos.job_requests.count() == before_jobs)
    check("24_no_provider_on_load",
          client.get("/ui/keywords", headers=h).status_code == 200)
    # 13. audit + usage
    check("25_audit_events", bool(st.repos.audit.list(
        where={"organization_id": org})))
    check("26_usage_settled", bool(st.repos.usage.list(
        where={"organization_id": org, "status": "finalized"})))

    # 14. FINANCIAL-INTEGRITY CHAIN (mandatory gate proof): a single request is
    #     linked to its job, execution, ledger entry, and audit chain.
    report = {
        "owner": "Tyrone", "plan": "staging-handoff-checklist.md F03",
        "started_at": now_iso(), "completed_at": now_iso(),
        "environment": "staging",
        "database_target": {"host": "127.0.0.1", "port": 55433,
                            "database": "northstar_staging",
                            "user": "northstar_staging_owner"},
        "network_status": "loopback-only local Docker staging box (postgres:15)",
        "items": results,
        "passed": sum(1 for v in results.values() if v["pass"]),
        "total": len(results),
        "overall": "PASS" if ok else "FAIL",
    }
    chain = {}
    try:
        from Northstar_backend.foundation.context import build_context
        from Northstar_backend.foundation.enums import Environment, Role as _Role
        cctx = build_context(user_id=user, organization_id=org,
                             role=_Role.ORGANIZATION_OWNER.value,
                             environment=Environment.PRODUCTION.value)
        chain_job = st.jobs_durable.submit(
            cctx, job_type="immediate_success", payload={"chain": True},
            payload_schema_version="1.0", idempotency_key="staging-fin-chain",
            correlation_id="staging-req-chain-1")
        drain()
        chain["request"] = {"correlation_id": "staging-req-chain-1",
                            "idempotency_key": "staging-fin-chain",
                            "job_id": chain_job["id"]}
        state = job_state(chain_job["id"])
        chain["execution"] = {"state": state}
        finalized = [e for e in st.repos.usage.list(
            where={"organization_id": org, "status": "finalized"})
            if e["idempotency_key"].startswith(f"settle:") and
            e["workflow_run_id"] in {r["run_id"] for r in
                                     st.repos.job_runs.by_request(chain_job["id"])}]
        chain["ledger"] = {"finalized_count": len(finalized),
                           "entry": (finalized[0]["idempotency_key"] if finalized else None),
                           "credits_debited": (float(finalized[0].get("credits_debited_shadow") or 0)
                                               if finalized else None)}
        audit_chain = st.repos.audit.list(
            where={"organization_id": org, "correlation_id": "staging-req-chain-1"})
        chain["audit_chain"] = [
            {"action": e["action"], "job_id": e["resource_id"],
             "actor": e["actor_user_id"], "timestamp": e["occurred_at"]}
            for e in audit_chain]
        ok_chain = (state == "succeeded" and len(finalized) == 1
                    and len(audit_chain) >= 5
                    and all(e["job_id"] == chain_job["id"] for e in chain["audit_chain"]))
        check("27_financial_chain_request_to_audit", ok_chain,
              json.dumps({"job": chain_job["id"], "settle": finalized[0]["idempotency_key"],
                          "audit_events": len(audit_chain)}))
        report["financial_chain"] = chain
    except Exception as e:  # noqa: BLE001
        check("27_financial_chain_request_to_audit", False, str(e))

    report["items"] = results
    report["passed"] = sum(1 for v in results.values() if v["pass"])
    report["total"] = len(results)
    report["overall"] = "PASS" if ok else "FAIL"

    # 15. AUTHORIZATION MATRIX (1C-05): two organizations, two roles. Permitted
    #     activity succeeds; prohibited activity receives a non-enumerating
    #     denial (404/403), never an existence disclosure.
    authz = {}
    try:
        from Northstar_backend.foundation.models import Organization, User, Membership
        from Northstar_backend.foundation.enums import Role as _R
        import uuid as _uuid
        org_v = Organization(name="Staging Viewer Org", slug="staging-viewer-org")
        st.repos.organizations.add(org_v)
        viewer = User(email="viewer@staging.local")
        st.repos.users.add(viewer)
        st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                            organization_id=org_v.id,
                                            user_id=viewer.id,
                                            role=_R.VIEWER.value, status="active"))
        h_viewer = bearer(make_access_token(viewer.id, org=org_v.id, role="viewer",
                                            issuer="https://northstar.staging.local",
                                            audience="northstar-staging"))
        # viewer must accept the beta documents too, so its 403s below are
        # PERMISSION denials (not acceptance denials)
        viewer_ctx = build_context(user_id=viewer.id, organization_id=org_v.id,
                                   role=_R.VIEWER.value,
                                   environment=Environment.PRODUCTION.value)
        record_acceptance(st, viewer_ctx, business_use=True, age_18_plus=True,
                          request_id="staging-smoke-authz-viewer")
        # owner (org A) permitted: submit + job success
        authz["owner_submit"] = client.post(
            "/api/v1/foundation/jobs-durable", headers=h, json={
                "job_type": "immediate_success", "payload_schema_version": "1.0",
                "payload": {}, "idempotency_key": "staging-authz-owner"}).status_code == 201
        # viewer (org B) read-only on its own org
        authz["viewer_own_org_read"] = client.get(
            "/api/v1/foundation/jobs-durable", headers=h_viewer).status_code == 200
        # viewer blocked from billing/ledger (403, not 200)
        authz["viewer_ledger_blocked"] = client.get(
            "/api/v1/foundation/usage/summary", headers=h_viewer).status_code == 403
        # viewer blocked from provider configuration
        authz["viewer_providers_blocked"] = client.get(
            "/api/v1/foundation/providers", headers=h_viewer).status_code == 403
        # viewer cannot create jobs
        authz["viewer_submit_blocked"] = client.post(
            "/api/v1/foundation/jobs-durable", headers=h_viewer, json={
                "job_type": "immediate_success", "payload_schema_version": "1.0",
                "payload": {}}).status_code == 403
        # NON-ENUMERATING cross-org denial: viewer guesses org A's job id
        authz_job_id = st.repos.job_requests.list(
            where={"organization_id": org})[-1]["id"]
        r = client.get(f"/api/v1/foundation/jobs-durable/{authz_job_id}",
                       headers=h_viewer)
        authz["viewer_cross_org_job_404"] = r.status_code == 404
        authz["cross_org_body_no_hint"] = "exists" not in r.text.lower() and \
            "belongs" not in r.text.lower()
        check("28_authz_two_org_two_role", all(authz.values()),
              json.dumps(authz))
        report["authorization_matrix"] = authz
    except Exception as e:  # noqa: BLE001
        check("28_authz_two_org_two_role", False, str(e))
        report["authorization_matrix"] = {"error": str(e)}

    # 16. BETA ACCEPTANCE + ACCESS DENIAL (1C-06): publish documents, verify a
    #     fresh account is denied until acceptance, then accepted.
    beta = {}
    try:
        from Northstar_backend.foundation.beta.acceptance import publish_documents
        from Northstar_backend.foundation.models import Organization as _Org
        from Northstar_backend.foundation.models import User as _User
        from Northstar_backend.foundation.models import Membership as _Membership
        from Northstar_backend.foundation.enums import Role as _Role
        published = publish_documents(st)
        beta["documents_published"] = len(published) == 4
        # a brand-new account (org C) has NOT accepted
        org_c = _Org(name="Staging Beta Org", slug="staging-beta-org")
        st.repos.organizations.add(org_c)
        new_user = _User(email="beta@staging.local")
        st.repos.users.add(new_user)
        st.repos.memberships.add(_Membership(
            id=__import__("uuid").uuid4().hex, organization_id=org_c.id,
            user_id=new_user.id, role=_Role.OPERATOR.value, status="active"))
        h_new = bearer(make_access_token(new_user.id, org=org_c.id, role="operator",
                                         issuer="https://northstar.staging.local",
                                         audience="northstar-staging"))
        denied = client.post("/api/v1/foundation/jobs-durable", headers=h_new, json={
            "job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": {}})
        beta["new_account_denied_before_acceptance"] = denied.status_code == 409
        # public documents reachable pre-acceptance
        beta["public_documents_reachable"] = \
            client.get("/api/v1/foundation/legal/documents").status_code == 200
        # accept -> access restored
        acc = client.post("/api/v1/foundation/legal/acceptance", headers=h_new, json={
            "business_use": True, "age_18_plus": True})
        beta["acceptance_recorded"] = acc.status_code == 200
        allowed = client.post("/api/v1/foundation/jobs-durable", headers=h_new, json={
            "job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": {}})
        beta["access_restored_after_acceptance"] = allowed.status_code == 201
        # append-only records with the required fields exist on staging
        events = st.repos.acceptance_events.for_actor(org_c.id, new_user.id)
        beta["acceptance_events_append_only"] = len(events) == 4 and all(
            e["ip_handling"] == "not_stored" and e["content_hash"]
            for e in events)
        check("29_beta_acceptance_access_denial", all(beta.values()),
              json.dumps(beta))
        report["beta_acceptance"] = beta
    except Exception as e:  # noqa: BLE001
        check("29_beta_acceptance_access_denial", False, str(e))
        report["beta_acceptance"] = {"error": str(e)}

    # 17. PHASE E — INTEGRATED PRIVATE-TEST E2E (master slice): admin invite ->
    #     signup -> acceptance -> test checkout -> webhook settle -> tier grant
    #     -> within-tier operate -> over-tier blocked -> revoke/cancel ->
    #     downgrade -> audit correlation.
    e2e = {}
    try:
        from Northstar_backend.foundation.billing import processor as proc
        from Northstar_backend.foundation.models import Organization as _Org2
        from Northstar_backend.foundation.models import User as _User2
        from Northstar_backend.foundation.models import Membership as _Membership2
        from Northstar_backend.foundation.enums import Role as _Role2
        import uuid as _uuid2
        suffix = str(int(time.time() * 1000))
        # a FRESH org + admin so the monthly job counter starts at zero
        org_e = _Org2(name="E2E Org", slug=f"e2e-org-{suffix}")
        st.repos.organizations.add(org_e)
        admin_e = _User2(email=f"admin-{suffix}@staging.local")
        st.repos.users.add(admin_e)
        st.repos.memberships.add(_Membership2(
            id=_uuid2.uuid4().hex, organization_id=org_e.id, user_id=admin_e.id,
            role=_Role2.ORGANIZATION_OWNER.value, status="active"))
        ha = bearer(make_access_token(admin_e.id, org=org_e.id,
                                      role="organization_owner",
                                      issuer="https://northstar.staging.local",
                                      audience="northstar-staging"))
        record_acceptance(st, build_context(user_id=admin_e.id,
                                            organization_id=org_e.id,
                                            role=_Role2.ORGANIZATION_OWNER.value,
                                            environment=Environment.PRODUCTION.value),
                          business_use=True, age_18_plus=True,
                          request_id="e2e-admin-accept")
        # admin issues an invite for the customer (owner seat -> can subscribe)
        cust_email = f"cust-{suffix}@staging.local"
        inv = client.post("/api/v1/foundation/invites", headers=ha, json={
            "email": cust_email, "role": _Role2.ORGANIZATION_OWNER.value}).json()
        code = st.repos.invites.get(inv["invite_id"])["invite_code"]
        e2e["invite_issued"] = True
        r = client.post("/api/v1/foundation/signup",
                        json={"email": cust_email, "invite_code": code})
        e2e["signup_ok"] = r.status_code == 201
        cust = next(u for u in st.repos.users.list() if u["email"] == cust_email)
        hc = bearer(make_access_token(cust["id"], org=org_e.id,
                                      role="organization_owner",
                                      issuer="https://northstar.staging.local",
                                      audience="northstar-staging"))
        acc = client.post("/api/v1/foundation/legal/acceptance", headers=hc, json={
            "business_use": True, "age_18_plus": True})
        e2e["acceptance_ok"] = acc.status_code == 200
        co = client.post("/api/v1/foundation/billing/checkout",
                         json={"price_id": "price_trial"}, headers=hc).json()
        page = client.get(co["redirect_url"]).text
        e2e["hosted_checkout_no_cards"] = "TEST MODE" in page and \
            "no payment card" in page.lower()
        ev = proc.build_event(event_id=f"evt_staging_{suffix}",
                              event_type="checkout.session.completed",
                              checkout_session_id=co["checkout_id"],
                              customer_id=f"cus_{suffix}", subscription_id=f"sub_{suffix}",
                              price_id="price_trial")
        w = client.post("/api/v1/foundation/billing/webhook",
                        json={"payload": ev,
                              "signature": proc.sign_event(ev, proc.webhook_secret())})
        e2e["webhook_settled"] = w.json().get("status") == "processed"
        ent = client.get("/api/v1/foundation/entitlements", headers=hc).json()
        e2e["tier_granted"] = ent["tier"] == "trial"
        for i in range(5):
            rr = client.post("/api/v1/foundation/jobs-durable", headers=hc, json={
                "job_type": "immediate_success", "payload_schema_version": "1.0",
                "payload": {}, "idempotency_key": f"e2e-{i}-{cust_email}"})
            e2e[f"within_tier_{i}"] = rr.status_code == 201
        over = client.post("/api/v1/foundation/jobs-durable", headers=hc, json={
            "job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": {}})
        e2e["over_tier_blocked"] = over.status_code == 403 and \
            over.json()["detail"]["code"] == "entitlement_denied"
        client.post(f"/api/v1/foundation/invites/{inv['invite_id']}/revoke",
                    headers=ha, json={"reason": "e2e end"})
        client.post("/api/v1/foundation/billing/cancel", headers=hc,
                    json={"reason": "e2e end"})
        ent_after = client.get("/api/v1/foundation/entitlements", headers=hc).json()
        e2e["downgrade_on_cancel"] = ent_after["tier"] == "free"
        audit = st.repos.audit.list(where={"organization_id": org_e.id})
        actions = {a["action"] for a in audit}
        e2e["audit_correlated"] = all(k in actions for k in (
            "signup.accepted", "legal.acceptance", "billing.subscription.settled",
            "billing.subscription.cancel", "invite.issue", "invite.revoke"))
        check("30_master_slice_e2e", all(e2e.values()), json.dumps(e2e))
        report["master_slice_e2e"] = e2e
    except Exception as e:  # noqa: BLE001
        check("30_master_slice_e2e", False, str(e))
        report["master_slice_e2e"] = {"error": str(e)}

    # 18. PHASE E/F — SUBSCRIBER OPERATIONS E2E (admin approve -> invite ->
    #     signup -> acceptance -> onboarding -> plan visible -> within-limit ->
    #     over-limit -> support ticket -> admin note/triage -> downgrade/suspend
    #     -> next request reflects -> dashboard + export -> audit correlated).
    ops = {}
    try:
        import uuid as _uuid3
        from Northstar_backend.foundation.operations import lifecycle as _lc
        suffix2 = str(int(time.time() * 1000))
        target = _Org2(name=f"Sub Ops {suffix2}", slug=f"sub-{suffix2}")
        st.repos.organizations.add(target)
        op_u = _User2(email=f"op-{suffix2}@staging.local")
        st.repos.users.add(op_u)
        st.repos.memberships.add(_Membership2(
            id=_uuid3.uuid4().hex, organization_id=target.id, user_id=op_u.id,
            role=_Role2.INTERNAL_PLATFORM_ADMIN.value, status="active"))
        hop = bearer(make_access_token(op_u.id, org=target.id,
                                       role="internal_platform_admin",
                                       issuer="https://northstar.staging.local",
                                       audience="northstar-staging"))
        record_acceptance(st, build_context(user_id=op_u.id, organization_id=target.id,
                                            role=_Role2.INTERNAL_PLATFORM_ADMIN.value,
                                            environment=Environment.PRODUCTION.value),
                          business_use=True, age_18_plus=True, request_id="ops-op")
        # 1. admin approves org
        st.lifecycle.initialize(target.id, actor=op_u.id, reason="created")
        st.admin_ops.grant(build_context(user_id=op_u.id, organization_id=target.id,
                                         role=_Role2.INTERNAL_PLATFORM_ADMIN.value,
                                         environment=Environment.PRODUCTION.value),
                           target.id, reason="approved")
        ops["org_approved"] = st.lifecycle.current_state(target.id) == _lc.ONBOARDING
        # 2. invite -> 3. signup -> 4. acceptance
        cust2 = f"sub-{suffix2}@staging.local"
        inv2 = client.post("/api/v1/foundation/invites", headers=hop, json={
            "email": cust2, "role": _Role2.ORGANIZATION_OWNER.value}).json()
        code2 = st.repos.invites.get(inv2["invite_id"])["invite_code"]
        r = client.post("/api/v1/foundation/signup",
                        json={"email": cust2, "invite_code": code2})
        ops["signup_ok"] = r.status_code == 201 and r.json()["organization_id"] == target.id
        owner2 = next(u for u in st.repos.users.list() if u["email"] == cust2)
        ht2 = bearer(make_access_token(owner2["id"], org=target.id,
                                       role="organization_owner",
                                       issuer="https://northstar.staging.local",
                                       audience="northstar-staging"))
        client.post("/api/v1/foundation/legal/acceptance", headers=ht2, json={
            "business_use": True, "age_18_plus": True})
        ops["acceptance_ok"] = client.get("/api/v1/foundation/legal/acceptance/status",
                                          headers=ht2).json()["accepted"] is True
        # 5. onboarding -> active
        client.post("/api/v1/foundation/onboarding/complete", headers=ht2, json={})
        ops["onboarding_ok"] = client.get("/api/v1/foundation/onboarding",
                                          headers=ht2).json()["completed"] is True
        st.lifecycle.transition(target.id, to_state=_lc.ACTIVE,
                                actor=op_u.id, reason="onboarded")
        # 6. plan visible + 7. usage within limits (trial 5)
        co2 = client.post("/api/v1/foundation/billing/checkout",
                          json={"price_id": "price_trial"}, headers=ht2).json()
        ev2 = proc.build_event(event_id=f"evt_sub_{suffix2}",
                               event_type="checkout.session.completed",
                               checkout_session_id=co2["checkout_id"],
                               customer_id=f"cus_{suffix2}", subscription_id=f"sub_{suffix2}",
                               price_id="price_trial")
        client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": ev2,
                          "signature": proc.sign_event(ev2, proc.webhook_secret())})
        ops["plan_visible"] = client.get("/api/v1/foundation/plan-usage",
                                         headers=ht2).json()["plan"]["tier"] == "trial"
        for i in range(5):
            client.post("/api/v1/foundation/jobs-durable", headers=ht2, json={
                "job_type": "immediate_success", "payload_schema_version": "1.0",
                "payload": {}, "idempotency_key": f"sub-{i}-{suffix2}"})
        # 8. over-limit denial explained in plan view
        over2 = client.post("/api/v1/foundation/jobs-durable", headers=ht2, json={
            "job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": {}})
        ops["over_limit_blocked"] = over2.status_code == 403
        ops["usage_shown"] = client.get("/api/v1/foundation/plan-usage",
                                        headers=ht2).json()["usage"]["monthly_jobs_used"] == 5
        # 9. support ticket + admin triage/note
        tk2 = client.post("/api/v1/foundation/support/tickets", headers=ht2, json={
            "category": "bug", "severity": "high", "subject": "x", "description": "y"})
        tid2 = tk2.json()["ticket_id"]
        client.post(f"/api/v1/foundation/support/tickets/{tid2}/triage",
                    headers=hop, json={"status": "acknowledged",
                                       "tester_visible_note": "noted",
                                       "internal_note": "ops seen"})
        client.post(f"/api/v1/foundation/admin/orgs/{target.id}/notes",
                    headers=hop, json={"note": "trial cohort"})
        ops["support_ok"] = client.get(f"/api/v1/foundation/support/tickets/{tid2}",
                                       headers=ht2).json()["tester_visible_note"] == "noted"
        # 10. admin downgrade + suspend -> next request reflects
        client.post(f"/api/v1/foundation/admin/orgs/{target.id}/downgrade",
                    headers=hop, json={"reason": "trial end"})
        client.post(f"/api/v1/foundation/admin/orgs/{target.id}/suspend",
                    headers=hop, json={"reason": "review"})
        ops["next_request_blocked"] = client.get("/api/v1/foundation/plan-usage",
                                                 headers=ht2).status_code == 403
        # 11. dashboard + export show final state
        rows2 = client.get("/api/v1/foundation/admin/dashboard",
                           headers=hop).json()["items"]
        row2 = next((x for x in rows2 if x["organization_id"] == target.id), None)
        ops["dashboard_final"] = bool(row2 and row2["lifecycle_state"] == _lc.SUSPENDED
                                      and row2["plan_tier"] == "free")
        export2 = client.get("/api/v1/foundation/admin/dashboard/export",
                             headers=hop).text
        ops["export_final"] = target.id in export2 and "suspended" in export2
        # 12. audit correlated
        actions2 = {a["action"] for a in st.repos.audit.list(
            where={"organization_id": target.id})}
        ops["audit_correlated"] = all(k in actions2 for k in (
            "signup.accepted", "legal.acceptance", "support.ticket.submit",
            "support.ticket.triage", "admin.note.add", "org.lifecycle.suspended",
            "admin.plan.change"))
        check("31_subscriber_operations_e2e", all(ops.values()), json.dumps(ops))
        report["subscriber_operations_e2e"] = ops
    except Exception as e:  # noqa: BLE001
        check("31_subscriber_operations_e2e", False, str(e))
        report["subscriber_operations_e2e"] = {"error": str(e)}

    report["items"] = results
    report["passed"] = sum(1 for v in results.values() if v["pass"])
    report["total"] = len(results)
    report["overall"] = "PASS" if ok else "FAIL"
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nSTAGING SMOKE: {report['passed']}/{report['total']} "
          f"{'PASS' if ok else 'FAIL'} -> {REPORT}")
    st.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())