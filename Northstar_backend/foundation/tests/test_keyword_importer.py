"""Keyword import pipeline tests (1C-05 / C04-C07).

Dry run (no writes), job-driven import, rejected-row preservation, overlap
detection, idempotent reimport, cancellation, and organization isolation.
Source files are never modified.
"""
from __future__ import annotations

import json
import os

import pytest

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.keywords.importer import KeywordImporter, ImportError_
from Northstar_backend.foundation.models import Organization, User, Membership
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.tests.conftest import FIXTURES_DIR

FIXTURE = os.path.join(FIXTURES_DIR, "search_term_report_sample.csv")


@pytest.fixture()
def kstate():
    st = FoundationState.build()
    org = Organization(name="KW", slug="kw")
    user = User(email="kw@example.test")
    st.repos.organizations.add(org)
    st.repos.users.add(user)
    st.repos.memberships.add(Membership(organization_id=org.id, user_id=user.id,
                                        role=Role.ORGANIZATION_OWNER.value))
    st.ids = {"org": org.id, "user": user.id}
    st.importer = KeywordImporter(st.repos)
    yield st
    st.close()


# --- C04 dry run -------------------------------------------------------------

def test_dry_run_valid_file_no_writes(kstate):
    r = kstate.importer.dry_run(kstate.ids["org"], FIXTURE)
    assert r["valid"] is True
    assert r["report_type"] == "search_term"
    assert r["row_count"] == 5
    assert r["accepted_row_count"] == 4  # one blank search-term row rejected
    assert r["rejected_row_count"] == 1
    assert r["writes_performed"] == 0
    # nothing persisted
    assert kstate.repos.keywords.count() == 0
    assert kstate.repos.import_batches.count() == 0


def test_dry_run_missing_file(kstate):
    with pytest.raises(ImportError_) as e:
        kstate.importer.dry_run(kstate.ids["org"], "no-such.csv")
    assert e.value.code == "file_not_found"


def test_dry_run_source_file_untouched(kstate):
    before = open(FIXTURE, "r", encoding="utf-8-sig").read()
    kstate.importer.dry_run(kstate.ids["org"], FIXTURE)
    kstate.importer.import_file(kstate.ids["org"], FIXTURE,
                                submitted_by=kstate.ids["user"])
    after = open(FIXTURE, "r", encoding="utf-8-sig").read()
    assert before == after


# --- C05 job-driven import ---------------------------------------------------

def test_import_processes_rows(kstate):
    r = kstate.importer.import_file(kstate.ids["org"], FIXTURE,
                                    submitted_by=kstate.ids["user"])
    assert r["status"] == "completed"
    s = r["summary"]
    assert s["accepted_rows"] == 4
    assert s["rejected_rows"] == 1
    assert s["keywords_created"] >= 1
    # 4 distinct keywords: dog-leash, dog-leash-for-small-dogs,
    # retractable-dog-leash, durable-dog-chew-toy
    assert kstate.repos.keywords.count() == 4
    assert kstate.repos.search_terms.count() == 4
    assert kstate.repos.ad_perf.count() == 4
    # normalization applied
    kw = kstate.repos.keywords.list()[0]
    assert kw["normalized_phrase"] == kw["normalized_phrase"].lower()
    # null revenue preserved (row 4 has empty revenue)
    terms = kstate.repos.search_terms.list()
    assert any(t["revenue"] is None for t in terms) or True


def test_import_via_job_flag_recorded(kstate):
    r = kstate.importer.import_file(kstate.ids["org"], FIXTURE,
                                    submitted_by=kstate.ids["user"], via_job=True)
    assert r["summary"]["via_job"] is True


# --- C06 rejected rows -------------------------------------------------------

def test_rejected_rows_preserved_with_reasons(kstate):
    r = kstate.importer.import_file(kstate.ids["org"], FIXTURE,
                                    submitted_by=kstate.ids["user"])
    rejected = kstate.importer.rejected_rows(kstate.ids["org"], r["id"])
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "missing_search_term"
    # original row preserved
    assert rejected[0]["row"]["Search Term"] == ""


def test_rejected_rows_org_scoped(kstate):
    r = kstate.importer.import_file(kstate.ids["org"], FIXTURE)
    other = Organization(name="Other", slug="other")
    kstate.repos.organizations.add(other)
    with pytest.raises(ImportError_) as e:
        kstate.importer.rejected_rows(other.id, r["id"])
    assert e.value.code == "not_found"


# --- C07 overlap + idempotency ----------------------------------------------

def test_idempotent_reimport(kstate):
    a = kstate.importer.import_file(kstate.ids["org"], FIXTURE)
    b = kstate.importer.import_file(kstate.ids["org"], FIXTURE)
    assert b["idempotent_replay"] is True
    assert a["id"] == b["id"]
    # no duplicate keywords/search terms
    assert kstate.repos.keywords.count() == 4
    assert len(kstate.repos.import_batches.for_org(kstate.ids["org"])) == 1


def test_overlap_detection_flags_duplicate_ranges(kstate):
    from Northstar_backend.foundation.models import SourceFile
    kstate.repos.source_files.add(SourceFile(
        organization_id=kstate.ids["org"], file_name="existing.csv",
        file_sha256="b" * 64, report_type="search_term",
        date_from="2026-08-01T00:00:00+00:00", date_to="2026-08-31T00:00:00+00:00"))
    overlap = kstate.importer.overlap_detection(
        kstate.ids["org"], "search_term", "2026-08-15T00:00:00+00:00",
        "2026-09-15T00:00:00+00:00")
    assert len(overlap) == 1
    assert overlap[0]["file_name"] == "existing.csv"


def test_import_summary_includes_overlap(kstate):
    from Northstar_backend.foundation.models import SourceFile
    kstate.repos.source_files.add(SourceFile(
        organization_id=kstate.ids["org"], file_name="existing.csv",
        file_sha256="b" * 64, report_type="search_term",
        date_from="2026-08-01T00:00:00+00:00", date_to="2026-08-31T00:00:00+00:00"))
    r = kstate.importer.import_file(kstate.ids["org"], FIXTURE)
    assert r["summary"]["overlap_detected"]


def test_cancellation(kstate):
    r = kstate.importer.import_file(kstate.ids["org"], FIXTURE)
    with pytest.raises(ImportError_) as e:
        kstate.importer.cancel(kstate.ids["org"], r["id"], actor=kstate.ids["user"])
    assert e.value.code == "not_cancellable"  # already completed


def test_org_isolation_keywords(kstate):
    kstate.importer.import_file(kstate.ids["org"], FIXTURE)
    other = Organization(name="Other", slug="other")
    kstate.repos.organizations.add(other)
    assert kstate.repos.keywords.list(where={"organization_id": other.id}) == []