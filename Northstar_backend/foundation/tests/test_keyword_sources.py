"""Source registry tests (1C-05 / C03)."""
from __future__ import annotations

import os

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.keywords.sources import (
    SourceRegistry, classify_report_type, sniff_csv, _sha256, NOT_PRESENT,
)

FIXTURE = os.path.join("Northstar_backend", "foundation", "tests", "fixtures",
                       "search_term_report_sample.csv")


def _state_and_org():
    st = FoundationState.build()
    from Northstar_backend.foundation.models import Organization, User, Membership
    from Northstar_backend.foundation.enums import Role
    org = Organization(name="KW", slug="kw")
    user = User(email="kw@example.test")
    st.repos.organizations.add(org)
    st.repos.users.add(user)
    st.repos.memberships.add(Membership(organization_id=org.id, user_id=user.id,
                                        role=Role.ORGANIZATION_OWNER.value))
    st.ids = {"org": org.id, "user": user.id}
    return st


def test_classify_report_type_detects_search_term():
    sniff = sniff_csv(FIXTURE)
    assert classify_report_type(sniff["headers"]) == "search_term"


def test_sha256_stable():
    a = _sha256(FIXTURE)
    b = _sha256(FIXTURE)
    assert a == b and len(a) == 64


def test_register_file_preserves_originals_and_metadata():
    st = _state_and_org()
    reg = SourceRegistry(st.repos)
    result = reg.register_file(st.ids["org"], FIXTURE)
    assert result["status"] == "registered"
    sf = result["source_file"]
    assert sf["report_type"] == "search_term"
    assert sf["file_name"] == "search_term_report_sample.csv"
    assert sf["file_sha256"] == _sha256(FIXTURE)
    assert sf["currency"] == "USD"
    assert sf["date_from"] is not None and sf["date_to"] is not None
    # original file untouched
    assert open(FIXTURE, "r", encoding="utf-8-sig").read() == \
        open(FIXTURE, "r", encoding="utf-8-sig").read()
    st.close()


def test_duplicate_detection():
    st = _state_and_org()
    reg = SourceRegistry(st.repos)
    reg.register_file(st.ids["org"], FIXTURE)
    again = reg.register_file(st.ids["org"], FIXTURE)
    assert again["status"] == "duplicate"
    assert len(st.repos.source_files.list(where={"organization_id": st.ids["org"]})) == 1
    st.close()


def test_absent_source_reports_not_present():
    st = _state_and_org()
    reg = SourceRegistry(st.repos)
    status = reg.source_status(st.ids["org"])
    for rtype in ("campaign", "placement", "top_of_search",
                  "advertised_product", "targeting", "business", "keyword_workbook"):
        assert status[rtype]["status"] == NOT_PRESENT
    assert status["search_term"]["status"] == NOT_PRESENT  # nothing registered yet
    st.close()


def test_discover_reports_present_and_absent():
    st = _state_and_org()
    reg = SourceRegistry(st.repos)
    discovered = reg.discover(st.ids["org"],
                              directory=os.path.dirname(FIXTURE))
    assert discovered["search_term"]["status"] == "PRESENT"
    assert discovered["search_term"]["files"]
    assert discovered["campaign"]["status"] == NOT_PRESENT
    st.close()