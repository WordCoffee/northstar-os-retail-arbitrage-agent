"""Keyword API, organization isolation, and shared read contracts tests
(1C-05 / C08, C09, C10)."""
from __future__ import annotations

import os

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.keywords.contracts import KeywordReadContracts
from Northstar_backend.foundation.keywords.importer import KeywordImporter
from Northstar_backend.foundation.models import Organization, User, Membership
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.tests.conftest import owner_headers, make_access_token, bearer, FIXTURES_DIR

FIXTURE = os.path.join(FIXTURES_DIR, "search_term_report_sample.csv")


def _seed_other_org(state):
    other = Organization(name="Other", slug="other")
    user = User(email="other@example.test")
    state.repos.organizations.add(other)
    state.repos.users.add(user)
    state.repos.memberships.add(Membership(organization_id=other.id, user_id=user.id,
                                           role=Role.OPERATOR.value))
    return other, user


def _import(state, org_id, user_id):
    state.keywords.import_file(org_id, FIXTURE, submitted_by=user_id)


# --- C08 organization isolation ----------------------------------------------

def test_cross_org_keyword_search_isolation(client, seeded_state):
    h = owner_headers(seeded_state)
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    other, user = _seed_other_org(seeded_state)
    token = make_access_token(user.id, org=other.id, role="operator")
    r = client.get("/api/v1/foundation/keywords/search?q=leash",
                   headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["items"] == []  # org A keywords invisible to org B
    r2 = client.get("/api/v1/foundation/keywords/search?q=leash", headers=h)
    assert len(r2.json()["items"]) >= 1


def test_cross_org_keyword_detail_denied(client, seeded_state):
    h = owner_headers(seeded_state)
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    kw = seeded_state.repos.keywords.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    other, user = _seed_other_org(seeded_state)
    token = make_access_token(user.id, org=other.id, role="operator")
    assert client.get(f"/api/v1/foundation/keywords/{kw['id']}",
                      headers=bearer(token)).status_code == 404


def test_cross_org_source_files_invisible(client, seeded_state):
    h = owner_headers(seeded_state)
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    other, user = _seed_other_org(seeded_state)
    token = make_access_token(user.id, org=other.id, role="operator")
    r = client.get("/api/v1/foundation/keywords/sources", headers=bearer(token))
    statuses = r.json()
    assert all(v["status"] != "PRESENT" or v["files"] == []
               for v in statuses.values())


def test_cross_org_import_batch_denied(client, seeded_state):
    h = owner_headers(seeded_state)
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    batch = seeded_state.repos.import_batches.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    other, user = _seed_other_org(seeded_state)
    token = make_access_token(user.id, org=other.id, role="operator")
    assert client.get(f"/api/v1/foundation/keywords/imports/{batch['id']}",
                      headers=bearer(token)).status_code == 404
    assert client.get(
        f"/api/v1/foundation/keywords/imports/{batch['id']}/rejected",
        headers=bearer(token)).status_code == 404


def test_cross_org_rank_invisible(client, seeded_state):
    h = owner_headers(seeded_state)
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    kw = seeded_state.repos.keywords.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    other, user = _seed_other_org(seeded_state)
    token = make_access_token(user.id, org=other.id, role="operator")
    r = client.get(f"/api/v1/foundation/keywords/rank-history/{kw['id']}",
                   headers=bearer(token))
    assert r.status_code == 200 and r.json()["items"] == []


def test_cross_org_search_term_performance_invisible(client, seeded_state):
    h = owner_headers(seeded_state)
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    other, user = _seed_other_org(seeded_state)
    token = make_access_token(user.id, org=other.id, role="operator")
    assert client.get("/api/v1/foundation/keywords/search-terms",
                      headers=bearer(token)).json()["items"] == []


# --- C09 shared read contracts ------------------------------------------------

def test_offerchisel_contracts(seeded_state):
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    c = KeywordReadContracts(seeded_state.repos)
    org = seeded_state.ids["org"]
    rel = c.relevant_keywords(org, query="leash")
    assert rel and all("dog leash" in k["normalized_phrase"] or
                       "retractable" in k["normalized_phrase"] for k in rel)
    kw = c.relevant_keywords(org)[0]
    coverage = c.listing_coverage(org, kw["id"])
    assert coverage["covered"] is False  # no product links in fixture
    gaps = c.keyword_gaps(org)
    assert isinstance(gaps, list)  # fixture rows create targets, so gaps may be empty
    intent = c.search_intent(org, kw["id"])
    assert intent["unknown"] is False


def test_auctioneer_contracts(seeded_state):
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    c = KeywordReadContracts(seeded_state.repos)
    org = seeded_state.ids["org"]
    terms = c.search_terms(org)
    assert len(terms) == 4
    # fixture terms have orders -> harvest candidates
    assert c.harvest_candidates(org)
    # no zero-order high-click terms in fixture (3 orders on top term)
    assert c.negation_candidates(org, min_clicks=10) == []
    perf = c.target_performance(org)
    assert isinstance(perf, list)


def test_rankledger_contracts(seeded_state):
    from Northstar_backend.foundation.models import RankObservation
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    kw = seeded_state.repos.keywords.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    seeded_state.repos.rank_observations.add(RankObservation(
        organization_id=seeded_state.ids["org"], keyword_id=kw["id"],
        asin="B0EXAMPLE", rank=3, placement="organic"))
    c = KeywordReadContracts(seeded_state.repos)
    hist = c.rank_history(seeded_state.ids["org"], kw["id"])
    assert len(hist) == 1 and hist[0]["rank"] == 3
    alerts = c.alert_conditions(seeded_state.ids["org"])
    assert len(alerts) >= 1  # the other keywords have no rank observations


def test_towncrier_contracts(seeded_state):
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    c = KeywordReadContracts(seeded_state.repos)
    themes = c.approved_themes(seeded_state.ids["org"])
    assert all(t["requires_human_review"] for t in themes)
    guidance = c.brand_language_guidance(seeded_state.ids["org"])
    assert "brands" in guidance


def test_autothink_contracts(seeded_state):
    _import(seeded_state, seeded_state.ids["org"], seeded_state.ids["user"])
    c = KeywordReadContracts(seeded_state.repos)
    g = c.graph_search(seeded_state.ids["org"], term="leash")
    assert g["organization_scoped"] is True
    assert g["nodes"]


# --- C10 API end-to-end -------------------------------------------------------

def test_import_dry_run_and_submit_flow(client, seeded_state):
    h = owner_headers(seeded_state)
    dr = client.post("/api/v1/foundation/keywords/imports/dry-run",
                     json={"file_name": "search_term_report_sample.csv"},
                     headers=h)
    assert dr.status_code == 200
    assert dr.json()["valid"] is True and dr.json()["writes_performed"] == 0
    sub = client.post("/api/v1/foundation/keywords/imports",
                      json={"file_name": "search_term_report_sample.csv",
                            "idempotency_key": "import-1"},
                      headers=h)
    assert sub.status_code == 202
    assert sub.json()["status"] == "submitted"
    job_id = sub.json()["job_id"]
    # job is queued; worker executes the import
    from Northstar_backend.foundation.jobs_worker import JobWorker
    worker = JobWorker(seeded_state.jobs_durable, worker_id="import-worker",
                       organization_id=seeded_state.ids["org"],
                       poll_interval=0.005)
    outcomes = worker.drain(max_iterations=10)
    assert outcomes and outcomes[0].state == "succeeded"
    # batch completed
    batches = client.get("/api/v1/foundation/keywords/imports", headers=h).json()["items"]
    assert batches and batches[0]["status"] == "completed"
    assert batches[0]["summary"]["accepted_rows"] == 4
    # rejected rows preserved
    rejected = client.get(
        f"/api/v1/foundation/keywords/imports/{batches[0]['id']}/rejected",
        headers=h).json()["items"]
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "missing_search_term"
    # keyword search now returns data
    search = client.get("/api/v1/foundation/keywords/search?q=dog", headers=h)
    assert search.json()["items"]


def test_import_submit_requires_permission(client, seeded_state):
    from Northstar_backend.foundation.models import User as U
    user = U(email="viewer@example.test")
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=seeded_state.ids["org"], user_id=user.id,
        role=Role.VIEWER.value))
    token = make_access_token(user.id, org=seeded_state.ids["org"], role="viewer")
    r = client.post("/api/v1/foundation/keywords/imports",
                    json={"file_name": "search_term_report_sample.csv"},
                    headers=bearer(token))
    assert r.status_code == 403


def test_get_reads_never_create(client, seeded_state):
    h = owner_headers(seeded_state)
    before_kw = seeded_state.repos.keywords.count()
    before_batches = seeded_state.repos.import_batches.count()
    for url in ("/api/v1/foundation/keywords/search?q=x",
                "/api/v1/foundation/keywords/gaps",
                "/api/v1/foundation/keywords/search-terms",
                "/api/v1/foundation/keywords/targets/performance",
                "/api/v1/foundation/keywords/conflicts",
                "/api/v1/foundation/keywords/sources"):
        assert client.get(url, headers=h).status_code == 200
    assert seeded_state.repos.keywords.count() == before_kw
    assert seeded_state.repos.import_batches.count() == before_batches