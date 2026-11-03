"""AdPilot PPC lane (U9) — the API over the existing specialist.

The point of these tests is that the endpoint does not re-implement any decision:
it hands the operator's rows to `ppc_agent`, hands the result to `ppc_bulk`, and
returns either a validated file or the reason there is none.
"""
from __future__ import annotations

import base64

import pytest


ROWS = [
    # A converting term inside the ACOS target -> harvest.
    {"campaign": "Lions Mane", "ad group": "Broad", "customer search term": "lions mane powder",
     "impressions": "1200", "clicks": "24", "spend": "12.00", "sales": "60.00", "orders": "2"},
    # A term with 8+ clicks and no order -> negative.
    {"campaign": "Lions Mane", "ad group": "Broad", "customer search term": "mushroom coffee cheap",
     "impressions": "900", "clicks": "11", "spend": "8.40", "sales": "0", "orders": "0"},
    # Too few clicks to judge: neither harvested nor negated.
    {"campaign": "Lions Mane", "ad group": "Phrase", "customer search term": "lion mane capsules",
     "impressions": "80", "clicks": "2", "spend": "0.90", "sales": "0", "orders": "0"},
]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_status_states_the_lane_is_file_only(client):
    r = client.get("/api/adpilot/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["amazon_api"] is False
    assert "search_term" in body["kinds"]
    assert "operation" in body["bulk_columns"]


def test_analyze_harvests_one_term_and_negates_one(client):
    r = client.post("/api/adpilot/analyze", json={"rows": ROWS, "target_acos": 0.35})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["rows_read"] == 3
    assert len(body["harvest"]) == 1
    assert body["harvest"][0]["source_row"]["customer search term"] == "lions mane powder"
    assert len(body["negatives"]) == 1
    assert body["negatives"][0]["clicks"] == 11
    # The undecidable row is in neither list.
    terms = [x["source_row"]["customer search term"] for x in body["harvest"] + body["negatives"]]
    assert "lion mane capsules" not in terms


def test_a_wrong_report_is_rejected_with_the_missing_columns(client):
    r = client.post("/api/adpilot/analyze",
                    json={"rows": [{"campaign": "x", "clicks": "3"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert "customer search term" in body["error"]
    assert body["expected"]


def test_bulk_returns_a_validated_xlsx_and_its_real_size(client):
    r = client.post("/api/adpilot/bulk", json={"rows": ROWS, "bid": 0.85})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["rows"] == 2
    payload = base64.b64decode(body["bytes_b64"])
    assert payload[:2] == b"PK", "an xlsx is a zip container"
    assert len(payload) == body["bytes"]
    assert body["filename"].endswith(".xlsx")
    assert "not" in body["note"].lower() or "own" in body["note"].lower()


def test_bulk_refuses_when_the_report_is_not_a_search_term_report(client):
    r = client.post("/api/adpilot/bulk", json={"rows": [{"campaign": "x"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert "missing column" in body["error"].lower()


def test_bulk_refuses_a_malformed_analysis_instead_of_raising(client, monkeypatch):
    """A boundary, not a 500: an analysis the writer cannot use is a refusal."""
    import adpilot_api

    def fake_analyze(rows, target_acos=0.35):
        return {
            "ok": True,
            "status": "planned",
            "summary": "a row with no source",
            "harvest": [{"orders": 1, "acos": 0.1}],  # no source_row
            "negatives": [],
        }

    monkeypatch.setattr(adpilot_api.ppc_agent, "analyze", fake_analyze)
    r = client.post("/api/adpilot/bulk", json={"rows": ROWS})
    assert r.status_code == 200, "a bad analysis must not become a 500"
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert body["error"]
