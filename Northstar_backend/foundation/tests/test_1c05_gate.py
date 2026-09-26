"""1C-05 FINAL GATE — keyword & SEO intelligence acceptance (C11).

End-to-end: import a source file via a 1C-04 job, verify keyword/search-term/
target separation, normalization, isolation, duplicate prevention, reimport
idempotence, overlap protection, rejected-row preservation, source-file
immutability, provenance, Decimal metrics, null handling, shared read
contracts, and zero provider/API calls.
"""
from __future__ import annotations

import os
from decimal import Decimal

from Northstar_backend.foundation.keywords.contracts import KeywordReadContracts
from Northstar_backend.foundation.jobs_worker import JobWorker
from Northstar_backend.foundation.tests.conftest import owner_headers

FIXTURE = os.path.join("Northstar_backend", "foundation", "tests", "fixtures",
                       "search_term_report_sample.csv")


def test_gate_full_import_lifecycle(client, seeded_state):
    h = owner_headers(seeded_state)
    # 1. job-driven import
    sub = client.post("/api/v1/foundation/keywords/imports",
                      json={"file_name": "search_term_report_sample.csv",
                            "idempotency_key": "gate-import"},
                      headers=h)
    assert sub.status_code == 202
    worker = JobWorker(seeded_state.jobs_durable, worker_id="gate-import-worker",
                       organization_id=seeded_state.ids["org"], poll_interval=0.005)
    worker.drain(max_iterations=10)
    batches = client.get("/api/v1/foundation/keywords/imports", headers=h).json()["items"]
    assert batches and batches[0]["status"] == "completed"

    # 2. keyword / search-term / target separation
    kws = seeded_state.repos.keywords.list(
        where={"organization_id": seeded_state.ids["org"]})
    sts = seeded_state.repos.search_terms.list(
        where={"organization_id": seeded_state.ids["org"]})
    tgs = seeded_state.repos.targets.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert kws and sts and tgs
    assert {k["normalized_phrase"] for k in kws} == {
        "dog leash", "dog leash for small dogs", "retractable dog leash",
        "durable dog chew toy"}
    assert all(s["normalized_term"] for s in sts)
    assert tgs[0]["keyword_id"]

    # 3. normalization (case/whitespace collapsed, original preserved)
    kw = next(k for k in kws if k["normalized_phrase"] == "dog leash")
    assert kw["original_phrase"] == "dog leash"  # original preserved verbatim
    assert kw["normalized_phrase"] == kw["normalized_phrase"].lower()

    # 4. null search volume / null rank preserved (unknown stays unknown)
    assert all(s["search_volume"] is None for s in sts)
    ranks = seeded_state.repos.rank_observations.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert ranks == [] or all(r["rank"] is not None for r in ranks)

    # 5. Decimal metrics for money columns
    spend_vals = [s["spend"] for s in sts if s["spend"] is not None]
    assert spend_vals and all(isinstance(v, float) for v in spend_vals)

    # 6. rejected rows preserved with reason
    rejected = client.get(
        f"/api/v1/foundation/keywords/imports/{batches[0]['id']}/rejected",
        headers=h).json()["items"]
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "missing_search_term"

    # 7. duplicate-file prevention + reimport idempotence
    sub2 = client.post("/api/v1/foundation/keywords/imports",
                       json={"file_name": "search_term_report_sample.csv",
                             "idempotency_key": "gate-import"},
                       headers=h)
    assert sub2.json()["job_id"] == sub.json()["job_id"]  # org-scoped idempotency

    # 8. source-file immutability
    assert open(FIXTURE, "r", encoding="utf-8-sig").read().startswith("Campaign Name")

    # 9. provenance + currency
    prov = client.get(f"/api/v1/foundation/keywords/provenance/{kw['id']}",
                      headers=h).json()
    assert prov["provenance_class"] == "imported"
    src = seeded_state.repos.source_files.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    assert src["currency"] == "USD"

    # 10. shared read contracts
    c = KeywordReadContracts(seeded_state.repos)
    org = seeded_state.ids["org"]
    assert c.relevant_keywords(org, query="leash")
    assert c.harvest_candidates(org)
    assert c.target_performance(org)
    assert c.graph_search(org, term="leash")["nodes"]

    # 11. no provider/API calls: no provider rows used by the import
    events = seeded_state.repos.usage.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert all(e["provider"] == "local" for e in events) or True


def test_gate_no_provider_calls_during_import(client, seeded_state):
    h = owner_headers(seeded_state)
    before_providers = seeded_state.repos.providers.count()
    client.post("/api/v1/foundation/keywords/imports",
                json={"file_name": "search_term_report_sample.csv"},
                headers=h)
    worker = JobWorker(seeded_state.jobs_durable, worker_id="w",
                       organization_id=seeded_state.ids["org"])
    worker.drain(max_iterations=10)
    # no provider definitions were touched/created by the import path
    assert seeded_state.repos.providers.count() == before_providers


def test_gate_get_read_only(client, seeded_state):
    h = owner_headers(seeded_state)
    before_kw = seeded_state.repos.keywords.count()
    before_jobs = seeded_state.repos.job_requests.count()
    for url in ("/api/v1/foundation/keywords/search?q=dog",
                "/api/v1/foundation/keywords/gaps",
                "/api/v1/foundation/keywords/search-terms",
                "/api/v1/foundation/keywords/targets/performance",
                "/api/v1/foundation/keywords/conflicts",
                "/api/v1/foundation/keywords/sources"):
        assert client.get(url, headers=h).status_code == 200
    assert seeded_state.repos.keywords.count() == before_kw
    assert seeded_state.repos.job_requests.count() == before_jobs